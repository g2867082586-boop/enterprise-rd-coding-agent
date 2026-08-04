from typing import Any

from app.config import get_settings


def make_mock_plan(query: str, request_id: str) -> tuple[str, list[dict[str, Any]]]:
    """Build deterministic plans only for documented Mock-mode demonstrations."""
    settings = get_settings()
    knowledge = {"name": "search_knowledge_base", "arguments": {"query": query, "top_k": 3}}
    database = [
        {"name": "describe_table", "arguments": {"table_name": "orders"}},
        {"name": "natural_language_query", "arguments": {"question": "查询最近七天失败订单，按照错误码分组"}},
    ]
    browser = {
        "name": "browser_check",
        "arguments": {
            "url": settings.sample_app_url,
            "expected_text": "系统运行正常",
            "selector": "#system-status",
            "request_id": request_id,
        },
    }
    lowered = query.lower()
    if "订单查询功能" in query or ("先查看" in query and "最后检查" in query):
        return "comprehensive", [knowledge, *database, {"name": "run_pytest", "arguments": {"test_path": "tests/scenarios/test_orders.py", "verbose": True}}, browser]
    if "pytest" in lowered or "测试" in query:
        target = "tests/scenarios/test_login.py" if "登录" in query else "tests/scenarios/test_orders.py"
        arguments: dict[str, Any] = {"test_path": target, "verbose": True}
        if "登录" in query:
            arguments["marker"] = "demo_failure"
        return "test", [knowledge, {"name": "run_pytest", "arguments": arguments}]
    if "最近七天" in query and "订单" in query:
        return "database", [knowledge, *database]
    if "首页" in query or "页面" in query or "浏览器" in query:
        return "browser", [browser]
    return "knowledge", [knowledge]
