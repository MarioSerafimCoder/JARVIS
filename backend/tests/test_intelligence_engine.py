from typing import Any

import pytest

from app.core.agent import AgentController
from app.core.cognitive_graph import cognitive_graph_service
from app.core.database import database
from app.services.domains import ConversationService, MemoryService, conversation_service, memory_service
from app.services.embeddings import EmbeddingProvider
from app.services.memory_consolidator import memory_consolidator
from app.services.repository import repository
from app.services.schemas import FeedbackInput, MemoryInput
from app.tools.executor import ToolExecutor
from app.tools.implementations import initial_tools
from app.tools.registry import ToolRegistry
from tests.fake_llm import FakeLLM


class SequenceLLM(FakeLLM):
    def __init__(self, responses: list[dict[str, Any]]):
        super().__init__()
        self.responses = responses

    async def chat(self, messages, tools=None):
        self.requests.append(messages)
        return self.responses.pop(0)


class EndlessToolLLM(FakeLLM):
    async def chat(self, messages, tools=None):
        self.requests.append(messages)
        return {"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "get_current_datetime", "arguments": {}}}]}}


class StaticEmbeddings(EmbeddingProvider):
    name = "test_local"; model_name = "test-multilingual"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            normalized = text.casefold()
            vectors.append([1.0, 0.0] if "café" in normalized or "manha" in normalized or "manhã" in normalized else [0.0, 1.0])
        return vectors


class UnavailableEmbeddings(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("modelo indisponível")


def tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}}


@pytest.mark.asyncio
async def test_agent_executes_multiple_tool_cycles(isolated_data):
    provider = SequenceLLM([tool_call("get_current_datetime", {}), tool_call("list_tasks", {}), {"message": {"role": "assistant", "content": "Concluído em duas etapas."}}])
    registry = ToolRegistry(initial_tools())
    agent = AgentController(provider, registry, ToolExecutor(registry), isolated_data)
    result = await agent.chat("Consulte a hora e depois minhas tarefas")
    assert result["agent_status"] == "completed"
    assert result["context"]["agent_steps"] == 3
    assert len(result["actions"]) == 2
    run = repository.row("SELECT status,step_count FROM agent_runs WHERE id=?", (result["agent_run_id"],))
    assert run == {"status": "completed", "step_count": 3}


@pytest.mark.asyncio
async def test_agent_stops_at_max_loop(isolated_data):
    registry = ToolRegistry(initial_tools())
    agent = AgentController(EndlessToolLLM(), registry, ToolExecutor(registry), isolated_data)
    result = await agent.chat("Continue consultando a hora")
    assert result["agent_status"] == "failed"
    assert result["context"]["limit_reached"] is True
    assert len(result["actions"]) == isolated_data.max_agent_cycles


@pytest.mark.asyncio
async def test_confirmation_resumes_same_run_and_can_use_next_tool(isolated_data):
    first = tool_call("create_task", {"title": "Validar retomada"})["message"]
    provider = FakeLLM([{"message": first}])
    provider.responses = [tool_call("list_tasks", {}), {"message": {"role": "assistant", "content": "Tarefa criada e lista conferida."}}]

    async def sequence_chat(messages, tools=None):
        provider.requests.append(messages)
        return provider.responses.pop(0)

    provider.chat = sequence_chat
    registry = ToolRegistry(initial_tools()); agent = AgentController(provider, registry, ToolExecutor(registry), isolated_data)
    events = [event async for event in agent.stream("Crie e depois confira a tarefa")]
    pending = next(event["action"] for event in events if event["type"] == "action")
    run_id = pending["agent_run_id"]
    result = await agent.confirm_action(pending["action_id"], True)
    assert result["agent_run_id"] == run_id and result["agent_status"] == "completed"
    assert repository.row("SELECT status FROM agent_runs WHERE id=?", (run_id,))["status"] == "completed"
    assert len(repository.rows("SELECT * FROM agent_run_steps WHERE agent_run_id=? AND kind='tool'", (run_id,))) == 2


def test_invalid_tool_arguments_are_rejected(isolated_data):
    executor = ToolExecutor(ToolRegistry(initial_tools()))
    result = executor.request("create_task", {"title": "X", "priority": "impossível"})
    assert result["status"] == "pending_confirmation"
    executed = executor.confirm(result["action_id"], True)
    assert executed["status"] == "failed"
    assert repository.rows("SELECT * FROM tasks") == []


def test_memory_candidates_dedupe_and_supersession(isolated_data):
    conversation = repository.create_conversation("Preferências")
    message = repository.add_message(conversation["id"], "user", "Prefiro treinar pela manhã.")
    candidates = memory_consolidator.analyze(message["content"], conversation_id=conversation["id"], source_message_id=message["id"])
    assert len(candidates) == 1 and repository.rows("SELECT * FROM memories") == []
    old = memory_consolidator.save(candidates[0]["id"])
    duplicate = memory_service.create(MemoryInput(content="Prefere treinar pela manhã.", category="preference"))
    assert duplicate["created"] is False
    new = memory_service.create(MemoryInput(content="Agora prefere treinar à noite.", category="preference", supersedes_id=old["id"]))
    assert repository.row("SELECT status FROM memories WHERE id=?", (old["id"],))["status"] == "superseded"
    assert new["supersedes_id"] == old["id"]


def test_hybrid_retrieval_and_embedding_fallback(isolated_data):
    service = MemoryService(StaticEmbeddings())
    coffee = service.create(MemoryInput(content="Prefere café forte pela manhã.", category="preference"))
    service.create(MemoryInput(content="Projeto usa compilador Rust.", category="project"))
    found = service.hybrid_search("bebida de café de manhã", 2)
    assert found[0]["id"] == coffee["id"]
    assert found[0]["ranking"]["embedding_status"] == "active"
    fallback = MemoryService(UnavailableEmbeddings()).hybrid_search("café forte", 2)
    assert fallback and fallback[0]["ranking"]["embedding_status"] == "fallback_fts5"


def test_summary_feedback_relationship_invalidation_and_stats(isolated_data):
    conversation = repository.create_conversation("Resumo")
    assistant_id = ""
    for index in range(6):
        item = repository.add_message(conversation["id"], "user" if index % 2 == 0 else "assistant", f"Mensagem {index}")
        if item["role"] == "assistant": assistant_id = item["id"]
    assert conversation_service.maybe_update_summary(conversation["id"], 6)
    feedback = ConversationService().feedback(assistant_id, FeedbackInput(rating=-1, correction="Seja mais direto."))
    assert feedback["rating"] == -1
    first = memory_service.create(MemoryInput(content="Projeto Jarvis arquitetura local.", category="project"))
    second = memory_service.create(MemoryInput(content="Arquitetura local do projeto Jarvis módulo cognitivo.", category="project"), allow_duplicate=True)
    cognitive_graph_service.memory_created(second["id"])
    assert repository.rows("SELECT * FROM memory_relationships")
    memory_service.archive(first["id"])
    assert repository.rows("SELECT * FROM memory_relationships WHERE source_memory_id=? OR target_memory_id=?", (first["id"], first["id"])) == []
    graph = cognitive_graph_service.build([{"name": f"tool-{i}", "description": "", "risk_level": "SAFE"} for i in range(14)])
    assert graph["stats"]["tools"] == 14
    assert graph["stats"]["memory_relationships"] == 0
    assert graph["stats"]["tool_connections"] == 14
