"""
Editor Agent（编辑 Agent）

根据 Critic 的审查意见，把初稿改成最终回答。
"""
from typing import Dict, List

from openai import OpenAI

from backend import config


class EditorAgent:
    def __init__(self):
        self.name = "Editor Agent"
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
        )

    def edit(
        self,
        query: str,
        summary: str,
        critique: str,
        chunks: List[str],
    ) -> Dict:
        """
        根据审查意见润色初稿

        Args:
            query: 用户的问题
            summary: Summarizer 生成的初稿
            critique: Critic 给出的审查意见
            chunks: 检索到的原文分块

        Returns:
            包含最终回答的字典
        """
        context = "\n\n---\n\n".join(chunks)

        prompt = f"""你是文档回答编辑。请根据审查意见修改初稿，并继续遵守“只用文档内容”的规则。

用户问题：
{query}

初稿回答：
{summary}

审查意见：
{critique}

文档内容（唯一事实来源）：
{context}

请输出修改后的最终回答："""

        response = self.client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是擅长根据文档内容润色回答的编辑。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        return {
            "status": "success",
            "final_answer": response.choices[0].message.content,
            "editing_applied": True,
        }
