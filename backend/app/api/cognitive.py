import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.container import tool_registry
from app.core.cognitive_graph import cognitive_graph_service
from app.core.cognitive_state import cognitive_state_service


router = APIRouter(tags=["cognitive-core"])


@router.get("/cognitive-graph")
def cognitive_graph() -> dict:
    return cognitive_graph_service.build(tool_registry.catalog())


@router.get("/cognitive-state")
def cognitive_state() -> dict:
    return cognitive_state_service.snapshot()


@router.get("/cognitive-events")
async def cognitive_events(request: Request, after: int = 0) -> StreamingResponse:
    header_id = request.headers.get("last-event-id")
    cursor = int(header_id) if header_id and header_id.isdigit() else after

    async def stream():
        nonlocal cursor
        snapshot = cognitive_state_service.snapshot()
        initial = {"id": snapshot["last_event_id"], "type": "STATE_SNAPSHOT", "state": snapshot["state"], "payload": {}}
        yield f"event: cognitive\nid: {initial['id']}\ndata: {json.dumps(initial, ensure_ascii=False)}\n\n"
        last_keepalive = 0
        while not await request.is_disconnected():
            events = cognitive_state_service.events_since(cursor)
            for event in events:
                cursor = event["id"]
                yield f"event: cognitive\nid: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            last_keepalive += 1
            if last_keepalive >= 30:
                yield ": keepalive\n\n"
                last_keepalive = 0
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
