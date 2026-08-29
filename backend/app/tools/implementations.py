import platform
import uuid
from datetime import datetime
from typing import Any

import psutil

from app.core.database import utc_now
from app.services.knowledge import search_documents
from app.services.repository import repository
from app.tools.base import RiskLevel, Tool


class FunctionTool(Tool):
    def __init__(self, name: str, description: str, schema: dict[str, Any], risk: RiskLevel, function):
        self.name, self.description, self.input_schema, self.risk_level = name, description, schema, risk
        self.function = function

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.function(payload)


def _get_current_datetime(_: dict) -> dict:
    now = datetime.now().astimezone()
    return {"iso": now.isoformat(), "formatted": now.strftime("%d/%m/%Y %H:%M:%S %Z")}


def _get_system_info(_: dict) -> dict:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "ram_gb": round(psutil.virtual_memory().total / 1024**3, 2),
        "ram_available_gb": round(psutil.virtual_memory().available / 1024**3, 2),
        "disk_free_gb": round(psutil.disk_usage("C:\\").free / 1024**3, 2),
    }


def _create_note(payload: dict) -> dict:
    title, content = payload.get("title", "").strip(), payload.get("content", "").strip()
    if not title or not content:
        raise ValueError("Título e conteúdo são obrigatórios.")
    item_id, now = str(uuid.uuid4()), utc_now()
    repository.execute("INSERT INTO notes VALUES (?,?,?,?,?)", (item_id, title, content, now, now))
    return {"id": item_id, "title": title, "created": True}


def _read_note(payload: dict) -> dict:
    note = repository.row("SELECT * FROM notes WHERE id=?", (payload.get("id"),))
    if not note:
        raise ValueError("Nota não encontrada.")
    return note


def _list_notes(_: dict) -> dict:
    return {"items": repository.rows("SELECT * FROM notes ORDER BY updated_at DESC")}


def _save_memory(payload: dict) -> dict:
    content = payload.get("content", "").strip()
    category = payload.get("category", "other")
    if not content:
        raise ValueError("Conteúdo da memória é obrigatório.")
    allowed = {"preference", "person", "project", "routine", "fact", "instruction", "decision", "other"}
    if category not in allowed:
        raise ValueError("Categoria de memória inválida.")
    item_id, now = str(uuid.uuid4()), utc_now()
    with repository_connection() as connection:
        connection.execute(
            "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?)",
            (item_id, content, category, int(payload.get("importance", 3)), "conversation", payload.get("source_reference"), now, now, None),
        )
        connection.execute("INSERT INTO memories_fts VALUES (?,?,?)", (item_id, content, category))
    return {"id": item_id, "content": content, "saved": True}


def _search_memory(payload: dict) -> dict:
    query = payload.get("query", "").strip()
    if not query:
        return {"items": []}
    try:
        items = repository.rows(
            "SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.id WHERE memories_fts MATCH ? ORDER BY rank LIMIT 10",
            (query,),
        )
    except Exception:
        items = repository.rows("SELECT * FROM memories WHERE content LIKE ? LIMIT 10", (f"%{query}%",))
    return {"items": items}


def _list_memories(_: dict) -> dict:
    return {"items": repository.rows("SELECT * FROM memories ORDER BY updated_at DESC")}


def _delete_memory(payload: dict) -> dict:
    item_id = payload.get("id")
    with repository_connection() as connection:
        exists = connection.execute("SELECT 1 FROM memories WHERE id=?", (item_id,)).fetchone()
        if not exists:
            raise ValueError("Memória não encontrada.")
        connection.execute("DELETE FROM memories WHERE id=?", (item_id,))
        connection.execute("DELETE FROM memories_fts WHERE id=?", (item_id,))
    return {"id": item_id, "deleted": True}


def _create_task(payload: dict) -> dict:
    title = payload.get("title", "").strip()
    if not title:
        raise ValueError("Título da tarefa é obrigatório.")
    item_id, now = str(uuid.uuid4()), utc_now()
    repository.execute(
        "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (item_id, title, payload.get("description", ""), "inbox", payload.get("priority", "normal"), now, now,
         payload.get("due_at"), None, payload.get("project"), "chat", payload.get("estimated_minutes")),
    )
    return {"id": item_id, "title": title, "created": True}


