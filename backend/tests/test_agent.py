import pytest

from app.core.agent import AgentController
from app.services.repository import repository
from app.tools.executor import ToolExecutor
from app.tools.implementations import initial_tools
from app.tools.registry import ToolRegistry
from tests.fake_llm import FakeLLM


@pytest.mark.asyncio
async def test_stream_persists_incremental_answer(isolated_data):
    registry = ToolRegistry(initial_tools())
    agent = AgentController(FakeLLM(), registry, ToolExecutor(registry), isolated_data)
    events = [event async for event in agent.stream("Olá")]
    assert [event["type"] for event in events] == ["start", "token", "token", "done"]
    conversation_id = events[0]["conversation_id"]
    assistant = repository.row("SELECT * FROM messages WHERE conversation_id=? AND role='assistant'", (conversation_id,))
    assert assistant and assistant["content"] == "Resposta local."


@pytest.mark.asyncio
async def test_confirmed_action_gets_model_follow_up(isolated_data):
    tool_event = {"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "Revisar projeto"}}}]}}
    provider = FakeLLM([tool_event])
    registry = ToolRegistry(initial_tools())
    agent = AgentController(provider, registry, ToolExecutor(registry), isolated_data)
    events = [event async for event in agent.stream("Crie uma tarefa")]
    action = next(event["action"] for event in events if event["type"] == "action")
    assert action["status"] == "pending_confirmation"
    result = await agent.confirm_action(action["action_id"], True)
    assert result["status"] == "success"
    assert result["message"] == "Resultado verificado e concluído."
    assert repository.row("SELECT * FROM tasks WHERE title='Revisar projeto'")
    assert "Resultado verificado" in provider.requests[-1][-1]["content"]

