import json
from typing import Any, AsyncIterator

import httpx

from app.core.config import Settings
from app.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _options(self) -> dict[str, Any]:
        return {
            "temperature": self.settings.temperature,
            "num_ctx": self.settings.context_length,
            "num_predict": self.settings.max_output_tokens,
        }

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model_name,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": self._options(),
        }
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{self.settings.ollama_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        payload = {
            "model": self.settings.model_name,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": self._options(),
        }
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream("POST", f"{self.settings.ollama_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        yield data.get("message", {}).get("content", "")

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.settings.ollama_url}/api/tags")
                response.raise_for_status()
                names = [model["name"] for model in response.json().get("models", [])]
            return {"status": "online", "model_available": self.settings.model_name in names, "models": names}
        except Exception as exc:
            return {"status": "offline", "model_available": False, "error": str(exc)}

    async def get_model_info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.settings.ollama_url}/api/show", json={"model": self.settings.model_name}
            )
            response.raise_for_status()
            data = response.json()
            return {"name": self.settings.model_name, "details": data.get("details", {}), "model_info": data.get("model_info", {})}