def _update_task(payload: dict) -> dict:
    item_id = payload.get("id")
    task = repository.row("SELECT * FROM tasks WHERE id=?", (item_id,))
    if not task:
        raise ValueError("Tarefa não encontrada.")
    allowed = {"title", "description", "status", "priority", "due_at", "project", "estimated_minutes"}
    changes = {key: value for key, value in payload.items() if key in allowed}
    if not changes:
        raise ValueError("Nenhuma alteração válida informada.")
    assignments = ", ".join(f"{key}=?" for key in changes)
    repository.execute(f"UPDATE tasks SET {assignments}, updated_at=? WHERE id=?", tuple(changes.values()) + (utc_now(), item_id))
    return {"id": item_id, "updated": True}


def _complete_task(payload: dict) -> dict:
    item_id, now = payload.get("id"), utc_now()
    if not repository.row("SELECT id FROM tasks WHERE id=?", (item_id,)):
        raise ValueError("Tarefa não encontrada.")
    repository.execute("UPDATE tasks SET status='done', completed_at=?, updated_at=? WHERE id=?", (now, now, item_id))
    return {"id": item_id, "completed": True}


def _list_tasks(payload: dict) -> dict:
    status = payload.get("status")
    if status:
        return {"items": repository.rows("SELECT * FROM tasks WHERE status=? ORDER BY updated_at DESC", (status,))}
    return {"items": repository.rows("SELECT * FROM tasks ORDER BY updated_at DESC")}


def _search_documents(payload: dict) -> dict:
    return {"items": search_documents(payload.get("query", ""))}


def repository_connection():
    from app.core.database import database
    return database()


OBJECT = {"type": "object", "properties": {}, "additionalProperties": False}


def initial_tools() -> list[Tool]:
    return [
        FunctionTool("get_current_datetime", "Obtém data e hora reais.", OBJECT, RiskLevel.SAFE, _get_current_datetime),
        FunctionTool("get_system_info", "Obtém informações reais e não sensíveis do computador.", OBJECT, RiskLevel.SAFE, _get_system_info),
        FunctionTool("create_note", "Cria uma nota local após confirmação.", {"type":"object","properties":{"title":{"type":"string"},"content":{"type":"string"}},"required":["title","content"]}, RiskLevel.CONFIRM, _create_note),
        FunctionTool("read_note", "Lê uma nota pelo id.", {"type":"object","properties":{"id":{"type":"string"}},"required":["id"]}, RiskLevel.SAFE, _read_note),
        FunctionTool("list_notes", "Lista notas locais.", OBJECT, RiskLevel.SAFE, _list_notes),
        FunctionTool("save_memory", "Salva memória estruturada após confirmação.", {"type":"object","properties":{"content":{"type":"string"},"category":{"type":"string"},"importance":{"type":"integer"}},"required":["content"]}, RiskLevel.CONFIRM, _save_memory),
        FunctionTool("search_memory", "Pesquisa a memória local.", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, RiskLevel.SAFE, _search_memory),
        FunctionTool("list_memories", "Lista memórias locais.", OBJECT, RiskLevel.SAFE, _list_memories),
        FunctionTool("delete_memory", "Exclui memória após confirmação.", {"type":"object","properties":{"id":{"type":"string"}},"required":["id"]}, RiskLevel.CONFIRM, _delete_memory),
        FunctionTool("create_task", "Cria uma tarefa local após confirmação.", {"type":"object","properties":{"title":{"type":"string"},"description":{"type":"string"},"priority":{"type":"string"},"due_at":{"type":["string","null"]}},"required":["title"]}, RiskLevel.CONFIRM, _create_task),
        FunctionTool("update_task", "Atualiza uma tarefa após confirmação.", {"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"status":{"type":"string"},"priority":{"type":"string"},"due_at":{"type":["string","null"]}},"required":["id"]}, RiskLevel.CONFIRM, _update_task),
        FunctionTool("complete_task", "Conclui uma tarefa após confirmação.", {"type":"object","properties":{"id":{"type":"string"}},"required":["id"]}, RiskLevel.CONFIRM, _complete_task),
        FunctionTool("list_tasks", "Lista tarefas reais.", {"type":"object","properties":{"status":{"type":"string"}}}, RiskLevel.SAFE, _list_tasks),
        FunctionTool("search_documents", "Pesquisa trechos da biblioteca local.", {"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}, RiskLevel.SAFE, _search_documents),
    ]

