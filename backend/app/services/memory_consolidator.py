from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.core.database import utc_now
from app.llm.base import LLMProvider
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
            candidates.append(self._save_candidate(content, category, confidence, importance, "Regra determinística: declaração explícita do usuário.", conversation_id, source_message_id))
        return candidates

    async def analyze_hybrid(self, text: str, *, conversation_id: str, source_message_id: str, provider: LLMProvider) -> list[dict[str, Any]]:
        """Combine conservative rules with a structured local-model proposal.

        Proposals remain candidates: this method never promotes them to memory.
        Malformed model output is discarded without affecting deterministic rules.
        """
        candidates = self.analyze(text, conversation_id=conversation_id, source_message_id=source_message_id)
        if self._mode() == "disabled" or len(text.strip()) < 8:
            return candidates
        durable_signal = re.search(r"\b(eu|meu|minha|prefiro|gosto|trabalho|decidi|sempre|normalmente|costumo|mudei)\b", text, re.I)
        if not durable_signal:
            return candidates
        prompt = (
            "Extraia somente fatos pessoais, preferências, projetos, rotinas ou decisões explicitamente declarados pelo usuário. "
            "Não infira e não extraia pedidos temporários. Retorne apenas JSON no formato "
            "{\"candidates\":[{\"content\":str,\"category\":\"preference|person|project|routine|decision|fact|instruction|other\","
            "\"confidence\":0..1,\"importance\":1..5,\"reason\":str}]}. Se nada for durável, retorne {\"candidates\":[]}.")
        try:
            response = await provider.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:6000]},
            ])
            raw = response.get("message", {}).get("content", "")
            match = re.search(r"\{.*\}", raw, re.S)
            payload = json.loads(match.group(0) if match else raw)
            for item in payload.get("candidates", [])[:5]:
                category = str(item.get("category", "other"))
                content = " ".join(str(item.get("content", "")).split())
                confidence = float(item.get("confidence", 0))
                importance = int(item.get("importance", 1))
                reason = " ".join(str(item.get("reason", "Proposta do modelo local.")).split())
                if category not in TYPE_BY_CATEGORY or not content or confidence < 0.72 or not 1 <= importance <= 5:
                    continue
                if any(existing.get("content", "").casefold() == content.casefold() for existing in candidates):
                    continue
                candidates.append(self._save_candidate(content, category, confidence, importance, reason, conversation_id, source_message_id))
        except Exception:
            pass
        return candidates

    @staticmethod
    def _save_candidate(content: str, category: str, confidence: float, importance: int, reason: str, conversation_id: str, source_message_id: str) -> dict[str, Any]:
        existing = repository.row("SELECT * FROM memory_candidates WHERE source_message_id=? AND content=?", (source_message_id, content))
        if existing:
            return existing
        dedupe = memory_service.classify_existing(content)
        item_id, now = str(uuid.uuid4()), utc_now()
        related = dedupe.get("memory", {}).get("id") if isinstance(dedupe.get("memory"), dict) else None
        repository.execute(
            "INSERT INTO memory_candidates (id,content,category,memory_type,confidence,importance,source_type,source_reference,source_message_id,status,dedupe_status,related_memory_id,created_at,updated_at,reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, content, category, TYPE_BY_CATEGORY[category], confidence, importance, "conversation",
             conversation_id, source_message_id, "candidate", dedupe["kind"], related, now, now, reason[:500]),
        )
        return repository.row("SELECT * FROM memory_candidates WHERE id=?", (item_id,)) or {}

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
