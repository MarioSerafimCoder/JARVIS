from pathlib import Path

from app.container import voice_profile_manager
from app.core.database import initialize_database


if __name__ == "__main__":
    initialize_database()
    imported = voice_profile_manager.import_project_references()
    report = voice_profile_manager.report_markdown()
    target = Path(__file__).resolve().parents[2] / "docs" / "VOICE_REFERENCE_REPORT.md"
    target.write_text(report, encoding="utf-8")
    print(f"Referências: {imported.get('total', 0)} | novas cópias: {imported.get('imported', 0)} | relatório: {target}")
