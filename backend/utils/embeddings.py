"""
OpenAI 向量化工具

负责把文本转成嵌入向量，供 Milvus 入库与检索使用。
"""
from typing import List, Optional

from openai import OpenAI

import config


# 全局 OpenAI 客户端
client = OpenAI(api_key=config.OPENAI_API_KEY)


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
