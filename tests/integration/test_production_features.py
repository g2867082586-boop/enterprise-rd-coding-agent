from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.database.models import (
    AgentAction,
    AppUser,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
    OrderAuditLog,
    OutboxEvent,
)
from app.database.session import create_app_session
from app.main import app


def register_and_login(client: TestClient, username: str) -> None:
    response = client.post("/api/auth/register", json={
        "username": username, "email": f"{username}@example.test",
        "password": "Example123", "display_name": username,
    })
    assert response.status_code == 201
    assert client.post("/api/auth/login", json={
        "username": username, "password": "Example123",
    }).status_code == 200


def promote(username: str, role: str) -> None:
    db = create_app_session()
    try:
        user = db.scalar(select(AppUser).where(AppUser.username == username))
        assert user
        user.role = role
        db.commit()
    finally:
        db.close()


def test_order_query_action_confirmation_idempotency_and_audit(seeded_database) -> None:
    with TestClient(app) as client:
        register_and_login(client, "operator")
        assert client.get("/api/orders?status=FAILED&page_size=2").status_code == 200
        denied = client.post("/api/order-actions", json={
            "action_type": "add_order_note",
            "parameters": {"order_no": "NS00000001", "note": "checked", "expected_version": 1},
            "idempotency_key": "order-note-denied",
        })
        assert denied.status_code == 403

        promote("operator", "order_operator")
        prepared = client.post("/api/order-actions", json={
            "action_type": "add_order_note",
            "parameters": {"order_no": "NS00000001", "note": "checked", "expected_version": 1},
            "idempotency_key": "order-note-0001",
        })
        assert prepared.status_code == 202, prepared.text
        action = prepared.json()
        confirmed = client.post(
            f"/api/order-actions/{action['id']}/confirm",
            headers={"Idempotency-Key": "order-note-0001"},
        )
        assert confirmed.status_code == 200, confirmed.text
        duplicate = client.post(
            f"/api/order-actions/{action['id']}/confirm",
            headers={"Idempotency-Key": "order-note-0001"},
        )
        assert duplicate.status_code == 200
        order = client.get("/api/orders/NS00000001").json()
        assert order["note"] == "checked"
        assert order["version"] == 2

        db = create_app_session()
        try:
            assert db.scalar(select(AgentAction).where(AgentAction.id == action["id"])).status == "completed"
            assert db.scalar(select(OrderAuditLog).where(OrderAuditLog.order_no == "NS00000001"))
            assert db.scalar(select(OutboxEvent).where(OutboxEvent.aggregate_id == "NS00000001"))
        finally:
            db.close()


def test_chat_attachment_submits_approval_and_publishes_versioned_index(
    tmp_path: Path,
) -> None:
    settings = get_settings()
    settings.upload_dir = str(tmp_path / "uploads")
    settings.enterprise_knowledge_dir = str(tmp_path / "enterprise")
    settings.knowledge_index_path = str(tmp_path / "index.json")
    settings.knowledge_index_versions_dir = str(tmp_path / "versions")
    settings.knowledge_catalog_path = str(tmp_path / "catalog.json")
    settings.embedding_provider = "lexical"
    settings.knowledge_corpus = "enterprise"
    with TestClient(app) as client:
        register_and_login(client, "knowledge_submitter")
        session_id = client.post("/api/chat/sessions", json={"title": "新对话"}).json()["id"]
        uploaded = client.post(
            f"/api/chat/sessions/{session_id}/attachments",
            files={"file": ("policy.md", b"# Refund Policy\nRefunds require approval.", "text/markdown")},
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment_id = uploaded.json()["id"]
        submitted = client.post(f"/api/chat/sessions/{session_id}/messages", json={
            "content": "请把这个文件添加进知识库",
            "attachment_ids": [attachment_id],
        })
        assert submitted.status_code == 200, submitted.text
        detail = client.get(f"/api/chat/sessions/{session_id}").json()
        submission = detail["messages"][-1]["metadata"]["knowledge_submissions"][0]
        assert submission["status"] == "pending_approval"

        promote("knowledge_submitter", "admin")
        approval_id = submission["approval_id"]
        assert client.post(f"/api/approvals/{approval_id}/approve", json={"reason": "reviewed"}).status_code == 200
        resumed = client.post(f"/api/approvals/{approval_id}/resume")
        assert resumed.status_code == 200, resumed.text
        job = client.get(f"/api/knowledge/jobs/{submission['job_id']}").json()
        if job["status"] == "queued":
            # A production Redis queue intentionally needs a separate worker. Execute the
            # worker function here so the integration test remains deterministic when a
            # developer already has Redis running.
            from app.knowledge.service import process_ingestion_job

            process_ingestion_job(submission["job_id"])
            job = client.get(f"/api/knowledge/jobs/{submission['job_id']}").json()
        assert job["status"] == "completed"
        assert Path(settings.knowledge_index_path).exists()
        assert list(Path(settings.knowledge_index_versions_dir).glob("*.json"))

        db = create_app_session()
        try:
            document = db.get(KnowledgeDocument, submission["document_id"])
            ingestion = db.get(KnowledgeIngestionJob, submission["job_id"])
            assert document and document.status == "published" and document.active_version_id
            assert ingestion and ingestion.progress == 100
            assert db.get(KnowledgeDocumentVersion, document.active_version_id).chunk_count > 0
        finally:
            db.close()
