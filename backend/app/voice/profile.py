from __future__ import annotations

import hashlib
import json
import shutil
import struct
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, Settings
from app.core.database import utc_now
from app.services.repository import repository
from app.voice.contracts import TextToSpeechProvider, VoiceEngineError, VoiceProfileProvider

ALLOWED_REFERENCE_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def _synchsafe(value: bytes) -> int:
    return ((value[0] & 0x7F) << 21) | ((value[1] & 0x7F) << 14) | ((value[2] & 0x7F) << 7) | (value[3] & 0x7F)


def inspect_mp3(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    offset = 10 + _synchsafe(data[6:10]) if data[:3] == b"ID3" and len(data) >= 10 else 0
    bitrate_v1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    bitrate_v2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
    sample_rates = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
    frames = 0; total_samples = 0; bitrate_sum = 0; first_rate = 0; channels = 0
    while offset + 4 <= len(data):
        header = int.from_bytes(data[offset:offset + 4], "big")
        if (header & 0xFFE00000) != 0xFFE00000:
            offset += 1; continue
        version = (header >> 19) & 0x3; layer = (header >> 17) & 0x3
        bitrate_index = (header >> 12) & 0xF; rate_index = (header >> 10) & 0x3
        if version == 1 or layer != 1 or rate_index == 3 or bitrate_index in {0, 15}:
            offset += 1; continue
        bitrate = (bitrate_v1 if version == 3 else bitrate_v2)[bitrate_index] * 1000
        sample_rate = sample_rates[version][rate_index]
        padding = (header >> 9) & 1
        samples_per_frame = 1152 if version == 3 else 576
        frame_length = (144 if version == 3 else 72) * bitrate // sample_rate + padding
        if frame_length < 4 or offset + frame_length > len(data):
            offset += 1; continue
        if not first_rate:
            first_rate = sample_rate; channels = 1 if ((header >> 6) & 0x3) == 3 else 2
        frames += 1; total_samples += samples_per_frame; bitrate_sum += bitrate; offset += frame_length
    if not frames or not first_rate:
        raise ValueError("Nenhum frame MP3 válido encontrado.")
    return {
        "duration_seconds": round(total_samples / first_rate, 3), "sample_rate": first_rate,
        "channels": channels, "bit_depth": None, "bitrate_kbps": round(bitrate_sum / frames / 1000),
        "leading_silence_ms": None, "trailing_silence_ms": None, "peak_dbfs": None,
        "clipping_apparent": None, "analysis_note": "Metadados MP3 validados; silêncio, pico e clipping exigem decoder PCM no Voice Worker.",
    }


def inspect_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        channels, width, rate, frames = stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()
        raw = stream.readframes(frames)
    if width != 2:
        return {
            "duration_seconds": round(frames / rate, 3), "sample_rate": rate, "channels": channels,
            "bit_depth": width * 8, "bitrate_kbps": round(rate * channels * width * 8 / 1000),
            "leading_silence_ms": None, "trailing_silence_ms": None, "peak_dbfs": None,
            "clipping_apparent": None, "analysis_note": "PCM diferente de 16 bits; análise de amplitude adiada ao Voice Worker.",
        }
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    peak = max((abs(value) for value in values), default=0)
    threshold = 32768 * 0.01
    frame_values = [max(abs(values[index + channel]) for channel in range(channels)) for index in range(0, len(values) - channels + 1, channels)]
    first = next((index for index, value in enumerate(frame_values) if value >= threshold), len(frame_values))
    last = next((index for index, value in enumerate(reversed(frame_values)) if value >= threshold), len(frame_values))
    peak_dbfs = None if not peak else round(20 * __import__("math").log10(peak / 32768), 2)
    return {
        "duration_seconds": round(frames / rate, 3), "sample_rate": rate, "channels": channels,
        "bit_depth": width * 8, "bitrate_kbps": round(rate * channels * width * 8 / 1000),
        "leading_silence_ms": round(first / rate * 1000), "trailing_silence_ms": round(last / rate * 1000),
        "peak_dbfs": peak_dbfs, "clipping_apparent": peak >= 32760,
        "analysis_note": "Amplitude PCM16 analisada sem modificar o original.",
    }


class VoiceProfileManager(VoiceProfileProvider):
    def __init__(self, settings: Settings, provider: TextToSpeechProvider):
        self.settings = settings; self.provider = provider

    @property
    def references_dir(self) -> Path:
        return self.settings.voice_path / "references"

    @property
    def profile_dir(self) -> Path:
        return self.settings.voice_path / "profile"

    def reference_files(self) -> list[Path]:
        return sorted(path for path in self.references_dir.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_REFERENCE_EXTENSIONS)

    def import_project_references(self) -> dict[str, Any]:
        source = (PROJECT_ROOT / "Jarvis-Voice").resolve()
        if not source.exists() or not source.is_dir():
            return {"imported": 0, "source": str(source), "available": False}
        imported = 0
        self.references_dir.mkdir(parents=True, exist_ok=True)
        for item in sorted(source.iterdir()):
            if not item.is_file() or item.suffix.lower() not in ALLOWED_REFERENCE_EXTENSIONS:
                continue
            target = self.references_dir / item.name
            if not target.exists() or target.stat().st_size != item.stat().st_size:
                shutil.copy2(item, target); imported += 1
        return {"imported": imported, "source": str(source), "available": True, "total": len(self.reference_files())}

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for path in self.reference_files():
            stat = path.stat()
            digest.update(path.name.encode("utf-8")); digest.update(str(stat.st_size).encode()); digest.update(str(stat.st_mtime_ns).encode())
        return digest.hexdigest()

    def analyze(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for path in self.reference_files():
            try:
                details = inspect_wav(path) if path.suffix.lower() == ".wav" else inspect_mp3(path) if path.suffix.lower() == ".mp3" else {
                    "duration_seconds": None, "sample_rate": None, "channels": None, "bit_depth": None,
                    "bitrate_kbps": None, "leading_silence_ms": None, "trailing_silence_ms": None,
                    "peak_dbfs": None, "clipping_apparent": None, "analysis_note": "Formato será decodificado no Voice Worker.",
                }
                status = "GOOD" if path.suffix.lower() == ".wav" and not details.get("clipping_apparent") else "ACCEPTABLE"
                reports.append({"filename": path.name, "size_bytes": path.stat().st_size, **details, "status": status})
            except Exception as exc:
                reports.append({"filename": path.name, "size_bytes": path.stat().st_size, "duration_seconds": None, "status": "POOR", "analysis_note": str(exc)})
        return reports

    async def status(self) -> dict[str, Any]:
        files = self.reference_files(); fingerprint = self.fingerprint() if files else ""
        record = repository.row("SELECT * FROM voice_profiles WHERE profile_name='Jarvis'")
        worker = await self.provider.health()
        manifest_path = self.profile_dir / "manifest.json"
        status = "REFERENCES_MISSING" if not files else "NOT_BUILT"
        if record:
            status = record["status"]
            if record.get("fingerprint") and record["fingerprint"] != fingerprint:
                status = "OUTDATED"
            if status == "READY":
                if not manifest_path.exists():
                    status = "NOT_BUILT"
                else:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    artifact = manifest.get("artifact")
                    if not artifact or not (self.profile_dir / Path(artifact).name).exists():
                        status = "NOT_BUILT"
        reports = self.analyze()
        return {
            "profile_name": "Jarvis", "status": status, "provider": "XTTS-v2", "worker": worker,
            "reference_count": len(files), "total_duration_seconds": round(sum(item.get("duration_seconds") or 0 for item in reports), 2),
            "fingerprint": fingerprint, "language": "pt-BR", "voice_dna": {
                "perceived_gender": "male", "delivery": "calm", "pace": "controlled", "energy": "low_to_medium",
                "formality": "refined", "humor": "dry_subtle", "urgency": "controlled",
            },
        }

    async def build(self) -> dict[str, Any]:
        files = self.reference_files()
        if not files:
            raise VoiceEngineError("VOICE_PROFILE_NOT_READY", "Nenhuma referência vocal autorizada foi encontrada.")
        worker = await self.provider.health()
        if worker.get("tts", {}).get("status", worker.get("status")) != "ready":
            raise VoiceEngineError("TTS_UNAVAILABLE", "XTTS não está pronto no Voice Worker local. Nenhuma voz genérica será usada.")
        fingerprint = self.fingerprint(); now = utc_now()
        repository.execute(
            "INSERT OR REPLACE INTO voice_profiles VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), "Jarvis", "XTTS-v2", "BUILDING", fingerprint, len(files), 0, "{}", now, now),
        )
        try:
            result = await self.provider.build_voice_profile(files, fingerprint, self.profile_dir)
            reports = self.analyze(); duration = sum(item.get("duration_seconds") or 0 for item in reports)
            manifest = {
                "profile_name": "Jarvis", "provider": "XTTS-v2", "fingerprint": fingerprint,
                "references": [item.name for item in files], "reference_count": len(files),
                "total_duration_seconds": round(duration, 3), "language": "pt-BR",
                "built_at": datetime.now(timezone.utc).isoformat(), "artifact": result.get("artifact"),
            }
            (self.profile_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            repository.execute(
                "UPDATE voice_profiles SET status='READY',total_duration_seconds=?,manifest_json=?,updated_at=? WHERE profile_name='Jarvis'",
                (duration, json.dumps(manifest, ensure_ascii=False), utc_now()),
            )
            return {**manifest, "status": "READY"}
        except Exception:
            repository.execute("UPDATE voice_profiles SET status='FAILED',updated_at=? WHERE profile_name='Jarvis'", (utc_now(),))
            raise

    def report_markdown(self) -> str:
        rows = self.analyze(); total = sum(item.get("duration_seconds") or 0 for item in rows)
        lines = [
            "# Relatório das referências vocais", "", "As referências originais foram preservadas. Nenhum áudio foi enviado para serviços externos.", "",
            f"- Arquivos: {len(rows)}", f"- Duração mensurável total: {total:.2f} s", f"- Fingerprint: `{self.fingerprint()}`", "",
            "| Arquivo | Duração | Taxa | Canais | Bits | Silêncio inicial/final | Pico | Clipping | Status |", "|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
        for item in rows:
            silence = "n/d" if item.get("leading_silence_ms") is None else f"{item['leading_silence_ms']}/{item['trailing_silence_ms']} ms"
            lines.append(
                f"| {item['filename'].replace('|', '/')} | {item.get('duration_seconds') or 'n/d'} s | {item.get('sample_rate') or 'n/d'} Hz | "
                f"{item.get('channels') or 'n/d'} | {item.get('bit_depth') or 'n/d'} | {silence} | {item.get('peak_dbfs') if item.get('peak_dbfs') is not None else 'n/d'} | "
                f"{item.get('clipping_apparent') if item.get('clipping_apparent') is not None else 'n/d'} | {item['status']} |"
            )
        lines += ["", "## Observações", "", "Arquivos MP3 tiveram estrutura, duração, sample rate e canais validados diretamente. Medidas PCM de silêncio, pico e clipping serão completadas pelo Voice Worker durante a preparação; a ausência dessas medidas não é tratada como aprovação automática."]
        return "\n".join(lines) + "\n"
