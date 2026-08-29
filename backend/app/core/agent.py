import json
from typing import Any

from app.core.config import Settings
from app.core.context import ContextBuilder
from app.core.persona import load_persona
from app.llm.base import LLMProvider
from app.services.repository import repository
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class AgentController:
    def __init__(self, provider: LLMProvider, registry: ToolRegistry, executor: ToolExecutor, settings: Settings):
        self.provider, self.registry, self.executor, self.settings = provider, registry, executor, settings
        self.context_builder = ContextBuilder()

    async def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]:
        conversation = repository.row("SELECT * FROM conversations WHERE id=?", (conversation_id,)) if conversation_id else None
        if not conversation:
            conversation = repository.create_conversation(message[:60] or "Nova conversa")
        conversation_id = conversation["id"]
        repository.add_message(conversation_id, "user", message)
        built = self.context_builder.build(conversation_id, message, load_persona())
        response = await self.provider.chat(built.messages, self.registry.schemas())
        model_message = response.get("message", {})
        actions: list[dict[str, Any]] = []
        safe_tool_messages: list[dict[str, str]] = []
        for call in model_message.get("tool_calls", []) or []:
            function = call.get("function", {})
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            outcome = self.executor.request(function.get("name", ""), arguments, conversation_id)
            actions.append(outcome)
            if outcome["status"] in {"success", "failed", "blocked"}:
                safe_tool_messages.append({"role": "tool", "content": json.dumps(outcome, ensure_ascii=False), "tool_name": function.get("name", "")})
        content = model_message.get("content", "").strip()
        if safe_tool_messages:
            follow_up = await self.provider.chat(built.messages + [model_message] + safe_tool_messages)
            content = follow_up.get("message", {}).get("content", "").strip()
            response = follow_up
        if actions and any(action["status"] == "pending_confirmation" for action in actions):
            pending_names = ", ".join(action["tool"] for action in actions if action["status"] == "pending_confirmation")
            content = content or f"Propus a ação {pending_names}. Ela só será executada depois da sua confirmação."
        content = content or "Não consegui gerar uma resposta útil. Verifique o estado do modelo local."
        built.evidence["actions"] = actions
        repository.add_message(conversation_id, "assistant", content, built.evidence)
        repository.usage(self.settings.model_name, int(response.get("prompt_eval_count", 0)), int(response.get("eval_count", 0)))
        return {"conversation_id": conversation_id, "message": content, "context": built.evidence, "actions": actions}

