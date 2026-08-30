from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


MemoryCategory = Literal["preference", "person", "project", "routine", "fact", "instruction", "decision", "other"]
MemoryType = Literal["semantic", "preference", "episodic", "procedural", "person", "project", "decision"]
MemoryStatus = Literal["candidate", "active", "superseded", "archived"]
TaskStatus = Literal["inbox", "planned", "doing", "done", "cancelled"]
TaskPriority = Literal["low", "normal", "high", "critical"]


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    category: MemoryCategory = "other"
    memory_type: MemoryType | None = None
    importance: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_type: Literal["conversation", "manual", "document", "integration", "system"] = "manual"
    source_reference: str | None = None
    source_message_id: str | None = None
    supersedes_id: str | None = None

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Conteúdo da memória é obrigatório.")
        return value


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=8000)
    status: TaskStatus = "inbox"
    priority: TaskPriority = "normal"
    due_at: str | None = None
    project: str | None = Field(default=None, max_length=300)
    estimated_minutes: int | None = Field(default=None, ge=1, le=100000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Título da tarefa é obrigatório.")
        return value

    @field_validator("due_at")
    @classmethod
    def valid_due_date(cls, value: str | None) -> str | None:
        if value:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Data da tarefa inválida.") from exc
        return value


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: str | None = None
    project: str | None = Field(default=None, max_length=300)
    estimated_minutes: int | None = Field(default=None, ge=1, le=100000)


class DocumentMetadataInput(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=30)
    description: str = Field(default="", max_length=4000)
    use_for_rag: bool = True
    collection: str | None = Field(default=None, max_length=200)


class FeedbackInput(BaseModel):
    rating: Literal[-1, 1]
    correction: str | None = Field(default=None, max_length=8000)


class MemoryBehaviorInput(BaseModel):
    mode: Literal["disabled", "suggest", "auto"] = "suggest"


class CandidatePatch(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    category: MemoryCategory
    memory_type: MemoryType
    importance: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
