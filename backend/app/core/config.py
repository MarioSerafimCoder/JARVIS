from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Jarvis Local"
    ollama_url: str = "http://127.0.0.1:11434"
    model_name: str = "qwen3.5:4b"
    temperature: float = 0.3
    context_length: int = 8192
    max_output_tokens: int = 768
    database_path: Path = Path("data/database/jarvis.db")
    library_path: Path = Path("data/library")
    notes_path: Path = Path("data/notes")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        for field_name in ("database_path", "library_path", "notes_path"):
            value = getattr(self, field_name)
            if not value.is_absolute():
                setattr(self, field_name, PROJECT_ROOT / value)

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.notes_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
