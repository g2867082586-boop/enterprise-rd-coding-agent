import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config import get_settings
from app.database.connection import get_engine
from app.database.repository import execute_readonly_sql, failed_orders_last_seven_days
from app.database.sql_guard import UnsafeSqlError


pytestmark = pytest.mark.mysql


def test_project_mysql_connection_dynamic_window_and_limit() -> None:
    assert get_settings().database_provider == "mysql"
    result = failed_orders_last_seven_days()
    assert result["columns"] == ["error_code", "failure_count"]
    assert all(row["error_code"] and row["failure_count"] > 0 for row in result["rows"])
    limited = execute_readonly_sql("SELECT order_no FROM orders LIMIT 1000")
    assert "LIMIT 100" in limited["sql"]
    assert limited["row_count"] == 6


@pytest.mark.parametrize("sql", [
    "UPDATE orders SET status='PAID'", "SELECT * FROM orders; SELECT * FROM users",
    "SELECT * FROM mysql.user", "SELECT SLEEP(1) FROM orders",
])
def test_mysql_guard_rejects_unsafe_queries(sql: str) -> None:
    with pytest.raises(UnsafeSqlError):
        execute_readonly_sql(sql)


def test_mysql_runtime_account_is_read_only_at_server_level() -> None:
    with pytest.raises(DBAPIError):
        with get_engine().begin() as connection:
            connection.execute(text("INSERT INTO orders (order_no, user_id, status, amount, created_at) VALUES ('FORBIDDEN-CI', 1, 'FAILED', 1, NOW())"))
