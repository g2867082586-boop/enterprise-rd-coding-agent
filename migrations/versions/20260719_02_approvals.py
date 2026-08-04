"""add durable approval requests

Revision ID: 20260719_02
Revises: 20260718_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260719_02"
down_revision = "20260718_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("request_user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("checkpoint_json", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decision_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    for column in ("thread_id", "request_user_id", "operation", "status", "created_at", "expires_at"):
        op.create_index(f"ix_approval_requests_{column}", "approval_requests", [column])


def downgrade() -> None:
    op.drop_table("approval_requests")
