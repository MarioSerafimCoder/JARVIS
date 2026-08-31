import json
import shutil

from app.core.config import BUNDLE_ROOT, RUNTIME_ROOT

DEFAULT_PERSONA_PATH = BUNDLE_ROOT / "app" / "prompts" / "persona.md"
if not DEFAULT_PERSONA_PATH.exists():
    DEFAULT_PERSONA_PATH = BUNDLE_ROOT / "backend" / "app" / "prompts" / "persona.md"
PERSONA_PATH = RUNTIME_ROOT / "data" / "persona.md"
PERSONA_META_PATH = RUNTIME_ROOT / "data" / "persona.meta.json"
DEFAULT_PERSONA_VERSION = 2


def ensure_persona() -> None:
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PERSONA_PATH.exists():
        shutil.copyfile(DEFAULT_PERSONA_PATH, PERSONA_PATH)
    if not PERSONA_META_PATH.exists():
        customized = PERSONA_PATH.read_text(encoding="utf-8").strip() != DEFAULT_PERSONA_PATH.read_text(encoding="utf-8").strip()
        _write_meta({"default_persona_version": DEFAULT_PERSONA_VERSION, "user_persona_version": 1 if customized else DEFAULT_PERSONA_VERSION, "customized": customized})


def _write_meta(meta: dict) -> None:
    PERSONA_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def persona_status() -> dict:
    ensure_persona()
    meta = json.loads(PERSONA_META_PATH.read_text(encoding="utf-8"))
    return {**meta, "update_available": int(meta["user_persona_version"]) < DEFAULT_PERSONA_VERSION}


def load_persona() -> str:
    ensure_persona()
    return PERSONA_PATH.read_text(encoding="utf-8")


def save_persona(content: str) -> None:
    if len(content.strip()) < 40:
        raise ValueError("A personalidade precisa conter instruções suficientes.")
    ensure_persona()
    PERSONA_PATH.write_text(content.strip() + "\n", encoding="utf-8")
    customized = content.strip() != DEFAULT_PERSONA_PATH.read_text(encoding="utf-8").strip()
    _write_meta({"default_persona_version": DEFAULT_PERSONA_VERSION, "user_persona_version": DEFAULT_PERSONA_VERSION, "customized": customized})


def compare_persona() -> dict:
    return {"current": load_persona(), "default": DEFAULT_PERSONA_PATH.read_text(encoding="utf-8"), **persona_status()}


def update_to_default() -> dict:
    ensure_persona()
    shutil.copyfile(DEFAULT_PERSONA_PATH, PERSONA_PATH)
    _write_meta({"default_persona_version": DEFAULT_PERSONA_VERSION, "user_persona_version": DEFAULT_PERSONA_VERSION, "customized": False})
    return {"content": load_persona(), **persona_status()}


def keep_persona() -> dict:
    status = persona_status()
    _write_meta({"default_persona_version": DEFAULT_PERSONA_VERSION, "user_persona_version": DEFAULT_PERSONA_VERSION, "customized": status["customized"]})
    return persona_status()
