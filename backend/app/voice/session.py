from __future__ import annotations

import base64
import time
import unicodedata
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.cognitive_state import CognitiveState, cognitive_state_service
from app.core.config import Settings
from app.core.database import utc_now
from app.services.repository import repository
from app.voice.contracts import SpeechToTextProvider, TextToSpeechProvider, VoiceActivityDetector, VoiceEngineError
from app.voice.delivery import SpeechChunker, SpeechTextNormalizer, TTSCache, VoiceResourceManager
from app.voice.profile import VoiceProfileManager


def confirmation_intent(text: str) -> bool | None:
    normalized = "".join(character for character in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(character) != "Mn")
    normalized = " ".join(normalized.replace(".", " ").replace("!", " ").replace("?", " ").split())
    positive = {"sim", "confirmo", "pode fazer", "pode executar", "faca isso", "pode", "execute"}
    negative = {"nao", "cancele", "nao faca", "cancelar", "deixe para la"}
    if normalized in positive:
        return True
    if normalized in negative:
        return False
    return None


@dataclass
class VoiceTurn:
    turn_id: str
    session_id: str
    state: str = "waiting"
    transcript: str = ""
    assistant_message_id: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: str | None = None
    timestamps: dict[str, float] = field(default_factory=dict)


@dataclass
class VoiceSession:
    session_id: str
    conversation_id: str | None
    status: str = "listening"
    muted: bool = False
    pending_action_id: str | None = None
    turns: list[VoiceTurn] = field(default_factory=list)
    playback_generation: int = 0
    queue: list[dict[str, Any]] = field(default_factory=list)


class VoiceTurnManager:
    VALID_STATES = {"waiting", "listening", "speech_detected", "transcribing", "processing", "speaking", "interrupted", "waiting_confirmation", "error"}

    def start(self, session: VoiceSession) -> VoiceTurn:
        turn = VoiceTurn(str(uuid.uuid4()), session.session_id, state="transcribing")
        session.turns.append(turn); return turn

    def transition(self, turn: VoiceTurn, state: str) -> VoiceTurn:
        if state not in self.VALID_STATES:
            raise ValueError(f"Estado de turno inválido: {state}")
        turn.state = state
        if state in {"waiting", "error"}:
            turn.ended_at = utc_now()
        return turn


class TTSPlaybackQueue:
    def __init__(self, items: list[dict[str, Any]]):
        self.items = items

    def enqueue(self, text: str, key: str) -> dict[str, Any]:
        item = {"id": str(uuid.uuid4()), "key": key, "status": "queued", "text": text}
        self.items.append(item); return item

    def cancel_all(self) -> None:
        for item in self.items:
            if item["status"] in {"queued", "generating", "ready", "playing"}:
                item["status"] = "cancelled"


