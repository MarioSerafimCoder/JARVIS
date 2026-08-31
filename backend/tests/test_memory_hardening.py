import pytest

from app.services.memory_consolidator import memory_consolidator
from app.services.repository import repository
from tests.fake_llm import FakeLLM


@pytest.mark.asyncio
async def test_malformed_local_extractor_never_saves_or_invents_memory(isolated_data):
    conversation = repository.create_conversation("Memória")
    message = repository.add_message(conversation["id"], "user", "Eu costumo avaliar isso depois")
    provider = FakeLLM(answer="isto não é JSON")
    candidates = await memory_consolidator.analyze_hybrid(
        message["content"], conversation_id=conversation["id"], source_message_id=message["id"], provider=provider,
    )
    assert candidates == []
    assert repository.rows("SELECT * FROM memories") == []
