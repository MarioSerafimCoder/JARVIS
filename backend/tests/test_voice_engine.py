import io
import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.cognitive_state import CognitiveState, cognitive_state_service
from app.services.repository import repository
from app.voice.contracts import FakeSTTProvider, FakeTTSProvider, FakeVADProvider, VoiceEngineError
from app.voice.delivery import SpeechChunker, SpeechTextNormalizer, TTSCache, VoiceResourceManager
from app.voice.profile import VoiceProfileManager, inspect_wav
from app.voice.providers import EnergyVADProvider
from app.voice.session import VoiceSessionManager, confirmation_intent
from app.main import app
from app.api import voice as voice_api


def wav_bytes(duration: float = 0.3, amplitude: int = 6000) -> bytes:
    stream = io.BytesIO(); rate = 16000
    with wave.open(stream, "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
        output.writeframes(b"".join(struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 220 * index / rate))) for index in range(int(rate * duration))))
    return stream.getvalue()


def create_reference(settings, name: str = "001.wav") -> Path:
    path = settings.voice_path / "references" / name
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(wav_bytes())
    return path


class FakeVoiceAgent:
    def __init__(self, action: bool = False):
        self.action = action; self.confirmations: list[bool] = []

    async def stream(self, transcript: str, conversation_id: str | None = None):
        conversation = conversation_id or repository.create_conversation(transcript)["id"]
        yield {"type": "start", "conversation_id": conversation, "agent_run_id": "run-voice"}
        if self.action:
            action = {"action_id": "pending-1", "tool": "create_task", "input": {"title": "Comprar leite"}, "status": "pending_confirmation"}
            yield {"type": "action", "action": action}
            yield {"type": "token", "content": "Posso criar a tarefa Comprar leite."}
            yield {"type": "done", "message_id": "assistant-1", "actions": [action]}
        else:
            yield {"type": "token", "content": "Há três pendências. "}
            yield {"type": "token", "content": "A apresentação é a mais urgente."}
            yield {"type": "done", "message_id": "assistant-1", "actions": []}

    async def confirm_action(self, action_id: str, approved: bool):
        self.confirmations.append(approved)
        return {"status": "success" if approved else "cancelled", "conversation_id": repository.rows("SELECT id FROM conversations")[0]["id"], "message": "Feito." if approved else "Cancelado.", "message_id": "assistant-2"}


async def built_manager(settings, transcripts: list[str], action: bool = False):
    tts = FakeTTSProvider(); create_reference(settings)
    profile = VoiceProfileManager(settings, tts); await profile.build()
    agent = FakeVoiceAgent(action)
    manager = VoiceSessionManager(agent, FakeSTTProvider(transcripts), tts, FakeVADProvider(), profile, settings)
    return manager, agent, tts, profile


def test_speech_text_normalizer_handles_markdown_time_urls_and_code():
    result = SpeechTextNormalizer().normalize("## Agenda\n- Reunião às 14:30. https://local.test\n```py\nprint('x')\n```")
    assert "quatorze e trinta" in result
    assert "endereço da internet" in result
    assert "bloco de código" in result
    assert "print" not in result


def test_speech_chunker_never_emits_partial_words():
    chunker = SpeechChunker()
    assert chunker.feed("Primeira frase. Segunda") == ["Primeira frase."]
    assert chunker.feed(" frase!") == ["Segunda frase!"]
    assert chunker.flush() == []


def test_energy_vad_detects_pcm_speech_and_rejects_silence():
    vad = EnergyVADProvider(minimum_speech_ms=100)
    assert vad.detect(wav_bytes()[44:]) is True
    assert vad.detect(b"\0" * 6400) is False


def test_confirmation_requires_unambiguous_phrase():
    assert confirmation_intent("Sim!") is True
    assert confirmation_intent("pode executar") is True
    assert confirmation_intent("não faça") is False
    assert confirmation_intent("acho que talvez sim") is None


def test_wav_reference_report_has_technical_measurements(isolated_data):
    path = create_reference(isolated_data)
    report = inspect_wav(path)
    assert report["sample_rate"] == 16000
    assert report["channels"] == 1
    assert report["bit_depth"] == 16
    assert report["clipping_apparent"] is False


@pytest.mark.asyncio
async def test_profile_persists_and_becomes_outdated(isolated_data):
    tts = FakeTTSProvider(); create_reference(isolated_data)
    manager = VoiceProfileManager(isolated_data, tts)
    built = await manager.build()
    assert built["status"] == "READY"
    assert (isolated_data.voice_path / "profile" / "manifest.json").exists()
    assert (await manager.status())["status"] == "READY"
    create_reference(isolated_data, "002.wav")
    assert (await manager.status())["status"] == "OUTDATED"


def test_tts_cache_is_deterministic_and_lru_bounded(tmp_path):
    cache = TTSCache(tmp_path, max_size_bytes=6)
    key = cache.key("profile", "texto", "neutral", {"speed": 1})
    assert key == cache.key("profile", "texto", "neutral", {"speed": 1})
    cache.put(key, b"1234"); cache.put("second", b"5678")
    assert sum(path.stat().st_size for path in tmp_path.glob("*.wav")) <= 6


