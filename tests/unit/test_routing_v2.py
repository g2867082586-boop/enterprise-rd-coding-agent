import pytest

from app.agent.nodes import route_query
from app.config import get_settings
from app.llm.mock_llm import route_with_rules


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("你好", "direct_answer"),
        ("Python 装饰器是什么？", "direct_answer"),
        ("登录接口需要哪些参数？", "knowledge_base"),
        ("ORDER002 是什么意思？", "knowledge_base"),
        ("最近七天失败订单有哪些？", "database"),
        ("过去一周哪些订单没有处理成功？", "database"),
        ("最近七天失败订单为什么这么多？", "hybrid"),
        ("运行用户登录测试", "test"),
        ("检查首页是否正常", "browser"),
        ("帮我处理一下订单问题", "clarify"),
    ],
)
def test_mock_router_is_deterministic(query: str, expected: str) -> None:
    decision = route_with_rules(query)
    assert decision.route == expected


def test_direct_answer_never_selects_enterprise_tools() -> None:
    decision = route_with_rules("REST API 是什么？")
    assert decision.route == "direct_answer"
    assert decision.required_tools == []


@pytest.mark.asyncio
async def test_missing_real_provider_configuration_is_explicit_mock_fallback(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("ALLOW_MOCK_FALLBACK", "true")
    get_settings.cache_clear()
    result = await route_query({
        "request_id": "fallback-test", "user_query": "你好", "normalized_query": "你好",
        "route": "", "route_confidence": 0, "route_reason": "", "provider_mode": "openai_compatible",
        "fallback_reason": None, "plan": [], "current_step": 0, "selected_tool": None,
        "tool_arguments": {}, "final_answer": None,
    })
    assert result["route"] == "direct_answer"
    assert result["provider_mode"] == "mock_fallback"
    assert result["fallback_reason"]
    get_settings.cache_clear()
