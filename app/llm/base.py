from typing import Any, Protocol, TypeVar

from pydantic import BaseModel


StructuredT = TypeVar("StructuredT", bound=BaseModel)


class LLMProvider(Protocol):
    mode: str

    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...

    async def generate_structured(
        self, system_prompt: str, user_prompt: str, schema: type[StructuredT]
    ) -> StructuredT: ...

    async def health_check(self) -> dict[str, Any]: ...
