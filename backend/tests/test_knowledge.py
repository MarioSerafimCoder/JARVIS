from pathlib import Path

from app.core.database import utc_now
from app.services.knowledge import chunk_text, index_document, search_documents
from app.services.repository import repository


def test_chunk_text_preserves_content():
    chunks = chunk_text("A" * 3000, size=1000, overlap=100)
    assert len(chunks) >= 3
    assert chunks[0].startswith("A")


def test_txt_document_is_indexed_and_searchable(tmp_path: Path):
    path = tmp_path / "manual.txt"
    path.write_text("O código ultravioleta do projeto é orquídea local.", encoding="utf-8")
    repository.execute(
        "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("doc-1", "stored.txt", "manual.txt", "txt", path.stat().st_size, "processing", "[]", "", utc_now(), 0, None),
    )
    result = index_document("doc-1", "manual.txt", path, ".txt")
    assert result["status"] == "ready"
    assert result["chunk_count"] == 1
    matches = search_documents("ultravioleta")
    assert matches and matches[0]["filename"] == "manual.txt"


def test_empty_document_reports_ocr_future(tmp_path: Path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    repository.execute(
        "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("doc-2", "empty.txt", "empty.txt", "txt", 0, "processing", "[]", "", utc_now(), 0, None),
    )
    result = index_document("doc-2", "empty.txt", path, ".txt")
    assert result["status"] == "error"
    assert "OCR" in result["error"]
