from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.database import utc_now
from app.services.repository import repository


VALID_RUN_STATES = {"running", "waiting_confirmation", "completed", "failed", "cancelled"}


class AgentRunService:
    def start(self, conversation_id: str, messages: list[dict[str, Any]], context: dict[str, Any], max_steps: int = 5) -> dict[str, Any]:
        run_id, now = str(uuid.uuid4()), utc_now()
        repository.execute(
            "INSERT INTO agent_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, conversation_id, "running", 0, max_steps, json.dumps(messages, ensure_ascii=False),
             json.dumps(context, ensure_ascii=False), now, now, None, None),
        )
        return self.get(run_id) or {}

    def get(self, run_id: str) -> dict[str, Any] | None:
        item = repository.row("SELECT * FROM agent_runs WHERE id=?", (run_id,))
        if item:
            item["messages"] = json.loads(item.pop("messages_json"))
            item["context"] = json.loads(item.pop("context_json"))
        return item

    def update(self, run_id: str, *, status: str, messages: list[dict[str, Any]], step_count: int, context: dict[str, Any] | None = None, error: str | None = None) -> None:
        if status not in VALID_RUN_STATES:
            raise ValueError("Estado de agent run inválido.")
        completed_at = utc_now() if status in {"completed", "failed", "cancelled"} else None
        repository.execute(
            "UPDATE agent_runs SET status=?,messages_json=?,context_json=COALESCE(?,context_json),step_count=?,updated_at=?,completed_at=?,error=? WHERE id=?",
            (status, json.dumps(messages, ensure_ascii=False), json.dumps(context, ensure_ascii=False) if context is not None else None,
             step_count, utc_now(), completed_at, error, run_id),
        )

    def step(self, run_id: str, step_index: int, kind: str, status: str, *, tool_name: str | None = None, input_data: dict[str, Any] | None = None, result: dict[str, Any] | None = None) -> dict[str, Any]:
        item_id = str(uuid.uuid4())
        repository.execute(
            "INSERT INTO agent_run_steps VALUES (?,?,?,?,?,?,?,?,?)",
            (item_id, run_id, step_index, kind, tool_name, status, json.dumps(input_data or {}, ensure_ascii=False),
             json.dumps(result or {}, ensure_ascii=False), utc_now()),
        )
        return {"id": item_id, "agent_run_id": run_id, "step_index": step_index, "kind": kind, "tool": tool_name, "status": status}

    def details(self, run_id: str) -> dict[str, Any] | None:
        run = self.get(run_id)
        if not run:
            return None
        steps = repository.rows("SELECT * FROM agent_run_steps WHERE agent_run_id=? ORDER BY step_index,created_at", (run_id,))
        for step in steps:
            step["input"] = json.loads(step.pop("input_json"))
            step["result"] = json.loads(step.pop("result_json"))
        return {**run, "steps": steps}


agent_run_service = AgentRunService()
