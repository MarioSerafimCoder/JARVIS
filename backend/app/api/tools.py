import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import api_error
from app.container import agent, tool_registry
from app.services.repository import repository


router = APIRouter(prefix="/tools", tags=["tools"])


class ConfirmationInput(BaseModel):
    approved: bool


@router.get("")
def tools() -> list[dict]:
    return tool_registry.catalog()


@router.get("/pending")
def pending_tools() -> list[dict]:
    items = repository.rows("SELECT * FROM pending_actions WHERE status='pending_confirmation' ORDER BY created_at DESC")
    for item in items:
        item["input"] = json.loads(item.pop("input_json"))
        item["display"] = json.loads(item.pop("display_json") or "{}")
        item["action_id"] = item["id"]
    return items


@router.post("/{action_id}/confirm")
async def confirm_tool(action_id: str, payload: ConfirmationInput) -> dict:
    try:
        return await agent.confirm_action(action_id, payload.approved)
    except ValueError as exc:
        raise api_error(404, "NOT_FOUND", str(exc)) from exc
