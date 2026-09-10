"""
多智能体系统的 LangGraph 工作流定义

流程：检索 -> 总结 -> 审查 -> （编辑 或 跳过） -> 结束
"""
from langgraph.graph import END, StateGraph

from .agent_state import AgentState
from .langgraph_nodes import (
    critic_node,
    editor_node,
    error_node,
    research_node,
    route_after_critique,
    route_after_research,
    route_after_summarizer,
    skip_editor_node,
    summarizer_node,
)


def create_agent_workflow() -> StateGraph:
    """
    创建并编译 LangGraph 工作流

    Returns:
        编译后可直接执行的工作流
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("research", research_node)
    workflow.add_node("summarize", summarizer_node)
    workflow.add_node("critique", critic_node)
    workflow.add_node("edit", editor_node)
    workflow.add_node("skip_edit", skip_editor_node)
    workflow.add_node("error", error_node)

    # 入口与顺序执行
    workflow.set_entry_point("research")
    workflow.add_conditional_edges(
        "research",
        route_after_research,
        {
            "continue": "summarize",
            "error": "error",
        },
    )
    workflow.add_conditional_edges(
        "summarize",
        route_after_summarizer,
        {
            "continue": "critique",
            "error": "error",
        },
    )

    # 审查后根据结果做条件路由
    workflow.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "edit": "edit",
            "skip_edit": "skip_edit",
            "error": "error",
        },
    )

    # 成功与失败路径最终都结束
    workflow.add_edge("edit", END)
    workflow.add_edge("skip_edit", END)
    workflow.add_edge("error", END)

    return workflow.compile()


def get_workflow_visualization() -> str:
    """
    获取工作流的 Mermaid 图

    Returns:
        Mermaid Markdown 字符串
    """
    graph = create_agent_workflow()
    try:
        return graph.get_graph().draw_mermaid()
    except Exception:
        return """
graph TD
    START([开始]) --> research[Research Agent]
    research -->|成功| summarize[Summarizer Agent]
    research -->|失败| error[错误终止]
    summarize -->|成功| critique[Critic Agent]
    summarize -->|失败| error
    critique -->|有缺口| edit[Editor Agent]
    critique -->|无缺口| skip[跳过编辑]
    critique -->|失败| error
    edit --> END([结束])
    skip --> END
    error --> END
"""


# 全局单例工作流
agent_workflow = create_agent_workflow()
