from collections.abc import AsyncIterator
from typing import Any

from app.llm.base import LLMProvider


class FakeLLM(LLMProvider):
    name = "fake"

    def __init__(self, events: list[dict[str, Any]] | None = None, answer: str = "Resultado verificado e concluído."):
        self.events = events or [
            {"message": {"role": "assistant", "content": "Resposta ", "tool_calls": []}},
            {"message": {"role": "assistant", "content": "local.", "tool_calls": []}, "eval_count": 2},
        ]
        self.answer = answer
        self.requests: list[list[dict[str, Any]]] = []

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        self.requests.append(messages)
        return {"message": {"role": "assistant", "content": self.answer}, "prompt_eval_count": 4, "eval_count": 3}

    async def stream_chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> AsyncIterator[dict[str, Any]]:
        self.requests.append(messages)
        for event in self.events:
            yield event

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "model": "fake"}

    async def get_model_info(self) -> dict[str, Any]:
        return {"name": "fake"}

