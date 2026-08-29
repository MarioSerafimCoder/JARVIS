import json
import platform
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.container import provider, settings, tool_registry
from app.core.cognitive_graph import cognitive_graph_service
from app.core.database import database, utc_now
from app.core.persona import load_persona, save_persona
from app.core.security import safe_child_path, validate_upload
from app.services.knowledge import index_document, search_documents
from app.services.repository import repository


router = APIRouter()


def not_found(label: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{label} não encontrado.")


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    category: Literal["preference", "person", "project", "routine", "fact", "instruction", "decision", "other"] = "other"
    importance: int = Field(default=3, ge=1, le=5)
    source_type: Literal["conversation", "manual", "document", "integration", "system"] = "manual"
    source_reference: str | None = None


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    status: Literal["inbox", "planned", "doing", "done", "cancelled"] = "inbox"
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    due_at: str | None = None
    project: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=100000)


class ConfirmationInput(BaseModel):
    approved: bool


class PersonaInput(BaseModel):
    content: str


class PreviewInput(BaseModel):
    content: str
    sample: str = "Como você responderia se eu estivesse adiando uma tarefa importante?"


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "llm": await provider.health()}


@router.get("/memory")
def list_memory(query: str | None = None) -> list[dict]:
    if query:
        return repository.rows("SELECT * FROM memories WHERE content LIKE ? ORDER BY updated_at DESC", (f"%{query}%",))
    return repository.rows("SELECT * FROM memories ORDER BY updated_at DESC")


@router.post("/memory")
def create_memory(payload: MemoryInput) -> dict:
    item_id, now = str(uuid.uuid4()), utc_now()
    with database() as connection:
        connection.execute(
            "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?)",
            (item_id, payload.content, payload.category, payload.importance, payload.source_type, payload.source_reference, now, now, None),
        )
        connection.execute("INSERT INTO memories_fts VALUES (?,?,?)", (item_id, payload.content, payload.category))
    result = repository.row("SELECT * FROM memories WHERE id=?", (item_id,)) or {}
    repository.audit("manual_save_memory", payload.model_dump(), result, "success")
    cognitive_graph_service.memory_created(item_id)
    return result


@router.put("/memory/{memory_id}")
def update_memory(memory_id: str, payload: MemoryInput) -> dict:
    if not repository.row("SELECT id FROM memories WHERE id=?", (memory_id,)):
        raise not_found("Memória")
    with database() as connection:
        connection.execute(
            "UPDATE memories SET content=?, category=?, importance=?, source_type=?, source_reference=?, updated_at=? WHERE id=?",
            (payload.content, payload.category, payload.importance, payload.source_type, payload.source_reference, utc_now(), memory_id),
        )
        connection.execute("DELETE FROM memories_fts WHERE id=?", (memory_id,))
        connection.execute("INSERT INTO memories_fts VALUES (?,?,?)", (memory_id, payload.content, payload.category))
    result = repository.row("SELECT * FROM memories WHERE id=?", (memory_id,)) or {}
    cognitive_graph_service.graph_changed("memory_updated", memory_id)
    return result


@router.delete("/memory/{memory_id}")
def delete_memory(memory_id: str) -> dict:
    if not repository.row("SELECT id FROM memories WHERE id=?", (memory_id,)):
        raise not_found("Memória")
    with database() as connection:
        connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        connection.execute("DELETE FROM memories_fts WHERE id=?", (memory_id,))
    result = {"id": memory_id, "deleted": True}
    repository.audit("manual_delete_memory", {"id": memory_id}, result, "success")
    cognitive_graph_service.graph_changed("memory_deleted", memory_id)
    return result


@router.get("/tasks")
def list_tasks(status: str | None = None) -> list[dict]:
    if status:
        return repository.rows("SELECT * FROM tasks WHERE status=? ORDER BY updated_at DESC", (status,))
    return repository.rows("SELECT * FROM tasks ORDER BY updated_at DESC")


@router.post("/tasks")
def create_task(payload: TaskInput) -> dict:
    item_id, now = str(uuid.uuid4()), utc_now()
    completed_at = now if payload.status == "done" else None
    repository.execute(
        "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (item_id, payload.title, payload.description, payload.status, payload.priority, now, now, payload.due_at,
         completed_at, payload.project, "manual", payload.estimated_minutes),
    )
    result = repository.row("SELECT * FROM tasks WHERE id=?", (item_id,)) or {}
    repository.audit("manual_create_task", payload.model_dump(), result, "success")
    cognitive_graph_service.graph_changed("task_created", item_id)
    return result


