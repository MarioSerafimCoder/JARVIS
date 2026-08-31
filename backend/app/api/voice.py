from __future__ import annotations

import asyncio
import base64
import json
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.container import voice_profile_manager, voice_session_manager, voice_worker_provider
from app.voice.contracts import VoiceEngineError
from app.voice.delivery import SpeechTextNormalizer

router = APIRouter(prefix="/voice", tags=["voice"])


def voice_error(exc: VoiceEngineError) -> HTTPException:
    status = 409 if exc.code == "VOICE_PROFILE_NOT_READY" else 503
    return HTTPException(status, detail={"code": exc.code, "message": str(exc)})


class SynthesisInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    style: str = Field(default="neutral", pattern="^(neutral|confirmation|warning|serious|dry_humor)$")
    speed: float = Field(default=1.0, ge=0.75, le=1.25)


class VoiceSettingsInput(BaseModel):
    resource_mode: str = Field(default="AUTO", pattern="^(AUTO|LOW_LATENCY|BALANCED|LOW_VRAM)$")
    speech_threshold: float = Field(default=0.018, ge=0.005, le=0.2)
    silence_end_ms: int = Field(default=850, ge=300, le=3000)
    echo_cancellation: bool = True
    noise_suppression: bool = True
    auto_gain_control: bool = True
    barge_in_sensitivity: float = Field(default=0.035, ge=0.01, le=0.2)
    include_references_in_backup: bool = False


def current_settings() -> dict[str, Any]:
    from app.services.repository import repository
    row = repository.row("SELECT value_json FROM voice_settings WHERE key='voice_config'")
    return json.loads(row["value_json"]) if row else VoiceSettingsInput().model_dump()


@router.get("/settings")
def get_voice_settings() -> dict[str, Any]:
    return current_settings()


@router.put("/settings")
def update_voice_settings(payload: VoiceSettingsInput) -> dict[str, Any]:
    from app.core.database import utc_now
    from app.services.repository import repository
    values = payload.model_dump()
    repository.execute("INSERT OR REPLACE INTO voice_settings VALUES (?,?,?)", ("voice_config", json.dumps(values), utc_now()))
    repository.execute("INSERT OR REPLACE INTO voice_settings VALUES (?,?,?)", ("include_references_in_backup", json.dumps(payload.include_references_in_backup), utc_now()))
    voice_session_manager.resources.mode = payload.resource_mode
    if hasattr(voice_session_manager.vad, "speech_threshold"):
        voice_session_manager.vad.speech_threshold = payload.speech_threshold
        voice_session_manager.vad.silence_end_ms = payload.silence_end_ms
    return values


@router.get("/status")
async def status() -> dict[str, Any]:
    worker = await voice_worker_provider.health()
    profile = await voice_profile_manager.status()
    return {**voice_session_manager.status(), "worker": worker, "profile": profile, "text_fallback": True}


@router.get("/profile")
async def profile() -> dict[str, Any]:
    return await voice_profile_manager.status()


@router.post("/profile/import")
async def import_references() -> dict[str, Any]:
    imported = voice_profile_manager.import_project_references()
    return {**imported, "profile": await voice_profile_manager.status()}


@router.get("/profile/references")
def references() -> list[dict[str, Any]]:
    return voice_profile_manager.analyze()


@router.post("/profile/build")
async def build_profile() -> dict[str, Any]:
    voice_profile_manager.import_project_references()
    try:
        return await voice_profile_manager.build()
    except VoiceEngineError as exc:
        raise voice_error(exc) from exc


@router.post("/synthesize")
async def synthesize(payload: SynthesisInput) -> Response:
    profile_state = await voice_profile_manager.status()
    if profile_state["status"] != "READY":
        raise voice_error(VoiceEngineError("VOICE_PROFILE_NOT_READY", "Perfil vocal do Jarvis ainda não configurado."))
    speech_text = SpeechTextNormalizer().normalize(payload.text)
    try:
        audio, metadata = await voice_worker_provider.synthesize(speech_text, profile_dir=voice_profile_manager.profile_dir, style=payload.style, speed=payload.speed)
    except VoiceEngineError as exc:
        raise voice_error(exc) from exc
    return Response(audio, media_type="audio/wav", headers={"X-Speech-Text": speech_text[:500], "X-Voice-Provider": str(metadata.get("provider", "XTTS-v2")), "X-Voice-Profile": "Jarvis"})


