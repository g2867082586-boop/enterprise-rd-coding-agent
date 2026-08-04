from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect, text

from app.config import get_settings
from app.database.connection import get_engine
from app.database.sql_guard import guard_readonly_sql


SENSITIVE_FIELDS = {"email"}


def _mask(name: str, value: Any) -> Any:
    if name.lower() == "email" and isinstance(value, str) and "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}***@{domain}"
    return value


def list_tables() -> list[str]:
    return [name for name in inspect(get_engine()).get_table_names() if name in {"users", "orders", "test_runs", "agent_traces"}]


def describe_table(table_name: str) -> list[dict[str, Any]]:
    if table_name not in {"users", "orders", "test_runs", "agent_traces"}:
        raise ValueError("table is not allowlisted")
    return [
        {"name": c["name"], "type": str(c["type"]), "nullable": c["nullable"]}
        for c in inspect(get_engine()).get_columns(table_name)
    ]


def execute_readonly_sql(sql: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = get_settings()
    dialect = "mysql" if settings.database_provider == "mysql" else "sqlite"
    guarded = guard_readonly_sql(sql, settings.db_max_rows, dialect=dialect)
    with get_engine().connect() as connection:
        result = connection.execute(text(guarded.sql), parameters or {})
        columns = list(result.keys())
        rows = [
            {name: _mask(name, value) for name, value in zip(columns, row, strict=True)}
            for row in result.fetchall()
        ]
    return {"sql": guarded.sql, "columns": columns, "rows": rows, "row_count": len(rows)}


def failed_orders_last_seven_days() -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=7)
    return execute_readonly_sql(
        "SELECT error_code, COUNT(*) AS failure_count FROM orders "
        "WHERE status = 'FAILED' AND created_at >= :cutoff "
        "GROUP BY error_code ORDER BY failure_count DESC",
        {"cutoff": cutoff.replace(tzinfo=None)},
    )


def failed_order_records_last_seven_days() -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=7)
    return execute_readonly_sql(
        "SELECT order_no, amount, error_code, created_at FROM orders "
        "WHERE status = 'FAILED' AND created_at >= :cutoff ORDER BY created_at DESC",
        {"cutoff": cutoff.replace(tzinfo=None)},
    )


def natural_language_query(question: str) -> dict[str, Any]:
    if any(term in question for term in ("最近", "过去一周")) and "失败" in question and "订单" in question:
        if any(term in question for term in ("哪些", "记录", "明细")):
            result = failed_order_records_last_seven_days()
            result["explanation"] = "查询 UTC 最近七天内 FAILED 订单明细。"
            return result
        result = failed_orders_last_seven_days()
        result["explanation"] = "统计 UTC 最近七天内 FAILED 订单，并按 error_code 分组。"
        return result
    raise ValueError("Mock NL-to-SQL only supports the documented recent failed-order query")
