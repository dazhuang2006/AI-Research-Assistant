# AI Research Assistant（MySQL + Milvus 版）

一个基于 **RAG + 多智能体 + LangGraph** 的文档问答项目。

- 文档解析：PDF / DOCX / HTML / TXT
- 文本分块：默认 500 字符，重叠 50 字符
- 嵌入：硅基流动 `BAAI/bge-m3`，向量维度 1024
- 向量库：Milvus
- 对话模型：DeepSeek 官方 API `deepseek-v4-flash`
- 会话记忆：MySQL
- API：FastAPI
- 工作流：Research Agent -> Summarizer Agent -> Critic Agent ->（Editor / 跳过）

## 项目结构

```text
AI-Research-Assistant/
├── backend/
│   ├── agents/         # 4 个 Agent + LangGraph 工作流 + 编排器
│   ├── db/             # MySQL 会话记忆、Milvus 向量存储
│   ├── models/         # Pydantic 请求/响应模型
│   ├── utils/          # 文档解析、OpenAI 兼容嵌入
│   ├── .env            # 本地配置（不提交 git）
│   ├── config.py       # 统一读取环境变量
│   ├── main.py         # FastAPI 入口
│   └── requirements.txt
└── .venv/              # Python 虚拟环境
```

## 启动步骤

### 1. 安装依赖

```powershell
cd D:\python\xiangmu\AI-Research-Assistant
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 2. 配置 .env

```powershell
Copy-Item backend\.env.example backend\.env
```

在 `backend\.env` 中填写：

- 硅基流动 API Key（嵌入）
- DeepSeek API Key（对话）
- MySQL 账号密码

### 3. 启动 Milvus

本机 Milvus 工具目录已有启动脚本：

```powershell
D:\program\docker_tool\Milvus\start_milvus.bat
```

确认端口 19530 可访问后继续。

### 4. 启动 MySQL

确认本机 MySQL 服务已运行。后端首次导入时会自动创建 `research_assistant` 数据库和两张表。

### 5. 启动后端

在项目根目录执行：

```powershell
.\.venv\Scripts\uvicorn.exe backend.main:app --reload --port 8000
```

打开 `http://127.0.0.1:8000/docs` 可查看 Swagger 文档。

## API 一览

```text
POST  /upload                 上传并向量化文档
GET   /documents              列出文档
DELETE /documents/{doc_id}    删除文档
POST  /ask                    多智能体问答
POST  /sessions/create        创建会话
GET   /sessions               列出会话
GET   /sessions/{id}/history  获取会话历史
DELETE /sessions/{id}         清空会话
GET   /workflow/diagram       工作流 Mermaid 图
GET   /stats                  统计
GET   /health                 健康检查
```

## 使用示例

先上传一个文档：

```text
POST /upload  (multipart/form-data, file=xxx.pdf)
```

再提问：

```json
POST /ask
{
  "query": "这个项目用到了哪些技术？",
  "top_k": 5,
  "session_id": null
}
```

返回中包含最终回答、来源文档、工作流日志和会话 ID，支持后续追问。
