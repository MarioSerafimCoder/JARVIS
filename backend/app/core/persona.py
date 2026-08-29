from pathlib import Path
import shutil
import sys

from app.core.config import BUNDLE_ROOT, RUNTIME_ROOT

DEFAULT_PERSONA_PATH = BUNDLE_ROOT / "app" / "prompts" / "persona.md"
PERSONA_PATH = RUNTIME_ROOT / "data" / "persona.md" if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1] / "prompts" / "persona.md"


def ensure_persona() -> None:
    if PERSONA_PATH.exists():
        return
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DEFAULT_PERSONA_PATH, PERSONA_PATH)


def load_persona() -> str:
    ensure_persona()
    return PERSONA_PATH.read_text(encoding="utf-8")


def save_persona(content: str) -> None:
    if len(content.strip()) < 40:
        raise ValueError("A personalidade precisa conter instruções suficientes.")
    ensure_persona()
    PERSONA_PATH.write_text(content.strip() + "\n", encoding="utf-8")
