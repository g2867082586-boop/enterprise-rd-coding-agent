from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    request_id: str
    thread_id: str
    user_id: str
    user_role: str
    user_query: str
    normalized_query: str
    route: str
    route_confidence: float
    route_reason: str
    rewritten_query: str
    required_tools: list[str]
    extracted_parameters: dict[str, Any]
    plan: list[dict[str, Any]]
    current_step: int
    completed_steps: list[str]
    selected_tool: str | None
    tool_arguments: dict[str, Any]
    tool_results: list[dict[str, Any]]
    retrieved_documents: list[dict[str, Any]]
    evidence_status: str
    evidence_reason: str
    answer_mode: str
    provider_mode: str
    fallback_reason: str | None
    errors: list[str]
    final_answer: str | None
    status: str
    iteration_count: int
    replan_count: int
    tool_call_count: int
    requires_approval: bool
    approval_status: str | None
    pending_action: dict[str, Any] | None
