from dataclasses import dataclass
from typing import Any

from app.services.knowledge import search_documents
from app.services.repository import repository


@dataclass
class BuiltContext:
    messages: list[dict[str, str]]
    evidence: dict[str, Any]


class ContextBuilder:
    def build(self, conversation_id: str, user_text: str, persona: str) -> BuiltContext:
        recent = repository.rows(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 12",
            (conversation_id,),
        )
        recent.reverse()
        terms = [term for term in user_text.split() if len(term) > 3][:5]
        pattern = "%" + "%".join(terms) + "%" if terms else "%"
        memories = repository.rows(
            "SELECT id, content, category FROM memories WHERE content LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT 5",
            (pattern,),
        )
        documents = search_documents(user_text, 4)
        tasks = repository.rows(
            "SELECT id, title, status, priority, due_at FROM tasks WHERE status NOT IN ('done','cancelled') ORDER BY updated_at DESC LIMIT 5"
        ) if any(word in user_text.lower() for word in ("tarefa", "hoje", "prazo", "pendente")) else []
        system_parts = [persona]
        if memories:
            system_parts.append("Memórias potencialmente relevantes:\n" + "\n".join(f"- {item['content']}" for item in memories))
        if documents:
            system_parts.append("Trechos de documentos:\n" + "\n".join(f"- [{item['filename']}] {item['relevant_text']}" for item in documents))
        if tasks:
            system_parts.append("Tarefas em aberto:\n" + "\n".join(f"- {item['title']} ({item['status']})" for item in tasks))
        return BuiltContext(
            messages=[{"role": "system", "content": "\n\n".join(system_parts)}] + recent,
            evidence={"memories": memories, "documents": documents, "tasks": tasks, "actions": []},
        )

