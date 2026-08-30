from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

import numpy as np
import soundfile as sf


def fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        stat = path.stat()
        digest.update(path.name.encode("utf-8"))
        digest.update(str(stat.st_size).encode())
        digest.update(str(stat.st_mtime_ns).encode())
    return digest.hexdigest()


def analyze(path: Path) -> dict[str, object]:
    samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    amplitude = np.max(np.abs(samples), axis=1) if len(samples) else np.zeros(0, dtype=np.float32)
    peak = float(amplitude.max()) if len(amplitude) else 0.0
    threshold = 10 ** (-40 / 20)
    active = np.flatnonzero(amplitude >= threshold)
    leading_ms = round((int(active[0]) if len(active) else len(amplitude)) / sample_rate * 1000)
    trailing_ms = round((len(amplitude) - 1 - int(active[-1]) if len(active) else len(amplitude)) / sample_rate * 1000)
    peak_dbfs = round(20 * math.log10(peak), 2) if peak else None
    clipping = peak >= 0.999
    status = "POOR" if clipping else "GOOD" if leading_ms <= 750 and trailing_ms <= 750 else "ACCEPTABLE"
    return {
        "filename": path.name,
        "duration_seconds": round(len(samples) / sample_rate, 3),
        "sample_rate": sample_rate,
        "channels": samples.shape[1],
        "leading_silence_ms": leading_ms,
        "trailing_silence_ms": trailing_ms,
        "peak_dbfs": peak_dbfs,
        "clipping": clipping,
        "status": status,
    }


def markdown(rows: list[dict[str, object]], source_paths: list[Path]) -> str:
    total = sum(float(row["duration_seconds"]) for row in rows)
    good = sum(row["status"] == "GOOD" for row in rows)
    acceptable = sum(row["status"] == "ACCEPTABLE" for row in rows)
    poor = sum(row["status"] == "POOR" for row in rows)
    lines = [
        "# Relatório das referências vocais",
        "",
        "As referências originais foram preservadas. Nenhum áudio foi enviado para serviços externos. A análise PCM foi executada localmente pelo ambiente isolado do Voice Worker.",
        "",
        f"- Arquivos: {len(rows)}",
        f"- Duração decodificada total: {total:.2f} s",
        f"- Qualidade: {good} GOOD, {acceptable} ACCEPTABLE, {poor} POOR",
        f"- Fingerprint: `{fingerprint(source_paths)}`",
        "- Limiar de silêncio: -40 dBFS; clipping aparente: pico >= -0,01 dBFS",
        "",
        "| Arquivo | Duração | Taxa | Canais | Silêncio inicial/final | Pico | Clipping | Status |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        name = str(row["filename"]).replace("|", "/")
        lines.append(
            f"| {name} | {row['duration_seconds']} s | {row['sample_rate']} Hz | {row['channels']} | "
            f"{row['leading_silence_ms']}/{row['trailing_silence_ms']} ms | {row['peak_dbfs']} dBFS | "
            f"{'sim' if row['clipping'] else 'não'} | {row['status']} |"
        )
    lines += [
        "",
        "## Critério",
        "",
        "GOOD indica ausência de clipping e até 750 ms de silêncio em cada extremidade. ACCEPTABLE preserva referências utilizáveis com silêncio maior; POOR sinaliza clipping aparente. O perfil XTTS usa os originais sem sobrescrevê-los.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--references", type=Path, default=project_root / "data" / "voices" / "jarvis" / "references")
    parser.add_argument("--output", type=Path, default=project_root / "docs" / "VOICE_REFERENCE_REPORT.md")
    args = parser.parse_args()
    paths = sorted(path for path in args.references.resolve().iterdir() if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".flac", ".ogg", ".m4a"})
    rows = [analyze(path) for path in paths]
    args.output.resolve().write_text(markdown(rows, paths), encoding="utf-8")
    print(f"{len(rows)} referências analisadas; relatório: {args.output.resolve()}")


if __name__ == "__main__":
    main()
