from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.database import initialize_database


@pytest.fixture(autouse=True)
def isolated_data(tmp_path: Path):
    settings = get_settings()
    previous = (settings.database_path, settings.library_path, settings.notes_path)
    settings.database_path = tmp_path / "database" / "jarvis.db"
    settings.library_path = tmp_path / "library"
    settings.notes_path = tmp_path / "notes"
    settings.ensure_directories()
    initialize_database()
    yield settings
    settings.database_path, settings.library_path, settings.notes_path = previous

