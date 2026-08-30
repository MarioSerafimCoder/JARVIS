from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

ROOT = Path(os.getenv("JARVIS_VOICE_ROOT", Path(__file__).resolve().parents[2] / "data" / "voices" / "jarvis")).resolve()
for name in ("references", "profile", "cache", "temp", "models"):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Jarvis Local Voice Worker", version="0.1.0")
_whisper = None
_xtts = None


def safe_path(value: str, expected_parent: Path) -> Path:
    path = Path(value).resolve()
    try:
        path.relative_to(expected_parent.resolve())
    except ValueError as exc:
        raise HTTPException(422, "Caminho fora do diretório vocal autorizado.") from exc
    return path


def package_status(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def load_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        model_path = ROOT / "models" / "faster-whisper-small"
        if not model_path.exists():
            raise HTTPException(503, "STT_MODEL_NOT_FOUND: faster-whisper-small não está instalado localmente.")
        _whisper = WhisperModel(str(model_path), device="cpu", compute_type="int8", local_files_only=True, cpu_threads=max(2, (os.cpu_count() or 4) // 2))
    return _whisper


def load_xtts():
    global _xtts
    if os.getenv("JARVIS_XTTS_LICENSE_ACCEPTED") != "1":
        raise HTTPException(409, "A licença não comercial CPML do XTTS-v2 ainda não foi aceita.")
    if _xtts is None:
        from TTS.api import TTS
        import torch
        _xtts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda" if torch.cuda.is_available() else "cpu")
    return _xtts


@app.get("/health")
def health() -> dict[str, Any]:
    stt_model = ROOT / "models" / "faster-whisper-small"
    tts_package = package_status("TTS") and package_status("torch")
    stt_status = "ready" if package_status("faster_whisper") and stt_model.exists() else "model_not_found" if package_status("faster_whisper") else "dependency_missing"
    tts_status = "ready" if tts_package and os.getenv("JARVIS_XTTS_LICENSE_ACCEPTED") == "1" else "license_not_accepted" if tts_package else "dependency_missing"
    return {"status": "ready" if stt_status == "ready" or tts_status == "ready" else "degraded", "architecture": "localhost_isolated_process", "stt": {"status": stt_status, "model": "small", "compute": "cpu_int8"}, "tts": {"status": tts_status, "model": "XTTS-v2", "license": "CPML non-commercial"}}


@app.get("/models")
def models() -> dict[str, Any]:
    return health()


@app.get("/profile")
def profile() -> dict[str, Any]:
    manifest = ROOT / "profile" / "manifest.json"
    return json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {"status": "not_built", "profile": "Jarvis"}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("pt")) -> dict[str, Any]:
    data = await audio.read()
    if not data:
        raise HTTPException(422, "STT_FAILED: áudio vazio.")
    suffix = Path(audio.filename or "utterance.webm").suffix or ".webm"
    started = time.perf_counter()
    with tempfile.NamedTemporaryFile(dir=ROOT / "temp", suffix=suffix, delete=False) as stream:
        stream.write(data); temp_path = Path(stream.name)
    try:
        segments, info = load_whisper().transcribe(str(temp_path), language=language, beam_size=3, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        return {"text": text, "language": info.language, "duration_seconds": info.duration, "generation_seconds": round(time.perf_counter() - started, 4), "provider": "faster-whisper", "model": "small", "compute": "cpu_int8"}
    finally:
        temp_path.unlink(missing_ok=True)


class BuildInput(BaseModel):
    fingerprint: str
    references: list[str]
    profile_dir: str


@app.post("/profile/build")
def build_profile(payload: BuildInput) -> dict[str, Any]:
    profile_dir = safe_path(payload.profile_dir, ROOT / "profile"); profile_dir.mkdir(parents=True, exist_ok=True)
    references = [safe_path(item, ROOT / "references") for item in payload.references]
    if not references or any(not item.is_file() for item in references):
        raise HTTPException(422, "Referências vocais inválidas.")
    tts = load_xtts(); model = tts.synthesizer.tts_model
    started = time.perf_counter()
    gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(audio_path=[str(item) for item in references])
    import torch
    artifact = profile_dir / "conditioning.pt"
    torch.save({"fingerprint": payload.fingerprint, "gpt_cond_latent": gpt_cond_latent.cpu(), "speaker_embedding": speaker_embedding.cpu()}, artifact)
    return {"status": "ready", "provider": "XTTS-v2", "artifact": artifact.name, "generation_seconds": round(time.perf_counter() - started, 3)}


class SynthesisInput(BaseModel):
    text: str
    profile_dir: str
    style: str = "neutral"
    speed: float = 1.0


@app.post("/synthesize")
def synthesize(payload: SynthesisInput) -> Response:
    profile_dir = safe_path(payload.profile_dir, ROOT / "profile")
    artifact = profile_dir / "conditioning.pt"
    if not artifact.exists():
        raise HTTPException(409, "VOICE_PROFILE_NOT_READY")
    if not payload.text.strip() or len(payload.text) > 2000:
        raise HTTPException(422, "Texto de síntese inválido.")
    tts = load_xtts(); model = tts.synthesizer.tts_model
    import torch
    saved = torch.load(artifact, map_location=model.device, weights_only=False)
    started = time.perf_counter()
    output = model.inference(payload.text, "pt", saved["gpt_cond_latent"].to(model.device), saved["speaker_embedding"].to(model.device), speed=max(0.75, min(payload.speed, 1.25)))
    samples = output["wav"]
    sample_rate = int(model.config.audio.output_sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        pcm = b"".join(int(max(-1.0, min(1.0, float(value))) * 32767).to_bytes(2, "little", signed=True) for value in samples)
        wav.writeframes(pcm)
    duration = len(samples) / sample_rate
    hardware = "cuda" if str(model.device).startswith("cuda") else "cpu"
    return Response(buffer.getvalue(), media_type="audio/wav", headers={"X-Voice-Provider": "XTTS-v2", "X-Voice-Profile": "Jarvis", "X-Audio-Duration": str(round(duration, 3)), "X-Generation-Seconds": str(round(time.perf_counter() - started, 3)), "X-Voice-Hardware": hardware})


@app.post("/unload")
def unload() -> dict[str, bool]:
    global _whisper, _xtts
    _whisper = None; _xtts = None
    if package_status("torch"):
        import torch
        if torch.cuda.is_available(): torch.cuda.empty_cache()
    return {"unloaded": True}
