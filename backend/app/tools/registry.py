from app.tools.base import Tool


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Ferramenta duplicada: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Ferramenta não registrada: {name}")
        return self._tools[name]

    def schemas(self) -> list[dict]:
        return [tool.ollama_schema() for tool in self._tools.values()]

    def catalog(self) -> list[dict]:
        return [{"name": tool.name, "description": tool.description, "risk_level": tool.risk_level.value} for tool in self._tools.values()]