def test_resource_modes_are_explicit_and_sequential():
    assert VoiceResourceManager("AUTO").policy()["heavy_processing"] == "sequential"
    assert VoiceResourceManager("LOW_VRAM").policy()["tts"] == "gpu_sequential"


@pytest.mark.asyncio
async def test_voice_session_runs_transcript_agent_chunked_tts_and_returns_to_listening(isolated_data):
    manager, _, tts, _ = await built_manager(isolated_data, ["O que tenho hoje?"])
    session = manager.open()
    events = [event async for event in manager.process_utterance(session.session_id, b"encoded-audio")]
    assert next(event for event in events if event["type"] == "transcript")["text"] == "O que tenho hoje?"
    assert len([event for event in events if event["type"] == "tts_chunk"]) == 2
    assert len(tts.synthesis_calls) == 2
    assert events[-1]["type"] == "listening"
    assert cognitive_state_service.snapshot()["state"] == CognitiveState.LISTENING
    assert not list((isolated_data.voice_path / "temp").glob("*"))


@pytest.mark.asyncio
async def test_barge_in_cancels_queue_and_keeps_microphone_session(isolated_data):
    manager, _, _, _ = await built_manager(isolated_data, ["Teste"])
    session = manager.open(); session.queue.append({"status": "playing"})
    event = manager.interrupt(session.session_id)
    assert event["state"] == "LISTENING"
    assert session.queue[0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_voice_tool_confirmation_accepts_clear_yes(isolated_data):
    manager, agent, _, _ = await built_manager(isolated_data, ["Crie uma tarefa.", "Sim"], action=True)
    session = manager.open()
    first = [event async for event in manager.process_utterance(session.session_id, b"one")]
    assert any(event["type"] == "confirmation_required" for event in first)
    second = [event async for event in manager.process_utterance(session.session_id, b"two")]
    assert any(event["type"] == "tool_result" and event["approved"] for event in second)
    assert agent.confirmations == [True]


@pytest.mark.asyncio
async def test_ambiguous_voice_confirmation_never_executes_tool(isolated_data):
    manager, agent, _, _ = await built_manager(isolated_data, ["Crie uma tarefa.", "talvez sim"], action=True)
    session = manager.open()
    _ = [event async for event in manager.process_utterance(session.session_id, b"one")]
    second = [event async for event in manager.process_utterance(session.session_id, b"two")]
    assert any(event.get("ambiguous") is True for event in second)
    assert agent.confirmations == []


@pytest.mark.asyncio
async def test_missing_profile_keeps_text_fallback(isolated_data):
    tts = FakeTTSProvider(); profile = VoiceProfileManager(isolated_data, tts)
    manager = VoiceSessionManager(FakeVoiceAgent(), FakeSTTProvider(["Olá"]), tts, FakeVADProvider(), profile, isolated_data)
    session = manager.open()
    events = [event async for event in manager.process_utterance(session.session_id, b"audio")]
    error = next(event for event in events if event["type"] == "error")
    assert error["error"]["code"] == "VOICE_PROFILE_NOT_READY"
    assert error["text_fallback"] is True


@pytest.mark.asyncio
async def test_empty_audio_is_rejected_by_fake_stt():
    with pytest.raises(VoiceEngineError, match="vazio"):
        await FakeSTTProvider().transcribe(b"")


def test_voice_websocket_protocol_with_fake_providers(isolated_data, monkeypatch):
    import asyncio
    manager, _, _, _ = asyncio.run(built_manager(isolated_data, ["Que horas são?"]))
    monkeypatch.setattr(voice_api, "voice_session_manager", manager)
    with TestClient(app) as client:
        with client.websocket_connect("/api/voice/session") as websocket:
            websocket.send_json({"type": "session_start", "mime_type": "audio/webm"})
            assert websocket.receive_json()["type"] == "session_ready"
            assert websocket.receive_json()["type"] == "listening"
            websocket.send_bytes(b"encoded-audio")
            event_types = []
            for _ in range(20):
                event = websocket.receive_json(); event_types.append(event["type"])
                if event["type"] == "listening":
                    break
            assert {"transcript", "thinking", "assistant_text", "tts_chunk", "speaking", "listening"}.issubset(event_types)
            websocket.send_json({"type": "session_stop"})


def test_voice_api_reports_text_fallback_when_worker_is_offline(isolated_data, monkeypatch):
    async def offline():
        return {"status": "unavailable", "reason": "worker_offline"}
    monkeypatch.setattr(voice_api.voice_worker_provider, "health", offline)
    with TestClient(app) as client:
        response = client.get("/api/voice/status")
    assert response.status_code == 200
    assert response.json()["text_fallback"] is True
    assert response.json()["worker"]["status"] == "unavailable"
