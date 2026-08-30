from __future__ import annotations

import io
import math
import struct
import wave
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import Any


class VoiceEngineError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SpeechToTextProvider(ABC):
    name = "base_stt"

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/webm", language: str = "pt") -> dict[str, Any]: ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_model_info(self) -> dict[str, Any]: ...

    @abstractmethod
    async def unload(self) -> None: ...


class VoiceActivityDetector(ABC):
    name = "base_vad"

    @abstractmethod
    def detect(self, pcm16: bytes, *, sample_rate: int = 16000) -> bool: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...


class TextToSpeechProvider(ABC):
    name = "base_tts"

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def build_voice_profile(self, references: list[Path], fingerprint: str, profile_dir: Path) -> dict[str, Any]: ...

    @abstractmethod
    async def synthesize(self, text: str, *, profile_dir: Path, style: str = "neutral", speed: float = 1.0) -> tuple[bytes, dict[str, Any]]: ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_voice_info(self) -> dict[str, Any]: ...

    @abstractmethod
    async def unload(self) -> None: ...


class VoiceProfileProvider(ABC):
    @abstractmethod
    async def status(self) -> dict[str, Any]: ...

    @abstractmethod
    async def build(self) -> dict[str, Any]: ...


class FakeSTTProvider(SpeechToTextProvider):
    name = "fake_stt"

    def __init__(self, transcripts: list[str] | None = None):
        self.transcripts = deque(transcripts or ["Teste de voz."])
        self.initialized = False

    async def initialize(self) -> None:
        self.initialized = True

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/webm", language: str = "pt") -> dict[str, Any]:
        if not audio:
            raise VoiceEngineError("STT_FAILED", "O áudio recebido está vazio.")
        text = self.transcripts.popleft() if self.transcripts else "Teste de voz."
        return {"text": text, "language": language, "duration_seconds": 0.1, "provider": self.name}

    async def health(self) -> dict[str, Any]:
        return {"status": "ready", "provider": self.name}

    async def get_model_info(self) -> dict[str, Any]:
        return {"provider": self.name, "model": "deterministic-test"}

    async def unload(self) -> None:
        self.initialized = False


class FakeTTSProvider(TextToSpeechProvider):
    name = "fake_tts"

    def __init__(self):
        self.synthesis_calls: list[dict[str, Any]] = []
        self.profile_fingerprint: str | None = None

    async def initialize(self) -> None:
        return None

    async def build_voice_profile(self, references: list[Path], fingerprint: str, profile_dir: Path) -> dict[str, Any]:
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "conditioning.fake").write_text(fingerprint, encoding="utf-8")
        self.profile_fingerprint = fingerprint
        return {"status": "ready", "provider": self.name, "artifact": "conditioning.fake"}

    @staticmethod
    def _wave_bytes(duration: float = 0.12, frequency: float = 220.0) -> bytes:
        sample_rate = 16000
        stream = io.BytesIO()
        with wave.open(stream, "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(sample_rate)
            frames = [struct.pack("<h", int(1400 * math.sin(2 * math.pi * frequency * i / sample_rate))) for i in range(int(sample_rate * duration))]
            output.writeframes(b"".join(frames))
        return stream.getvalue()

    async def synthesize(self, text: str, *, profile_dir: Path, style: str = "neutral", speed: float = 1.0) -> tuple[bytes, dict[str, Any]]:
        if not (profile_dir / "conditioning.fake").exists():
            raise VoiceEngineError("VOICE_PROFILE_NOT_READY", "Perfil de teste não construído.")
        self.synthesis_calls.append({"text": text, "style": style, "speed": speed})
        audio = self._wave_bytes()
        return audio, {"provider": self.name, "profile": "Jarvis", "duration_seconds": 0.12, "hardware": "test"}

    async def health(self) -> dict[str, Any]:
        return {"status": "ready", "provider": self.name}

    async def get_voice_info(self) -> dict[str, Any]:
        return {"provider": self.name, "profile": "Jarvis", "fingerprint": self.profile_fingerprint}

    async def unload(self) -> None:
        return None


class FakeVADProvider(VoiceActivityDetector):
    name = "fake_vad"

    def __init__(self, detected: bool = True):
        self.detected = detected

    def detect(self, pcm16: bytes, *, sample_rate: int = 16000) -> bool:
        return bool(pcm16) and self.detected

    def health(self) -> dict[str, Any]:
        return {"status": "ready", "provider": self.name}
