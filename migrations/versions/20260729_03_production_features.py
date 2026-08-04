"""add production order, attachment and knowledge workflow tables

Revision ID: 20260729_03
Revises: 20260719_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20260729_03"
down_revision = "20260719_02"
branch_labels = None
depends_on = None


def _index(table: str, column: str) -> None:
    op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "chat_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE")),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("chat_messages.id", ondelete="SET NULL")),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(100), nullable=False, unique=True),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("extension", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("user_id", "session_id", "message_id", "sha256", "status", "created_at"):
        _index("chat_attachments", column)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("access_scope", sa.String(30), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("active_version_id", sa.String(36)),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("title", "department", "access_scope", "status", "created_by", "updated_at"):
        _index("knowledge_documents", column)

    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.String(36), sa.ForeignKey("chat_attachments.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime()),
        sa.UniqueConstraint("document_id", "version_number", name="uq_knowledge_document_version"),
    )
    for column in ("document_id", "content_hash", "status"):
        _index("knowledge_document_versions", column)

    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_document_versions.id"), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(500)),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    )
    for column in ("document_id", "version_id", "requested_by", "status", "created_at"):
        _index("knowledge_ingestion_jobs", column)

    op.create_table(
        "knowledge_index_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_path", sa.String(500), nullable=False, unique=True),
        sa.Column("retrieval_mode", sa.String(60), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("activated_at", sa.DateTime()),
    )
    _index("knowledge_index_versions", "status")

    op.create_table(
        "agent_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("session_id", sa.String(36)),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("parameter_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )
    for column in ("request_user_id", "session_id", "action_type", "risk_level", "status", "idempotency_key", "created_at", "expires_at"):
        _index("agent_actions", column)

    op.create_table(
        "order_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_no", sa.String(32), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("after_json", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("order_no", "action_type", "actor_user_id", "request_id", "created_at"):
        _index("order_audit_logs", column)

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime()),
    )
    for column in ("aggregate_type", "aggregate_id", "event_type", "created_at", "published_at"):
        _index("outbox_events", column)

    inspector = sa.inspect(op.get_bind())
    if "orders" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("orders")}
        with op.batch_alter_table("orders") as batch:
            if "version" not in existing:
                batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
            if "note" not in existing:
                batch.add_column(sa.Column("note", sa.Text()))
            if "cancel_reason" not in existing:
                batch.add_column(sa.Column("cancel_reason", sa.String(500)))
            if "created_by" not in existing:
                batch.add_column(sa.Column("created_by", sa.String(36)))
            if "updated_by" not in existing:
                batch.add_column(sa.Column("updated_by", sa.String(36)))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "orders" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("orders")}
        with op.batch_alter_table("orders") as batch:
            for column in ("updated_by", "created_by", "cancel_reason", "note", "version"):
                if column in existing:
                    batch.drop_column(column)
    for table in (
        "outbox_events", "order_audit_logs", "agent_actions", "knowledge_index_versions",
        "knowledge_ingestion_jobs", "knowledge_document_versions", "knowledge_documents",
        "chat_attachments",
    ):
        op.drop_table(table)
