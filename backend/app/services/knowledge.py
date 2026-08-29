import re
import uuid
from pathlib import Path

import fitz
from docx import Document as DocxDocument

from app.core.database import database, utc_now
from app.services.repository import repository


def extract_text(path: Path, extension: str) -> str:
    if extension == ".pdf":
        with fitz.open(path) as document:
            return "\n".join(page.get_text() for page in document)
    if extension == ".docx":
        document = DocxDocument(path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, size: int = 1200, overlap: int = 160) -> list[str]:
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not clean:
        return []
    chunks: list[str] = []
    cursor = 0
    while cursor < len(clean):
        end = min(len(clean), cursor + size)
        if end < len(clean):
            boundary = clean.rfind("\n", cursor, end)
            if boundary > cursor + size // 2:
                end = boundary
        chunks.append(clean[cursor:end].strip())
        if end >= len(clean):
            break
        cursor = max(end - overlap, cursor + 1)
    return chunks


def index_document(document_id: str, filename: str, path: Path, extension: str) -> dict:
    try:
        text = extract_text(path, extension)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("Este documento parece não possuir texto extraível. OCR será implementado futuramente.")
        with database() as connection:
            for position, content in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO document_chunks VALUES (?,?,?,?,?)",
                    (chunk_id, document_id, content, f"trecho {position + 1}", position),
                )
                connection.execute(
                    "INSERT INTO document_chunks_fts VALUES (?,?,?,?)",
                    (chunk_id, document_id, filename, content),
                )
            connection.execute(
                "UPDATE documents SET status='ready', chunk_count=?, error=NULL WHERE id=?",
                (len(chunks), document_id),
            )
        return {"status": "ready", "chunk_count": len(chunks)}
    except Exception as exc:
        repository.execute("UPDATE documents SET status='error', error=? WHERE id=?", (str(exc), document_id))
        return {"status": "error", "error": str(exc)}


def search_documents(query: str, limit: int = 5) -> list[dict]:
    safe_query = " ".join(part for part in re.findall(r"[\wÀ-ÿ]+", query) if len(part) > 1)
    if not safe_query:
        return []
    try:
        return repository.rows(
            "SELECT document_id, filename, content AS relevant_text, bm25(document_chunks_fts) AS score "
            "FROM document_chunks_fts WHERE document_chunks_fts MATCH ? ORDER BY score LIMIT ?",
            (safe_query, limit),
        )
    except Exception:
        return []
