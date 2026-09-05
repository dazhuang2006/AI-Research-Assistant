"""
AI Research Assistant 后端入口

运行方式（在项目根目录）：
    uvicorn backend.main:app --reload --port 8000
"""
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

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
from backend.utils.embeddings import get_embedding

app = FastAPI(title="AI Research Assistant")

# 本地开发允许跨域；上线前需要改成具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


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
    filename = file.filename or "document"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持 {SUPPORTED_EXTENSIONS}",
        )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    temp_file.write(await file.read())
    temp_file.close()

    try:
        # 提取文本并切片
        text, file_type = extract_text_from_file(temp_file.name)
        chunks = chunk_text(text)
        if not chunks:
            raise HTTPException(status_code=400, detail="未从文件中提取到有效文本")

        # 每个分块向量化
        vectors = [get_embedding(chunk) for chunk in chunks]

        # 存入 Milvus
        inserted = vector_store.save_document(
            doc_id=filename,
            original_filename=filename,
            file_type=file_type,
            chunks=chunks,
            vectors=vectors,
            characters=len(text),
        )

        return UploadResponse(
            status="uploaded",
            filename=filename,
            file_type=file_type,
            chunks=inserted,
            characters=len(text),
            vectors=inserted,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


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

    # 用户消息先写入历史
    conversation_memory.add_message(session_id, "user", req.query)

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

    # 助手回答写入历史
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
