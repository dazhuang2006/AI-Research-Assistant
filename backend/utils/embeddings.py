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
    model = model or config.EMBEDDING_MODEL
    response = client.embeddings.create(
        input=text,
        model=model,
    )
    return response.data[0].embedding
