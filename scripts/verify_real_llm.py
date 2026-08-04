"""Verify the configured real LLM without printing credentials."""
import asyncio
import json

from app.agent.graph import close_graph, run_agent
from app.llm.provider import get_llm
from app.llm.schemas import RouteDecision


async def main() -> None:
    provider = get_llm()
    results: dict[str, object] = {"health": await provider.health_check()}
    route = await provider.generate_structured(
        "You are a router. Return json. Concrete business records use database.",
        "最近七天失败订单有哪些？", RouteDecision,
    )
    results["structured_route"] = route.model_dump()
    try:
        scenarios = {}
        for name, query in {
            "direct": "Python 装饰器是什么？",
            "database": "最近七天失败订单有哪些？",
            "hybrid": "最近七天失败订单为什么这么多？",
        }.items():
            state = await run_agent(query, f"real-{name}-verification")
            scenarios[name] = {
                "status": state["status"], "route": state["route"],
                "provider_mode": state["provider_mode"],
                "fallback_reason": state.get("fallback_reason"),
                "tools": [item["tool"] for item in state.get("tool_results", [])],
                "answer": state.get("final_answer"), "errors": state.get("errors", []),
            }
        results["agent_scenarios"] = scenarios
    finally:
        await close_graph()
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
