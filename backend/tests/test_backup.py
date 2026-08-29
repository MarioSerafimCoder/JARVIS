import zipfile
from pathlib import Path

from app.api.backup import create_backup


def test_backup_contains_consistent_database_and_persona(isolated_data):
    result = create_backup()
    path = Path(result["path"])
    assert result["size_bytes"] > 0
    assert path.parent == isolated_data.backup_path
    with zipfile.ZipFile(path) as archive:
        assert {"database/jarvis.db", "persona.md"}.issubset(archive.namelist())
