"""
Agent 工作流的 LangGraph 节点函数

每个函数接收 AgentState，执行一个 Agent，并返回更新后的状态。
"""
from .agent_state import AgentState
from .critic_agent import CriticAgent
from .editor_agent import EditorAgent
from .research_agent import ResearchAgent
from .summarizer_agent import SummarizerAgent


# 每个 Agent 只初始化一次
research_agent = ResearchAgent()
summarizer_agent = SummarizerAgent()
critic_agent = CriticAgent()
editor_agent = EditorAgent()


def research_node(state: AgentState) -> AgentState:
    """
    Research 节点：在 Milvus 中检索相关分块

    Args:
        state: 当前工作流状态

    Returns:
        更新了检索结果的状态
    """
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append("[1/4] Research Agent: 正在检索文档...")

    result = research_agent.search_multi_doc(
        query=state["query"],
        doc_ids=state.get("doc_ids"),
        top_k=state.get("top_k", 5),
    )

    if result["status"] == "error":
        return {
            **state,
            "status": "error",
            "error_message": result["message"],
            "workflow_log": workflow_log,
            "chunks": [],
            "sources": [],
            "searched_docs": [],
            "num_chunks_found": 0,
            "research_complete": False,
        }

    workflow_log.append(
        f"[1/4] 完成 - 检索到 {len(result['chunks'])} 个分块，"
        f"来自 {len(result.get('searched_docs', []))} 个文档"
    )

    return {
        **state,
        "chunks": result["chunks"],
        "sources": result["sources"],
        "searched_docs": result.get("searched_docs", []),
        "num_chunks_found": len(result["chunks"]),
        "workflow_log": workflow_log,
        "research_complete": True,
        "status": "research_complete",
    }


def summarizer_node(state: AgentState) -> AgentState:
    """
    Summarizer 节点：基于分块生成初稿

    Args:
        state: 当前工作流状态

    Returns:
        更新了初稿的状态
    """
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append("[2/4] Summarizer Agent: 正在生成初稿...")

    result = summarizer_agent.summarize(
        query=state["query"],
        chunks=state["chunks"],
        conversation_context=state.get("conversation_context", ""),
    )

    if result["status"] == "error":
        return {
            **state,
            "status": "error",
            "error_message": result["message"],
            "workflow_log": workflow_log,
            "initial_summary": "",
            "summary_complete": False,
        }

    workflow_log.append("[2/4] 完成 - 初稿已生成")

    return {
        **state,
        "initial_summary": result["summary"],
        "workflow_log": workflow_log,
        "summary_complete": True,
        "status": "summary_complete",
    }


def critic_node(state: AgentState) -> AgentState:
    """
    Critic 节点：检查初稿是否有缺口

    Args:
        state: 当前工作流状态

    Returns:
        更新了审查结果的状态
    """
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append("[3/4] Critic Agent: 正在审查初稿...")

    result = critic_agent.critique(
        query=state["query"],
        summary=state["initial_summary"],
        chunks=state["chunks"],
    )

    # 审查失败时保守处理：按没有缺口继续
    if result["status"] == "error":
        workflow_log.append("[3/4] 警告 - 审查失败，继续使用初稿")
        return {
            **state,
            "critique": "审查不可用",
            "has_gaps": False,
            "suggestions": [],
            "workflow_log": workflow_log,
            "critique_complete": True,
            "status": "critique_complete",
        }

    has_gaps = result.get("has_gaps", False)
    workflow_log.append(f"[3/4] 完成 - 发现缺口: {has_gaps}")

    return {
        **state,
        "critique": result["critique"],
        "has_gaps": has_gaps,
        "suggestions": result.get("suggestions", []),
        "workflow_log": workflow_log,
        "critique_complete": True,
        "status": "critique_complete",
    }


def editor_node(state: AgentState) -> AgentState:
    """
    Editor 节点：根据审查意见润色最终回答

    Args:
        state: 当前工作流状态

    Returns:
        更新了最终回答的状态
    """
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append("[4/4] Editor Agent: 正在润色回答...")

    result = editor_agent.edit(
        query=state["query"],
        summary=state["initial_summary"],
        critique=state["critique"],
        chunks=state["chunks"],
    )

    workflow_log.append("[4/4] 完成 - 最终回答已生成")

    return {
        **state,
        "final_answer": result.get("final_answer", state["initial_summary"]),
        "editing_applied": result.get("editing_applied", False),
        "workflow_log": workflow_log,
        "editor_complete": True,
        "status": "complete",
    }


def skip_editor_node(state: AgentState) -> AgentState:
    """
    跳过编辑：初稿质量合格，直接作为最终回答

    Args:
        state: 当前工作流状态

    Returns:
        以初稿作为最终回答的状态
    """
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append("[4/4] 跳过编辑 - 初稿质量合格")

    return {
        **state,
        "final_answer": state["initial_summary"],
        "editing_applied": False,
        "workflow_log": workflow_log,
        "editor_complete": True,
        "status": "complete",
    }


def should_edit(state: AgentState) -> str:
    """
    条件路由：决定是否进入 Editor

    Args:
        state: 当前工作流状态

    Returns:
        需要编辑返回 "edit"，否则返回 "skip_edit"
    """
    return "edit" if state.get("has_gaps", False) else "skip_edit"
