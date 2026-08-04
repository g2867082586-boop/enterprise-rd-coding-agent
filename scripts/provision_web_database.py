"""Run web migrations and provision the least-privilege MySQL application account."""

import re
import subprocess
import sys

import pymysql

from app.config import ROOT_DIR, get_settings


WEB_TABLES = ("app_users", "user_sessions", "chat_sessions", "chat_messages", "approval_requests")
PRODUCTION_APP_TABLES = (
    "chat_attachments", "knowledge_documents", "knowledge_document_versions",
    "knowledge_ingestion_jobs", "knowledge_index_versions", "agent_actions",
)
ORDER_READ_TABLES = ("users", "orders")
ORDER_WRITE_TABLES = ("orders", "order_audit_logs", "outbox_events")


def provision() -> dict[str, object]:
    settings = get_settings()
    if settings.database_provider == "sqlite":
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT_DIR, check=True)
        return {"provider": "sqlite", "migrated": True}
    identifier = re.compile(r"^[A-Za-z0-9_]+$")
    if not identifier.fullmatch(settings.mysql_app_user) or not settings.mysql_app_password:
        raise RuntimeError("MYSQL_APP_USER and MYSQL_APP_PASSWORD must be set in local .env")
    order_password = settings.mysql_order_password or (
        settings.mysql_app_password if settings.app_env != "production" else ""
    )
    if not identifier.fullmatch(settings.mysql_order_user) or not order_password:
        raise RuntimeError("MYSQL_ORDER_USER and MYSQL_ORDER_PASSWORD must be set in local .env")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT_DIR, check=True)
    connection = pymysql.connect(
        host=settings.mysql_host, port=settings.mysql_port, user=settings.mysql_admin_user,
        password=settings.mysql_admin_password, database=settings.mysql_database,
        charset="utf8mb4", autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{settings.mysql_app_user}'@'%%' IDENTIFIED BY %s",
                (settings.mysql_app_password,),
            )
            cursor.execute(
                f"ALTER USER '{settings.mysql_app_user}'@'%%' IDENTIFIED BY %s",
                (settings.mysql_app_password,),
            )
            cursor.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{settings.mysql_app_user}'@'%'")
            for table in (*WEB_TABLES, *PRODUCTION_APP_TABLES):
                cursor.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{settings.mysql_database}`.`{table}` "
                    f"TO '{settings.mysql_app_user}'@'%'"
                )
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{settings.mysql_order_user}'@'%%' IDENTIFIED BY %s",
                (order_password,),
            )
            cursor.execute(
                f"ALTER USER '{settings.mysql_order_user}'@'%%' IDENTIFIED BY %s",
                (order_password,),
            )
            cursor.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{settings.mysql_order_user}'@'%'")
            for table in ORDER_READ_TABLES:
                cursor.execute(
                    f"GRANT SELECT ON `{settings.mysql_database}`.`{table}` "
                    f"TO '{settings.mysql_order_user}'@'%'"
                )
            for table in ORDER_WRITE_TABLES:
                cursor.execute(
                    f"GRANT SELECT, INSERT, UPDATE ON `{settings.mysql_database}`.`{table}` "
                    f"TO '{settings.mysql_order_user}'@'%'"
                )
        connection.commit()
    finally:
        connection.close()
    return {
        "provider": "mysql", "migrated": True,
        "application_account": settings.mysql_app_user,
        "order_account": settings.mysql_order_user,
        "privileges": "web DML and separately restricted order-domain DML",
    }


if __name__ == "__main__":
    print(provision())
