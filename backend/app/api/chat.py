import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.errors import api_error
from app.container import agent
from app.core.cognitive_state import CognitiveEventType, CognitiveState, cognitive_state_service


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None


@router.post("")
async def chat(payload: ChatInput) -> dict:
    try:
        return await agent.chat(payload.message, payload.conversation_id)
    except Exception as exc:
        cognitive_state_service.set_state(CognitiveState.ERROR, reason="chat_failed")
        cognitive_state_service.emit(CognitiveEventType.ERROR, {"message": str(exc)})
        raise api_error(503, "OLLAMA_UNAVAILABLE", "Falha ao conversar com o modelo local.", str(exc)) from exc


@router.post("/stream")
async def stream_chat(payload: ChatInput) -> StreamingResponse:
    async def events():
        try:
            async for event in agent.stream(payload.message, payload.conversation_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            cognitive_state_service.set_state(CognitiveState.ERROR, reason="stream_failed")
            cognitive_state_service.emit(CognitiveEventType.ERROR, {"message": str(exc)})
            error = {"type": "error", "error": {"code": "GENERATION_FAILED", "message": str(exc)}}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
