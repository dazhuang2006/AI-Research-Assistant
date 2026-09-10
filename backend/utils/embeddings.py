"""
OpenAI 向量化工具

负责把文本转成嵌入向量，供 Milvus 入库与检索使用。
"""
from typing import List, Optional

from openai import OpenAI

from backend import config


# 嵌入服务客户端（OpenAI 兼容，指向硅基流动）
client = OpenAI(
    api_key=config.EMBEDDING_API_KEY,
    base_url=config.EMBEDDING_BASE_URL,
)


def get_embedding(
    text: str,
    model: Optional[str] = None,
) -> List[float]:
    """
    获取文本对应的嵌入向量

    Args:
        text: 输入文本
        model: 嵌入模型名称，默认取 config.EMBEDDING_MODEL

    Returns:
        嵌入向量列表
    """
    return get_embeddings([text], model=model)[0]


def get_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
) -> List[List[float]]:
    """
    批量获取文本嵌入向量。

    Args:
        texts: 输入文本列表
        model: 嵌入模型名称，默认取 config.EMBEDDING_MODEL
        batch_size: 每批请求的文本数量

    Returns:
        与 texts 顺序一致的嵌入向量列表
    """
    if not texts:
        return []

    model = model or config.EMBEDDING_MODEL
    batch_size = batch_size or config.EMBEDDING_BATCH_SIZE
    vectors: List[List[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        response = client.embeddings.create(
            input=batch,
            model=model,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)

    return vectors
