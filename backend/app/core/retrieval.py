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
        tokens = normalize_query(query)
        if not tokens:
            return []
        match = " OR ".join(f'"{token}"' for token in tokens)
        try:
            items = repository.rows(
                "SELECT m.*, bm25(memories_fts) AS fts_rank FROM memories_fts f "
                "JOIN memories m ON m.id=f.id WHERE memories_fts MATCH ? LIMIT ?",
                (match, limit * 3),
            )
        except Exception:
            return []
        now = datetime.now(timezone.utc)
        for item in items:
            try:
                age_days = max(0.0, (now - datetime.fromisoformat(item["updated_at"])).total_seconds() / 86400)
            except Exception:
                age_days = 365.0
            textual = max(0.0, -float(item.get("fts_rank") or 0))
            item["score"] = round(textual + item["importance"] * 0.2 + 0.25 / (1 + age_days / 30), 4)
        return sorted(items, key=lambda item: item["score"], reverse=True)[:limit]

    def mark_used(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        with database() as connection:
            connection.executemany("UPDATE memories SET last_used_at=? WHERE id=?", [(utc_now(), item["id"]) for item in items])


class KnowledgeRetriever:
    def retrieve(self, query: str, limit: int) -> list[dict[str, Any]]:
        return search_documents(query, limit)


class TaskContextRetriever:
    TRIGGERS = {"tarefa", "tarefas", "hoje", "prazo", "pendente", "projeto", "prioridade"}

    def retrieve(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not set(normalize_query(query)) & self.TRIGGERS:
            return []
        return repository.rows(
            "SELECT id,title,status,priority,due_at,project FROM tasks "
            "WHERE status NOT IN ('done','cancelled') ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, updated_at DESC LIMIT ?",
            (limit,),
        )

