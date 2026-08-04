import pytest

from app.llm.openai_compatible import OpenAICompatibleLLM
from app.llm.schemas import RouteDecision


@pytest.mark.asyncio
async def test_openai_compatible_structured_output_uses_json_object_and_validates_schema(monkeypatch) -> None:
    provider = OpenAICompatibleLLM("sk-test-not-real", "https://example.test", "test-model")
    captured = {}

    async def fake_post(payload):
        captured.update(payload)
        return {"choices": [{"message": {"content": '{"route":"database","confidence":0.9,"reason":"records","rewritten_query":"q","required_tools":["natural_language_query"],"extracted_parameters":{},"needs_planning":false}'}}]}

    monkeypatch.setattr(provider, "_post", fake_post)
    result = await provider.generate_structured("return json", "q", RouteDecision)
    assert result.route == "database"
    assert captured["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in captured["messages"][0]["content"]
