import asyncio
import json

from app.agent.graph import close_graph, run_agent


async def main() -> None:
    try:
        state = await run_agent("最近七天失败订单为什么这么多？", "real-hybrid-final")
        print(json.dumps({
            "status": state["status"], "route": state["route"],
            "provider_mode": state["provider_mode"], "fallback_reason": state.get("fallback_reason"),
            "plan": state.get("plan"), "tools": [item["tool"] for item in state.get("tool_results", [])],
            "tool_success": [item.get("success") for item in state.get("tool_results", [])],
            "evidence_status": state.get("evidence_status"), "errors": state.get("errors"),
            "answer": state.get("final_answer"),
        }, ensure_ascii=False, indent=2))
    finally:
        await close_graph()


if __name__ == "__main__":
    asyncio.run(main())
