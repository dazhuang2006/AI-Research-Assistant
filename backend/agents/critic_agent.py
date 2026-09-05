"""
Critic Agent（审查 Agent）

检查初稿是否基于文档内容、有没有漏掉关键信息，并判断是否需要编辑。
"""
from typing import Dict, List

from openai import OpenAI

from backend import config


class CriticAgent:
    def __init__(self):
        self.name = "Critic Agent"
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    def critique(
        self,
        query: str,
        summary: str,
        chunks: List[str],
    ) -> Dict:
        """
        审查初稿质量

        Args:
            query: 用户的问题
            summary: Summarizer 生成的初稿
            chunks: 检索到的原文分块

        Returns:
            包含审查结果和是否发现缺口的字典
        """
        if not summary:
            return {
                "status": "error",
                "message": "没有可审查的初稿",
                "critique": "",
                "has_gaps": False,
                "suggestions": [],
            }

        # 只看前 3 个最相关的分块即可完成大部分校验
        context = "\n\n---\n\n".join(chunks[:3])

        prompt = f"""你是回答质量审查员。请检查下面的回答是否严格来自文档内容。

用户问题：
{query}

初稿回答：
{summary}

可用文档内容：
{context}

请按以下格式输出：
STRENGTHS: 回答做得好的地方
GAPS: 回答的问题，例如编造内容或遗漏关键信息；如果没有就写 None
SUGGESTIONS: 具体修改建议；如果没有就写 None

请只输出这三行。"""

        response = self.client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的文档回答审查员。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        critique = response.choices[0].message.content

        # 简单判断：GAPS 一栏内容明显多于 None 时认为需要编辑
        gaps_text = ""
        if "GAPS:" in critique:
            gaps_text = critique.split("GAPS:", 1)[1].split("SUGGESTIONS:", 1)[0].strip()
        has_gaps = bool(gaps_text) and gaps_text.lower() != "none"

        suggestions = []
        if "SUGGESTIONS:" in critique:
            raw = critique.split("SUGGESTIONS:", 1)[1].strip()
            suggestions = [
                line.strip("- ").strip()
                for line in raw.splitlines()
                if line.strip() and line.strip().lower() != "none"
            ]

        return {
            "status": "success",
            "critique": critique,
            "has_gaps": has_gaps,
            "suggestions": suggestions[:5],
        }
