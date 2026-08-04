import pytest

from app.database.sql_guard import UnsafeSqlError, guard_readonly_sql


def test_select_gets_bounded_limit() -> None:
    guarded = guard_readonly_sql("SELECT order_no FROM orders", max_rows=25)
    assert "LIMIT 25" in guarded.sql
    assert guarded.tables == ("orders",)


@pytest.mark.parametrize("sql", ["DELETE FROM orders", "SELECT * FROM orders; DROP TABLE orders", "SELECT * FROM secrets", "SELECT SLEEP(10) FROM orders"])
def test_dangerous_sql_is_rejected(sql: str) -> None:
    with pytest.raises(UnsafeSqlError):
        guard_readonly_sql(sql)


def test_comment_cannot_hide_second_statement() -> None:
    with pytest.raises(UnsafeSqlError):
        guard_readonly_sql("SELECT * FROM orders; -- harmless\nDELETE FROM orders")

