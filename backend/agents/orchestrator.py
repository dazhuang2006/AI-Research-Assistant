"""
编排器

负责初始化状态、调用 LangGraph 工作流，并把结果整理成 API 需要的格式。
"""
from typing import Dict, List, Optional

from .agent_state import AgentState
from .langgraph_workflow import agent_workflow


class Orchestrator:
    def __init__(self):
        self.workflow = agent_workflow

    def process_query(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        top_k: int = 5,
        conversation_context: str = "",
    ) -> Dict:
        """
        执行完整的多智能体问答流程

        Args:
            query: 用户的问题
            doc_ids: 要搜索的文档 ID 列表（None 表示全部文档）
            top_k: 检索的分块数量
            conversation_context: 之前的对话历史

        Returns:
            包含最终回答、来源和工作流元数据的字典
        """
        initial_state: AgentState = {
            # 输入
            "query": query,
            "top_k": top_k,
            "doc_ids": doc_ids,
            "conversation_context": conversation_context,

            # 输出占位
            "chunks": [],
            "sources": [],
            "num_chunks_found": 0,
            "searched_docs": [],
            "initial_summary": "",
            "critique": "",
            "has_gaps": False,
            "suggestions": [],
            "final_answer": "",
            "editing_applied": False,

            # 元数据
            "workflow_log": [],
            "status": "initialized",
            "error_message": None,

            # 执行标记
            "research_complete": False,
            "summary_complete": False,
            "critique_complete": False,
            "editor_complete": False,
        }

        try:
            final_state = self.workflow.invoke(initial_state)
        except Exception as e:
            return {
                "status": "error",
                "answer": f"多智能体工作流执行失败: {str(e)}",
                "sources": [],
                "searched_docs": [],
                "workflow_log": [],
                "metadata": {},
            }

        if final_state.get("status") == "error":
            return {
                "status": "error",
                "answer": final_state.get("error_message", "未知错误"),
                "sources": [],
                "searched_docs": final_state.get("searched_docs", []),
                "workflow_log": final_state.get("workflow_log", []),
                "metadata": {},
            }

        return {
            "status": "success",
            "answer": final_state["final_answer"],
            "sources": final_state.get("sources", []),
            "searched_docs": final_state.get("searched_docs", []),
            "workflow_log": final_state.get("workflow_log", []),
            "metadata": {
                "num_chunks": final_state.get("num_chunks_found", 0),
                "has_gaps": final_state.get("has_gaps", False),
                "editing_applied": final_state.get("editing_applied", False),
                "workflow_type": "langgraph",
            },
        }

    def get_workflow_diagram(self) -> str:
        """
        获取工作流的 Mermaid 可视化图

        Returns:
            Mermaid Markdown 字符串
        """
        from .langgraph_workflow import get_workflow_visualization

        return get_workflow_visualization()
