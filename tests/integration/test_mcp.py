import pytest

from app.mcp.client import call_mcp_tool, list_mcp_tools


@pytest.mark.asyncio
async def test_official_mcp_stdio_discovers_and_calls_tools(seeded_database) -> None:
    tools = await list_mcp_tools()
    assert {"search_knowledge_base", "natural_language_query", "run_pytest", "browser_check"}.issubset(tools)
    result = await call_mcp_tool(
        "search_knowledge_base",
        {"query": "ORDER002 库存预占", "top_k": 1, "corpus_type": "mock"},
    )
    assert result and "ORDER002" in result[0]["snippet"]
