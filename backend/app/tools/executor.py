import json
import uuid
from typing import Any

from app.core.database import utc_now
from app.core.cognitive_graph import cognitive_graph_service
from app.core.cognitive_state import CognitiveEventType, CognitiveState, cognitive_state_service
from app.services.repository import repository
from app.tools.base import RiskLevel
from app.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def request(self, name: str, payload: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        try:
            tool = self.registry.get(name)
        except KeyError as exc:
            result = {"status": "blocked", "error": str(exc)}
            repository.audit(name, payload, result, "blocked", conversation_id)
            return result
        if tool.risk_level == RiskLevel.DANGEROUS:
            result = {"status": "blocked", "error": "Ferramenta perigosa desabilitada nesta versão."}
            repository.audit(name, payload, result, "blocked", conversation_id)
            return result
        if tool.risk_level == RiskLevel.CONFIRM:
            action_id = str(uuid.uuid4())
            repository.execute(
                "INSERT INTO pending_actions (id,tool,input_json,status,conversation_id,created_at,resolved_at,executed_at) VALUES (?,?,?,?,?,?,?,?)",
                (action_id, name, json.dumps(payload, ensure_ascii=False), "pending_confirmation", conversation_id, utc_now(), None, None),
            )
            cognitive_state_service.set_state(CognitiveState.WAITING_CONFIRMATION, reason=name)
            cognitive_state_service.emit(CognitiveEventType.TOOL_REQUESTED, {"tool": name, "action_id": action_id, "status": "pending_confirmation"})
            return {"status": "pending_confirmation", "action_id": action_id, "tool": name, "input": payload}
        return self._execute(tool.name, payload, conversation_id)

    def confirm(self, action_id: str, approved: bool) -> dict[str, Any]:
        action = repository.row("SELECT * FROM pending_actions WHERE id=?", (action_id,))
        if not action or action["status"] != "pending_confirmation":
            raise ValueError("Ação pendente não encontrada.")
        if not approved:
            result = {"status": "cancelled", "action_id": action_id}
            repository.execute("UPDATE pending_actions SET status='cancelled', resolved_at=? WHERE id=?", (utc_now(), action_id))
            repository.audit(action["tool"], json.loads(action["input_json"]), result, "cancelled", action["conversation_id"])
            return result
        repository.execute("UPDATE pending_actions SET status='executing' WHERE id=?", (action_id,))
        result = self._execute(action["tool"], json.loads(action["input_json"]), action["conversation_id"])
        now = utc_now()
        repository.execute("UPDATE pending_actions SET status=?, resolved_at=?, executed_at=? WHERE id=?", (result["status"], now, now, action_id))
        return {**result, "action_id": action_id}

    def _execute(self, name: str, payload: dict[str, Any], conversation_id: str | None) -> dict[str, Any]:
        tool = self.registry.get(name)
        cognitive_state_service.set_state(CognitiveState.USING_TOOL, reason=name)
        try:
            data = tool.execute(payload)
            result = {"status": "success", "data": data}
            repository.audit(name, payload, result, "success", conversation_id)
            cognitive_state_service.emit(CognitiveEventType.TOOL_EXECUTED, {"tool": name, "result": "success"})
            if name == "save_memory" and isinstance(data, dict) and data.get("id"):
                cognitive_graph_service.memory_created(data["id"])
            elif name in {"delete_memory", "create_task", "update_task", "complete_task", "create_note"}:
                cognitive_graph_service.graph_changed(f"tool_{name}", data.get("id") if isinstance(data, dict) else None)
            return result
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}
            repository.audit(name, payload, result, "failed", conversation_id)
            cognitive_state_service.set_state(CognitiveState.ERROR, reason=name)
            cognitive_state_service.emit(CognitiveEventType.TOOL_FAILED, {"tool": name, "error": str(exc)})
            return result
