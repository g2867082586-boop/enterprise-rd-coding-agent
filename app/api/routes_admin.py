import json
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import admin_user
from app.agent.approval_workflow import resume_approval_checkpoint, start_approval_checkpoint
from app.auth.service import utcnow
from app.config import get_settings
from app.database.models import AppUser, ApprovalRequest
from app.database.session import get_db
from app.rag.indexer import SUPPORTED_SUFFIXES, build_index
from app.knowledge.service import enqueue_ingestion

router = APIRouter(prefix="/api", tags=["admin-workbench"])


class DecisionBody(BaseModel):
    reason: str = Field(default="", max_length=500)


def _serialize(row: ApprovalRequest) -> dict[str, object]:
    now = utcnow()
    if row.status == "pending" and row.expires_at <= now:
        row.status = "expired"
    return {
        "id": row.id, "thread_id": row.thread_id, "request_user_id": row.request_user_id,
        "operation": row.operation, "risk_level": row.risk_level, "status": row.status,
        "parameters": json.loads(row.parameters_json), "decided_by": row.decided_by,
        "decision_reason": row.decision_reason, "created_at": row.created_at,
        "expires_at": row.expires_at, "decided_at": row.decided_at,
        "completed_at": row.completed_at,
    }


def _approval(db: Session, approval_id: str) -> ApprovalRequest:
    row = db.get(ApprovalRequest, approval_id)
    if not row:
        raise HTTPException(404, "审批记录不存在")
    if row.status == "pending" and row.expires_at <= utcnow():
        row.status = "expired"
        db.commit()
    return row


@router.get("/approvals")
def list_approvals(_: AppUser = Depends(admin_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    rows = list(db.scalars(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())))
    result = [_serialize(row) for row in rows]
    db.commit()
    return result


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: str, _: AppUser = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, object]:
    return _serialize(_approval(db, approval_id))


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, body: DecisionBody, user: AppUser = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, object]:
    row = _approval(db, approval_id)
    if row.status == "approved":
        return _serialize(row)
    if row.status != "pending":
        raise HTTPException(409, f"当前状态 {row.status} 不可批准")
    row.status, row.decided_by, row.decision_reason, row.decided_at = "approved", user.id, body.reason, utcnow()
    db.commit()
    return _serialize(row)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, body: DecisionBody, user: AppUser = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, object]:
    row = _approval(db, approval_id)
    if row.status == "rejected":
        return _serialize(row)
    if row.status != "pending":
        raise HTTPException(409, f"当前状态 {row.status} 不可拒绝")
    row.status, row.decided_by, row.decision_reason, row.decided_at = "rejected", user.id, body.reason, utcnow()
    resume_approval_checkpoint(row.thread_id, approved=False)
    db.commit()
    return _serialize(row)


@router.post("/approvals/{approval_id}/resume")
def resume(approval_id: str, _: AppUser = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, object]:
    row = _approval(db, approval_id)
    if row.status == "completed":
        return _serialize(row)
    if row.status != "approved":
        raise HTTPException(409, "只有已批准且未过期的任务可恢复")
    parameters = json.loads(row.parameters_json)  # server-owned immutable parameters
    resumed_state = resume_approval_checkpoint(row.thread_id, approved=True)
    if resumed_state.get("approval_status") != "approved":
        raise HTTPException(409, "LangGraph 审批 Checkpoint 未恢复为批准状态")
    if row.operation == "rebuild_enterprise_knowledge":
        source = get_settings().project_path(parameters["source_dir"])
        report = build_index(source_dir=source)
        row.status, row.completed_at = "completed", utcnow()
    elif row.operation == "ingest_knowledge_document":
        report = enqueue_ingestion(parameters["job_id"])
        row.status = "completed" if report["mode"] in {"inline_fallback", "already_completed"} else "approved"
        row.completed_at = utcnow() if row.status == "completed" else None
    else:
        raise HTTPException(400, "未实现的受控操作")
    row.checkpoint_json = json.dumps(
        {**json.loads(row.checkpoint_json), "result": report}, ensure_ascii=False
    )
    db.commit()
    return _serialize(row) | {"result": report}


@router.get("/knowledge/documents")
def knowledge_documents(_: AppUser = Depends(admin_user)) -> dict[str, object]:
    settings = get_settings()
    index = settings.project_path(settings.knowledge_index_path)
    payload = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {"documents": []}
    unique = {row["document_id"]: {key: row.get(key) for key in ("document_id", "title", "document_type", "department", "version", "updated_at", "access_scope", "corpus_type", "embedding_model")} for row in payload.get("documents", [])}
    return {"retrieval_mode": payload.get("retrieval_mode", "not_built"), "embedding_model": payload.get("embedding_model"), "documents": list(unique.values())}


@router.post("/knowledge/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), _: AppUser = Depends(admin_user)) -> dict[str, object]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, "不支持的文档格式")
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    target_dir = get_settings().project_path(get_settings().enterprise_knowledge_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / safe_name).resolve()
    if target.parent != target_dir:
        raise HTTPException(400, "文件路径不安全")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件超过 10MB 限制")
    target.write_bytes(content)
    return {"document_id": target.stem, "stored_name": safe_name, "original_name": Path(file.filename or "").name, "indexed": False}


@router.post("/knowledge/rebuild", status_code=status.HTTP_202_ACCEPTED)
def request_rebuild(user: AppUser = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, object]:
    now, approval_id, thread_id = utcnow(), str(uuid.uuid4()), f"approval-{uuid.uuid4()}"
    settings = get_settings()
    parameters = {"source_dir": settings.enterprise_knowledge_dir}
    row = ApprovalRequest(
        id=approval_id, thread_id=thread_id, request_user_id=user.id,
        operation="rebuild_enterprise_knowledge", risk_level="high", status="pending",
        parameters_json=json.dumps(parameters),
        checkpoint_json=json.dumps({"thread_id": thread_id, "approval_status": "pending", "operation": "rebuild_enterprise_knowledge"}),
        created_at=now, expires_at=now + timedelta(hours=24),
    )
    db.add(row); db.commit()
    start_approval_checkpoint(approval_id, thread_id, row.operation, parameters)
    return _serialize(row)
