from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateChatSessionRequest(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=160)


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    status: str
    request_id: str | None
    sources: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: datetime


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None


class ChatSessionDetail(ChatSessionSummary):
    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=2, max_length=2000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)


class AgentMessageResponse(BaseModel):
    message_id: str
    session_id: str
    request_id: str | None
    status: str
    answer: str
    sources: list[dict[str, Any]]
    trace_summary: dict[str, Any]
    runtime_mode: dict[str, str]
    created_at: datetime


class TraceSummaryResponse(BaseModel):
    request_id: str
    question: str
    created_at: datetime
    status: str
    tools: list[str]
    duration_ms: int
    success: bool
