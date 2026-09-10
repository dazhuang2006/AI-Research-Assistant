"""
统一的 Pydantic 请求/响应模型

所有 FastAPI 接口都通过这里定义的模型校验输入与输出。
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from backend import config


class AskRequest(BaseModel):
    """提问接口的请求体"""

    query: str = Field(default="", max_length=config.MAX_QUERY_LENGTH)
    top_k: int = Field(default=5, ge=1, le=config.MAX_TOP_K)
    doc_ids: Optional[List[str]] = Field(default=None, max_length=config.MAX_DOC_IDS)
    session_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("doc_ids")
    @classmethod
    def validate_doc_ids(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value

        cleaned = []
        for doc_id in value:
            doc_id = doc_id.strip()
            if not doc_id:
                raise ValueError("doc_ids 不能包含空字符串")
            if len(doc_id) > 512:
                raise ValueError("单个 doc_id 不能超过 512 个字符")
            cleaned.append(doc_id)
        return cleaned


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
    doc_id: str
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
