import json
import uuid
from typing import Any

from app.core.database import database, utc_now


class Repository:
    def rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with database() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def row(self, query: str, parameters: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with database() as connection:
            result = connection.execute(query, parameters).fetchone()
            return dict(result) if result else None

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> None:
        with database() as connection:
            connection.execute(query, parameters)

    def create_conversation(self, title: str = "Nova conversa") -> dict[str, Any]:
        item_id, now = str(uuid.uuid4()), utc_now()
        self.execute("INSERT INTO conversations VALUES (?,?,?,?)", (item_id, title, now, now))
        return self.row("SELECT * FROM conversations WHERE id=?", (item_id,)) or {}

    def add_message(self, conversation_id: str, role: str, content: str, context: dict[str, Any] | None = None, generation_status: str = "complete") -> dict[str, Any]:
        item_id, now = str(uuid.uuid4()), utc_now()
        self.execute(
            "INSERT INTO messages (id,conversation_id,role,content,context_json,created_at,generation_status) VALUES (?,?,?,?,?,?,?)",
            (item_id, conversation_id, role, content, json.dumps(context or {}, ensure_ascii=False), now, generation_status),
        )
        self.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        return self.row("SELECT * FROM messages WHERE id=?", (item_id,)) or {}

    def audit(self, tool: str, payload: dict[str, Any], result: dict[str, Any], status: str, conversation_id: str | None = None) -> None:
        self.execute(
            "INSERT INTO activity_log VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), utc_now(), tool, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), status, conversation_id),
        )

    def usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        self.execute(
            "INSERT INTO usage_events VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), "ollama", model, input_tokens, output_tokens, 0.0, utc_now()),
        )


repository = Repository()
