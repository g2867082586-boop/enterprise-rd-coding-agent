import asyncio
import json
import uuid
from typing import Any

from app.agent.graph import close_graph, run_agent


TASKS = [
    "用户登录接口需要哪些参数？登录失败时应该从哪些方面排查？",
    "查询最近七天失败订单的数量，按照错误码分组，并分析最常见的问题。",
    "运行用户登录相关的 pytest 测试，并分析失败原因。",
    "检查本地演示系统首页能否正常访问，并确认页面包含“系统运行正常”。",
    "检查订单查询功能是否正常。先查看相关接口和数据库文档，再查询最近失败订单，运行订单相关测试，最后检查 Web 页面，并给出综合结论。",
]


async def main() -> None:
    results: list[dict[str, Any]] = []
    try:
        for index, task in enumerate(TASKS, 1):
            state = await run_agent(task, session_id=f"demo-{index}-{uuid.uuid4()}")
            results.append({"demo": index, "request_id": state["request_id"], "status": state["status"], "tools": [item["tool"] for item in state.get("tool_results", [])], "errors": state.get("errors", []), "answer": state.get("final_answer", "")[:500]})
        print(json.dumps({"runtime_mode": "Mock LLM + lexical TF-IDF", "results": results}, ensure_ascii=False, indent=2))
    finally:
        await close_graph()


if __name__ == "__main__":
    asyncio.run(main())
