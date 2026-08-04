import asyncio
import json

from app.mcp.client import call_mcp_tool, list_mcp_tools


async def main() -> None:
    tools = await list_mcp_tools()
    result = await call_mcp_tool("search_knowledge_base", {"query": "ORDER002 是什么", "top_k": 1})
    print(json.dumps({"tools": tools, "search_result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

