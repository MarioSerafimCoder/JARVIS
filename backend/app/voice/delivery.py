from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any


class SpeechTextNormalizer:
    NUMBER_WORDS = {
        0: "zero", 1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito", 9: "nove",
        10: "dez", 11: "onze", 12: "doze", 13: "treze", 14: "quatorze", 15: "quinze", 16: "dezesseis", 17: "dezessete",
        18: "dezoito", 19: "dezenove", 20: "vinte", 30: "trinta", 40: "quarenta", 50: "cinquenta", 60: "sessenta",
    }

    @classmethod
    def _number(cls, value: int) -> str:
        if value in cls.NUMBER_WORDS:
            return cls.NUMBER_WORDS[value]
        if 20 < value < 70:
            tens = value // 10 * 10
            return f"{cls.NUMBER_WORDS[tens]} e {cls.NUMBER_WORDS[value % 10]}"
        return str(value)

    def normalize(self, text: str) -> str:
        code_blocks = len(re.findall(r"```[\s\S]*?```", text))
        text = re.sub(r"```[\s\S]*?```", " Adicionei um bloco de código à resposta. ", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"https?://\S+", "um endereço da internet", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"^\s*[-*#>]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda match: f"{self._number(int(match.group(1)))} e {self._number(int(match.group(2)))}", text)
        text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", lambda match: f"{self._number(int(match.group(1)))} do {self._number(int(match.group(2)))} de {match.group(3)}", text)
        abbreviations = {"Qwen": "Quen", "GB": "gigabytes", "MB": "megabytes", "CPU": "C P U", "GPU": "G P U", "URL": "U R L"}
        for source, target in abbreviations.items():
            text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        if code_blocks > 1:
            text = text.replace("Adicionei um bloco de código à resposta.", "Adicionei blocos de código à resposta.", 1)
        return text


class SpeechChunker:
    def __init__(self, maximum_chars: int = 280):
        self.buffer = ""; self.maximum_chars = maximum_chars

    def feed(self, text: str) -> list[str]:
        self.buffer += text
        ready: list[str] = []
        while True:
            match = re.search(r"(?<=[.!?])\s+", self.buffer)
            if not match:
                break
            sentence = self.buffer[:match.end()].strip(); self.buffer = self.buffer[match.end():]
            if sentence:
                ready.append(sentence)
        if self.buffer.rstrip().endswith((".", "!", "?")):
            sentence = self.buffer.strip(); self.buffer = ""
            if sentence:
                ready.append(sentence)
        if len(self.buffer) > self.maximum_chars:
            split_at = self.buffer.rfind(" ", 0, self.maximum_chars)
            split_at = split_at if split_at > 40 else self.maximum_chars
            ready.append(self.buffer[:split_at].strip()); self.buffer = self.buffer[split_at:].lstrip()
        return ready

    def flush(self) -> list[str]:
        remainder = self.buffer.strip(); self.buffer = ""
        return [remainder] if remainder else []


class TTSCache:
    def __init__(self, directory: Path, max_size_bytes: int = 256 * 1024 * 1024):
        self.directory = directory; self.max_size_bytes = max_size_bytes
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(profile: str, speech_text: str, style: str, config: dict[str, Any]) -> str:
        payload = json.dumps({"profile": profile, "speech_text": speech_text, "style": style, "config": config}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> bytes | None:
        path = self.directory / f"{key}.wav"
        if not path.exists():
            return None
        path.touch(); return path.read_bytes()

    def put(self, key: str, audio: bytes) -> Path:
        path = self.directory / f"{key}.wav"; path.write_bytes(audio); self.cleanup(); return path

    def cancel(self, keys: list[str]) -> None:
        for key in keys:
            path = self.directory / f"{key}.wav"
            if path.exists():
                path.unlink()

    def cleanup(self) -> int:
        files = sorted(self.directory.glob("*.wav"), key=lambda item: item.stat().st_mtime)
        total = sum(item.stat().st_size for item in files); removed = 0
        for path in files:
            if total <= self.max_size_bytes:
                break
            size = path.stat().st_size; path.unlink(); total -= size; removed += 1
        return removed


class VoiceResourceManager:
    MODES = {"AUTO", "LOW_LATENCY", "BALANCED", "LOW_VRAM"}

    def __init__(self, mode: str = "AUTO"):
        self.mode = mode if mode in self.MODES else "AUTO"

    def policy(self) -> dict[str, Any]:
        policies = {
            "AUTO": {"stt": "cpu_int8_small", "tts": "gpu_sequential", "unload_tts_idle_seconds": 180},
            "LOW_LATENCY": {"stt": "gpu_float16_small", "tts": "gpu_resident", "unload_tts_idle_seconds": 0},
            "BALANCED": {"stt": "cpu_int8_small", "tts": "gpu_resident", "unload_tts_idle_seconds": 300},
            "LOW_VRAM": {"stt": "cpu_int8_small", "tts": "gpu_sequential", "unload_tts_idle_seconds": 45},
        }
        return {"mode": self.mode, **policies[self.mode], "heavy_processing": "sequential"}
