from __future__ import annotations

import re
import uuid
from typing import Any

from app.core.database import utc_now
from app.services.domains import TYPE_BY_CATEGORY, memory_service
from app.services.repository import repository
from app.services.schemas import MemoryInput


class MemoryConsolidator:
    """Creates observable candidates with conservative local rules; it never auto-saves."""

    PATTERNS = [
        (re.compile(r"\b(?:eu\s+)?prefiro\s+(.+?)(?:[.!?]|$)", re.I), "preference", .91, 3),
        (re.compile(r"\bmeu nome (?:é|e)\s+(.+?)(?:[.!?]|$)", re.I), "person", .97, 4),
        (re.compile(r"\b(?:estou trabalhando|trabalho) (?:no|na|em)\s+(.+?)(?:[.!?]|$)", re.I), "project", .86, 3),
        (re.compile(r"\b(?:eu\s+)?decidi\s+(.+?)(?:[.!?]|$)", re.I), "decision", .90, 4),
    ]

    def analyze(self, text: str, *, conversation_id: str, source_message_id: str) -> list[dict[str, Any]]:
        if self._mode() == "disabled":
            return []
        candidates = []
        for pattern, category, confidence, importance in self.PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            content = self._canonical(category, match.group(1).strip())
            dedupe = memory_service.classify_existing(content)
            existing = repository.row("SELECT * FROM memory_candidates WHERE source_message_id=? AND content=?", (source_message_id, content))
            if existing:
                candidates.append(existing)
                continue
            item_id, now = str(uuid.uuid4()), utc_now()
            related = dedupe.get("memory", {}).get("id") if isinstance(dedupe.get("memory"), dict) else None
            repository.execute(
                "INSERT INTO memory_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, content, category, TYPE_BY_CATEGORY[category], confidence, importance, "conversation",
                 conversation_id, source_message_id, "candidate", dedupe["kind"], related, now, now),
            )
            candidates.append(repository.row("SELECT * FROM memory_candidates WHERE id=?", (item_id,)) or {})
        return candidates

    def list(self) -> list[dict[str, Any]]:
        return repository.rows("SELECT * FROM memory_candidates WHERE status='candidate' ORDER BY created_at DESC")

    def ignore(self, candidate_id: str) -> dict[str, Any]:
        repository.execute("UPDATE memory_candidates SET status='archived',updated_at=? WHERE id=?", (utc_now(), candidate_id))
        return {"id": candidate_id, "status": "archived"}

    def save(self, candidate_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        candidate = repository.row("SELECT * FROM memory_candidates WHERE id=? AND status='candidate'", (candidate_id,))
        if not candidate:
            raise ValueError("Sugestão de memória não encontrada.")
        values = {**candidate, **(overrides or {})}
        supersedes_id = values.get("related_memory_id") if values.get("dedupe_status") == "conflict" else None
        result = memory_service.create(
            MemoryInput(
                content=values["content"], category=values["category"], memory_type=values["memory_type"],
                confidence=values["confidence"], importance=values["importance"], source_type="conversation",
                source_reference=values.get("source_reference"), source_message_id=values.get("source_message_id"), supersedes_id=supersedes_id,
            )
        )
        repository.execute("UPDATE memory_candidates SET status='active',updated_at=? WHERE id=?", (utc_now(), candidate_id))
        return result

    @staticmethod
    def _canonical(category: str, value: str) -> str:
        value = value.rstrip(" .")
        if category == "preference":
            return f"Prefere {value}."
        if category == "person":
            return f"O nome do usuário é {value}."
        if category == "project":
            return f"Trabalha em {value}."
        return f"Decidiu {value}."

    @staticmethod
    def _mode() -> str:
        row = repository.row("SELECT value_json FROM app_settings WHERE key='memory_behavior'")
        if not row:
            return "suggest"
        try:
            return str(__import__("json").loads(row["value_json"]).get("mode", "suggest"))
        except Exception:
            return "suggest"


memory_consolidator = MemoryConsolidator()
