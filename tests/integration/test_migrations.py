from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import ROOT_DIR, get_settings


def test_alembic_upgrade_and_downgrade_sqlite(tmp_path, monkeypatch) -> None:
    database = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(database))
    get_settings.cache_clear()
    config = Config(str(ROOT_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())
    assert {"app_users", "user_sessions", "chat_sessions", "chat_messages", "alembic_version"}.issubset(tables)
    assert {
        "chat_attachments", "knowledge_documents", "knowledge_document_versions",
        "knowledge_ingestion_jobs", "knowledge_index_versions", "agent_actions",
        "order_audit_logs", "outbox_events",
    }.issubset(tables)
    command.downgrade(config, "base")
    remaining = set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())
    assert not {"app_users", "user_sessions", "chat_sessions", "chat_messages"} & remaining
