"""
多智能体工作流的 LangGraph 状态定义
"""
from typing import List, Optional, TypedDict


class AgentState(TypedDict):
    """在工作流中传递的共享状态，每个 Agent 都可以读写"""

    # 输入
    query: str                              # 用户的问题
    top_k: int                              # 需要检索的分块数量
    doc_ids: Optional[List[str]]            # 要搜索的文档 ID 列表
    conversation_context: str               # 之前的对话历史

    # Research Agent 输出
    chunks: List[str]                       # 检索到的文本分块
    sources: List[str]                      # 分块对应的来源文档
    num_chunks_found: int                   # 检索到的分块数量
    searched_docs: List[str]                # 实际搜索过的文档

    # Summarizer Agent 输出
    initial_summary: str                    # 第一版草稿回答

    # Critic Agent 输出
    critique: str                           # 回答质量评估
    has_gaps: bool                          # 是否发现缺口
    suggestions: List[str]                  # 改进建议

    # Editor Agent 输出
    final_answer: str                       # 最终回答
    editing_applied: bool                   # 是否执行了编辑

    # 工作流元数据
    workflow_log: List[str]                 # 进度日志
    status: str                             # 当前状态
    error_message: Optional[str]            # 错误信息

    # Agent 执行标记
    research_complete: bool
    summary_complete: bool
    critique_complete: bool
    editor_complete: bool
