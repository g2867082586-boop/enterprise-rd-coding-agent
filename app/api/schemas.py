from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)


class AgentRunResponse(BaseModel):
    request_id: str
    status: str
    answer: str
    sources: list[str]
    tool_calls: list[dict[str, Any]]
    trace_summary: dict[str, Any]
    runtime_mode: dict[str, str]

