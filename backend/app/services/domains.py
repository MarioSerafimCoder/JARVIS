from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from app.core.database import database, utc_now
from app.core.retrieval import normalize_query
from app.services.embeddings import EmbeddingProvider, cosine_similarity, embedding_provider
from app.services.knowledge import search_documents
from app.services.repository import repository
from app.services.schemas import DocumentMetadataInput, FeedbackInput, MemoryInput, TaskInput, TaskPatch


TYPE_BY_CATEGORY = {
    "preference": "preference", "person": "person", "project": "project", "routine": "procedural",
    "decision": "decision", "fact": "semantic", "instruction": "procedural", "other": "semantic",
}


def _text_similarity(left: str, right: str) -> float:
    a, b = set(normalize_query(left, 64)), set(normalize_query(right, 64))
    jaccard = len(a & b) / max(1, len(a | b))
    sequence = SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
    return max(jaccard, sequence * 0.9)


class MemoryService:
    HYBRID_WEIGHTS = {"fts": 0.50, "embedding": 0.30, "importance": 0.12, "recency": 0.08}

    def __init__(self, embeddings: EmbeddingProvider | None = None) -> None:
        self.embeddings = embeddings or embedding_provider
        self._embedding_index: dict[str, list[float]] = {}
        self._embedding_index_version: tuple[int, str] | None = None

    def _load_embedding_index(self) -> dict[str, list[float]]:
        marker = repository.row("SELECT COUNT(*) AS count,COALESCE(MAX(updated_at),'') AS updated_at FROM memory_embeddings") or {}
        version = (int(marker.get("count", 0)), str(marker.get("updated_at", "")))
        if version != self._embedding_index_version:
            self._embedding_index = {
                row["memory_id"]: json.loads(row["vector_json"])
                for row in repository.rows("SELECT memory_id,vector_json FROM memory_embeddings")
            }
            self._embedding_index_version = version
        return self._embedding_index

    def list(self, query: str | None = None, status: str | None = "active") -> list[dict[str, Any]]:
        clauses, parameters = [], []
        if status:
            clauses.append("status=?")
            parameters.append(status)
        if query:
            clauses.append("content LIKE ?")
            parameters.append(f"%{query.strip()}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return repository.rows(f"SELECT * FROM memories{where} ORDER BY updated_at DESC", tuple(parameters))

    def get(self, memory_id: str) -> dict[str, Any] | None:
        return repository.row("SELECT * FROM memories WHERE id=?", (memory_id,))

    def classify_existing(self, content: str, exclude_id: str | None = None) -> dict[str, Any]:
        items = repository.rows("SELECT id,content,status FROM memories WHERE status IN ('active','superseded')")
        items = [item for item in items if item["id"] != exclude_id]
        if not items:
            return {"kind": "new", "score": 0.0, "method": "lexical_fallback"}
        semantic: dict[str, float] = {}
        try:
            candidate_vector = self.embeddings.embed([content])[0]
            semantic = {memory_id: max(0.0, cosine_similarity(candidate_vector, vector)) for memory_id, vector in self._load_embedding_index().items()}
        except Exception:
            pass
        scored = [
            (item, max(_text_similarity(content, item["content"]), semantic.get(item["id"], 0.0)), semantic.get(item["id"], 0.0))
            for item in items
        ]
        item, score, semantic_score = max(scored, key=lambda pair: pair[1])
        normalized_new, normalized_old = content.casefold(), item["content"].casefold()
        conflict = score >= 0.48 and any(word in normalized_new for word in ("agora", "não ", "deixei", "mudou", "prefiro")) and normalized_new != normalized_old
        kind = "duplicate" if score >= 0.90 else "conflict" if conflict else "similar" if score >= 0.58 else "new"
        return {"kind": kind, "score": round(score, 4), "semantic_score": round(semantic_score, 4), "memory": item, "method": "hybrid" if semantic else "lexical_fallback"}

    def create(self, payload: MemoryInput, *, allow_duplicate: bool = False) -> dict[str, Any]:
        match = self.classify_existing(payload.content)
        if match["kind"] == "duplicate" and not allow_duplicate:
            return {**(self.get(match["memory"]["id"]) or match["memory"]), "created": False, "dedupe": match}
        if payload.supersedes_id and not self.get(payload.supersedes_id):
            raise ValueError("Memória substituída não encontrada.")
        item_id, now = str(uuid.uuid4()), utc_now()
        memory_type = payload.memory_type or TYPE_BY_CATEGORY[payload.category]
        with database() as connection:
            connection.execute(
                "INSERT INTO memories (id,content,category,importance,source_type,source_reference,created_at,updated_at,last_used_at,memory_type,status,confidence,supersedes_id,source_message_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, payload.content, payload.category, payload.importance, payload.source_type, payload.source_reference,
                 now, now, None, memory_type, "active", payload.confidence, payload.supersedes_id, payload.source_message_id),
            )
            connection.execute("INSERT INTO memories_fts VALUES (?,?,?)", (item_id, payload.content, payload.category))
            if payload.supersedes_id:
                connection.execute("UPDATE memories SET status='superseded',updated_at=? WHERE id=?", (now, payload.supersedes_id))
                self._invalidate_relationships(connection, payload.supersedes_id)
        self._store_embedding(item_id, payload.content)
        result = self.get(item_id) or {}
        repository.audit("save_memory", payload.model_dump(), result, "success")
        self._notify_graph("memory_created", item_id)
        return {**result, "created": True, "dedupe": match}

    def update(self, memory_id: str, payload: MemoryInput) -> dict[str, Any]:
        if not self.get(memory_id):
            raise ValueError("Memória não encontrada.")
        memory_type, now = payload.memory_type or TYPE_BY_CATEGORY[payload.category], utc_now()
        with database() as connection:
            connection.execute(
                "UPDATE memories SET content=?,category=?,importance=?,source_type=?,source_reference=?,updated_at=?,memory_type=?,confidence=?,supersedes_id=?,source_message_id=? WHERE id=?",
                (payload.content, payload.category, payload.importance, payload.source_type, payload.source_reference, now,
                 memory_type, payload.confidence, payload.supersedes_id, payload.source_message_id, memory_id),
            )
            connection.execute("DELETE FROM memories_fts WHERE id=?", (memory_id,))
            connection.execute("INSERT INTO memories_fts VALUES (?,?,?)", (memory_id, payload.content, payload.category))
            self._invalidate_relationships(connection, memory_id)
        self._store_embedding(memory_id, payload.content)
        self._notify_graph("memory_updated", memory_id)
        return self.get(memory_id) or {}

    def archive(self, memory_id: str) -> dict[str, Any]:
        if not self.get(memory_id):
            raise ValueError("Memória não encontrada.")
        with database() as connection:
            connection.execute("UPDATE memories SET status='archived',updated_at=? WHERE id=?", (utc_now(), memory_id))
            self._invalidate_relationships(connection, memory_id)
        self._notify_graph("memory_archived", memory_id)
        return self.get(memory_id) or {}

    def delete(self, memory_id: str) -> dict[str, Any]:
        if not self.get(memory_id):
            raise ValueError("Memória não encontrada.")
        with database() as connection:
            self._invalidate_relationships(connection, memory_id)
            connection.execute("DELETE FROM memories_fts WHERE id=?", (memory_id,))
            connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        result = {"id": memory_id, "deleted": True}
        repository.audit("delete_memory", {"id": memory_id}, result, "success")
        self._notify_graph("memory_deleted", memory_id)
        return result

    def hybrid_search(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        tokens = normalize_query(query, 12)
        if not tokens:
            return []
        candidates: dict[str, dict[str, Any]] = {item["id"]: item for item in repository.rows("SELECT * FROM memories WHERE status='active'")}
        fts_scores: dict[str, float] = {}
        match = " OR ".join(f'"{token}"' for token in tokens)
        try:
            for item in repository.rows(
                "SELECT m.*,bm25(memories_fts) AS rank FROM memories_fts f JOIN memories m ON m.id=f.id "
                "WHERE memories_fts MATCH ? AND m.status='active' LIMIT ?", (match, limit * 8),
            ):
                candidates[item["id"]] = item
                fts_scores[item["id"]] = 1 / (1 + abs(float(item.get("rank") or 0)))
        except Exception:
            pass
        semantic: dict[str, float] = {}
        embedding_status = "fallback_fts5"
        try:
            query_vector = self.embeddings.embed([query])[0]
            rows = repository.rows("SELECT memory_id,vector_json FROM memory_embeddings")
            for row in rows:
                semantic[row["memory_id"]] = max(0.0, cosine_similarity(query_vector, json.loads(row["vector_json"])))
            embedding_status = "active"
        except Exception:
            pass
        now = datetime.now(timezone.utc)
        results = []
        for item in candidates.values():
            lexical = fts_scores.get(item["id"], _text_similarity(query, item["content"]) * 0.55)
            try:
                age_days = max(0.0, (now - datetime.fromisoformat(item["updated_at"])).total_seconds() / 86400)
            except Exception:
                age_days = 365.0
            importance = float(item["importance"]) / 5
            recency = 1 / (1 + age_days / 30)
            score = lexical * .50 + semantic.get(item["id"], 0.0) * .30 + importance * .12 + recency * .08
            if item["id"] in fts_scores or lexical >= 0.20 or semantic.get(item["id"], 0.0) > 0.40:
                results.append({**item, "score": round(score, 5), "ranking": {"fts": round(lexical, 4), "embedding": round(semantic.get(item["id"], 0.0), 4), "importance": round(importance, 4), "recency": round(recency, 4), "embedding_status": embedding_status}})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]

    def _store_embedding(self, memory_id: str, content: str) -> None:
        try:
            vector = self.embeddings.embed([content])[0]
        except Exception:
            return
        repository.execute(
            "INSERT OR REPLACE INTO memory_embeddings VALUES (?,?,?,?,?,?)",
            (memory_id, self.embeddings.name, self.embeddings.model_name, len(vector), json.dumps(vector), utc_now()),
        )
        self._embedding_index_version = None

    @staticmethod
    def _invalidate_relationships(connection, memory_id: str) -> None:
        connection.execute("DELETE FROM memory_relationships WHERE source_memory_id=? OR target_memory_id=?", (memory_id, memory_id))

    @staticmethod
    def _notify_graph(reason: str, memory_id: str) -> None:
        from app.core.cognitive_graph import cognitive_graph_service
        if reason == "memory_created":
            cognitive_graph_service.memory_created(memory_id)
        else:
            cognitive_graph_service.graph_changed(reason, memory_id)