class VoiceSessionManager:
    def __init__(
        self, agent: Any, stt: SpeechToTextProvider, tts: TextToSpeechProvider,
        vad: VoiceActivityDetector, profile: VoiceProfileManager, settings: Settings,
    ):
        self.agent = agent; self.stt = stt; self.tts = tts; self.vad = vad; self.profile = profile; self.settings = settings
        self.normalizer = SpeechTextNormalizer(); self.cache = TTSCache(settings.voice_path / "cache")
        self.resources = VoiceResourceManager(settings.voice_resource_mode); self.turns = VoiceTurnManager(); self.sessions: dict[str, VoiceSession] = {}

    def open(self, conversation_id: str | None = None) -> VoiceSession:
        session_id = str(uuid.uuid4()); session = VoiceSession(session_id, conversation_id)
        self.sessions[session_id] = session
        repository.execute("INSERT INTO voice_sessions_metadata VALUES (?,?,?,?,?,?,?)", (session_id, conversation_id, "active", 0, utc_now(), None, None))
        cognitive_state_service.set_state(CognitiveState.LISTENING, reason="voice_session_started")
        return session

    def get(self, session_id: str) -> VoiceSession:
        session = self.sessions.get(session_id)
        if not session:
            raise VoiceEngineError("VOICE_SESSION_FAILED", "Sessão de voz não encontrada.")
        return session

    def mute(self, session_id: str, muted: bool) -> VoiceSession:
        session = self.get(session_id); session.muted = muted
        if not muted:
            cognitive_state_service.set_state(CognitiveState.LISTENING, reason="voice_unmuted")
        return session

    def interrupt(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id); session.playback_generation += 1
        TTSPlaybackQueue(session.queue).cancel_all()
        session.status = "listening"
        if session.turns:
            session.turns[-1].state = "interrupted"
        cognitive_state_service.set_state(CognitiveState.LISTENING, reason="voice_barge_in")
        return {"type": "interrupted", "session_id": session_id, "state": "LISTENING"}

    async def close(self, session_id: str, error: str | None = None) -> None:
        session = self.get(session_id); session.status = "closed"; session.queue.clear()
        repository.execute(
            "UPDATE voice_sessions_metadata SET status=?,turn_count=?,ended_at=?,last_error=? WHERE id=?",
            ("failed" if error else "completed", len(session.turns), utc_now(), error, session_id),
        )
        self.sessions.pop(session_id, None)
        cognitive_state_service.set_state(CognitiveState.IDLE, reason="voice_session_stopped")

    async def confirm_visual(self, session_id: str, approved: bool) -> list[dict[str, Any]]:
        session = self.get(session_id)
        if not session.pending_action_id:
            raise VoiceEngineError("VOICE_SESSION_FAILED", "Não há ação aguardando confirmação nesta sessão.")
        action_id = session.pending_action_id; session.pending_action_id = None
        cognitive_state_service.set_state(CognitiveState.THINKING, reason="visual_voice_confirmation")
        result = await self.agent.confirm_action(action_id, approved)
        session.conversation_id = result.get("conversation_id") or session.conversation_id
        message = result.get("message", "Ação executada." if approved else "Ação cancelada.")
        events = [
            {"type": "tool_result", "approved": approved, "status": result.get("status"), "result": result},
            {"type": "assistant_text", "text": message, "final": True, "message_id": result.get("message_id")},
        ]
        events.extend(await self._speech_events(session, message, "confirmation", session.playback_generation))
        session.status = "listening"; cognitive_state_service.set_state(CognitiveState.LISTENING, reason="voice_confirmation_complete")
        events.append({"type": "listening", "state": "LISTENING"})
        return events

    async def _speech_events(self, session: VoiceSession, text: str, style: str, generation: int) -> list[dict[str, Any]]:
        speech_text = self.normalizer.normalize(text)
        if not speech_text:
            return []
        profile_status = await self.profile.status()
        if profile_status["status"] != "READY":
            return [{"type": "error", "error": {"code": "VOICE_PROFILE_NOT_READY", "message": "Perfil vocal do Jarvis ainda não configurado."}, "text_fallback": True}]
        if generation != session.playback_generation:
            return []
        config = {"speed": 1.0, "language": "pt-BR"}; key = self.cache.key(profile_status["fingerprint"], speech_text, style, config)
        queue_item = TTSPlaybackQueue(session.queue).enqueue(speech_text, key)
        audio = self.cache.get(key); metadata: dict[str, Any] = {"cache_hit": bool(audio), "profile": "Jarvis"}
        if audio is None:
            queue_item["status"] = "generating"; started = time.perf_counter()
            try:
                audio, provider_metadata = await self.tts.synthesize(speech_text, profile_dir=self.profile.profile_dir, style=style, speed=1.0)
            except VoiceEngineError as exc:
                queue_item["status"] = "cancelled"
                return [{"type": "error", "error": {"code": exc.code, "message": str(exc)}, "text_fallback": True}]
            metadata.update(provider_metadata); metadata["generation_seconds"] = round(time.perf_counter() - started, 4)
            self.cache.put(key, audio)
        if generation != session.playback_generation:
            queue_item["status"] = "cancelled"; return []
        queue_item["status"] = "ready"
        return [{
            "type": "tts_chunk", "audio": base64.b64encode(audio).decode("ascii"), "mime_type": "audio/wav",
            "speech_text": speech_text, "style": style, "queue_id": queue_item["id"], "metadata": metadata,
        }]

    async def process_utterance(self, session_id: str, audio: bytes, *, mime_type: str = "audio/webm") -> AsyncIterator[dict[str, Any]]:
        session = self.get(session_id)
        if session.muted:
            raise VoiceEngineError("MIC_UNAVAILABLE", "O microfone está silenciado.")
        turn = self.turns.start(session)
        started = time.perf_counter(); turn.timestamps["speech_end"] = started
        session.status = "transcribing"; cognitive_state_service.set_state(CognitiveState.TRANSCRIBING, reason="voice_utterance_complete")
        yield {"type": "speech_ended", "turn_id": turn.turn_id, "state": "TRANSCRIBING"}
        try:
            result = await self.stt.transcribe(audio, mime_type=mime_type, language="pt")
        except VoiceEngineError:
            self.turns.transition(turn, "error"); session.status = "listening"; cognitive_state_service.set_state(CognitiveState.LISTENING, reason="stt_failed")
            raise
        transcript = " ".join(str(result.get("text", "")).split())
        if not transcript:
            raise VoiceEngineError("STT_FAILED", "O STT local não produziu uma transcrição.")
        turn.transcript = transcript; turn.timestamps["transcript_ready"] = time.perf_counter()
        yield {"type": "transcript", "turn_id": turn.turn_id, "text": transcript, "final": True, "latency_ms": round((turn.timestamps["transcript_ready"] - started) * 1000)}
        generation = session.playback_generation
        if session.pending_action_id:
            intent = confirmation_intent(transcript)
            if intent is None:
                self.turns.transition(turn, "waiting_confirmation"); session.status = "waiting_confirmation"
                message = "Preciso de uma confirmação inequívoca. Diga ‘confirmo’ ou ‘cancele’."
                yield {"type": "confirmation_required", "action_id": session.pending_action_id, "message": message, "ambiguous": True}
                for event in await self._speech_events(session, message, "confirmation", generation): yield event
                return
            cognitive_state_service.set_state(CognitiveState.THINKING, reason="voice_confirmation")
            confirmed = await self.agent.confirm_action(session.pending_action_id, intent)
            session.pending_action_id = None; session.conversation_id = confirmed.get("conversation_id") or session.conversation_id
            message = confirmed.get("message", "Ação executada." if intent else "Ação cancelada.")
            yield {"type": "tool_result", "approved": intent, "status": confirmed.get("status"), "result": confirmed}
            yield {"type": "assistant_text", "text": message, "final": True, "message_id": confirmed.get("message_id")}
            for event in await self._speech_events(session, message, "confirmation", generation): yield event
        else:
            self.turns.transition(turn, "processing"); session.status = "processing"; cognitive_state_service.set_state(CognitiveState.THINKING, reason="voice_agent")
            chunker = SpeechChunker(); full_text = ""
            async for event in self.agent.stream(transcript, session.conversation_id):
                if event.get("type") == "start":
                    session.conversation_id = event.get("conversation_id")
                    repository.execute("UPDATE voice_sessions_metadata SET conversation_id=? WHERE id=?", (session.conversation_id, session_id))
                    yield {"type": "thinking", "conversation_id": session.conversation_id, "agent_run_id": event.get("agent_run_id")}
                elif event.get("type") == "token":
                    piece = event.get("content", ""); full_text += piece
                    yield {"type": "assistant_text", "text": piece, "final": False}
                    for sentence in chunker.feed(piece):
                        for speech_event in await self._speech_events(session, sentence, "neutral", generation): yield speech_event
                elif event.get("type") == "action":
                    action = event.get("action", {})
                    if action.get("status") == "pending_confirmation":
                        session.pending_action_id = action.get("action_id")
                        yield {"type": "confirmation_required", "action": action, "action_id": session.pending_action_id, "ambiguous": False}
                elif event.get("type") == "done":
                    turn.assistant_message_id = event.get("message_id")
                    yield {"type": "assistant_text", "text": full_text, "final": True, "message_id": turn.assistant_message_id, "actions": event.get("actions", [])}
            for sentence in chunker.flush():
                for speech_event in await self._speech_events(session, sentence, "neutral", generation): yield speech_event
        self.turns.transition(turn, "speaking"); session.status = "speaking"; cognitive_state_service.set_state(CognitiveState.SPEAKING, reason="voice_playback")
        yield {"type": "speaking", "turn_id": turn.turn_id, "state": "SPEAKING"}
        self.turns.transition(turn, "waiting"); session.status = "listening"
        repository.execute("UPDATE voice_sessions_metadata SET turn_count=? WHERE id=?", (len(session.turns), session_id))
        cognitive_state_service.set_state(CognitiveState.LISTENING, reason="voice_turn_complete")
        yield {"type": "listening", "turn_id": turn.turn_id, "state": "LISTENING"}

    def status(self) -> dict[str, Any]:
        return {
            "active_sessions": len(self.sessions), "vad": self.vad.health(), "resource_policy": self.resources.policy(),
            "privacy": {"raw_microphone_saved": False, "external_audio_transfer": False, "transport": "localhost_websocket"},
        }
