import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from app.container import settings
from app.core.persona import PERSONA_PATH, ensure_persona


router = APIRouter(prefix="/backup", tags=["backup"])


@router.post("")
def create_backup() -> dict:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    target = settings.backup_path / f"jarvis-backup-{timestamp}.zip"
    with tempfile.TemporaryDirectory(prefix="jarvis-backup-") as temp_dir:
        temp = Path(temp_dir)
        source = sqlite3.connect(settings.database_path)
        destination = sqlite3.connect(temp / "jarvis.db")
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        ensure_persona()
        shutil.copy2(PERSONA_PATH, temp / "persona.md")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp / "jarvis.db", "database/jarvis.db")
            archive.write(temp / "persona.md", "persona.md")
            if settings.library_path.exists():
                for file in settings.library_path.iterdir():
                    if file.is_file():
                        archive.write(file, f"library/{file.name}")
    return {"created": True, "filename": target.name, "path": str(target), "size_bytes": target.stat().st_size}
