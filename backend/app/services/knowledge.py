import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz
from docx import Document as DocxDocument

from app.core.database import database, utc_now
from app.services.repository import repository


@dataclass
class SourceSegment:
    content: str
    location: str


def extract_segments(path: Path, extension: str) -> list[SourceSegment]:
    if extension == ".pdf":
        with fitz.open(path) as document:
            segments: list[SourceSegment] = []
            for page_number, page in enumerate(document, start=1):
                for content in chunk_text(page.get_text()):
                    segments.append(SourceSegment(content, f"Página {page_number}"))
            return segments
    if extension == ".docx":
        document = DocxDocument(path)
        segments = []
        for index, paragraph in enumerate(document.paragraphs, start=1):
            content = paragraph.text.strip()
            if content:
                style = paragraph.style.name if paragraph.style else "Parágrafo"
                segments.append(SourceSegment(content, f"Parágrafo {index} ({style})"))
        return segments
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    segments = []
    for start in range(0, len(lines), 35):
        end = min(len(lines), start + 40)
        content = "\n".join(lines[start:end]).strip()
        if content:
            segments.append(SourceSegment(content, f"Linhas {start + 1}-{end}"))
    return segments


def extract_text(path: Path, extension: str) -> str:
    return "\n".join(segment.content for segment in extract_segments(path, extension))


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
        segments = extract_segments(path, extension)
        if not segments:
            raise ValueError("Este documento parece não possuir texto extraível. OCR será implementado futuramente.")
        with database() as connection:
            for position, segment in enumerate(segments):
                chunk_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO document_chunks VALUES (?,?,?,?,?)",
                    (chunk_id, document_id, segment.content, segment.location, position),
                )
                connection.execute(
                    "INSERT INTO document_chunks_fts VALUES (?,?,?,?)",
                    (chunk_id, document_id, filename, segment.content),
                )
            connection.execute(
                "UPDATE documents SET status='ready', chunk_count=?, error=NULL WHERE id=?",
                (len(segments), document_id),
            )
        return {"status": "ready", "chunk_count": len(segments)}
    except Exception as exc:
        repository.execute("UPDATE documents SET status='error', error=? WHERE id=?", (str(exc), document_id))
        return {"status": "error", "error": str(exc)}


def search_documents(query: str, limit: int = 5) -> list[dict]:
    tokens = [part.lower() for part in re.findall(r"[\wÀ-ÿ]+", query) if len(part) > 2][:8]
    if not tokens:
        return []
    safe_query = " OR ".join(f'"{token}"' for token in tokens)
    try:
        return repository.rows(
            "SELECT f.document_id, f.filename, f.content AS relevant_text, c.location, bm25(document_chunks_fts) AS score "
            "FROM document_chunks_fts f JOIN document_chunks c ON c.id=f.chunk_id "
            "WHERE document_chunks_fts MATCH ? ORDER BY score LIMIT ?",
            (safe_query, limit),
        )
    except Exception:
        return []
