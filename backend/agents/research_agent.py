"""
Research Agent（检索 Agent）

负责把用户问题转成向量，在 Milvus 中检索最相关的文档分块。
"""
from typing import Dict, List, Optional

from backend.db.milvus_store import vector_store
from backend.utils.embeddings import get_embedding


class ResearchAgent:
    def __init__(self):
        self.name = "Research Agent"

    def search_multi_doc(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict:
        """
        在 Milvus 中检索与问题最相关的文档分块

        Args:
            query: 用户的问题
            doc_ids: 要搜索的文档 ID 列表（None 表示全部文档）
            top_k: 返回的分块数量

        Returns:
            包含分块、来源和搜索文档的字典
        """
        all_docs = vector_store.list_documents()
        if not all_docs:
            return {
                "status": "error",
                "message": "向量库中还没有文档，请先上传",
                "chunks": [],
                "sources": [],
                "searched_docs": [],
            }

        # 未指定文档时默认搜索全部
        if not doc_ids:
            doc_ids = [doc["doc_id"] for doc in all_docs]

        # 过滤掉不存在的文档 ID
        valid_ids = {doc["doc_id"] for doc in all_docs}
        doc_ids = [doc_id for doc_id in doc_ids if doc_id in valid_ids]
        if not doc_ids:
            return {
                "status": "error",
                "message": "指定的文档不存在，请检查 doc_ids",
                "chunks": [],
                "sources": [],
                "searched_docs": [],
            }

        # 把问题转成向量
        query_vector = get_embedding(query)

        # 在 Milvus 中检索
        chunks, sources, distances = vector_store.search_documents(
            query_vector=query_vector,
            doc_ids=doc_ids,
            top_k=top_k,
        )

        return {
            "status": "success",
            "chunks": chunks,
            "sources": sources,
            "distances": distances,
            "num_results": len(chunks),
            "searched_docs": doc_ids,
        }
