import asyncio
import json
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import get_settings


class LLMProviderError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    mode = "openai_compatible"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key or not base_url or not model:
            raise ValueError("LLM_API_KEY, LLM_BASE_URL and LLM_MODEL are required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self._api_key}"}, json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_error = exc
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(min(2 ** attempt, 4))
        raise LLMProviderError("真实模型调用失败，请检查服务地址、模型权限或网络状态") from last_error

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model, "temperature": get_settings().llm_temperature,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        }
        data = await self._post(payload)
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("真实模型返回格式不完整") from exc

    async def generate_structured(self, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel:
        # DeepSeek and several OpenAI-compatible providers support json_object
        # but not OpenAI's json_schema response format. The schema is included
        # in the prompt and Pydantic remains the deterministic enforcement layer.
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        structured_system = (
            f"{system_prompt}\nYou must return one JSON object matching this JSON Schema exactly. "
            f"Do not use markdown fences. Schema: {schema_json}"
        )
        last_error: Exception | None = None
        for _ in range(get_settings().llm_max_retries + 1):
            payload = {
                "model": self._model, "temperature": get_settings().llm_temperature,
                "max_tokens": 4096,
                "messages": [{"role": "system", "content": structured_system},
                             {"role": "user", "content": user_prompt}],
                "response_format": {"type": "json_object"},
            }
            # DeepSeek V4 enables thinking by default. A bounded JSON request can
            # otherwise spend the whole output budget on reasoning and return an
            # empty ``content`` field, which cannot be validated. Keep this
            # provider-specific so other OpenAI-compatible APIs do not receive an
            # unsupported extension parameter.
            if "api.deepseek.com" in self._base_url.lower():
                payload["thinking"] = {"type": "disabled"}
            data = await self._post(payload)
            try:
                content = data["choices"][0]["message"]["content"]
                return schema.model_validate(json.loads(content))
            except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
        raise LLMProviderError(f"真实模型结构化输出不符合 {schema.__name__}") from last_error

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=min(get_settings().llm_timeout_seconds, 10)) as client:
                response = await client.get(f"{self._base_url}/models", headers={"Authorization": f"Bearer {self._api_key}"})
                response.raise_for_status()
            return {"ok": True, "mode": self.mode, "model": self._model, "api_key_set": True}
        except httpx.HTTPError:
            return {"ok": False, "mode": self.mode, "model": self._model, "api_key_set": True, "error": "provider unavailable"}
