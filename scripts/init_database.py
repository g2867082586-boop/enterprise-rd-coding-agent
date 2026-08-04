from datetime import UTC, datetime, timedelta
import re

import pymysql
from sqlalchemy import text

from app.config import get_settings
from app.database.connection import get_engine


SCHEMA = [
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL, email VARCHAR(255) NOT NULL, status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL, last_login_at DATETIME)",
    "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, order_no VARCHAR(32) UNIQUE NOT NULL, amount NUMERIC(12,2) NOT NULL, status VARCHAR(20) NOT NULL, error_code VARCHAR(32), created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, version INTEGER NOT NULL DEFAULT 1, note TEXT, cancel_reason VARCHAR(500), created_by VARCHAR(36), updated_by VARCHAR(36))",
    "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at)",
    "CREATE TABLE IF NOT EXISTS test_runs (id INTEGER PRIMARY KEY, request_id VARCHAR(64) NOT NULL, test_target VARCHAR(255) NOT NULL, total_count INTEGER NOT NULL, passed_count INTEGER NOT NULL, failed_count INTEGER NOT NULL, output TEXT, created_at DATETIME NOT NULL)",
    "CREATE TABLE IF NOT EXISTS agent_traces (id INTEGER PRIMARY KEY, request_id VARCHAR(64) NOT NULL, step_index INTEGER NOT NULL, node_name VARCHAR(64) NOT NULL, tool_name VARCHAR(64), tool_arguments TEXT, tool_result TEXT, status VARCHAR(20) NOT NULL, error_message TEXT, started_at DATETIME NOT NULL, finished_at DATETIME NOT NULL, duration_ms INTEGER NOT NULL)",
]


