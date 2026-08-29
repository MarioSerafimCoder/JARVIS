from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...

    @abstractmethod
    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]: ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_model_info(self) -> dict[str, Any]: ...

