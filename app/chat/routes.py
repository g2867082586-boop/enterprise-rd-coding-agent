import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.auth.service import utcnow
from app.chat.schemas import (
    AgentMessageResponse,
    ChatSessionDetail,
    ChatSessionSummary,
    CreateChatSessionRequest,
    SendMessageRequest,
    TraceSummaryResponse,
)
from app.chat.service import execute_chat_message, owned_session, serialize_message
from app.config import get_settings
from app.database.models import AppUser, ChatMessage, ChatSession
from app.knowledge.service import owned_attachments, store_attachment
from app.database.session import get_db
from app.tracing.recorder import read_traces


router = APIRouter(prefix="/api", tags=["chat"])


def _json_load(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _trace_detail(request_id: str, events: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    ordered = sorted(events, key=lambda item: int(item.get("sequence") or 0))
    root = next((event for event in ordered if event.get("event_type") == "root"), ordered[0] if ordered else {})
    spans: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    tools: list[str] = []
    total_duration = 0
    for event in ordered:
        tool_name = event.get("tool_name")
        if tool_name and tool_name not in tools:
            tools.append(tool_name)
        if event.get("error"):
            errors.append({
                "sequence": event.get("sequence"),
                "span_name": event.get("span_name") or event.get("node_name"),
                "error": event.get("error"),
            })
        total_duration += int(event.get("duration_ms") or 0)
        spans.append({
            "sequence": event.get("sequence"),
            "span_id": event.get("span_id"),
            "parent_span_id": event.get("parent_span_id"),
            "event_type": event.get("event_type", "span"),
            "span_name": event.get("span_name") or event.get("node_name"),
            "node_name": event.get("node_name"),
            "tool_name": tool_name,
            "started_at": event.get("started_at"),
            "finished_at": event.get("finished_at"),
            "duration_ms": int(event.get("duration_ms") or 0),
            "success": event.get("success"),
            "error": event.get("error"),
            "input": event.get("input") or {
                "tool_arguments": event.get("tool_arguments", {}),
                "current_step": event.get("current_step", 0),
            },
            "output": event.get("output", event.get("tool_result_summary")),
            "model_info": event.get("model_info", {}),
            "route": event.get("route"),
            "route_confidence": event.get("route_confidence"),
        })
    model_info = root.get("model_info") or next((span.get("model_info") for span in spans if span.get("model_info")), {})
    return {
        "request_id": request_id,
        "summary": {
            "question": root.get("user_query") or next((e.get("user_query") for e in ordered if e.get("user_query")), ""),
            "thread_id": root.get("thread_id") or metadata.get("thread_id"),
            "status": root.get("status") or metadata.get("status"),
            "success": root.get("success"),
            "started_at": root.get("started_at"),
            "finished_at": root.get("finished_at"),
            "duration_ms": int(root.get("duration_ms") or total_duration),
            "span_count": len(spans),
            "tool_count": len(tools or metadata.get("tools", [])),
            "tools": tools or metadata.get("tools", []),
            "errors": errors,
            "model_info": model_info,
        },
        "spans": spans,
        "raw_events": ordered,
    }


@router.post("/chat/sessions", response_model=ChatSessionSummary, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: CreateChatSessionRequest,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ChatSession:
    now = utcnow()
    chat = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=payload.title.strip(),
        created_at=now,
        updated_at=now,
        last_message_at=None,
        is_archived=False,
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("/chat/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    user: AppUser = Depends(current_user), db: Session = Depends(get_db)
) -> list[ChatSession]:
    return list(db.scalars(
        select(ChatSession).where(
            ChatSession.user_id == user.id, ChatSession.is_archived.is_(False)
        ).order_by(ChatSession.last_message_at.desc(), ChatSession.created_at.desc())
    ))


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session(
    session_id: str,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat = owned_session(db, user, session_id)
    messages = list(db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == chat.id).order_by(ChatMessage.created_at)
    ))
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "last_message_at": chat.last_message_at,
        "messages": [serialize_message(message) for message in messages],
    }


@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_session(
    session_id: str,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    chat = owned_session(db, user, session_id)
    chat.is_archived = True
    chat.updated_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chat/sessions/{session_id}/messages", response_model=AgentMessageResponse)
async def send_message(
    session_id: str,
    payload: SendMessageRequest,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat = owned_session(db, user, session_id)
    attachments = owned_attachments(db, user, chat.id, payload.attachment_ids)
    assistant = await execute_chat_message(db, user, chat, payload.content, attachments)
    sources = _json_load(assistant.sources_json, [])
    metadata = _json_load(assistant.metadata_json, {})
    runtime = metadata.get("runtime_mode", {
        "llm": get_settings().llm_provider,
        "retrieval": get_settings().embedding_provider,
        "database": get_settings().database_provider,
    })
    return {
        "message_id": assistant.id,
        "session_id": chat.id,
        "request_id": assistant.request_id,
        "status": assistant.status,
        "answer": assistant.content,
        "sources": sources,
        "trace_summary": {"tools": metadata.get("tools", []), "steps": metadata.get("steps", 0)},
        "runtime_mode": runtime,
        "created_at": assistant.created_at,
    }


@router.post("/chat/sessions/{session_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_chat_attachment(
    session_id: str,
    file: UploadFile = File(...),
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat = owned_session(db, user, session_id)
    attachment = await store_attachment(db, user, chat, file)
    return {
        "id": attachment.id, "name": attachment.original_name, "size": attachment.size_bytes,
        "mime_type": attachment.mime_type, "status": attachment.status,
    }


@router.get("/traces", response_model=list[TraceSummaryResponse])
def list_own_traces(
    user: AppUser = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    rows = db.execute(
        select(ChatMessage, ChatSession)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(
            ChatSession.user_id == user.id,
            ChatMessage.role == "assistant",
            ChatMessage.request_id.is_not(None),
        )
        .order_by(ChatMessage.created_at.desc())
    ).all()
    results = []
    for message, _ in rows:
        events = read_traces(message.request_id or "")
        metadata = _json_load(message.metadata_json, {})
        root_duration = next((e.get("duration_ms") for e in events if e.get("event_type") == "root"), None)
        question = next((e.get("user_query", "") for e in events if e.get("user_query")), "")
        results.append({
            "request_id": message.request_id,
            "question": question,
            "created_at": message.created_at,
            "status": message.status,
            "tools": metadata.get("tools", []),
            "duration_ms": int(root_duration or sum(int(e.get("duration_ms", 0)) for e in events)),
            "success": message.status in {"completed", "completed_with_errors"},
        })
    return results


@router.get("/traces/{request_id}")
def get_own_trace(
    request_id: str,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    message = db.scalar(
        select(ChatMessage).join(ChatSession).where(
            ChatSession.user_id == user.id, ChatMessage.request_id == request_id
        )
    )
    if not message:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    events = read_traces(request_id)
    metadata = _json_load(message.metadata_json, {})
    metadata["status"] = message.status
    return _trace_detail(request_id, events, metadata)