class TaskService:
    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            return repository.rows("SELECT * FROM tasks WHERE status=? ORDER BY updated_at DESC", (status,))
        return repository.rows("SELECT * FROM tasks ORDER BY updated_at DESC")

    def relevant(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        normalized = " ".join(normalize_query(query, 20))
        intent = any(phrase in query.casefold() for phrase in ("o que preciso fazer", "alguma coisa importante", "o que está atrasado", "tenho algo", "pendências", "prioridades"))
        intent = intent or bool(set(normalized.split()) & {"fazer", "atrasado", "atrasada", "importante", "prioridade", "tarefas", "pendente", "preciso"})
        if not intent:
            return []
        overdue_only = "atrasad" in query.casefold()
        important_only = "important" in query.casefold() or "prioridad" in query.casefold()
        clauses = ["status NOT IN ('done','cancelled')"]
        params: list[Any] = []
        if overdue_only:
            clauses.append("due_at IS NOT NULL AND due_at < ?")
            params.append(utc_now())
        if important_only:
            clauses.append("priority IN ('critical','high')")
        params.append(limit)
        return repository.rows(
            "SELECT id,title,status,priority,due_at,project FROM tasks WHERE " + " AND ".join(clauses) +
            " ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,due_at IS NULL,due_at,updated_at DESC LIMIT ?", tuple(params),
        )

    def create(self, payload: TaskInput, source: str = "manual") -> dict[str, Any]:
        item_id, now = str(uuid.uuid4()), utc_now()
        completed_at = now if payload.status == "done" else None
        repository.execute(
            "INSERT INTO tasks (id,title,description,status,priority,created_at,updated_at,due_at,completed_at,project,source,estimated_minutes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, payload.title, payload.description, payload.status, payload.priority, now, now, payload.due_at, completed_at, payload.project, source, payload.estimated_minutes),
        )
        result = repository.row("SELECT * FROM tasks WHERE id=?", (item_id,)) or {}
        repository.audit("create_task", payload.model_dump(), result, "success")
        self._notify("task_created", item_id)
        return result

    def update(self, task_id: str, payload: TaskInput | TaskPatch) -> dict[str, Any]:
        current = repository.row("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not current:
            raise ValueError("Tarefa não encontrada.")
        changes = payload.model_dump(exclude_none=True)
        if not changes:
            raise ValueError("Nenhuma alteração válida informada.")
        completed_at = utc_now() if changes.get("status") == "done" else None if "status" in changes else current.get("completed_at")
        changes.update({"updated_at": utc_now(), "completed_at": completed_at})
        assignments = ",".join(f"{key}=?" for key in changes)
        repository.execute(f"UPDATE tasks SET {assignments} WHERE id=?", tuple(changes.values()) + (task_id,))
        self._notify("task_updated", task_id)
        return repository.row("SELECT * FROM tasks WHERE id=?", (task_id,)) or {}

    def delete(self, task_id: str) -> dict[str, Any]:
        if not repository.row("SELECT id FROM tasks WHERE id=?", (task_id,)):
            raise ValueError("Tarefa não encontrada.")
        repository.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self._notify("task_deleted", task_id)
        return {"id": task_id, "deleted": True}

    @staticmethod
    def _notify(reason: str, task_id: str) -> None:
        from app.core.cognitive_graph import cognitive_graph_service
        cognitive_graph_service.graph_changed(reason, task_id)


class KnowledgeService:
    def list(self) -> list[dict[str, Any]]:
        return repository.rows("SELECT * FROM documents ORDER BY created_at DESC")

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return search_documents(query, limit)

    def update(self, document_id: str, payload: DocumentMetadataInput) -> dict[str, Any]:
        if not repository.row("SELECT id FROM documents WHERE id=?", (document_id,)):
            raise ValueError("Documento não encontrado.")
        repository.execute(
            "UPDATE documents SET tags=?,description=?,use_for_rag=?,collection=? WHERE id=?",
            (json.dumps(payload.tags, ensure_ascii=False), payload.description, int(payload.use_for_rag), payload.collection, document_id),
        )
        return repository.row("SELECT * FROM documents WHERE id=?", (document_id,)) or {}


class ConversationService:
    def summary(self, conversation_id: str) -> dict[str, Any] | None:
        return repository.row("SELECT * FROM conversation_summaries WHERE conversation_id=?", (conversation_id,))

    def maybe_update_summary(self, conversation_id: str, interval: int = 6) -> dict[str, Any] | None:
        messages = repository.rows(
            "SELECT role,content FROM messages WHERE conversation_id=? AND role IN ('user','assistant') ORDER BY created_at", (conversation_id,),
        )
        previous = self.summary(conversation_id)
        if len(messages) < interval or (previous and len(messages) - int(previous["message_count"]) < interval):
            return previous
        selected: list[str] = []
        used = 0
        for item in reversed(messages):
            line = f"{'Usuário' if item['role']=='user' else 'Jarvis'}: {' '.join(item['content'].split())}"
            if selected and used + len(line) > 3200:
                break
            selected.append(line)
            used += len(line)
        summary = "Resumo incremental da conversa:\n" + "\n".join(reversed(selected))
        now = utc_now()
        repository.execute(
            "INSERT INTO conversation_summaries VALUES (?,?,?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET summary=excluded.summary,message_count=excluded.message_count,updated_at=excluded.updated_at",
            (conversation_id, summary, len(messages), previous["created_at"] if previous else now, now),
        )
        return self.summary(conversation_id)

    def feedback(self, message_id: str, payload: FeedbackInput) -> dict[str, Any]:
        message = repository.row("SELECT id,role FROM messages WHERE id=?", (message_id,))
        if not message or message["role"] != "assistant":
            raise ValueError("Resposta do Jarvis não encontrada.")
        item_id, now = str(uuid.uuid4()), utc_now()
        repository.execute(
            "INSERT INTO message_feedback VALUES (?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET rating=excluded.rating,correction=excluded.correction,created_at=excluded.created_at",
            (item_id, message_id, payload.rating, payload.correction, now),
        )
        return repository.row("SELECT * FROM message_feedback WHERE message_id=?", (message_id,)) or {}

    def learning(self) -> list[dict[str, Any]]:
        return repository.rows(
            "SELECT f.*,m.content AS response,c.title AS conversation_title FROM message_feedback f "
            "JOIN messages m ON m.id=f.message_id JOIN conversations c ON c.id=m.conversation_id ORDER BY f.created_at DESC"
        )


memory_service = MemoryService()
task_service = TaskService()
knowledge_service = KnowledgeService()
conversation_service = ConversationService()
