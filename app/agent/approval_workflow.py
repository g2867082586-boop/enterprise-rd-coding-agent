import sqlite3
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.config import get_settings


class ApprovalState(TypedDict, total=False):
    approval_id: str
    thread_id: str
    operation: str
    parameters: dict[str, Any]
    approval_status: str


_connection: sqlite3.Connection | None = None
_graph: Any = None


def _pause_for_approval(state: ApprovalState) -> dict[str, str]:
    decision = interrupt({
        "approval_id": state["approval_id"], "operation": state["operation"],
        "parameters": state["parameters"], "approval_status": "pending",
    })
    approved = bool(isinstance(decision, dict) and decision.get("approved"))
    return {"approval_status": "approved" if approved else "rejected"}


def get_approval_graph() -> Any:
    global _connection, _graph
    if _graph is None:
        path = get_settings().project_path(get_settings().approval_checkpoint_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(path, check_same_thread=False)
        saver = SqliteSaver(_connection); saver.setup()
        workflow = StateGraph(ApprovalState)
        workflow.add_node("human_approval", _pause_for_approval)
        workflow.add_edge(START, "human_approval"); workflow.add_edge("human_approval", END)
        _graph = workflow.compile(checkpointer=saver)
    return _graph


def start_approval_checkpoint(approval_id: str, thread_id: str, operation: str,
                              parameters: dict[str, Any]) -> None:
    get_approval_graph().invoke(
        {"approval_id": approval_id, "thread_id": thread_id, "operation": operation,
         "parameters": parameters, "approval_status": "pending"},
        config={"configurable": {"thread_id": thread_id}},
    )


def resume_approval_checkpoint(thread_id: str, approved: bool) -> ApprovalState:
    return get_approval_graph().invoke(
        Command(resume={"approved": approved}),
        config={"configurable": {"thread_id": thread_id}},
    )
