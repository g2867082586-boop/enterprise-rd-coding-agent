import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import ROOT_DIR
from app.observability import span


logger = logging.getLogger("nebula.mcp.client")


def _decode_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured.get("result", structured) if isinstance(structured, dict) else structured
    texts = [item.text for item in result.content if getattr(item, "type", None) == "text"]
    if not texts:
        return None
    text = "\n".join(texts)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.server"],
        cwd=str(ROOT_DIR),
        # The SDK otherwise builds a restricted environment on Windows. Runtime
        # provider/temporary test database settings must reach the real server.
        env=os.environ.copy(),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def list_mcp_tools() -> list[str]:
    async with mcp_session() as session:
        response = await session.list_tools()
        return [tool.name for tool in response.tools]


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> Any:
    logger.info("MCP_CLIENT_REQUEST tool=%s", name)
    error_message: str | None = None
    with span("mcp.client.call", tool=name):
        async with mcp_session() as session:
            result = await session.call_tool(name, arguments=arguments)
            if result.isError:
                error_message = f"MCP tool failed: {_decode_result(result)}"
                decoded = None
            else:
                decoded = _decode_result(result)
    if error_message:
        raise RuntimeError(error_message)
    logger.info("MCP_CLIENT_RESPONSE tool=%s", name)
    return decoded
