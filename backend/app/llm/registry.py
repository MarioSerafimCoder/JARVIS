from app.llm.base import LLMProvider


class LLMRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise KeyError(f"Provider não registrado: {name}")
        return self._providers[name]

