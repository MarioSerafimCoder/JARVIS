import json
import platform
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.container import browser_agent, provider, settings, tool_registry, voice_profile_manager, voice_worker_provider
from app.core.cognitive_graph import cognitive_graph_service
from app.core.config import PROJECT_ROOT, RUNTIME_ROOT
from app.core.database import database, utc_now
from app.core.persona import compare_persona, keep_persona, load_persona, persona_status, save_persona, update_to_default
from app.core.security import safe_child_path, validate_upload
from app.services.agent_runs import agent_run_service
from app.services.domains import conversation_service, knowledge_service, memory_service, task_service
from app.services.embeddings import embedding_provider
from app.services.knowledge import index_document
from app.services.memory_consolidator import memory_consolidator
from app.services.repository import repository
from app.services.schemas import CandidatePatch, DocumentMetadataInput, MemoryBehaviorInput, MemoryInput, TaskInput


router = APIRouter()


class PersonaInput(BaseModel):
    content: str


class PreviewInput(BaseModel):
    content: str
    sample: str = "Como você responderia se eu estivesse adiando uma tarefa importante?"


class OnboardingInput(BaseModel):
    user_name: str
    memory_mode: str = "suggest"


def not_found(label: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{label} não encontrado.")


@router.get("/health")
async def health() -> dict:
    llm = await provider.health()
    voice = await voice_worker_provider.health()
    return {
        "status": "ok", "architecture": "local-first with optional controlled network",
        "app": {"status": "online"}, "ollama": {"status": llm.get("status", "offline")},
        "model": {"status": "available" if llm.get("model_available") or llm.get("status") == "ok" else "unavailable", "name": settings.model_name},
        "cognitive_events": {"status": "online", "last_event_id": __import__("app.core.cognitive_state", fromlist=["cognitive_state_service"]).cognitive_state_service.snapshot()["last_event_id"]},
        "llm": llm, "voice": voice, "browser": browser_agent.worker.health(),
    }


@router.get("/briefing")
def briefing() -> dict:
    tasks = repository.rows("SELECT * FROM tasks WHERE status NOT IN ('done','cancelled') ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,due_at IS NULL,due_at LIMIT 20")
    now = utc_now()
    important = [item for item in tasks if item["priority"] in {"critical", "high"}]
    overdue = [item for item in tasks if item.get("due_at") and item["due_at"] < now]
    return {
        "next_action": (overdue or important or tasks or [None])[0],
        "important": important[:5], "overdue": overdue[:5],
        "waiting": repository.rows("SELECT id AS action_id,tool,input_json,status,created_at FROM pending_actions WHERE status='pending_confirmation' ORDER BY created_at DESC LIMIT 5"),
        "memory_candidates": memory_consolidator.list()[:5],
        "activity": repository.rows("SELECT id,tool,status,timestamp FROM activity_log ORDER BY timestamp DESC LIMIT 5"),
    }


@router.get("/memory")
def list_memory(query: str | None = None, status: str | None = "active") -> list[dict]:
    return memory_service.list(query, status)


@router.get("/memory/{memory_id}")
def get_memory(memory_id: str) -> dict:
    result = memory_service.get(memory_id)
    if not result:
        raise not_found("Memória")
    result["history"] = repository.rows("SELECT * FROM memories WHERE supersedes_id=? ORDER BY created_at", (memory_id,))
    return result


@router.post("/memory")
def create_memory(payload: MemoryInput) -> dict:
    return memory_service.create(payload)


@router.put("/memory/{memory_id}")
def update_memory(memory_id: str, payload: MemoryInput) -> dict:
    try:
        return memory_service.update(memory_id, payload)
    except ValueError as exc:
        raise not_found("Memória") from exc


@router.post("/memory/{memory_id}/archive")
def archive_memory(memory_id: str) -> dict:
    try:
        return memory_service.archive(memory_id)
    except ValueError as exc:
        raise not_found("Memória") from exc


@router.delete("/memory/{memory_id}")
def delete_memory(memory_id: str) -> dict:
    try:
        return memory_service.delete(memory_id)
    except ValueError as exc:
        raise not_found("Memória") from exc


@router.get("/memory-candidates")
def candidates() -> list[dict]:
    return memory_consolidator.list()


@router.patch("/memory-candidates/{candidate_id}")
def edit_candidate(candidate_id: str, payload: CandidatePatch) -> dict:
    if not repository.row("SELECT id FROM memory_candidates WHERE id=? AND status='candidate'", (candidate_id,)):
        raise not_found("Sugestão")
    repository.execute(
        "UPDATE memory_candidates SET content=?,category=?,memory_type=?,importance=?,confidence=?,updated_at=? WHERE id=?",
        (payload.content, payload.category, payload.memory_type, payload.importance, payload.confidence, utc_now(), candidate_id),
    )
    return repository.row("SELECT * FROM memory_candidates WHERE id=?", (candidate_id,)) or {}


@router.post("/memory-candidates/{candidate_id}/save")
def save_candidate(candidate_id: str) -> dict:
    try:
        return memory_consolidator.save(candidate_id)
    except ValueError as exc:
        raise not_found("Sugestão") from exc


@router.post("/memory-candidates/{candidate_id}/ignore")
def ignore_candidate(candidate_id: str) -> dict:
    return memory_consolidator.ignore(candidate_id)


@router.get("/tasks")
def list_tasks(status: str | None = None) -> list[dict]:
    return task_service.list(status)


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    item = repository.row("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not item:
        raise not_found("Tarefa")
    return item


@router.post("/tasks")
def create_task(payload: TaskInput) -> dict:
    return task_service.create(payload)


@router.put("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskInput) -> dict:
    try:
        return task_service.update(task_id, payload)
    except ValueError as exc:
        raise not_found("Tarefa") from exc


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> dict:
    try:
        return task_service.delete(task_id)
    except ValueError as exc:
        raise not_found("Tarefa") from exc


def _process_document(job_id: str, document_id: str, original_name: str, path: Path, extension: str) -> None:
    repository.execute("UPDATE processing_jobs SET status='running',updated_at=? WHERE id=?", (utc_now(), job_id))
    result = index_document(document_id, original_name, path, extension)
    repository.execute("UPDATE processing_jobs SET status=?,error=?,updated_at=? WHERE id=?", ("completed" if result["status"] == "ready" else "failed", result.get("error"), utc_now(), job_id))
    repository.audit("index_document", {"document_id": document_id}, result, result["status"])
    cognitive_graph_service.graph_changed("document_indexed", document_id)


@router.get("/library")
def library() -> list[dict]:
    return knowledge_service.list()


@router.get("/library/{document_id}")
def get_document(document_id: str) -> dict:
    item = repository.row("SELECT * FROM documents WHERE id=?", (document_id,))
    if not item:
        raise not_found("Documento")
    item["tags"] = json.loads(item["tags"])
    item["job"] = repository.row("SELECT * FROM processing_jobs WHERE entity_id=? ORDER BY created_at DESC LIMIT 1", (document_id,))
    return item


@router.post("/library", status_code=202)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        extension = validate_upload(file.filename or "", len(data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    item_id, job_id, stored_name, now = str(uuid.uuid4()), str(uuid.uuid4()), f"{uuid.uuid4()}{extension}", utc_now()
    path = safe_child_path(settings.library_path, stored_name)
    path.write_bytes(data)
    repository.execute(
        "INSERT INTO documents (id,filename,original_name,type,size,status,tags,description,created_at,chunk_count,error,use_for_rag,collection) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (item_id, stored_name, file.filename, extension[1:], len(data), "queued", "[]", "", now, 0, None, 1, None),
    )
    repository.execute("INSERT INTO processing_jobs VALUES (?,?,?,?,?,?,?)", (job_id, "document_index", item_id, "queued", None, now, now))
    background_tasks.add_task(_process_document, job_id, item_id, file.filename or stored_name, path, extension)
    cognitive_graph_service.graph_changed("document_queued", item_id)
    return {**(repository.row("SELECT * FROM documents WHERE id=?", (item_id,)) or {}), "job_id": job_id}


@router.put("/library/{document_id}")
def update_document(document_id: str, payload: DocumentMetadataInput) -> dict:
    try:
        return knowledge_service.update(document_id, payload)
    except ValueError as exc:
        raise not_found("Documento") from exc


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
        item["input"] = json.loads(item.pop("input_json")); item["result"] = json.loads(item.pop("result_json"))
    return items


@router.get("/learning")
def learning() -> list[dict]:
    return conversation_service.learning()


@router.get("/agent-runs/{run_id}")
def agent_run(run_id: str) -> dict:
    item = agent_run_service.details(run_id)
    if not item:
        raise not_found("Agent run")
    return item


@router.get("/persona")
def persona() -> dict:
    return {"content": load_persona(), **persona_status()}


@router.put("/persona")
def update_persona(payload: PersonaInput) -> dict:
    try:
        save_persona(payload.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"saved": True, "content": load_persona()}


@router.get("/persona/compare")
def persona_compare() -> dict:
    return compare_persona()


@router.post("/persona/update-default")
def persona_update_default() -> dict:
    return update_to_default()


@router.post("/persona/keep")
def persona_keep() -> dict:
    return keep_persona()


@router.post("/persona/preview")
async def preview_persona(payload: PreviewInput) -> dict:
    result = await provider.chat([{"role": "system", "content": payload.content}, {"role": "user", "content": payload.sample}])
    return {"message": result.get("message", {}).get("content", "")}


@router.get("/usage")
def usage() -> dict:
    totals = repository.row("SELECT COUNT(*) AS inferences,COALESCE(SUM(input_tokens),0) AS input_tokens,COALESCE(SUM(output_tokens),0) AS output_tokens,COALESCE(SUM(estimated_cost),0) AS cost FROM usage_events") or {}
    network = repository.row("SELECT COUNT(*) AS count FROM activity_log WHERE tool LIKE 'web_%' OR tool LIKE 'browser_%'") or {"count": 0}
    return {"provider": "Ollama", "model": settings.model_name, "network_actions": network["count"], "paid_external_apis": 0, **totals}


@router.get("/system")
async def system() -> dict:
    system_tool = tool_registry.get("get_system_info").execute({})
    return {**system_tool, "ollama": await provider.health(), "model": settings.model_name, "context_length": settings.context_length, "embeddings": embedding_provider.health()}


@router.get("/settings")
async def get_app_settings() -> dict:
    values = {item["key"]: json.loads(item["value_json"]) for item in repository.rows("SELECT * FROM app_settings")}
    voice_values = {item["key"]: json.loads(item["value_json"]) for item in repository.rows("SELECT * FROM voice_settings")}
    return {"memory_behavior": values.get("memory_behavior", {"mode": "suggest"}), "web_access": values.get("web_access", {"mode": "ASK"}), "browser_access": values.get("browser_access", {"mode": "OFF"}), "model": {"name": settings.model_name, "context_length": settings.context_length}, "cognitive_core": {"max_relationship_degree": 4}, "privacy": {"architecture": "local_first", "telemetry": False, "raw_microphone_saved": False, "network_only_when_enabled": True, "cookies_exposed_to_model": False}, "data": {"database": str(settings.database_path), "browser_profile": str(settings.browser_profile_path)}, "backup": {"directory": str(settings.backup_path), "include_voice_references": voice_values.get("include_references_in_backup", False)}, "system": {"max_agent_cycles": settings.max_agent_cycles}, "voice": {"resource_mode": settings.voice_resource_mode, "worker_url": settings.voice_worker_url, "profile": await voice_profile_manager.status()}}


@router.put("/settings/memory")
def update_memory_behavior(payload: MemoryBehaviorInput) -> dict:
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,?)", ("memory_behavior", payload.model_dump_json(), utc_now()))
    return payload.model_dump()


@router.get("/onboarding")
async def onboarding() -> dict:
    llm = await provider.health()
    saved = repository.row("SELECT value_json FROM app_settings WHERE key='onboarding'")
    profile = repository.row("SELECT value_json FROM app_settings WHERE key='user_profile'")
    candidates = []
    for path in {PROJECT_ROOT / "data", RUNTIME_ROOT / "data"}:
        if path.resolve() != settings.database_path.parents[1].resolve() and path.exists():
            candidates.append({"path": str(path), "available": True})
    app_settings = await get_app_settings()
    return {"completed": bool(saved and json.loads(saved["value_json"]).get("completed")), "user_name": json.loads(profile["value_json"]).get("name", "") if profile else "", "backend": "online", "ollama": llm.get("status", "offline"), "model_available": bool(llm.get("model_available") or llm.get("status") == "ok"), "model": settings.model_name, "gpu_detected": Path("C:/Windows/System32/nvidia-smi.exe").exists(), "memory_behavior": app_settings["memory_behavior"], "migration_candidates": candidates, "requires_account": False, "external_transfer": False}


@router.post("/onboarding/complete")
def complete_onboarding(payload: OnboardingInput) -> dict:
    name = " ".join(payload.user_name.split())[:120]
    if not name:
        raise HTTPException(422, "Informe como o Jarvis deve chamar você.")
    if payload.memory_mode not in {"disabled", "suggest", "auto"}:
        raise HTTPException(422, "Comportamento de memória inválido.")
    now = utc_now()
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,?)", ("user_profile", json.dumps({"name": name}, ensure_ascii=False), now))
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,?)", ("memory_behavior", json.dumps({"mode": payload.memory_mode}), now))
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,?)", ("onboarding", json.dumps({"completed": True}), now))
    return {"completed": True, "user_name": name, "memory_mode": payload.memory_mode}


@router.get("/devices")
def devices() -> list[dict]:
    return [{"id": "local-pc", "name": platform.node() or "Este computador", "type": "PC", "status": "online", "last_seen": utc_now(), "capabilities": ["backend", "ollama"]}]


@router.get("/integrations")
def integrations() -> list[dict]:
    amazon = browser_agent.sessions.status("amazon")
    return [{"name": "Amazon", "site": "amazon", "status": amazon.get("status", "not_connected"), "authenticated": amazon.get("authenticated", False), "implemented": True, "capabilities": amazon.get("capabilities", []), "manual_login": True}, *[{"name": name, "status": "not_connected", "implemented": False} for name in ("Google", "Microsoft", "GitHub", "Home Assistant")]]


@router.get("/search")
def global_search(query: str) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    pattern = f"%{query}%"; results: list[dict[str, Any]] = []
    for item in repository.rows("SELECT id,content AS title,category AS subtitle FROM memories WHERE status='active' AND content LIKE ? LIMIT 8", (pattern,)):
        results.append({"type": "memory", "path": f"/memory/{item['id']}", **item})
    for item in repository.rows("SELECT id,title,status AS subtitle FROM tasks WHERE title LIKE ? OR description LIKE ? LIMIT 8", (pattern, pattern)):
        results.append({"type": "task", "path": f"/tasks/{item['id']}", **item})
    for item in repository.rows("SELECT id,title,updated_at AS subtitle FROM conversations WHERE title LIKE ? LIMIT 8", (pattern,)):
        results.append({"type": "conversation", "path": f"/chat/{item['id']}", **item})
    for item in knowledge_service.search(query, 8):
        results.append({"type": "document", "path": f"/library/{item['document_id']}", "id": item["document_id"], "title": item["filename"], "subtitle": item["relevant_text"][:180]})
    return results


@router.get("/export")
def export_data() -> dict:
    tables = ("conversations", "messages", "conversation_summaries", "message_feedback", "memories", "memory_candidates", "notes", "tasks", "documents", "activity_log", "agent_runs", "agent_run_steps", "usage_events")
    return {table: repository.rows(f"SELECT * FROM {table}") for table in tables}
