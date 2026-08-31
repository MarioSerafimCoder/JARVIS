from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.database import utc_now
from app.llm.base import LLMProvider
from app.services.repository import repository


class ConversationState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = ""
    summary: str = ""
    decisions: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    pending_items: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    user_preferences_relevant: list[str] = Field(default_factory=list)

    def rendered(self) -> str:
        sections = [("Assunto", [self.subject] if self.subject else []), ("Resumo", [self.summary] if self.summary else []), ("Decisões", self.decisions), ("Fatos explícitos", self.facts), ("Restrições", self.constraints), ("Pendências", self.pending_items), ("Perguntas em aberto", self.unresolved_questions), ("Preferências relevantes", self.user_preferences_relevant)]
        return "Estado consolidado da conversa:\n" + "\n".join(f"{title}: " + "; ".join(values) for title, values in sections if values)


class ConversationStateService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        row = repository.row("SELECT * FROM conversation_states WHERE conversation_id=?", (conversation_id,))
        if row:
            row["state"] = json.loads(row.pop("state_json"))
        return row

    async def maybe_update(self, conversation_id: str, interval: int = 6) -> dict[str, Any] | None:
        rows = repository.rows("SELECT role,content FROM messages WHERE conversation_id=? AND role IN ('user','assistant') ORDER BY created_at", (conversation_id,))
        previous_row = self.get(conversation_id)
        previous_count = int(previous_row["source_message_count"]) if previous_row else 0
        if len(rows) < interval or len(rows) - previous_count < interval:
            return previous_row
        previous = ConversationState.model_validate(previous_row["state"]) if previous_row else ConversationState()
        segment = rows[previous_count:]
        prompt = (
            "Atualize o estado estruturado da conversa usando somente fatos explícitos. Não exponha raciocínio. "
            "Não remova fatos, decisões ou restrições anteriores sem evidência explícita nas mensagens novas. "
            "Retorne apenas JSON válido com as chaves subject, summary, decisions, facts, constraints, pending_items, "
            "unresolved_questions e user_preferences_relevant.\n\nEstado anterior:\n"
            + previous.model_dump_json()
            + "\n\nNovas mensagens:\n"
            + "\n".join(f"{item['role']}: {item['content'][:2000]}" for item in segment)
        )
        try:
            response = await self.provider.chat([{"role": "system", "content": "Você consolida estado factual em JSON estrito."}, {"role": "user", "content": prompt}])
            raw = response.get("message", {}).get("content", "")
            match = re.search(r"\{.*\}", raw, re.S)
            candidate = ConversationState.model_validate_json(match.group(0) if match else raw)
            for field in ("facts", "decisions", "constraints"):
                setattr(candidate, field, list(dict.fromkeys(getattr(previous, field) + getattr(candidate, field))))
        except Exception:
            candidate = self._fallback(previous, segment)
        now = utc_now()
        repository.execute(
            "INSERT INTO conversation_states VALUES (?,?,?,?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET state_json=excluded.state_json,rendered_text=excluded.rendered_text,source_message_count=excluded.source_message_count,version=excluded.version,updated_at=excluded.updated_at",
            (conversation_id, candidate.model_dump_json(), candidate.rendered(), len(rows), 1, now),
        )
        return self.get(conversation_id)

    @staticmethod
    def _fallback(previous: ConversationState, segment: list[dict[str, Any]]) -> ConversationState:
        lines = [f"{'Usuário' if item['role']=='user' else 'Jarvis'}: {' '.join(item['content'].split())[:500]}" for item in segment[-8:]]
        subject = previous.subject or next((item["content"][:160] for item in segment if item["role"] == "user"), "")
        return previous.model_copy(update={"subject": subject, "summary": "\n".join(lines)})
