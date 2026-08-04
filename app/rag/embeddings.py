from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config import get_settings


class EmbeddingProvider(Protocol):
    mode: str
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def dimension(self) -> int: ...


class LocalFastEmbedProvider:
    mode = "local_semantic_embedding"

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name, providers=["CPUExecutionProvider"])
        self._dimension: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [vector.tolist() for vector in self._model.embed(texts)]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def dimension(self) -> int:
        if self._dimension is None:
            self.embed(["维度探测"])
        return int(self._dimension or 0)


class OpenAICompatibleEmbeddingProvider:
    mode = "openai_compatible_embedding"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key or not base_url or not model:
            raise ValueError("embedding API key, base URL and model are required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model_name = model
        self._dimension = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self.model_name, "input": texts},
            timeout=get_settings().llm_timeout_seconds,
        )
        response.raise_for_status()
        vectors = [item["embedding"] for item in sorted(response.json()["data"], key=lambda row: row["index"])]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def dimension(self) -> int:
        if not self._dimension:
            self.embed(["维度探测"])
        return self._dimension


class LexicalFallback:
    mode = "tfidf_fallback"
    model_name = "tfidf_char_2_4"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("TF-IDF fallback is lexical retrieval, not a semantic embedding provider")

    def dimension(self) -> int:
        return 0


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return LocalFastEmbedProvider(settings.embedding_model)
    if settings.embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(
            settings.embedding_api_key, settings.embedding_base_url, settings.embedding_model
        )
    if settings.embedding_provider in {"lexical", "tfidf_fallback"}:
        return LexicalFallback()
    raise ValueError(f"unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}")


def embedding_health() -> dict[str, Any]:
    settings = get_settings()
    try:
        provider = get_embedding_provider()
        return {"ok": True, "mode": provider.mode, "model": provider.model_name,
                "dimension": provider.dimension(), "api_key_set": bool(settings.embedding_api_key)}
    except Exception as exc:
        return {"ok": False, "mode": settings.embedding_provider, "model": settings.embedding_model,
                "api_key_set": bool(settings.embedding_api_key), "error": str(exc)[:300]}
