import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    ask_clarification, create_plan, direct_answer_node, evidence_check, execute_step,
    generate_final_answer, inspect_result, normalize_query, replan, retrieve_knowledge,
    route_query, save_trace,
)
from app.agent.state import AgentState
from app.config import get_settings
from app.observability import span
from app.tracing.recorder import record_trace, replace_trace_event


_connection: aiosqlite.Connection | None = None
_graph: Any = None


def _route_branch(state: AgentState) -> str:
    route = state.get("route", "clarify")
    if route == "direct_answer": return "direct"
    if route == "clarify": return "clarify"
    if route == "knowledge_base": return "knowledge"
    return "plan"


def _after_evidence(state: AgentState) -> str:
    return "final"


def _after_inspect(state: AgentState) -> str:
    if state.get("status") == "replanning": return "replan"
    if state.get("status") == "checking_evidence": return "evidence"
    if state.get("status") == "synthesizing": return "final"
    return "execute"


def _after_replan(state: AgentState) -> str:
    return "execute" if state.get("status") == "running" else "final"


async def build_graph(checkpoint_path: Path | None = None) -> Any:
    global _connection
    path = checkpoint_path or get_settings().project_path(get_settings().checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _connection = await aiosqlite.connect(path)
    checkpointer = AsyncSqliteSaver(_connection)
    await checkpointer.setup()
    workflow = StateGraph(AgentState)
    for name, node in {
        "normalize_query": normalize_query, "route_query": route_query,
        "direct_answer": direct_answer_node, "ask_clarification": ask_clarification,
        "retrieve_knowledge": retrieve_knowledge, "evidence_check": evidence_check,
        "create_plan": create_plan, "execute_step": execute_step, "inspect_result": inspect_result,
        "replan": replan, "generate_final_answer": generate_final_answer, "save_trace": save_trace,
    }.items(): workflow.add_node(name, node)
    workflow.add_edge(START, "normalize_query")
    workflow.add_edge("normalize_query", "route_query")
    workflow.add_conditional_edges("route_query", _route_branch,
                                   {"direct": "direct_answer", "clarify": "ask_clarification",
                                    "knowledge": "retrieve_knowledge", "plan": "create_plan"})
    workflow.add_edge("direct_answer", "save_trace")
    workflow.add_edge("ask_clarification", "save_trace")
    workflow.add_edge("retrieve_knowledge", "evidence_check")
    workflow.add_conditional_edges("evidence_check", _after_evidence, {"final": "generate_final_answer"})
    workflow.add_edge("create_plan", "execute_step")
    workflow.add_edge("execute_step", "inspect_result")
    workflow.add_conditional_edges("inspect_result", _after_inspect,
                                   {"replan": "replan", "evidence": "evidence_check",
                                    "final": "generate_final_answer", "execute": "execute_step"})
    workflow.add_conditional_edges("replan", _after_replan,
                                   {"execute": "execute_step", "final": "generate_final_answer"})
    workflow.add_edge("generate_final_answer", "save_trace")
    workflow.add_edge("save_trace", END)
    return workflow.compile(checkpointer=checkpointer)


async def get_graph() -> Any:
    global _graph
    if _graph is None: _graph = await build_graph()
    return _graph


async def close_graph() -> None:
    global _connection, _graph
    if _connection is not None: await _connection.close()
    _connection, _graph = None, None


async def run_agent(query: str, session_id: str | None = None,
                    user_id: str = "anonymous", user_role: str = "user") -> AgentState:
    request_id, thread_id = str(uuid.uuid4()), session_id or str(uuid.uuid4())
    settings = get_settings()
    initial: AgentState = {
        "request_id": request_id, "thread_id": thread_id, "user_id": user_id,
        "user_role": user_role, "user_query": query, "normalized_query": "", "route": "",
        "route_confidence": 0, "route_reason": "", "rewritten_query": query,
        "required_tools": [], "extracted_parameters": {}, "plan": [], "current_step": 0,
        "completed_steps": [], "selected_tool": None, "tool_arguments": {}, "tool_results": [],
        "retrieved_documents": [], "evidence_status": "not_checked", "evidence_reason": "",
        "answer_mode": "", "provider_mode": settings.llm_provider, "fallback_reason": None,
        "errors": [], "final_answer": None, "status": "created", "iteration_count": 0,
        "replan_count": 0, "tool_call_count": 0, "requires_approval": False,
        "approval_status": None, "pending_action": None,
    }
    started = datetime.now(UTC)
    record_trace(request_id, {
        "event_type": "root",
        "span_id": "agent-root",
        "span_name": "agent.request",
        "node_name": "agent.request",
        "user_query": query,
        "thread_id": thread_id,
        "user_id": user_id,
        "started_at": started.isoformat(),
        "success": None,
        "status": "running",
        "input": {"query": query, "session_id": session_id, "user_role": user_role},
        "model_info": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model or "mock",
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "database_provider": settings.database_provider,
            "knowledge_corpus": settings.knowledge_corpus,
        },
    })
    graph = await get_graph()
    with span("agent.request", request_id=request_id, thread_id=thread_id, user_id=user_id):
        try:
            result = await graph.ainvoke(initial, config={"configurable": {"thread_id": thread_id},
                                                          "recursion_limit": settings.agent_max_steps * 5 + 20})
            finished = datetime.now(UTC)
            replace_trace_event(request_id, {"span_id": "agent-root"}, {
                "event_type": "root",
                "span_id": "agent-root",
                "span_name": "agent.request",
                "node_name": "agent.request",
                "user_query": query,
                "thread_id": thread_id,
                "user_id": user_id,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "duration_ms": round((finished - started).total_seconds() * 1000),
                "success": result.get("status") not in {"failed"},
                "status": result.get("status", "completed"),
                "input": {"query": query, "session_id": session_id, "user_role": user_role},
                "output": {
                    "status": result.get("status"),
                    "route": result.get("route"),
                    "tools": [item.get("tool") for item in result.get("tool_results", []) if item.get("tool")],
                    "errors": result.get("errors", []),
                    "final_answer_length": len(result.get("final_answer") or ""),
                },
                "model_info": {
                    "llm_provider": result.get("provider_mode") or settings.llm_provider,
                    "llm_model": settings.llm_model or "mock",
                    "embedding_provider": settings.embedding_provider,
                    "embedding_model": settings.embedding_model,
                    "database_provider": settings.database_provider,
                    "knowledge_corpus": settings.knowledge_corpus,
                },
            })
            return result
        except Exception as exc:
            finished = datetime.now(UTC)
            replace_trace_event(request_id, {"span_id": "agent-root"}, {
                "event_type": "root",
                "span_id": "agent-root",
                "span_name": "agent.request",
                "node_name": "agent.request",
                "user_query": query,
                "thread_id": thread_id,
                "user_id": user_id,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "duration_ms": round((finished - started).total_seconds() * 1000),
                "success": False,
                "status": "failed",
                "error": str(exc)[:500],
                "input": {"query": query, "session_id": session_id, "user_role": user_role},
                "output": {"error_type": type(exc).__name__},
            })
            raise
