from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any

import httpx

from app.voice.contracts import SpeechToTextProvider, TextToSpeechProvider, VoiceActivityDetector, VoiceEngineError


class EnergyVADProvider(VoiceActivityDetector):
    """Dependency-free PCM16 VAD. Browser VAD remains the fallback for encoded WebM chunks."""

    name = "energy_pcm16"

    def __init__(self, speech_threshold: float = 0.018, minimum_speech_ms: int = 220, silence_end_ms: int = 850, maximum_utterance_seconds: int = 30):
        self.speech_threshold = speech_threshold
        self.minimum_speech_ms = minimum_speech_ms
        self.silence_end_ms = silence_end_ms
        self.maximum_utterance_seconds = maximum_utterance_seconds

    def detect(self, pcm16: bytes, *, sample_rate: int = 16000) -> bool:
        if len(pcm16) < 2:
            return False
        count = len(pcm16) // 2
        samples = struct.unpack(f"<{count}h", pcm16[: count * 2])
        rms = math.sqrt(sum(float(value) ** 2 for value in samples) / count) / 32768.0
        duration_ms = count / max(sample_rate, 1) * 1000
        return duration_ms >= self.minimum_speech_ms and rms >= self.speech_threshold

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready", "provider": self.name, "speech_threshold": self.speech_threshold,
            "minimum_speech_ms": self.minimum_speech_ms, "silence_end_ms": self.silence_end_ms,
            "maximum_utterance_seconds": self.maximum_utterance_seconds,
        }


class VoiceWorkerProvider(SpeechToTextProvider, TextToSpeechProvider):
    """Localhost client for the isolated Whisper/XTTS process. It never uses a cloud API."""

    name = "local_voice_worker"

    def __init__(self, base_url: str, timeout: float = 300.0):
        if not base_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("O Voice Worker deve estar restrito ao localhost.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def initialize(self) -> None:
        health = await self.health()
        if health.get("status") != "ready":
            raise VoiceEngineError("TTS_UNAVAILABLE", "Voice Worker local não está disponível.")

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise VoiceEngineError("VOICE_SESSION_FAILED", f"Voice Worker local indisponível: {exc}") from exc

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/webm", language: str = "pt") -> dict[str, Any]:
        extension = ".wav" if "wav" in mime_type else ".webm"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/transcribe",
                    files={"audio": (f"utterance{extension}", audio, mime_type)},
                    data={"language": language},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise VoiceEngineError("STT_FAILED", f"Falha no STT local: {exc}") from exc

    async def build_voice_profile(self, references: list[Path], fingerprint: str, profile_dir: Path) -> dict[str, Any]:
        return await self._request_json(
            "POST", "/profile/build",
            json={"fingerprint": fingerprint, "references": [str(path.resolve()) for path in references], "profile_dir": str(profile_dir.resolve())},
        )

    async def synthesize(self, text: str, *, profile_dir: Path, style: str = "neutral", speed: float = 1.0) -> tuple[bytes, dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/synthesize",
                    json={"text": text, "profile_dir": str(profile_dir.resolve()), "style": style, "speed": speed},
                )
                response.raise_for_status()
                metadata = {
                    "provider": response.headers.get("X-Voice-Provider", "xtts_v2"),
                    "profile": response.headers.get("X-Voice-Profile", "Jarvis"),
                    "duration_seconds": float(response.headers.get("X-Audio-Duration", "0")),
                    "generation_seconds": float(response.headers.get("X-Generation-Seconds", "0")),
                    "hardware": response.headers.get("X-Voice-Hardware", "unknown"),
                }
                return response.content, metadata
        except httpx.HTTPError as exc:
            raise VoiceEngineError("TTS_FAILED", f"Falha no TTS local: {exc}") from exc

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
            return {"status": "unavailable", "provider": self.name, "reason": "worker_offline"}

    async def get_model_info(self) -> dict[str, Any]:
        return await self._request_json("GET", "/models")

    async def get_voice_info(self) -> dict[str, Any]:
        return await self._request_json("GET", "/profile")

    async def unload(self) -> None:
        try:
            await self._request_json("POST", "/unload")
        except VoiceEngineError:
            return None
