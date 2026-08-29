import json

from fastapi import APIRouter

from app.api.errors import api_error
from app.core.database import utc_now
from app.services.repository import repository


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
def list_conversations() -> list[dict]:
    return repository.rows("SELECT * FROM conversations ORDER BY updated_at DESC")


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    item = repository.row("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    if not item:
        raise api_error(404, "NOT_FOUND", "Conversa não encontrada.")
    messages = repository.rows("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conversation_id,))
    for message in messages:
        message["context"] = json.loads(message.pop("context_json"))
    return {**item, "messages": messages}


@router.patch("/{conversation_id}")
def rename_conversation(conversation_id: str, payload: dict[str, str]) -> dict:
    title = payload.get("title", "").strip()
    if not title:
        raise api_error(422, "VALIDATION_ERROR", "Título obrigatório.")
    repository.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title, utc_now(), conversation_id))
    item = repository.row("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    if not item:
        raise api_error(404, "NOT_FOUND", "Conversa não encontrada.")
    return item


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    if not repository.row("SELECT id FROM conversations WHERE id=?", (conversation_id,)):
        raise api_error(404, "NOT_FOUND", "Conversa não encontrada.")
    repository.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    return {"id": conversation_id, "deleted": True}

