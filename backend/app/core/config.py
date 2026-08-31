from functools import lru_cache
from pathlib import Path
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
RUNTIME_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT


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
    backup_path: Path = Path("backups")
    voice_path: Path = Path("data/voices/jarvis")
    voice_worker_url: str = "http://127.0.0.1:8766"
    voice_stt_model: str = "small"
    voice_resource_mode: str = "AUTO"
    browser_worker_url: str = "http://127.0.0.1:8767"
    browser_profile_path: Path = Path("data/browser/profiles/jarvis")
    browser_worker_token: str = ""
    browser_candidate_ttl_seconds: int = 900
    max_recent_messages: int = 16
    max_memory_items: int = 6
    max_document_chunks: int = 5
    max_context_chars: int = 28000
    max_agent_cycles: int = 5
    conversation_summary_interval: int = 6
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        for field_name in ("database_path", "library_path", "notes_path", "backup_path", "voice_path", "browser_profile_path"):
            value = getattr(self, field_name)
            if not value.is_absolute():
                setattr(self, field_name, RUNTIME_ROOT / value)

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.notes_path.mkdir(parents=True, exist_ok=True)
        self.backup_path.mkdir(parents=True, exist_ok=True)
        for directory in ("references", "profile", "cache", "generated", "temp", "models"):
            (self.voice_path / directory).mkdir(parents=True, exist_ok=True)
        self.browser_profile_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
