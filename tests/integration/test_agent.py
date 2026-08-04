import uuid

import pytest

from app.agent.graph import get_graph, run_agent
from app.tracing.recorder import read_traces


@pytest.mark.asyncio
async def test_langgraph_agent_uses_mcp_checkpoint_and_trace(seeded_database) -> None:
    session = f"test-{uuid.uuid4()}"
    state = await run_agent("查询最近七天失败订单的数量，按照错误码分组", session)
    assert state["status"] == "completed"
    tools = [item["tool"] for item in state["tool_results"]]
    assert tools == ["natural_language_query"]
    assert "search_knowledge_base" not in tools
    assert state["route"] == "database"
    assert state["thread_id"] == session
    events = read_traces(state["request_id"])
    assert len(events) >= 7
    assert {event["node_name"] for event in events} >= {"route_query", "execute_step", "generate_final_answer"}
    graph = await get_graph()
    snapshot = await graph.aget_state({"configurable": {"thread_id": session}})
    assert snapshot.values["request_id"] == state["request_id"]
    assert snapshot.values["status"] == "completed"
