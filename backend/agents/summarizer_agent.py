"""
Summarizer Agent（总结 Agent）

根据检索到的分块生成初稿回答，只允许使用文档上下文中的信息。
"""
from typing import Dict, List

from openai import OpenAI

from backend import config


class SummarizerAgent:
    def __init__(self):
        self.name = "Summarizer Agent"
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
        )

    def summarize(
        self,
        query: str,
        chunks: List[str],
        conversation_context: str = "",
    ) -> Dict:
        """
        基于检索分块生成初稿

        Args:
            query: 用户的问题
            chunks: Milvus 检索到的文本分块
            conversation_context: 之前的对话历史

        Returns:
            包含 summary 的字典
        """
        if not chunks:
            return {
                "status": "error",
                "message": "没有可供总结的文档分块",
                "summary": "",
            }

        context = "\n\n---\n\n".join(chunks)
        history = f"{conversation_context}\n\n" if conversation_context else ""

        prompt = f"""{history}你是文档问答助手。请只根据下面给出的文档内容回答问题。

规则：
1. 只能使用文档中明确出现的信息
2. 不要编造文档里没有的内容
3. 如果文档里找不到答案，明确说“文档中未找到相关信息”
4. 如果用户是追问，先结合上面的历史对话理解指代对象

文档内容：
{context}

用户问题：
{query}

请给出回答："""

        response = self.client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的文档研究助手，回答必须只基于文档内容。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        return {
            "status": "success",
            "summary": response.choices[0].message.content,
            "num_chunks_used": len(chunks),
        }
