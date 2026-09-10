"""
AI Research Assistant 后端入口

运行方式（在项目根目录）：
    uvicorn backend.main:app --reload --port 8000
"""
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.agents.orchestrator import Orchestrator
from backend.db.milvus_store import vector_store
from backend.db.mysql_memory import conversation_memory
from backend.models.schemas import (
    AskRequest,
    DocumentInfo,
    SessionCreateResponse,
    SessionHistoryResponse,
    UploadResponse,
)
from backend.utils.document_parser import (
    SUPPORTED_EXTENSIONS,
    chunk_text,
    extract_text_from_file,
)
from backend.utils.embeddings import get_embeddings

app = FastAPI(title="AI Research Assistant")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# 本地开发允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()


def _format_dependency_error(exc: Exception) -> str:
    """生成不包含完整敏感信息的依赖错误描述"""
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


async def _save_upload_to_temp(file: UploadFile, suffix: str) -> tuple[str, int]:
    """流式保存上传文件，并限制最大文件大小"""
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name
    total_bytes = 0

    try:
        while True:
            data = await file.read(1024 * 1024)
            if not data:
                break
            total_bytes += len(data)
            if total_bytes > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件大小不能超过 {config.MAX_UPLOAD_SIZE_MB} MB",
                )
            temp_file.write(data)
    except Exception:
        temp_file.close()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    else:
        temp_file.close()

    return temp_path, total_bytes


@app.get("/health")
def health():
    """检查 API 配置及其依赖服务状态"""
    missing_keys = [
        key
        for key, value in {
            "EMBEDDING_API_KEY": config.EMBEDDING_API_KEY,
            "LLM_API_KEY": config.LLM_API_KEY,
        }.items()
        if not value
    ]
    checks = {
        "config": {
            "status": "ok" if not missing_keys else "error",
            "missing": missing_keys,
        }
    }

    for name, checker in (
        ("mysql", conversation_memory.ping),
        ("milvus", vector_store.ping),
    ):
        try:
            checker()
            checks[name] = {"status": "ok"}
        except Exception as exc:
            checks[name] = {
                "status": "error",
                "detail": _format_dependency_error(exc),
            }

    is_healthy = all(check["status"] == "ok" for check in checks.values())
    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={
            "status": "ok" if is_healthy else "degraded",
            "checks": checks,
        },
    )


@app.get("/documents", response_model=dict)
def list_documents():
    """列出 Milvus 中已入库的文档"""
    documents = vector_store.list_documents()
    return {"documents": documents, "count": len(documents)}


@app.delete("/documents/{doc_id}", response_model=dict)
def delete_document(doc_id: str):
    """删除指定文档及其全部分块"""
    if not vector_store.document_exists(doc_id):
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    vector_store.delete_document(doc_id)
    return {"status": "deleted", "doc_id": doc_id}


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    上传文档：
    1. 提取文本并切片
    2. 每个分块生成 OpenAI 嵌入向量
    3. 存入 Milvus
    """
    filename = (file.filename or "document").replace("\\", "/").split("/")[-1]
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持 {SUPPORTED_EXTENSIONS}",
        )

    temp_path, _ = await _save_upload_to_temp(file, ext)

    try:
        # 提取文本并切片
        text, file_type = extract_text_from_file(temp_path)
        chunks = chunk_text(text)
        if not chunks:
            raise HTTPException(status_code=400, detail="未从文件中提取到有效文本")
        if len(chunks) > config.MAX_DOCUMENT_CHUNKS:
            raise HTTPException(
                status_code=413,
                detail=f"文档分块数量不能超过 {config.MAX_DOCUMENT_CHUNKS}",
            )

        # 每个分块向量化
        vectors = get_embeddings(chunks)

        # 存入 Milvus
        doc_id = str(uuid.uuid4())
        inserted = vector_store.save_document(
            doc_id=doc_id,
            original_filename=filename,
            file_type=file_type,
            chunks=chunks,
            vectors=vectors,
            characters=len(text),
        )

        return UploadResponse(
            status="uploaded",
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            chunks=inserted,
            characters=len(text),
            vectors=inserted,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@app.post("/ask", response_model=dict)
def ask(req: AskRequest):
    """
    提问接口：
    1. 创建或读取会话
    2. 把问题交给多智能体工作流
    3. 保存问答记录并返回结果
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    # 创建或获取会话
    session_id = req.session_id
    if not session_id:
        session_id = conversation_memory.create_session()
    elif not conversation_memory.session_exists(session_id):
        session_id = conversation_memory.create_session(session_id)

    # 组装最近对话上下文
    context_history = conversation_memory.get_context(session_id, max_messages=10)

    # 调用多智能体工作流
    result = orchestrator.process_query(
        query=req.query,
        doc_ids=req.doc_ids,
        top_k=req.top_k,
        conversation_context=context_history,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["answer"])

    # 成功后再写入本轮问答，避免失败请求污染会话历史
    conversation_memory.add_message(session_id, "user", req.query)
    conversation_memory.add_message(
        session_id,
        "assistant",
        result["answer"],
        metadata={
            "sources": result.get("sources", []),
            "searched_docs": result.get("searched_docs", []),
            "workflow_log": result.get("workflow_log", []),
        },
    )

    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "searched_docs": result.get("searched_docs", []),
        "workflow_log": result.get("workflow_log", []),
        "metadata": result.get("metadata", {}),
        "session_id": session_id,
    }


@app.post("/sessions/create", response_model=SessionCreateResponse)
def create_session():
    """创建新会话"""
    session_id = conversation_memory.create_session()
    metadata = conversation_memory.get_session_metadata(session_id)
    return SessionCreateResponse(
        session_id=session_id,
        created_at=metadata["created_at"],
    )


@app.get("/sessions", response_model=dict)
def list_sessions():
    """列出所有会话"""
    sessions = conversation_memory.get_all_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
def get_session_history(session_id: str):
    """获取某个会话的历史"""
    if not conversation_memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = conversation_memory.get_history(session_id)
    metadata = conversation_memory.get_session_metadata(session_id)
    return SessionHistoryResponse(
        session_id=session_id,
        messages=messages,
        metadata=metadata,
    )


@app.delete("/sessions/{session_id}", response_model=dict)
def clear_session(session_id: str):
    """清空某个会话"""
    if not conversation_memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    conversation_memory.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/workflow/diagram", response_model=dict)
def get_workflow_diagram():
    """获取 LangGraph 工作流 Mermaid 图"""
    return {
        "diagram": orchestrator.get_workflow_diagram(),
        "format": "mermaid",
    }


@app.get("/stats", response_model=dict)
def get_stats():
    """MySQL 与 Milvus 的整体统计"""
    return {
        "conversations": conversation_memory.get_stats(),
        "documents": vector_store.get_stats(),
    }


@app.get("/", include_in_schema=False)
def frontend_redirect():
    """将根路径重定向到前端工作台"""
    return RedirectResponse(url="/app/")


app.mount(
    "/app",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend",
)
