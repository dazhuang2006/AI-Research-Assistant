"""
统一配置模块：从 .env 文件读取 OpenAI、MySQL、Milvus 相关配置
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 始终加载 backend 目录下的 .env，与当前工作目录无关
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

# 嵌入服务（硅基流动，OpenAI 兼容接口）
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# 对话服务（DeepSeek 官方 API）
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")

# MySQL 会话记忆
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "research_assistant")

# Milvus 向量库
MILVUS_URI = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
MILVUS_CHUNK_COLLECTION = os.getenv("MILVUS_CHUNK_COLLECTION", "document_chunks")
MILVUS_DOC_COLLECTION = os.getenv("MILVUS_DOC_COLLECTION", "document_meta")
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "1024"))
