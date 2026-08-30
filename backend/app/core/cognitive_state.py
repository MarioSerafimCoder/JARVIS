from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import StrEnum
from threading import Lock
from typing import Any


class CognitiveState(StrEnum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    SEARCHING_MEMORY = "SEARCHING_MEMORY"
    SEARCHING_KNOWLEDGE = "SEARCHING_KNOWLEDGE"
    SEARCHING_WEB = "SEARCHING_WEB"
    BROWSING = "BROWSING"
    USING_TOOL = "USING_TOOL"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    ERROR = "ERROR"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    SPEAKING = "SPEAKING"


class CognitiveEventType(StrEnum):
    MEMORY_RETRIEVED = "MEMORY_RETRIEVED"
    MEMORY_CREATED = "MEMORY_CREATED"
    DOCUMENT_RETRIEVED = "DOCUMENT_RETRIEVED"
    WEB_SEARCHED = "WEB_SEARCHED"
    WEB_PAGE_READ = "WEB_PAGE_READ"
    BROWSER_ACTION = "BROWSER_ACTION"
    TOOL_REQUESTED = "TOOL_REQUESTED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    TOOL_FAILED = "TOOL_FAILED"
    GENERATION_STARTED = "GENERATION_STARTED"
    GENERATION_FINISHED = "GENERATION_FINISHED"
    ERROR = "ERROR"
    GRAPH_CHANGED = "GRAPH_CHANGED"


class CognitiveStateService:
    """UI-agnostic state and ephemeral event journal. It never stores chain-of-thought."""

    def __init__(self, capacity: int = 512) -> None:
        self._state = CognitiveState.IDLE
        self._sequence = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = Lock()

    def set_state(self, state: CognitiveState, *, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._state = state
        return self.emit("STATE_CHANGED", {"state": state.value, "reason": reason})

    def emit(self, event_type: CognitiveEventType | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._sequence += 1
            event = {
                "id": self._sequence,
                "type": str(event_type),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state": self._state.value,
                "payload": payload or {},
            }
            self._events.append(event)
            return dict(event)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"state": self._state.value, "last_event_id": self._sequence}

    def events_since(self, event_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(event) for event in self._events if event["id"] > event_id]


cognitive_state_service = CognitiveStateService()
