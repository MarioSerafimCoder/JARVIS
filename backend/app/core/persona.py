from pathlib import Path


PERSONA_PATH = Path(__file__).resolve().parents[1] / "prompts" / "persona.md"


def load_persona() -> str:
    return PERSONA_PATH.read_text(encoding="utf-8")


def save_persona(content: str) -> None:
    if len(content.strip()) < 40:
        raise ValueError("A personalidade precisa conter instruções suficientes.")
    PERSONA_PATH.write_text(content.strip() + "\n", encoding="utf-8")

