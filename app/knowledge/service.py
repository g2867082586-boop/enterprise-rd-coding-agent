import hashlib
import json
import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.approval_workflow import start_approval_checkpoint
from app.auth.service import utcnow
from app.config import ROOT_DIR, get_settings
from app.database.models import (
    ApprovalRequest,
    AppUser,
    ChatAttachment,
    ChatSession,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
    KnowledgeIndexVersion,
)
from app.database.session import create_app_session
from app.infrastructure.redis_client import publish_event
from app.jobs.queue import enqueue
from app.rag.indexer import SUPPORTED_SUFFIXES, build_index


MIME_BY_SUFFIX = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".json": {"application/json", "text/json", "text/plain", "application/octet-stream"},
    ".csv": {"text/csv", "application/csv", "text/plain", "application/octet-stream"},
}


def _signature_ok(suffix: str, content: bytes) -> bool:
    if suffix == ".pdf":
        return content.startswith(b"%PDF-")
    if suffix == ".docx":
        return content.startswith(b"PK\x03\x04")
    if b"\x00" in content[:4096]:
        return False
    return True


async def store_attachment(
    db: Session,
    user: AppUser,
    chat: ChatSession,
    file: UploadFile,
) -> ChatAttachment:
    settings = get_settings()
    original = Path(file.filename or "attachment").name
    suffix = Path(original).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, "不支持的文档格式")
    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(400, "文件为空")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, f"文件超过 {settings.max_upload_bytes // 1024 // 1024}MB 限制")
    mime = (file.content_type or "application/octet-stream").lower()
    if mime not in MIME_BY_SUFFIX.get(suffix, set()) or not _signature_ok(suffix, content):
        raise HTTPException(400, "文件类型与内容不匹配")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(ChatAttachment).where(
            ChatAttachment.user_id == user.id,
            ChatAttachment.sha256 == digest,
            ChatAttachment.status.in_(["uploaded", "submitted", "published"]),
        )
    )
    if existing:
        existing.session_id = chat.id
        db.commit()
        return existing
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    upload_root = settings.project_path(settings.upload_dir).resolve()
    quarantine = (upload_root / "quarantine").resolve()
    quarantine.mkdir(parents=True, exist_ok=True)
    target = (quarantine / stored_name).resolve()
    if target.parent != quarantine:
        raise HTTPException(400, "文件路径不安全")
    target.write_bytes(content)
    attachment = ChatAttachment(
        id=str(uuid.uuid4()), user_id=user.id, session_id=chat.id, message_id=None,
        original_name=original, stored_name=stored_name, storage_path=str(target),
        mime_type=mime, extension=suffix, size_bytes=len(content), sha256=digest,
        status="uploaded", created_at=utcnow(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def owned_attachments(
    db: Session, user: AppUser, session_id: str, attachment_ids: list[str]
) -> list[ChatAttachment]:
    if not attachment_ids:
        return []
    rows = list(db.scalars(
        select(ChatAttachment).where(
            ChatAttachment.id.in_(attachment_ids),
            ChatAttachment.user_id == user.id,
            ChatAttachment.session_id == session_id,
        )
    ))
    if len(rows) != len(set(attachment_ids)):
        raise HTTPException(404, "附件不存在或不属于当前会话")
    return rows


def is_ingestion_command(content: str) -> bool:
    normalized = "".join(content.lower().split())
    return any(command in normalized for command in ("添加进知识库", "加入知识库", "导入知识库"))


def submit_ingestion_requests(
    db: Session,
    user: AppUser,
    attachments: list[ChatAttachment],
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = metadata or {}
    results = []
    for attachment in attachments:
        existing_version = db.scalar(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.content_hash == attachment.sha256,
                KnowledgeDocumentVersion.status.in_(["pending_approval", "queued", "published"]),
            )
        )
        if existing_version:
            results.append({
                "attachment_id": attachment.id, "duplicate": True,
                "document_id": existing_version.document_id, "version_id": existing_version.id,
            })
            continue
        title = str(metadata.get("title") or Path(attachment.original_name).stem)[:255]
        document = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.title == title,
                KnowledgeDocument.department == str(metadata.get("department", "通用"))[:100],
            )
        )
        now = utcnow()
        if not document:
            document = KnowledgeDocument(
                id=str(uuid.uuid4()), title=title,
                department=str(metadata.get("department", "通用"))[:100],
                access_scope=str(metadata.get("access_scope", "authenticated"))[:30],
                tags_json=json.dumps(metadata.get("tags", []), ensure_ascii=False),
                status="pending_approval", active_version_id=None, created_by=user.id,
                created_at=now, updated_at=now,
            )
            db.add(document)
            db.flush()
        version_number = int(db.scalar(
            select(func.max(KnowledgeDocumentVersion.version_number)).where(
                KnowledgeDocumentVersion.document_id == document.id
            )
        ) or 0) + 1
        version = KnowledgeDocumentVersion(
            id=str(uuid.uuid4()), document_id=document.id, attachment_id=attachment.id,
            version_number=version_number, source_path=attachment.storage_path,
            content_hash=attachment.sha256, status="pending_approval", chunk_count=0,
            error_message=None, created_by=user.id, created_at=now, published_at=None,
        )
        job = KnowledgeIngestionJob(
            id=str(uuid.uuid4()), document_id=document.id, version_id=version.id,
            requested_by=user.id, status="pending_approval", progress=0, stage="pending_approval",
            attempts=0, error_message=None, result_json="{}", created_at=now,
            started_at=None, completed_at=None,
        )
        approval_id, thread_id = str(uuid.uuid4()), f"knowledge-{uuid.uuid4()}"
        parameters = {"job_id": job.id, "version_id": version.id, "document_id": document.id}
        approval = ApprovalRequest(
            id=approval_id, thread_id=thread_id, request_user_id=user.id,
            operation="ingest_knowledge_document", risk_level="medium", status="pending",
            parameters_json=json.dumps(parameters), checkpoint_json=json.dumps({
                "thread_id": thread_id, "approval_status": "pending",
                "operation": "ingest_knowledge_document",
            }),
            created_at=now, expires_at=now + timedelta(hours=24),
        )
        attachment.status = "submitted"
        db.add_all([version, job, approval])
        db.commit()
        start_approval_checkpoint(approval_id, thread_id, approval.operation, parameters)
        results.append({
            "attachment_id": attachment.id, "duplicate": False, "document_id": document.id,
            "version_id": version.id, "job_id": job.id, "approval_id": approval.id,
            "status": "pending_approval",
        })
    return results


