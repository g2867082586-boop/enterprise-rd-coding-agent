from typing import Any

from pydantic import BaseModel

from app.llm.schemas import ExecutionPlan, PlanStep, RouteDecision
import re


class MockLLM:
    """Deterministic offline provider; it does not claim general semantic reasoning."""

    mode = "mock"

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        query = user_prompt.strip()
        if any(word in query.lower() for word in ("python 装饰器", "python decorator")):
            return "Python 装饰器是在不修改原函数主体的情况下包装并扩展函数或类行为的可调用对象。"
        if "rest api" in query.lower():
            return "REST API 使用资源化 URL 和 HTTP 方法表达操作，通常以无状态请求交换 JSON 等表示。"
        if any(word in query for word in ("你好", "您好")):
            return "你好，我可以回答通用问题，也能按需查询企业知识库、业务数据、测试结果和本地页面。"
        return "Mock LLM 无法可靠回答这个开放问题。请补充目标、对象和期望结果，或配置真实 LLM。"

    async def generate_structured(
        self, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> BaseModel:
        if schema is RouteDecision:
            return route_with_rules(user_prompt)
        if schema is ExecutionPlan:
            route = route_with_rules(user_prompt)
            return plan_with_rules(user_prompt, route)
        raise ValueError(f"Mock structured output does not support {schema.__name__}")

    async def health_check(self) -> dict[str, Any]:
        return {"ok": True, "mode": self.mode, "real_model": False}


def route_with_rules(query: str) -> RouteDecision:
    text = " ".join(query.strip().split())
    lowered = text.lower()
    tools: list[str] = []
    extracted: dict[str, Any] = {}
    if not text or text in {"帮我处理一下订单问题", "这个功能为什么不行", "帮我看看"}:
        route, confidence, reason = "clarify", 0.92, "缺少具体对象、现象或期望结果"
    elif any(term in text for term in ("修复代码", "修改代码", "实现代码")):
        route, confidence, reason, tools = "codebase", 0.96, "需要在隔离工作区执行编码任务", ["run_coding_task"]
    elif any(term in text for term in ("搜索代码", "查找代码", "定位函数", "代码仓库")):
        route, confidence, reason, tools = "codebase", 0.96, "需要检索本地代码仓库", ["search_code"]
    elif any(term in text for term in ("检查首页", "页面是否", "网页", "浏览器")):
        route, confidence, reason, tools = "browser", 0.96, "需要实际访问本地页面", ["browser_check"]
    elif "pytest" in lowered or (("运行" in text or "执行" in text) and "测试" in text):
        route, confidence, reason, tools = "test", 0.97, "明确要求执行测试", ["run_pytest"]
    elif "订单" in text and any(term in text for term in ("创建", "新增", "修改状态", "取消", "添加备注")):
        route, confidence, reason, tools = "order_mutation", 0.98, "请求执行受控订单写操作", ["prepare_order_action"]
        order_match = re.search(r"NS\d{8}", text)
        version_match = re.search(r"(?:版本|version)\s*(\d+)", text, re.IGNORECASE)
        if order_match:
            extracted["order_no"] = order_match.group(0)
        if version_match:
            extracted["expected_version"] = int(version_match.group(1))
        if "创建" in text or "新增" in text:
            user_match = re.search(r"用户(?:ID)?\s*(\d+)", text, re.IGNORECASE)
            amount_match = re.search(r"金额\s*([0-9]+(?:\.[0-9]{1,2})?)", text)
            if user_match:
                extracted["user_id"] = int(user_match.group(1))
            if amount_match:
                extracted["amount"] = amount_match.group(1)
        elif "状态" in text:
            status_match = re.search(r"(PROCESSING|PAID|FAILED|CANCELLED)", text, re.IGNORECASE)
            if status_match:
                extracted["target_status"] = status_match.group(1).upper()
        elif "取消" in text:
            reason_match = re.search(r"(?:原因|因为)[：:\s]*(.+?)(?:，|。|$)", text)
            extracted["reason"] = reason_match.group(1) if reason_match else "用户请求取消"
        elif "备注" in text:
            note_match = re.search(r"备注[：:\s]*(.+)$", text)
            if note_match:
                extracted["note"] = note_match.group(1)
    elif "订单" in text and any(term in text for term in ("为什么这么多", "分析原因", "结合错误码", "并运行")):
        route, confidence, reason, tools = "hybrid", 0.93, "需要业务数据与企业资料联合分析", ["natural_language_query", "search_knowledge_base"]
    elif re.search(r"NS\d{8}", text):
        route, confidence, reason, tools = "database", 0.98, "按订单号查询实时订单", ["get_order"]
    elif any(term in text for term in ("最近七天", "过去一周")) and "失败" in text and "订单" in text:
        route, confidence, reason, tools = "database", 0.96, "查询最近失败订单", ["natural_language_query"]
    elif any(term in text for term in ("今天新增", "多少", "统计", "哪些订单", "查询订单")) and any(term in text for term in ("订单", "用户")):
        route, confidence, reason, tools = "database", 0.96, "询问具体记录或统计，应查询实时业务数据", ["search_orders"]
    elif any(term in text for term in ("接口", "字段", "错误码", "规范", "ORDER002", "ORDER003")):
        route, confidence, reason, tools = "knowledge_base", 0.95, "询问企业接口、字段、错误码或制度", ["search_knowledge_base"]
    elif any(term in lowered for term in ("python 装饰器", "rest api")) or any(term in text for term in ("你好", "你能做什么")):
        route, confidence, reason = "direct_answer", 0.96, "通用知识或能力说明，无需企业数据"
    else:
        route, confidence, reason = "clarify", 0.7, "Mock 规则无法可靠判断意图"
    return RouteDecision(
        route=route, confidence=confidence, reason=reason, rewritten_query=text or query,
        required_tools=tools, extracted_parameters=extracted, needs_planning=route == "hybrid",
    )


def plan_with_rules(query: str, decision: RouteDecision) -> ExecutionPlan:
    steps: list[PlanStep] = []
    for index, tool in enumerate(decision.required_tools, 1):
        parameters: dict[str, Any]
        if tool == "search_knowledge_base":
            parameters = {"query": query, "top_k": 5}
        elif tool == "natural_language_query":
            parameters = {"question": query}
        elif tool == "get_order":
            match = re.search(r"NS\d{8}", query)
            parameters = {"order_no": match.group(0) if match else ""}
        elif tool == "search_orders":
            parameters = {"page": 1, "page_size": 20}
        elif tool == "prepare_order_action":
            action = (
                "cancel_order" if "取消" in query else
                "add_order_note" if "备注" in query else
                "update_order_status" if "状态" in query else "create_order"
            )
            parameters = {"action_type": action, "parameters": decision.extracted_parameters}
        elif tool == "run_pytest":
            parameters = {"test_path": "tests/scenarios/test_login.py" if "登录" in query else "tests/scenarios/test_orders.py", "verbose": True}
        elif tool == "browser_check":
            parameters = {"expected_text": "系统运行正常", "selector": "#system-status"}
        elif tool == "search_code":
            quoted = re.search(r"[`'\"]([^`'\"]+)[`'\"]", query)
            symbol = re.search(r"(?:搜索代码|查找代码|定位函数)\s*[:：]?\s*([A-Za-z_][A-Za-z0-9_.]*)", query)
            parameters = {"query": (quoted.group(1) if quoted else symbol.group(1) if symbol else query)}
        elif tool == "run_coding_task":
            parameters = {"issue": query, "workspace_id": "task-placeholder", "max_attempts": 2}
        else:
            parameters = {}
        steps.append(PlanStep(step_id=f"step_{index}", action=tool, objective=f"执行 {tool}",
                              depends_on=[f"step_{index-1}"] if index > 1 else [], parameters=parameters))
    return ExecutionPlan(goal=query, steps=steps or [PlanStep(step_id="step_1", action="ask_clarification", objective="澄清需求", parameters={})], max_steps=max(1, len(steps)))
