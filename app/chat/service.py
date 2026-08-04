import json
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import run_agent
from app.auth.service import utcnow
from app.config import get_settings
from app.database.models import AppUser, ChatAttachment, ChatMessage, ChatSession
from app.knowledge.service import is_ingestion_command, submit_ingestion_requests
from app.tracing.recorder import read_traces
from app.infrastructure.redis_client import acquire_lock, distributed_rate_limit, release_lock


_rate_lock = threading.Lock()
_recent_requests: dict[str, deque[float]] = defaultdict(deque)
_running_users: set[str] = set()


def _json_load(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def serialize_message(message: ChatMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "request_id": message.request_id,
        "sources": _json_load(message.sources_json, []),
        "metadata": _json_load(message.metadata_json, {}),
        "created_at": message.created_at,
    }


def owned_session(db: Session, user: AppUser, session_id: str, include_archived: bool = False) -> ChatSession:
    clauses = [ChatSession.id == session_id, ChatSession.user_id == user.id]
    if not include_archived:
        clauses.append(ChatSession.is_archived.is_(False))
    chat = db.scalar(select(ChatSession).where(*clauses))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return chat


def check_chat_limits(user_id: str) -> None:
    settings = get_settings()
    distributed = distributed_rate_limit(f"chat:{user_id}", settings.chat_rate_limit_per_minute)
    if distributed is False:
        raise HTTPException(status_code=429, detail="提问过于频繁，请稍后再试")
    lock = acquire_lock(f"chat:{user_id}", settings.agent_request_timeout_seconds)
    if lock is False:
        raise HTTPException(status_code=409, detail="已有问题正在处理中，请等待完成")
    if distributed is True and lock is True:
        return
    now = time.monotonic()
    with _rate_lock:
        requests = _recent_requests[user_id]
        while requests and now - requests[0] >= 60:
            requests.popleft()
        if len(requests) >= settings.chat_rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="提问过于频繁，请稍后再试")
        if user_id in _running_users:
            raise HTTPException(status_code=409, detail="已有问题正在处理中，请等待完成")
        requests.append(now)
        _running_users.add(user_id)


def release_chat_limit(user_id: str) -> None:
    release_lock(f"chat:{user_id}")
    with _rate_lock:
        _running_users.discard(user_id)


async def execute_chat_message(
    db: Session,
    user: AppUser,
    chat: ChatSession,
    content: str,
    attachments: list[ChatAttachment] | None = None,
) -> ChatMessage:
    attachments = attachments or []
    check_chat_limits(user.id)
    now = utcnow()
    user_message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=chat.id,
        role="user",
        content=content.strip(),
        status="completed",
        request_id=None,
        sources_json="[]",
        metadata_json=json.dumps({
            "attachments": [
                {"id": item.id, "name": item.original_name, "size": item.size_bytes}
                for item in attachments
            ]
        }, ensure_ascii=False),
        created_at=now,
    )
    db.add(user_message)
    db.flush()
    for attachment in attachments:
        attachment.message_id = user_message.id
    chat.last_message_at = now
    chat.updated_at = now
    if chat.title == "新对话":
        chat.title = content.strip()[:50]
    db.commit()
    try:
        if is_ingestion_command(content) and attachments:
            submissions = submit_ingestion_requests(db, user, attachments)
            pending = [item for item in submissions if not item.get("duplicate")]
            duplicates = [item for item in submissions if item.get("duplicate")]
            lines = []
            if pending:
                lines.append(
                    f"已提交 {len(pending)} 个知识库导入申请。管理员批准后会在后台执行解析、分块、"
                    "中文语义向量和词法索引构建。"
                )
            if duplicates:
                lines.append(f"{len(duplicates)} 个附件内容已存在，未重复导入。")
            assistant = ChatMessage(
                id=str(uuid.uuid4()), session_id=chat.id, role="assistant",
                content="\n\n".join(lines) or "附件已经处理。",
                status="pending_approval" if pending else "completed", request_id=None,
                sources_json="[]", metadata_json=json.dumps({
                    "knowledge_submissions": submissions,
                    "runtime_mode": {
                        "llm": "deterministic_command", "retrieval": get_settings().embedding_provider,
                        "database": get_settings().database_provider, "corpus": get_settings().knowledge_corpus,
                    },
                }, ensure_ascii=False), created_at=utcnow(),
            )
        elif attachments:
            assistant = ChatMessage(
                id=str(uuid.uuid4()), session_id=chat.id, role="assistant",
                content="附件已安全上传。若要正式导入，请在消息中明确输入“添加进知识库”。",
                status="needs_instruction", request_id=None, sources_json="[]",
                metadata_json=json.dumps({"attachments": [item.id for item in attachments]}),
                created_at=utcnow(),
            )
        else:
            state = await run_agent(content.strip(), session_id=chat.id, user_id=user.id, user_role=user.role)
            sources = [
                {
                    "title": doc.get("title", "知识库文档"),
                    "source": doc.get("source", ""),
                    "snippet": doc.get("snippet", "")[:600],
                    "score": doc.get("relevance", 0),
                }
                for doc in state.get("retrieved_documents", [])
            ]
            traces = read_traces(state["request_id"])
            tools = list(dict.fromkeys(
                item.get("tool", "") for item in state.get("tool_results", []) if item.get("tool")
            ))
            metadata = {
                "tools": tools,
                "steps": len(traces),
                "thread_id": state["thread_id"],
                "runtime_mode": {
                    "llm": state.get("provider_mode", get_settings().llm_provider),
                    "retrieval": (state.get("retrieved_documents") or [{}])[0].get("retrieval_mode", get_settings().embedding_provider),
                    "database": get_settings().database_provider,
                    "corpus": get_settings().knowledge_corpus,
                },
                "route": state.get("route"), "route_confidence": state.get("route_confidence"),
                "route_reason": state.get("route_reason"), "plan": state.get("plan", []),
                "fallback_reason": state.get("fallback_reason"), "evidence_status": state.get("evidence_status"),
            }
            assistant = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=chat.id,
                role="assistant",
                content=state.get("final_answer") or "未生成回答",
                status=state.get("status", "completed"),
                request_id=state["request_id"],
                sources_json=json.dumps(sources, ensure_ascii=False),
                metadata_json=json.dumps(metadata, ensure_ascii=False),
                created_at=utcnow(),
            )
    except Exception:
        assistant = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=chat.id,
            role="assistant",
            content="Agent 执行失败，请稍后重试。",
            status="failed",
            request_id=None,
            sources_json="[]",
            metadata_json="{}",
            created_at=utcnow(),
        )
    finally:
        release_chat_limit(user.id)
    db.add(assistant)
    chat.last_message_at = assistant.created_at
    chat.updated_at = assistant.created_at
    db.commit()
    db.refresh(assistant)
    return assistant