@router.put("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskInput) -> dict:
    if not repository.row("SELECT id FROM tasks WHERE id=?", (task_id,)):
        raise not_found("Tarefa")
    completed_at = utc_now() if payload.status == "done" else None
    repository.execute(
        "UPDATE tasks SET title=?,description=?,status=?,priority=?,updated_at=?,due_at=?,completed_at=?,project=?,estimated_minutes=? WHERE id=?",
        (payload.title, payload.description, payload.status, payload.priority, utc_now(), payload.due_at,
         completed_at, payload.project, payload.estimated_minutes, task_id),
    )
    result = repository.row("SELECT * FROM tasks WHERE id=?", (task_id,)) or {}
    cognitive_graph_service.graph_changed("task_updated", task_id)
    return result


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> dict:
    if not repository.row("SELECT id FROM tasks WHERE id=?", (task_id,)):
        raise not_found("Tarefa")
    repository.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    result = {"id": task_id, "deleted": True}
    repository.audit("manual_delete_task", {"id": task_id}, result, "success")
    cognitive_graph_service.graph_changed("task_deleted", task_id)
    return result


@router.get("/library")
def library() -> list[dict]:
    return repository.rows("SELECT * FROM documents ORDER BY created_at DESC")


@router.post("/library")
async def upload_document(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        extension = validate_upload(file.filename or "", len(data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    item_id, stored_name, now = str(uuid.uuid4()), f"{uuid.uuid4()}{extension}", utc_now()
    path = safe_child_path(settings.library_path, stored_name)
    path.write_bytes(data)
    repository.execute(
        "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (item_id, stored_name, file.filename, extension[1:], len(data), "processing", "[]", "", now, 0, None),
    )
    indexed = index_document(item_id, file.filename or stored_name, path, extension)
    result = repository.row("SELECT * FROM documents WHERE id=?", (item_id,)) or indexed
    repository.audit("upload_document", {"name": file.filename, "size": len(data)}, result, "success" if indexed["status"] == "ready" else "failed")
    cognitive_graph_service.graph_changed("document_created", item_id)
    return result


@router.delete("/library/{document_id}")
def delete_document(document_id: str) -> dict:
    document = repository.row("SELECT * FROM documents WHERE id=?", (document_id,))
    if not document:
        raise not_found("Documento")
    path = safe_child_path(settings.library_path, document["filename"])
    with database() as connection:
        connection.execute("DELETE FROM document_chunks_fts WHERE document_id=?", (document_id,))
        connection.execute("DELETE FROM documents WHERE id=?", (document_id,))
    if path.exists():
        path.unlink()
    result = {"id": document_id, "deleted": True}
    repository.audit("delete_document", {"id": document_id}, result, "success")
    cognitive_graph_service.graph_changed("document_deleted", document_id)
    return result


@router.get("/activity")
def activity() -> list[dict]:
    items = repository.rows("SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 200")
    for item in items:
        item["input"] = json.loads(item.pop("input_json"))
        item["result"] = json.loads(item.pop("result_json"))
    return items


@router.get("/persona")
def persona() -> dict:
    return {"content": load_persona()}


@router.put("/persona")
def update_persona(payload: PersonaInput) -> dict:
    try:
        save_persona(payload.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"saved": True, "content": load_persona()}


@router.post("/persona/preview")
async def preview_persona(payload: PreviewInput) -> dict:
    result = await provider.chat([{"role": "system", "content": payload.content}, {"role": "user", "content": payload.sample}])
    return {"message": result.get("message", {}).get("content", "")}


@router.get("/usage")
def usage() -> dict:
    totals = repository.row("SELECT COUNT(*) AS inferences, COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens, COALESCE(SUM(estimated_cost),0) AS cost FROM usage_events") or {}
    return {"provider": "Ollama", "model": settings.model_name, "external_apis": 0, **totals}


@router.get("/system")
async def system() -> dict:
    system_tool = tool_registry.get("get_system_info").execute({})
    return {**system_tool, "ollama": await provider.health(), "model": settings.model_name, "context_length": settings.context_length}


@router.get("/devices")
def devices() -> list[dict]:
    return [{"id": "local-pc", "name": platform.node() or "Este computador", "type": "PC", "status": "online", "last_seen": utc_now(), "capabilities": ["backend", "ollama"]}]


@router.get("/integrations")
def integrations() -> list[dict]:
    return [{"name": name, "status": "not_connected", "implemented": False} for name in ("Google", "Microsoft", "GitHub", "Home Assistant")]


@router.get("/search")
def global_search(query: str) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    pattern = f"%{query}%"
    results: list[dict[str, Any]] = []
    for item in repository.rows("SELECT id, content AS title, category AS subtitle FROM memories WHERE content LIKE ? LIMIT 8", (pattern,)):
        results.append({"type": "memory", **item})
    for item in repository.rows("SELECT id, title, status AS subtitle FROM tasks WHERE title LIKE ? OR description LIKE ? LIMIT 8", (pattern, pattern)):
        results.append({"type": "task", **item})
    for item in repository.rows("SELECT id, title, updated_at AS subtitle FROM conversations WHERE title LIKE ? LIMIT 8", (pattern,)):
        results.append({"type": "conversation", **item})
    for item in search_documents(query, 8):
        results.append({"type": "document", "id": item["document_id"], "title": item["filename"], "subtitle": item["relevant_text"][:180]})
    return results


@router.get("/export")
def export_data() -> dict:
    tables = ("conversations", "messages", "memories", "notes", "tasks", "documents", "activity_log", "usage_events")
    return {table: repository.rows(f"SELECT * FROM {table}") for table in tables}
