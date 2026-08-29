from app.core.agent import AgentController
from app.core.config import get_settings
from app.llm.ollama_provider import OllamaProvider
from app.llm.registry import LLMRegistry
from app.tools.executor import ToolExecutor
from app.tools.implementations import initial_tools
from app.tools.registry import ToolRegistry


settings = get_settings()
provider = OllamaProvider(settings)
llm_registry = LLMRegistry()
llm_registry.register(provider)
tool_registry = ToolRegistry(initial_tools())
tool_executor = ToolExecutor(tool_registry)
agent = AgentController(provider, tool_registry, tool_executor, settings)

