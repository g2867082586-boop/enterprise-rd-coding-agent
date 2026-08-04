from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.mock_llm import MockLLM
from app.llm.openai_compatible import OpenAICompatibleLLM


def get_llm() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLM()
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLM(settings.llm_api_key, settings.llm_base_url, settings.llm_model)
    raise ValueError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
