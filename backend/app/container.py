from app.core.agent import AgentController
from app.core.config import get_settings
from app.llm.ollama_provider import OllamaProvider
from app.llm.registry import LLMRegistry
from app.tools.executor import ToolExecutor
from app.tools.implementations import initial_tools
from app.tools.registry import ToolRegistry
from app.voice.profile import VoiceProfileManager
from app.voice.providers import EnergyVADProvider, VoiceWorkerProvider
from app.voice.session import VoiceSessionManager


settings = get_settings()
provider = OllamaProvider(settings)
llm_registry = LLMRegistry()
llm_registry.register(provider)
tool_registry = ToolRegistry(initial_tools())
tool_executor = ToolExecutor(tool_registry)
agent = AgentController(provider, tool_registry, tool_executor, settings)
voice_worker_provider = VoiceWorkerProvider(settings.voice_worker_url)
voice_vad_provider = EnergyVADProvider()
voice_profile_manager = VoiceProfileManager(settings, voice_worker_provider)
voice_session_manager = VoiceSessionManager(agent, voice_worker_provider, voice_worker_provider, voice_vad_provider, voice_profile_manager, settings)
