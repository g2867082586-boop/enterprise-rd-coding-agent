import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import admin_user, current_user
from app.auth.service import utcnow
from app.database.models import (
    AppUser,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
)
from app.database.session import get_db
from app.jobs.queue import enqueue
from app.rag.indexer import build_index


router = APIRouter(prefix="/api/knowledge", tags=["knowledge-lifecycle"])


def _enqueue_index_rebuild() -> dict[str, str]:
    return enqueue(build_index, job_id=f"index-rebuild-{uuid.uuid4()}")


def _owned_job(db: Session, user: AppUser, job_id: str) -> KnowledgeIngestionJob:
    job = db.get(KnowledgeIngestionJob, job_id)
    if not job or (job.requested_by != user.id and user.role != "admin"):
        raise HTTPException(404, "知识库任务不存在")
    return job


def _job_payload(job: KnowledgeIngestionJob) -> dict[str, object]:
    return {
        "id": job.id, "document_id": job.document_id, "version_id": job.version_id,
        "status": job.status, "stage": job.stage, "progress": job.progress,
        "attempts": job.attempts, "error": job.error_message,
        "result": json.loads(job.result_json or "{}"), "created_at": job.created_at,
        "started_at": job.started_at, "completed_at": job.completed_at,
    }


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str, user: AppUser = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    return _job_payload(_owned_job(db, user, job_id))


async def _job_stream(db_factory: object, user_id: str, role: str, job_id: str) -> AsyncIterator[str]:
    from app.database.session import create_app_session

    previous = None
    while True:
        db = create_app_session()
        try:
            job = db.get(KnowledgeIngestionJob, job_id)
            if not job or (job.requested_by != user_id and role != "admin"):
                yield "event: error\ndata: {\"detail\":\"任务不存在\"}\n\n"
                return
            payload = _job_payload(job)
            serialized = json.dumps(payload, ensure_ascii=False, default=str)
            if serialized != previous:
                yield f"event: progress\ndata: {serialized}\n\n"
                previous = serialized
            if job.status in {"completed", "failed", "cancelled"}:
                return
        finally:
            db.close()
        await asyncio.sleep(1)


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: str, user: AppUser = Depends(current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    _owned_job(db, user, job_id)
    return StreamingResponse(
        _job_stream(None, user.id, user.role, job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/managed-documents")
def managed_documents(
    _: AppUser = Depends(admin_user), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    documents = list(db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())))
    result = []
    for row in documents:
        versions = list(db.scalars(
            select(KnowledgeDocumentVersion)
            .where(KnowledgeDocumentVersion.document_id == row.id)
            .order_by(KnowledgeDocumentVersion.version_number.desc())
        ))
        result.append({
            "id": row.id, "title": row.title, "department": row.department,
            "access_scope": row.access_scope, "tags": json.loads(row.tags_json),
            "status": row.status, "active_version_id": row.active_version_id,
            "created_at": row.created_at, "updated_at": row.updated_at,
            "versions": [{
                "id": version.id, "version": version.version_number, "status": version.status,
                "chunk_count": version.chunk_count, "created_at": version.created_at,
                "published_at": version.published_at,
            } for version in versions],
        })
    return result


@router.post("/managed-documents/{document_id}/deactivate")
def deactivate_document(
    document_id: str,
    _: AppUser = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(404, "知识文档不存在")
    document.status = "inactive"
    document.updated_at = utcnow()
    versions = list(db.scalars(
        select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.document_id == document.id)
    ))
    for version in versions:
        path = Path(version.source_path)
        sidecar = path.with_suffix(path.suffix + ".metadata.json")
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["is_active"] = False
            sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    db.commit()
    queued = _enqueue_index_rebuild()
    return {
        "id": document.id, "status": document.status,
        "rebuild_required": queued["mode"] != "inline_fallback", "rebuild_job": queued,
    }


@router.post("/managed-documents/{document_id}/rollback/{version_id}")
def rollback_document(
    document_id: str,
    version_id: str,
    _: AppUser = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    document = db.get(KnowledgeDocument, document_id)
    version = db.get(KnowledgeDocumentVersion, version_id)
    if not document or not version or version.document_id != document.id:
        raise HTTPException(404, "文档版本不存在")
    versions = list(db.scalars(
        select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.document_id == document.id)
    ))
    for item in versions:
        path = Path(item.source_path)
        sidecar = path.with_suffix(path.suffix + ".metadata.json")
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["is_active"] = item.id == version.id
            sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if item.id != version.id and item.status == "published":
            item.status = "superseded"
    version.status = "published"
    document.active_version_id, document.status = version.id, "published"
    db.commit()
    queued = _enqueue_index_rebuild()
    return {
        "id": document.id, "active_version_id": version.id,
        "rebuild_required": queued["mode"] != "inline_fallback", "rebuild_job": queued,
    }
