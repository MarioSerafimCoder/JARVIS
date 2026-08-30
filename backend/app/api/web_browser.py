from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.container import browser_agent
from app.core.database import utc_now
from app.services.repository import repository


router = APIRouter(tags=["web-browser"])


class AccessModeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str


def _set_mode(key: str, payload: AccessModeInput, allowed: set[str]) -> dict:
    mode = payload.mode.upper()
    if mode not in allowed:
        raise HTTPException(422, f"Modo inválido. Use: {', '.join(sorted(allowed))}.")
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,?)", (key, json.dumps({"mode": mode}), utc_now()))
    return {"mode": mode}


@router.put("/settings/web-access")
def update_web_access(payload: AccessModeInput) -> dict:
    return _set_mode("web_access", payload, {"OFF", "ASK", "ON"})


@router.put("/settings/browser-access")
def update_browser_access(payload: AccessModeInput) -> dict:
    return _set_mode("browser_access", payload, {"OFF", "ON"})


@router.get("/browser/sites")
def sites() -> list[dict]:
    return [browser_agent.sessions.status("amazon")]


@router.post("/browser/sites/{site}/connect")
def connect_site(site: str) -> dict:
    try:
        return browser_agent.sessions.connect(site)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(503 if isinstance(exc, RuntimeError) else 422, str(exc)) from exc


@router.get("/browser/sites/{site}/status")
def site_status(site: str) -> dict:
    if site != "amazon":
        raise HTTPException(404, "Site não suportado.")
    return browser_agent.sessions.status(site)


@router.post("/browser/sites/{site}/disconnect")
def disconnect_site(site: str) -> dict:
    try:
        return browser_agent.sessions.disconnect(site)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/web/sources/{conversation_id}")
def web_sources(conversation_id: str) -> list[dict]:
    return repository.rows("SELECT * FROM web_sources WHERE conversation_id=? ORDER BY retrieved_at DESC", (conversation_id,))

