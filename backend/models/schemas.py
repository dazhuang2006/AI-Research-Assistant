"""
统一的 Pydantic 请求/响应模型

所有 FastAPI 接口都通过这里定义的模型校验输入与输出。
"""
from typing import Dict, List, Optional

from pydantic import BaseModel


class AskRequest(BaseModel):
    """提问接口的请求体"""

    query: str = ""
    top_k: int = 5
    doc_ids: Optional[List[str]] = None  # None 表示搜索全部文档
    session_id: Optional[str] = None     # 为空时后端自动创建新会话


class DocumentInfo(BaseModel):
    """Milvus 中文档的元信息"""

    doc_id: str
    original_filename: str
    file_type: str
    upload_date: str
    characters: int
    chunks: int


class UploadResponse(BaseModel):
    """上传文档后的响应"""

    status: str
    filename: str
    file_type: str
    chunks: int
    characters: int
    vectors: int
    storage_type: str = "milvus"


class SessionCreateResponse(BaseModel):
    """创建会话后的响应"""

    session_id: str
    created_at: str


class SessionHistoryResponse(BaseModel):
    """会话历史响应"""

    session_id: str
    messages: List[Dict]
    metadata: Dict