def init_database() -> dict[str, object]:
    settings = get_settings()
    if settings.database_provider == "mysql":
        return init_mysql(settings)
    now = datetime.now(UTC).replace(tzinfo=None)
    users = [(1, "alice", "alice@example.test", "ACTIVE", now - timedelta(days=90), now - timedelta(hours=2)), (2, "bob", "bob@example.test", "ACTIVE", now - timedelta(days=30), None)]
    orders = [
        (1, 1, "NS00000001", 199.00, "FAILED", "ORDER002", now - timedelta(days=1), now - timedelta(days=1)),
        (2, 1, "NS00000002", 299.00, "FAILED", "ORDER002", now - timedelta(days=3), now - timedelta(days=3)),
        (3, 2, "NS00000003", 88.00, "FAILED", "ORDER002", now - timedelta(days=6), now - timedelta(days=6)),
        (4, 2, "NS00000004", 59.00, "FAILED", "ORDER003", now - timedelta(days=2), now - timedelta(days=2)),
        (5, 1, "NS00000005", 109.00, "FAILED", "ORDER002", now - timedelta(days=10), now - timedelta(days=10)),
        (6, 1, "NS00000006", 399.00, "PAID", None, now - timedelta(days=1), now - timedelta(days=1)),
    ]
    engine = get_engine()
    with engine.begin() as connection:
        for statement in SCHEMA:
            connection.execute(text(statement))
        connection.execute(text("DELETE FROM orders"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("INSERT INTO users (id, username, email, status, created_at, last_login_at) VALUES (:id,:username,:email,:status,:created_at,:last_login_at)"), [dict(zip(("id","username","email","status","created_at","last_login_at"), row, strict=True)) for row in users])
        connection.execute(text("INSERT INTO orders (id,user_id,order_no,amount,status,error_code,created_at,updated_at) VALUES (:id,:user_id,:order_no,:amount,:status,:error_code,:created_at,:updated_at)"), [dict(zip(("id","user_id","order_no","amount","status","error_code","created_at","updated_at"), row, strict=True)) for row in orders])
    return {"provider": settings.database_provider, "users": len(users), "orders": len(orders), "utc_seed_time": now.isoformat()}


def init_mysql(settings) -> dict[str, object]:
    """Initialize trusted schema and seed data through admin credentials, then grant SELECT only."""
    identifier = re.compile(r"^[A-Za-z0-9_]+$")
    if not identifier.fullmatch(settings.mysql_database) or not identifier.fullmatch(settings.mysql_readonly_user):
        raise ValueError("MySQL database and user names must be simple identifiers")
    if not settings.mysql_admin_password or not settings.mysql_readonly_password:
        raise RuntimeError(
            "MySQL mode requires non-empty MYSQL_ADMIN_PASSWORD and "
            "MYSQL_READONLY_PASSWORD in the project-root .env. "
            "Save .env before running this script and do not overwrite it by "
            "copying .env.example again."
        )
    try:
        connection = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_admin_user,
            password=settings.mysql_admin_password,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=settings.db_query_timeout_seconds,
        )
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else None
        endpoint = f"{settings.mysql_host}:{settings.mysql_port}"
        if code == 1045:
            raise RuntimeError(
                f"MySQL at {endpoint} rejected the configured admin credentials. "
                "Verify that this endpoint is the project Docker MySQL and that "
                "MYSQL_ADMIN_PASSWORD matches the password used when its data "
                "volume was first initialized. Do not reuse an unrelated local MySQL."
            ) from exc
        if code in {2002, 2003}:
            raise RuntimeError(
                f"No project MySQL is reachable at {endpoint}. Confirm Docker "
                "Desktop Engine is healthy and 'docker compose up -d mysql' "
                "completed successfully before initialization."
            ) from exc
        raise
    now = datetime.now(UTC).replace(tzinfo=None)
    schema = [
        f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
        "CREATE TABLE IF NOT EXISTS users (id BIGINT PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL, email VARCHAR(255) NOT NULL, status VARCHAR(20) NOT NULL, created_at DATETIME(6) NOT NULL, last_login_at DATETIME(6) NULL)",
        "CREATE TABLE IF NOT EXISTS orders (id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL, order_no VARCHAR(32) UNIQUE NOT NULL, amount DECIMAL(12,2) NOT NULL, status VARCHAR(20) NOT NULL, error_code VARCHAR(32), created_at DATETIME(6) NOT NULL, updated_at DATETIME(6) NOT NULL, version INT NOT NULL DEFAULT 1, note TEXT, cancel_reason VARCHAR(500), created_by VARCHAR(36), updated_by VARCHAR(36), INDEX idx_orders_status_created(status, created_at), CONSTRAINT fk_orders_user FOREIGN KEY(user_id) REFERENCES users(id))",
        "CREATE TABLE IF NOT EXISTS test_runs (id BIGINT PRIMARY KEY AUTO_INCREMENT, request_id VARCHAR(64) NOT NULL, test_target VARCHAR(255) NOT NULL, total_count INT NOT NULL, passed_count INT NOT NULL, failed_count INT NOT NULL, output TEXT, created_at DATETIME(6) NOT NULL)",
        "CREATE TABLE IF NOT EXISTS agent_traces (id BIGINT PRIMARY KEY AUTO_INCREMENT, request_id VARCHAR(64) NOT NULL, step_index INT NOT NULL, node_name VARCHAR(64) NOT NULL, tool_name VARCHAR(64), tool_arguments JSON, tool_result JSON, status VARCHAR(20) NOT NULL, error_message TEXT, started_at DATETIME(6) NOT NULL, finished_at DATETIME(6) NOT NULL, duration_ms INT NOT NULL, INDEX idx_trace_request(request_id, step_index))",
    ]
    users = [(1, "alice", "alice@example.test", "ACTIVE", now - timedelta(days=90), now - timedelta(hours=2)), (2, "bob", "bob@example.test", "ACTIVE", now - timedelta(days=30), None)]
    orders = [
        (1, 1, "NS00000001", 199.00, "FAILED", "ORDER002", now - timedelta(days=1), now - timedelta(days=1)),
        (2, 1, "NS00000002", 299.00, "FAILED", "ORDER002", now - timedelta(days=3), now - timedelta(days=3)),
        (3, 2, "NS00000003", 88.00, "FAILED", "ORDER002", now - timedelta(days=6), now - timedelta(days=6)),
        (4, 2, "NS00000004", 59.00, "FAILED", "ORDER003", now - timedelta(days=2), now - timedelta(days=2)),
        (5, 1, "NS00000005", 109.00, "FAILED", "ORDER002", now - timedelta(days=10), now - timedelta(days=10)),
        (6, 1, "NS00000006", 399.00, "PAID", None, now - timedelta(days=1), now - timedelta(days=1)),
    ]
    try:
        with connection.cursor() as cursor:
            cursor.execute(schema[0])
            cursor.execute(f"USE `{settings.mysql_database}`")
            for statement in schema[1:]:
                cursor.execute(statement)
            cursor.execute("DELETE FROM orders")
            cursor.execute("DELETE FROM users")
            cursor.executemany("INSERT INTO users (id,username,email,status,created_at,last_login_at) VALUES (%s,%s,%s,%s,%s,%s)", users)
            cursor.executemany("INSERT INTO orders (id,user_id,order_no,amount,status,error_code,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", orders)
            cursor.execute(f"CREATE USER IF NOT EXISTS '{settings.mysql_readonly_user}'@'%%' IDENTIFIED BY %s", (settings.mysql_readonly_password,))
            cursor.execute(f"ALTER USER '{settings.mysql_readonly_user}'@'%%' IDENTIFIED BY %s", (settings.mysql_readonly_password,))
            cursor.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{settings.mysql_readonly_user}'@'%'")
            cursor.execute(f"GRANT SELECT ON `{settings.mysql_database}`.* TO '{settings.mysql_readonly_user}'@'%'")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"provider": "mysql", "users": len(users), "orders": len(orders), "utc_seed_time": now.isoformat(), "runtime_account": settings.mysql_readonly_user, "runtime_privilege": "SELECT only"}


if __name__ == "__main__":
    print(init_database())
