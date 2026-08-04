"""Opt-in real-LLM routing evaluation. This consumes configured API quota."""
import asyncio
import json
from datetime import UTC, datetime

from app.agent.nodes import _router_prompt
from app.config import ROOT_DIR
from app.llm.provider import get_llm
from app.llm.schemas import RouteDecision


async def main() -> None:
    rows = json.loads((ROOT_DIR / "tests/evaluation/routing_dataset.json").read_text(encoding="utf-8"))
    provider = get_llm(); results = []; correct = tool_correct = forbidden = 0
    for row in rows:
        decision = await provider.generate_structured(_router_prompt(), row["query"], RouteDecision)
        route_ok = decision.route == row["expected_route"]
        tools_ok = set(decision.required_tools) == set(row["expected_tools"])
        forbidden_hit = bool(set(decision.required_tools) & set(row["forbidden_tools"]))
        correct += int(route_ok); tool_correct += int(tools_ok); forbidden += int(forbidden_hit)
        results.append({"query": row["query"], "expected_route": row["expected_route"],
                        "actual_route": decision.route, "route_ok": route_ok,
                        "actual_tools": decision.required_tools, "tools_ok": tools_ok,
                        "forbidden_tool_called": forbidden_hit})
    report = {"generated_at": datetime.now(UTC).isoformat(), "provider": provider.mode,
              "total": len(rows), "routing_accuracy": correct / len(rows),
              "tool_accuracy": tool_correct / len(rows),
              "forbidden_tool_rate": forbidden / len(rows), "samples": results}
    output = ROOT_DIR / "artifacts/evaluation/real-routing-report-v2.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "samples"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
