import platform
import uuid
from datetime import datetime
from typing import Any

import psutil
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import utc_now
from app.services.domains import knowledge_service, memory_service, task_service
from app.services.repository import repository
from app.services.schemas import MemoryInput, TaskInput, TaskPatch
from app.tools.base import RiskLevel, Tool


class FunctionTool(Tool):
    def __init__(self, name: str, description: str, schema: dict[str, Any], risk: RiskLevel, function, input_model: type[BaseModel] | None = None):
        self.name, self.description, self.input_schema, self.risk_level = name, description, schema, risk
        self.function, self.input_model = function, input_model

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.input_model:
            payload = self.input_model.model_validate(payload).model_dump(exclude_none=True)
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
    return memory_service.create(MemoryInput(**payload, source_type="conversation"))


def _search_memory(payload: dict) -> dict:
    query = payload.get("query", "").strip()
    if not query:
        return {"items": []}
    return {"items": memory_service.hybrid_search(query, 10)}


def _list_memories(_: dict) -> dict:
    return {"items": memory_service.list()}


def _delete_memory(payload: dict) -> dict:
    return memory_service.delete(payload["id"])


def _create_task(payload: dict) -> dict:
    return task_service.create(TaskInput(**payload), source="chat")


def _update_task(payload: dict) -> dict:
    item_id = payload.pop("id")
    return task_service.update(item_id, TaskPatch(**payload))


def _complete_task(payload: dict) -> dict:
    return task_service.update(payload["id"], TaskPatch(status="done"))


def _list_tasks(payload: dict) -> dict:
    return {"items": task_service.list(payload.get("status"))}


def _search_documents(payload: dict) -> dict:
    return {"items": knowledge_service.search(payload.get("query", ""))}


def repository_connection():
    from app.core.database import database
    return database()


OBJECT = {"type": "object", "properties": {}, "additionalProperties": False}


class IdPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)


class QueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)


class TaskCreateToolInput(TaskInput):
    model_config = ConfigDict(extra="forbid")


class TaskUpdateToolInput(TaskPatch):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)


class MemoryToolInput(MemoryInput):
    model_config = ConfigDict(extra="forbid")


def initial_tools() -> list[Tool]:
    return [
        FunctionTool("get_current_datetime", "Obtém data e hora reais.", OBJECT, RiskLevel.SAFE, _get_current_datetime),
        FunctionTool("get_system_info", "Obtém informações reais e não sensíveis do computador.", OBJECT, RiskLevel.SAFE, _get_system_info),
        FunctionTool("create_note", "Cria uma nota local após confirmação.", {"type":"object","properties":{"title":{"type":"string"},"content":{"type":"string"}},"required":["title","content"]}, RiskLevel.CONFIRM, _create_note),
        FunctionTool("read_note", "Lê uma nota pelo id.", {"type":"object","properties":{"id":{"type":"string"}},"required":["id"]}, RiskLevel.SAFE, _read_note),
        FunctionTool("list_notes", "Lista notas locais.", OBJECT, RiskLevel.SAFE, _list_notes),
        FunctionTool("save_memory", "Salva memória estruturada após confirmação.", MemoryToolInput.model_json_schema(), RiskLevel.CONFIRM, _save_memory, MemoryToolInput),
        FunctionTool("search_memory", "Pesquisa a memória local por ranking híbrido.", QueryPayload.model_json_schema(), RiskLevel.SAFE, _search_memory, QueryPayload),
        FunctionTool("list_memories", "Lista memórias locais.", OBJECT, RiskLevel.SAFE, _list_memories),
        FunctionTool("delete_memory", "Exclui memória após confirmação.", IdPayload.model_json_schema(), RiskLevel.CONFIRM, _delete_memory, IdPayload),
        FunctionTool("create_task", "Cria uma tarefa local após confirmação.", TaskCreateToolInput.model_json_schema(), RiskLevel.CONFIRM, _create_task, TaskCreateToolInput),
        FunctionTool("update_task", "Atualiza uma tarefa após confirmação.", TaskUpdateToolInput.model_json_schema(), RiskLevel.CONFIRM, _update_task, TaskUpdateToolInput),
        FunctionTool("complete_task", "Conclui uma tarefa após confirmação.", IdPayload.model_json_schema(), RiskLevel.CONFIRM, _complete_task, IdPayload),
        FunctionTool("list_tasks", "Lista tarefas reais.", {"type":"object","properties":{"status":{"type":"string"}}}, RiskLevel.SAFE, _list_tasks),
        FunctionTool("search_documents", "Pesquisa trechos ativos da biblioteca local.", QueryPayload.model_json_schema(), RiskLevel.SAFE, _search_documents, QueryPayload),
    ]
