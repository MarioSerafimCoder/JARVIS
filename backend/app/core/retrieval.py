import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from app.core.database import database, utc_now
from app.services.knowledge import search_documents
from app.services.repository import repository


STOP_WORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e", "em",
    "eu", "me", "meu", "minha", "na", "nas", "no", "nos", "o", "os", "para", "por",
    "que", "se", "sem", "um", "uma", "você", "voce",
}


def normalize_query(text: str, limit: int = 8) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    tokens = re.findall(r"[a-z0-9_-]+", normalized)
    return [token for token in tokens if len(token) > 2 and token not in STOP_WORDS][:limit]


class ConversationContextRetriever:
    def retrieve(self, conversation_id: str, limit: int) -> list[dict[str, Any]]:
        items = repository.rows(
            "SELECT role,content,created_at,generation_status FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        )
        items.reverse()
        return items


class MemoryRetriever:
    def retrieve(self, query: str, limit: int) -> list[dict[str, Any]]:
        from app.services.domains import memory_service
        return memory_service.hybrid_search(query, limit)

    def mark_used(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        with database() as connection:
            connection.executemany("UPDATE memories SET last_used_at=? WHERE id=?", [(utc_now(), item["id"]) for item in items])


class KnowledgeRetriever:
    def retrieve(self, query: str, limit: int) -> list[dict[str, Any]]:
        return search_documents(query, limit)


class TaskContextRetriever:
    def retrieve(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        from app.services.domains import task_service
        return task_service.relevant(query, limit)
