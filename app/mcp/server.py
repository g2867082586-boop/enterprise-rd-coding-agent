import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.database.repository import (
    describe_table as db_describe_table,
    execute_readonly_sql as db_execute_readonly_sql,
    list_tables as db_list_tables,
    natural_language_query as db_natural_language_query,
)
from app.rag.indexer import search
from app.tools.browser_tool import async_browser_check as do_browser_check
from app.tools.terminal_tool import run_pytest as do_run_pytest
from app.tools.terminal_tool import run_terminal_command as do_run_terminal_command
from app.database.session import create_app_session
from app.orders.schemas import OrderSearchParams
from app.orders.service import (
    get_order as order_get,
    order_statistics,
    prepare_action,
    search_orders as order_search,
)


logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nebula.mcp.server")
mcp = FastMCP("nebula-rd-tools", log_level="ERROR")


def _run(name: str, function: Any, *args: Any, **kwargs: Any) -> Any:
    logger.info("MCP_SERVER_EXECUTE tool=%s", name)
    result = function(*args, **kwargs)
    logger.info("MCP_SERVER_RETURN tool=%s ok=true", name)
    return result


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3, doc_type: str | None = None,
                          allowed_scopes: list[str] | None = None,
                          corpus_type: str | None = None) -> list[dict[str, Any]]:
    """Search the local Nebula Shop knowledge base using lexical TF-IDF retrieval."""
    return _run("search_knowledge_base", search, query, min(max(top_k, 1), 10), doc_type,
                allowed_scopes, corpus_type)


@mcp.tool()
def list_tables() -> list[str]:
    """List allowlisted business tables."""
    return _run("list_tables", db_list_tables)


@mcp.tool()
def describe_table(table_name: str) -> list[dict[str, Any]]:
    """Describe an allowlisted business table."""
    return _run("describe_table", db_describe_table, table_name)


@mcp.tool()
def execute_readonly_sql(sql: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate with a SQL AST policy and execute one read-only query."""
    return _run("execute_readonly_sql", db_execute_readonly_sql, sql, parameters)


@mcp.tool()
def natural_language_query(question: str) -> dict[str, Any]:
    """Map a supported Mock-mode Chinese business question to guarded read-only SQL."""
    return _run("natural_language_query", db_natural_language_query, question)


@mcp.tool()
def run_terminal_command(command: str, args: list[str], timeout_seconds: int = 30) -> dict[str, Any]:
    """Run a structured allowlisted command with shell disabled."""
    return _run("run_terminal_command", do_run_terminal_command, command, args, timeout_seconds)


@mcp.tool()
def run_pytest(test_path: str = "tests/scenarios", keyword: str | None = None, marker: str | None = None, verbose: bool = False) -> dict[str, Any]:
    """Run a constrained pytest target and parse the real result."""
    return _run("run_pytest", do_run_pytest, test_path, keyword, marker, verbose)


@mcp.tool()
async def browser_check(url: str, expected_text: str = "", selector: str = "", request_id: str = "browser-check") -> dict[str, Any]:
    """Validate an allowlisted local page using installed Google Chrome."""
    logger.info("MCP_SERVER_EXECUTE tool=browser_check")
    result = await do_browser_check(url, expected_text, selector, request_id)
    logger.info("MCP_SERVER_RETURN tool=browser_check ok=%s", result.get("ok"))
    return result


@mcp.tool()
def search_orders(
    order_no: str | None = None, user_id: int | None = None, status: str | None = None,
    error_code: str | None = None, created_from: str | None = None,
    created_to: str | None = None, min_amount: float | None = None,
    max_amount: float | None = None, page: int = 1, page_size: int = 20,
    sort: str = "created_at_desc",
) -> dict[str, Any]:
    """Query current order records through structured, parameterized filters."""
    params = OrderSearchParams.model_validate(locals())
    return _run("search_orders", order_search, params)


@mcp.tool()
def get_order(order_no: str) -> dict[str, Any] | None:
    """Get one current order by its exact order number."""
    return _run("get_order", order_get, order_no)


@mcp.tool()
def get_order_statistics(
    created_from: str | None = None, created_to: str | None = None
) -> dict[str, Any]:
    """Aggregate current orders by status and failed error code."""
    return _run("get_order_statistics", order_statistics, created_from, created_to)


@mcp.tool()
def prepare_order_action(
    action_type: str, parameters: dict[str, Any], request_user_id: str,
    idempotency_key: str, session_id: str | None = None,
) -> dict[str, Any]:
    """Create an immutable, idempotent order action that requires confirmation."""
    db = create_app_session()
    try:
        row = prepare_action(
            db, request_user_id, session_id, action_type, parameters, idempotency_key
        )
        return {
            "action_id": row.id, "action_type": row.action_type, "status": row.status,
            "risk_level": row.risk_level, "expires_at": row.expires_at.isoformat(),
        }
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
