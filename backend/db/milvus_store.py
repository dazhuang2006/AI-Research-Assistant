"""
基于 Milvus 的多文档向量存储

一个 Collection 保存所有文档的分块向量；每个分块行同时冗余保存
doc_id、原文件名、文件类型、上传时间等文档信息，便于列表查询与删除。
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pymilvus import DataType, MilvusClient

from backend import config


def _escape_milvus(value: str) -> str:
    """转义 Milvus filter 中字符串字面量里的反斜杠和双引号"""
    return value.replace("\\", "\\\\").replace('"', '\\"')


class MilvusVectorStore:
    """
    使用 Milvus 保存文档分块向量

    字段说明：
    - doc_id / original_filename / file_type / upload_date / characters / chunks：文档信息
    - text：分块原文
    - embedding：分块向量
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        collection_name: Optional[str] = None,
        dim: Optional[int] = None,
    ):
        self.uri = uri or config.MILVUS_URI
        self.collection_name = collection_name or config.MILVUS_CHUNK_COLLECTION
        self.dim = dim or config.VECTOR_DIM

        self.client = MilvusClient(uri=self.uri)
        self._ensure_collection()

    def _ensure_collection(self):
        """如果 Collection 不存在则按约定 Schema 创建"""
        if self.client.has_collection(self.collection_name):
            return

        schema = self.client.create_schema(auto_id=True)
        schema.add_field(field_name="pk", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="original_filename", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="file_type", datatype=DataType.VARCHAR, max_length=32)
        schema.add_field(field_name="upload_date", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="characters", datatype=DataType.INT64)
        schema.add_field(field_name="chunks", datatype=DataType.INT64)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self.dim)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

    @staticmethod
    def _doc_filter(doc_ids: List[str]) -> str:
        """把文档 ID 列表拼成 Milvus 使用的过滤表达式"""
        quoted = ", ".join(f'"{_escape_milvus(doc_id)}"' for doc_id in doc_ids)
        return f"doc_id in [{quoted}]"

    def save_document(
        self,
        doc_id: str,
        original_filename: str,
        file_type: str,
        chunks: List[str],
        vectors: List[List[float]],
        characters: int,
    ) -> int:
        """
        保存一个文档的全部分块向量

        Args:
            doc_id: 文档标识（内部使用）
            original_filename: 上传时的原始文件名
            file_type: 文件类型，例如 PDF / DOCX / TXT
            chunks: 文本分块列表
            vectors: 与 chunks 一一对应的嵌入向量列表
            characters: 文档原始字符数

        Returns:
            成功插入的分块数量
        """
        if len(chunks) != len(vectors):
            raise ValueError("chunks 和 vectors 长度必须一致")

        # 同名文档重新上传时先清掉旧数据
        if self.document_exists(doc_id):
            self.delete_document(doc_id)

        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            {
                "doc_id": doc_id,
                "original_filename": original_filename,
                "file_type": file_type,
                "upload_date": upload_date,
                "characters": characters,
                "chunks": len(chunks),
                "text": chunk,
                "embedding": vector,
            }
            for chunk, vector in zip(chunks, vectors)
        ]

        self.client.insert(collection_name=self.collection_name, data=rows)
        return len(rows)

    def document_exists(self, doc_id: str) -> bool:
        """检查某个文档是否已经入库"""
        result = self.client.query(
            collection_name=self.collection_name,
            filter=f'doc_id == "{_escape_milvus(doc_id)}"',
            output_fields=["doc_id"],
            limit=1,
        )
        return bool(result)

    def delete_document(self, doc_id: str) -> bool:
        """按 doc_id 删除文档的全部分块"""
        self.client.delete(
            collection_name=self.collection_name,
            filter=f'doc_id == "{_escape_milvus(doc_id)}"',
        )
        return True

    def list_documents(self) -> List[Dict]:
        """
        列出所有已入库的文档

        Returns:
            文档信息字典列表（同一个 doc_id 只保留一条）
        """
        rows = self.client.query(
            collection_name=self.collection_name,
            filter="",
            output_fields=[
                "doc_id",
                "original_filename",
                "file_type",
                "upload_date",
                "characters",
                "chunks",
            ],
            limit=10000,
        )

        documents = {}
        for row in rows:
            doc_id = row.get("doc_id")
            if doc_id and doc_id not in documents:
                documents[doc_id] = {
                    "doc_id": doc_id,
                    "original_filename": row.get("original_filename"),
                    "file_type": row.get("file_type"),
                    "upload_date": row.get("upload_date"),
                    "characters": row.get("characters"),
                    "chunks": row.get("chunks"),
                }
        return list(documents.values())

    def search_documents(
        self,
        query_vector: List[float],
        doc_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Tuple[List[str], List[str], List[float]]:
        """
        在 Milvus 中检索与查询向量最相似的分块

        Args:
            query_vector: 用户问题生成的嵌入向量
            doc_ids: 要搜索的文档 ID 列表（None 表示全部文档）
            top_k: 返回的分块数量

        Returns:
            (chunks, sources, distances) 元组
        """
        filter_expr = self._doc_filter(doc_ids) if doc_ids else ""

        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            filter=filter_expr,
            limit=top_k,
            output_fields=["doc_id", "original_filename", "text"],
        )

        chunks = []
        sources = []
        distances = []

        for hit in (results[0] if results else []):
            entity = hit.get("entity", {})
            chunks.append(entity.get("text", ""))
            sources.append(entity.get("original_filename") or entity.get("doc_id"))
            distances.append(float(hit.get("distance", 0.0)))

        return chunks, sources, distances

    def get_stats(self) -> Dict:
        """获取向量库整体统计信息"""
        documents = self.list_documents()
        row_count = self.client.get_collection_stats(self.collection_name).get("row_count", 0)
        return {
            "total_documents": len(documents),
            "total_vectors": row_count,
            "total_chunks": row_count,
            "documents": documents,
        }


# 全局单例：后续 FastAPI 统一使用这一个实例
vector_store = MilvusVectorStore()
