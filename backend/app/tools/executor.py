import asyncio
import json
import uuid
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.core.database import utc_now
from app.core.cognitive_graph import cognitive_graph_service
from app.core.cognitive_state import CognitiveEventType, CognitiveState, cognitive_state_service
from app.services.repository import repository
from app.tools.base import RiskLevel
from app.tools.registry import ToolRegistry
from app.web.security import WebQuerySanitizer


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    @staticmethod
    def _audit_payload(name: str, payload: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
        if name == "web_search":
            data = (result or {}).get("data", {})
            if isinstance(data, dict) and data.get("query"):
                return {"query": data["query"], "max_results": payload.get("max_results"), "domains": payload.get("domains", []), "redactions": data.get("redactions", [])}
            try:
                query, redactions = WebQuerySanitizer().sanitize(str(payload.get("query", "")))
                return {"query": query, "redactions": redactions}
            except ValueError:
                return {"query": "[consulta_removida]"}
        if name == "web_read":
            parsed = urlparse(str(payload.get("url", "")))
            safe_netloc = parsed.hostname or "[host_invalido]"
            if parsed.port:
                safe_netloc += f":{parsed.port}"
            return {"url": urlunparse((parsed.scheme, safe_netloc, parsed.path, "", "", ""))}
        return payload

    @staticmethod
    def _display(name: str, payload: dict[str, Any]) -> dict[str, Any]:
        labels = {
            "create_task": "Criar tarefa", "update_task": "Atualizar tarefa", "complete_task": "Concluir tarefa",
            "save_memory": "Salvar memória", "delete_memory": "Excluir memória", "create_note": "Criar nota",
            "browser_add_to_cart": "Adicionar ao carrinho", "browser_remove_from_cart": "Remover do carrinho",
            "browser_change_cart_quantity": "Alterar quantidade",
        }
        title = payload.get("title") or payload.get("content") or payload.get("query")
        details: dict[str, Any] = {}
        if name == "browser_add_to_cart" and payload.get("candidate_id"):
            candidate = repository.row("SELECT title,price_amount,price_currency,seller,variant FROM product_candidates WHERE id=?", (payload["candidate_id"],))
            if candidate:
                title = candidate.get("title") or title
                details = {"price": {"amount": candidate.get("price_amount"), "currency": candidate.get("price_currency")}, "seller": candidate.get("seller"), "variant": payload.get("variant") or candidate.get("variant"), "quantity": payload.get("quantity", 1)}
        return {"kind": name, "label": labels.get(name, name.replace("_", " ").title()), "title": str(title or payload.get("candidate_id") or payload.get("item_id") or "Ação local"), "details": details}

    def request(self, name: str, payload: dict[str, Any], conversation_id: str | None = None, agent_run_id: str | None = None) -> dict[str, Any]:
        try:
            tool = self.registry.get(name)
        except KeyError as exc:
            result = {"status": "blocked", "error": str(exc)}
            repository.audit(name, self._audit_payload(name, payload, result), result, "blocked", conversation_id)
            return result
        risk_level = tool.risk_for(payload)
        if risk_level == RiskLevel.DANGEROUS:
            result = {"status": "blocked", "error": tool.blocked_reason(payload)}
            repository.audit(name, self._audit_payload(name, payload, result), result, "blocked", conversation_id)
            return result
        if risk_level == RiskLevel.CONFIRM:
            action_id = str(uuid.uuid4())
            display = self._display(name, payload)
            repository.execute(
                "INSERT INTO pending_actions (id,tool,input_json,status,conversation_id,created_at,resolved_at,executed_at,agent_run_id,display_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (action_id, name, json.dumps(payload, ensure_ascii=False), "pending_confirmation", conversation_id, utc_now(), None, None, agent_run_id, json.dumps(display, ensure_ascii=False)),
            )
            cognitive_state_service.set_state(CognitiveState.WAITING_CONFIRMATION, reason=name)
            cognitive_state_service.emit(CognitiveEventType.TOOL_REQUESTED, {"tool": name, "action_id": action_id, "status": "pending_confirmation"})
            return {"status": "pending_confirmation", "action_id": action_id, "tool": name, "input": payload, "display": display, "agent_run_id": agent_run_id}
        return self._execute(tool.name, payload, conversation_id)

    async def request_async(self, name: str, payload: dict[str, Any], conversation_id: str | None = None, agent_run_id: str | None = None) -> dict[str, Any]:
        try:
            tool = self.registry.get(name)
        except KeyError as exc:
            result = {"status": "blocked", "error": str(exc)}
            repository.audit(name, self._audit_payload(name, payload, result), result, "blocked", conversation_id)
            return result
        risk_level = tool.risk_for(payload)
        if risk_level == RiskLevel.DANGEROUS:
            result = {"status": "blocked", "error": tool.blocked_reason(payload)}
            repository.audit(name, self._audit_payload(name, payload, result), result, "blocked", conversation_id)
            return result
        if risk_level == RiskLevel.CONFIRM:
            return self.request(name, payload, conversation_id, agent_run_id)
        return await self._execute_async(tool.name, payload, conversation_id)

    def confirm(self, action_id: str, approved: bool) -> dict[str, Any]:
        action = repository.row("SELECT * FROM pending_actions WHERE id=?", (action_id,))
        if not action or action["status"] != "pending_confirmation":
            raise ValueError("Ação pendente não encontrada.")
        if not approved:
            result = {"status": "cancelled", "action_id": action_id}
            repository.execute("UPDATE pending_actions SET status='cancelled', resolved_at=? WHERE id=?", (utc_now(), action_id))
            raw = json.loads(action["input_json"])
            repository.audit(action["tool"], self._audit_payload(action["tool"], raw, result), result, "cancelled", action["conversation_id"])
            return result
        repository.execute("UPDATE pending_actions SET status='executing' WHERE id=?", (action_id,))
        result = self._execute(action["tool"], json.loads(action["input_json"]), action["conversation_id"])
        now = utc_now()
        repository.execute("UPDATE pending_actions SET status=?, resolved_at=?, executed_at=? WHERE id=?", (result["status"], now, now, action_id))
        return {**result, "action_id": action_id, "agent_run_id": action.get("agent_run_id")}

    async def confirm_async(self, action_id: str, approved: bool) -> dict[str, Any]:
        action = repository.row("SELECT * FROM pending_actions WHERE id=?", (action_id,))
        if not action or action["status"] != "pending_confirmation":
            raise ValueError("Ação pendente não encontrada.")
        if not approved:
            return self.confirm(action_id, False)
        repository.execute("UPDATE pending_actions SET status='executing' WHERE id=?", (action_id,))
        result = await self._execute_async(action["tool"], json.loads(action["input_json"]), action["conversation_id"])
        now = utc_now()
        repository.execute("UPDATE pending_actions SET status=?, resolved_at=?, executed_at=? WHERE id=?", (result["status"], now, now, action_id))
        return {**result, "action_id": action_id, "agent_run_id": action.get("agent_run_id")}

    def _state_for(self, name: str) -> None:
        if name == "web_search":
            cognitive_state_service.set_state(CognitiveState.SEARCHING_WEB, reason=name)
        elif name == "web_read" or name.startswith("browser_"):
            cognitive_state_service.set_state(CognitiveState.BROWSING, reason=name)
        else:
            cognitive_state_service.set_state(CognitiveState.USING_TOOL, reason=name)

    def _success(self, name: str, payload: dict[str, Any], data: dict[str, Any], conversation_id: str | None) -> dict[str, Any]:
        semantic_status = str(data.get("status", "")).upper() if isinstance(data, dict) else ""
        # Authentication and CAPTCHA are execution failures to callers, while
        # their precise machine state remains available in data.status.
        status = "failed" if semantic_status in {"AUTH_REQUIRED", "CAPTCHA_REQUIRED", "FAILED"} else semantic_status if semantic_status in {"PRICE_CHANGED", "VARIANT_UNAVAILABLE", "STALE_CANDIDATE", "UNKNOWN", "UNAVAILABLE"} else "success"
        result = {"status": status, "data": data}
        if status == "failed":
            result["error"] = semantic_status or str(data.get("error", "Falha na ferramenta."))
        repository.audit(name, self._audit_payload(name, payload, result), result, status, conversation_id)
        cognitive_state_service.emit(CognitiveEventType.TOOL_EXECUTED, {"tool": name, "result": status})
        if name == "web_search":
            cognitive_state_service.emit(CognitiveEventType.WEB_SEARCHED, {"tool": name, "source_count": len(data.get("sources", []))})
        elif name == "web_read":
            cognitive_state_service.emit(CognitiveEventType.WEB_PAGE_READ, {"tool": name, "url": data.get("url")})
        elif name.startswith("browser_"):
            cognitive_state_service.emit(CognitiveEventType.BROWSER_ACTION, {"tool": name, "verified": data.get("verified", False)})
        if name == "save_memory" and data.get("id"):
            cognitive_graph_service.memory_created(data["id"])
        elif name in {"delete_memory", "create_task", "update_task", "complete_task", "create_note"}:
            cognitive_graph_service.graph_changed(f"tool_{name}", data.get("id"))
        return result

    def _execute(self, name: str, payload: dict[str, Any], conversation_id: str | None) -> dict[str, Any]:
        tool = self.registry.get(name)
        self._state_for(name)
        try:
            data = tool.execute(payload)
            return self._success(name, payload, data, conversation_id)
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}
            repository.audit(name, self._audit_payload(name, payload, result), result, "failed", conversation_id)
            cognitive_state_service.set_state(CognitiveState.ERROR, reason=name)
            cognitive_state_service.emit(CognitiveEventType.TOOL_FAILED, {"tool": name, "error": str(exc)})
            return result

    async def _execute_async(self, name: str, payload: dict[str, Any], conversation_id: str | None) -> dict[str, Any]:
        tool = self.registry.get(name)
        self._state_for(name)
        try:
            data = await asyncio.wait_for(tool.execute_async(payload), timeout=60)
            return self._success(name, payload, data, conversation_id)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            result = {"status": "failed", "error": "TOOL_TIMEOUT"}
            repository.audit(name, self._audit_payload(name, payload, result), result, "failed", conversation_id)
            cognitive_state_service.set_state(CognitiveState.ERROR, reason=f"{name}_timeout")
            cognitive_state_service.emit(CognitiveEventType.TOOL_FAILED, {"tool": name, "error": "TOOL_TIMEOUT"})
            return result
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}
            repository.audit(name, self._audit_payload(name, payload, result), result, "failed", conversation_id)
            cognitive_state_service.set_state(CognitiveState.ERROR, reason=name)
            cognitive_state_service.emit(CognitiveEventType.TOOL_FAILED, {"tool": name, "error": str(exc)})
            return result
