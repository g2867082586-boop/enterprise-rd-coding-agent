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
from app.tools.codebase_tool import (
    apply_code_patch as do_apply_code_patch,
    create_code_workspace as do_create_code_workspace,
    discard_code_workspace as do_discard_code_workspace,
    git_diff as do_git_diff,
    list_repository as do_list_repository,
    read_code_file as do_read_code_file,
    run_code_checks as do_run_code_checks,
    search_code as do_search_code,
)
from app.coding.agent import run_coding_task as do_run_coding_task
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
def create_code_workspace(workspace_id: str) -> dict[str, Any]:
    """Create an isolated detached Git worktree for one coding task."""
    return _run("create_code_workspace", do_create_code_workspace, workspace_id)


@mcp.tool()
def discard_code_workspace(workspace_id: str) -> dict[str, Any]:
    """Remove a generated detached worktree after a coding task is complete."""
    return _run("discard_code_workspace", do_discard_code_workspace, workspace_id)


@mcp.tool()
def list_repository(workspace_id: str | None = None, relative_path: str = ".", max_entries: int = 200) -> list[str]:
    """List repository files while excluding generated and dependency directories."""
    return _run("list_repository", do_list_repository, workspace_id, relative_path, max_entries)


@mcp.tool()
def search_code(query: str, workspace_id: str | None = None, relative_path: str = ".", max_results: int = 50) -> list[dict[str, Any]]:
    """Search text source files and return path, line number and matching text."""
    return _run("search_code", do_search_code, query, workspace_id, relative_path, max_results)


@mcp.tool()
def read_code_file(path: str, workspace_id: str | None = None, start_line: int = 1, end_line: int = 200) -> dict[str, Any]:
    """Read a bounded line range from a UTF-8 source file."""
    return _run("read_code_file", do_read_code_file, path, workspace_id, start_line, end_line)


@mcp.tool()
def apply_code_patch(workspace_id: str, patch_text: str) -> dict[str, Any]:
    """Validate and apply a unified diff inside an isolated worktree."""
    return _run("apply_code_patch", do_apply_code_patch, workspace_id, patch_text)


@mcp.tool()
def get_code_diff(workspace_id: str) -> dict[str, Any]:
    """Return the current Git diff for an isolated coding workspace."""
    return _run("get_code_diff", do_git_diff, workspace_id)


@mcp.tool()
def run_code_checks(workspace_id: str, test_path: str = "tests/unit", timeout_seconds: int = 90) -> dict[str, Any]:
    """Run a bounded pytest target inside an isolated coding workspace."""
    return _run("run_code_checks", do_run_code_checks, workspace_id, test_path, timeout_seconds)


@mcp.tool()
async def run_coding_task(issue: str, workspace_id: str, max_attempts: int = 2) -> dict[str, Any]:
    """Run a bounded LLM patch-test-repair loop in an isolated Git worktree."""
    return await do_run_coding_task(issue, workspace_id, max_attempts)


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