@router.post("/microphone-test")
async def microphone_test(audio: UploadFile = File(...), language: str = Form("pt")) -> dict[str, Any]:
    data = await audio.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "A amostra de microfone excede 20 MB.")
    try:
        return await voice_worker_provider.transcribe(data, mime_type=audio.content_type or "audio/webm", language=language)
    except VoiceEngineError as exc:
        raise voice_error(exc) from exc


async def _run_utterance(session_id: str, audio: bytes, mime_type: str, outgoing: asyncio.Queue[dict[str, Any]]) -> None:
    try:
        async for event in voice_session_manager.process_utterance(session_id, audio, mime_type=mime_type):
            await outgoing.put(event)
    except asyncio.CancelledError:
        await outgoing.put(voice_session_manager.interrupt(session_id))
        raise
    except VoiceEngineError as exc:
        await outgoing.put({"type": "error", "error": {"code": exc.code, "message": str(exc)}, "text_fallback": True})
    except Exception as exc:
        await outgoing.put({"type": "error", "error": {"code": "VOICE_SESSION_FAILED", "message": str(exc)}, "text_fallback": True})


@router.websocket("/session")
async def voice_session(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin", "")
    if origin and not origin.startswith(("http://127.0.0.1:", "http://localhost:")):
        await websocket.close(code=1008, reason="Voice Session aceita apenas origens localhost.")
        return
    await websocket.accept()
    session = None; current_task: asyncio.Task | None = None; outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue(); mime_type = "audio/webm"

    async def sender() -> None:
        while True:
            await websocket.send_json(await outgoing.get())

    sender_task = asyncio.create_task(sender())
    try:
        while True:
            message = await websocket.receive()
            if message.get("bytes") is not None:
                audio = message["bytes"]
                if current_task and not current_task.done():
                    await outgoing.put({"type": "error", "error": {"code": "VOICE_SESSION_FAILED", "message": "Um turno ainda está em processamento."}})
                elif session:
                    current_task = asyncio.create_task(_run_utterance(session.session_id, audio, mime_type, outgoing))
                continue
            text = message.get("text")
            if text is None:
                continue
            payload = json.loads(text); event_type = payload.get("type")
            if event_type == "session_start":
                if session:
                    continue
                mime_type = str(payload.get("mime_type") or "audio/webm")
                session = voice_session_manager.open(payload.get("conversation_id"))
                await outgoing.put({"type": "session_ready", "session_id": session.session_id, "state": "LISTENING", "protocol_version": 1})
                await outgoing.put({"type": "listening", "state": "LISTENING"})
            elif event_type == "audio_chunk" and session:
                audio = base64.b64decode(payload.get("audio", ""), validate=True)
                if not current_task or current_task.done():
                    current_task = asyncio.create_task(_run_utterance(session.session_id, audio, str(payload.get("mime_type") or mime_type), outgoing))
            elif event_type == "interrupt" and session:
                if current_task and not current_task.done(): current_task.cancel()
                await outgoing.put(voice_session_manager.interrupt(session.session_id))
            elif event_type in {"playback_started", "playback_finished", "playback_interrupted"} and session:
                try:
                    await outgoing.put(voice_session_manager.playback_event(session.session_id, str(payload.get("queue_id", "")), event_type))
                except VoiceEngineError as exc:
                    await outgoing.put({"type": "error", "error": {"code": exc.code, "message": str(exc)}})
            elif event_type in {"mute", "unmute"} and session:
                updated = voice_session_manager.mute(session.session_id, event_type == "mute")
                await outgoing.put({"type": event_type, "muted": updated.muted})
            elif event_type == "confirmation" and session:
                try:
                    for event in await voice_session_manager.confirm_visual(session.session_id, payload.get("approved") is True):
                        await outgoing.put(event)
                except VoiceEngineError as exc:
                    await outgoing.put({"type": "error", "error": {"code": exc.code, "message": str(exc)}})
            elif event_type == "session_stop":
                break
    except (WebSocketDisconnect, json.JSONDecodeError, ValueError):
        pass
    finally:
        if current_task and not current_task.done():
            current_task.cancel();
            with suppress(asyncio.CancelledError): await current_task
        if session:
            with suppress(VoiceEngineError): await voice_session_manager.close(session.session_id)
        sender_task.cancel()
        with suppress(asyncio.CancelledError): await sender_task