def _job_update(db: Session, job: KnowledgeIngestionJob, stage: str, progress: int) -> None:
    job.stage, job.status, job.progress = stage, "running", progress
    db.commit()
    publish_event(f"knowledge-job:{job.id}", {"stage": stage, "progress": progress})


def process_ingestion_job(job_id: str) -> dict[str, Any]:
    db = create_app_session()
    try:
        job = db.get(KnowledgeIngestionJob, job_id)
        if not job:
            raise ValueError("知识库任务不存在")
        if job.status == "completed":
            return json.loads(job.result_json)
        version = db.get(KnowledgeDocumentVersion, job.version_id)
        document = db.get(KnowledgeDocument, job.document_id)
        attachment = db.get(ChatAttachment, version.attachment_id if version else "")
        if not version or not document or not attachment:
            raise ValueError("知识库任务关联数据不完整")
        job.started_at, job.attempts = utcnow(), job.attempts + 1
        _job_update(db, job, "parsing", 15)
        source = Path(attachment.storage_path).resolve()
        if not source.exists():
            raise ValueError("上传文件不存在")
        target_root = get_settings().project_path(get_settings().enterprise_knowledge_dir).resolve()
        target_root.mkdir(parents=True, exist_ok=True)
        target = (target_root / f"{document.id}-v{version.version_number}{attachment.extension}").resolve()
        if target.parent != target_root:
            raise ValueError("知识库目标路径不安全")
        shutil.copy2(source, target)
        sidecar = target.with_suffix(target.suffix + ".metadata.json")
        sidecar.write_text(json.dumps({
            "document_id": document.id, "title": document.title, "department": document.department,
            "version": str(version.version_number), "access_scope": document.access_scope,
            "is_active": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        for other in db.scalars(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.document_id == document.id,
                KnowledgeDocumentVersion.id != version.id,
            )
        ):
            old_path = Path(other.source_path)
            old_sidecar = old_path.with_suffix(old_path.suffix + ".metadata.json")
            if old_sidecar.exists():
                old_metadata = json.loads(old_sidecar.read_text(encoding="utf-8"))
                old_metadata["is_active"] = False
                old_sidecar.write_text(json.dumps(old_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            if other.status == "published":
                other.status = "superseded"
        version.source_path = str(target)
        _job_update(db, job, "chunking_embedding", 45)
        report = build_index()
        _job_update(db, job, "publishing", 85)
        version.status, version.published_at = "published", utcnow()
        version.chunk_count = int(report.get("document_chunk_counts", {}).get(document.id, 0))
        document.active_version_id = version.id
        document.status, document.updated_at = "published", utcnow()
        attachment.status = "published"
        job.status, job.stage, job.progress = "completed", "completed", 100
        job.completed_at = utcnow()
        job.result_json = json.dumps(report, ensure_ascii=False, default=str)
        artifact = report.get("version_artifact")
        if artifact:
            index_version = KnowledgeIndexVersion(
                id=str(report["index_version_id"]), artifact_path=str(artifact),
                retrieval_mode=str(report["mode"]), embedding_model=str(report["embedding_model"]),
                chunk_count=int(report["document_count"]), checksum=str(report["checksum"]),
                status="active", created_by=job.requested_by, created_at=utcnow(), activated_at=utcnow(),
            )
            for active in db.scalars(
                select(KnowledgeIndexVersion).where(KnowledgeIndexVersion.status == "active")
            ):
                active.status = "superseded"
            db.add(index_version)
        db.commit()
        publish_event(f"knowledge-job:{job.id}", {"stage": "completed", "progress": 100})
        return report
    except Exception as exc:
        job = db.get(KnowledgeIngestionJob, job_id)
        if job:
            job.status, job.stage = "failed", "failed"
            job.error_message, job.completed_at = str(exc)[:500], utcnow()
            version = db.get(KnowledgeDocumentVersion, job.version_id)
            if version:
                version.status, version.error_message = "failed", str(exc)[:500]
            db.commit()
            publish_event(f"knowledge-job:{job.id}", {
                "stage": "failed", "progress": job.progress, "error": str(exc)[:300],
            })
        raise
    finally:
        db.close()


def enqueue_ingestion(job_id: str) -> dict[str, str]:
    db = create_app_session()
    try:
        job = db.get(KnowledgeIngestionJob, job_id)
        if not job:
            raise ValueError("知识库任务不存在")
        if job.status == "completed":
            return {"mode": "already_completed", "job_id": job_id}
        job.status, job.stage = "queued", "queued"
        version = db.get(KnowledgeDocumentVersion, job.version_id)
        if version:
            version.status = "queued"
        db.commit()
    finally:
        db.close()
    return enqueue(process_ingestion_job, job_id, job_id=job_id)
