import asyncio
import json
from collections.abc import AsyncIterator
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
        self.context_builder = ContextBuilder(settings)

    def _conversation(self, conversation_id: str | None, title: str) -> dict[str, Any]:
        conversation = repository.row("SELECT * FROM conversations WHERE id=?", (conversation_id,)) if conversation_id else None
        return conversation or repository.create_conversation(title[:60] or "Nova conversa")

    @staticmethod
    def _calls(model_message: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        calls: list[tuple[str, dict[str, Any]]] = []
        for call in model_message.get("tool_calls", []) or []:
            function = call.get("function", {})
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            calls.append((function.get("name", ""), arguments))
        return calls

    async def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]:
        conversation = self._conversation(conversation_id, message)
        conversation_id = conversation["id"]
        repository.add_message(conversation_id, "user", message)
        built = self.context_builder.build(conversation_id, message, load_persona())
        response = await self.provider.chat(built.messages, self.registry.schemas())
        model_message = response.get("message", {})
        actions: list[dict[str, Any]] = []
        tool_messages: list[dict[str, str]] = []
        for name, arguments in self._calls(model_message):
            outcome = self.executor.request(name, arguments, conversation_id)
            actions.append(outcome)
            if outcome["status"] in {"success", "failed", "blocked"}:
                tool_messages.append({"role": "tool", "content": json.dumps(outcome, ensure_ascii=False), "tool_name": name})
                repository.add_message(conversation_id, "tool", json.dumps({"tool": name, **outcome}, ensure_ascii=False), {"actions": [outcome]})
        content = model_message.get("content", "").strip()
        if tool_messages:
            follow_up = await self.provider.chat(built.messages + [model_message] + tool_messages)
            content = follow_up.get("message", {}).get("content", "").strip()
            response = follow_up
        if any(action["status"] == "pending_confirmation" for action in actions):
            names = ", ".join(action["tool"] for action in actions if action["status"] == "pending_confirmation")
            content = content or f"Propus a ação {names}. Ela só será executada depois da sua confirmação."
        content = content or "Não consegui gerar uma resposta útil. Verifique o estado do modelo local."
        built.evidence["actions"] = actions
        repository.add_message(conversation_id, "assistant", content, built.evidence)
        repository.usage(self.settings.model_name, int(response.get("prompt_eval_count", 0)), int(response.get("eval_count", 0)))
        return {"conversation_id": conversation_id, "message": content, "context": built.evidence, "actions": actions}

    async def stream(self, message: str, conversation_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        conversation = self._conversation(conversation_id, message)
        conversation_id = conversation["id"]
        repository.add_message(conversation_id, "user", message)
        built = self.context_builder.build(conversation_id, message, load_persona())
        content = ""
        actions: list[dict[str, Any]] = []
        model_message: dict[str, Any] = {"role": "assistant", "content": ""}
        metrics: dict[str, Any] = {}
        yield {"type": "start", "conversation_id": conversation_id, "context": built.evidence}
        try:
            async for event in self.provider.stream_chat(built.messages, self.registry.schemas()):
                metrics = event
                chunk_message = event.get("message", {})
                piece = chunk_message.get("content", "")
                if piece:
                    content += piece
                    yield {"type": "token", "content": piece}
                if chunk_message.get("tool_calls"):
                    model_message = chunk_message
            tool_messages: list[dict[str, str]] = []
            for name, arguments in self._calls(model_message):
                outcome = self.executor.request(name, arguments, conversation_id)
                actions.append(outcome)
                yield {"type": "action", "action": outcome}
                if outcome["status"] in {"success", "failed", "blocked"}:
                    payload = json.dumps({"tool": name, **outcome}, ensure_ascii=False)
                    tool_messages.append({"role": "tool", "content": payload, "tool_name": name})
                    repository.add_message(conversation_id, "tool", payload, {"actions": [outcome]})
            if tool_messages:
                async for event in self.provider.stream_chat(built.messages + [model_message] + tool_messages):
                    metrics = event
                    piece = event.get("message", {}).get("content", "")
                    if piece:
                        content += piece
                        yield {"type": "token", "content": piece}
            if actions and not content.strip():
                names = ", ".join(action.get("tool", "ferramenta") for action in actions)
                content = f"Propus a ação {names}. Ela só será executada depois da sua confirmação."
                yield {"type": "token", "content": content}
            built.evidence["actions"] = actions
            repository.add_message(conversation_id, "assistant", content, built.evidence)
            repository.usage(self.settings.model_name, int(metrics.get("prompt_eval_count", 0)), int(metrics.get("eval_count", 0)))
            yield {"type": "done", "conversation_id": conversation_id, "message": content, "context": built.evidence, "actions": actions}
        except asyncio.CancelledError:
            if content.strip():
                repository.add_message(conversation_id, "assistant", content, built.evidence, generation_status="cancelled")
            raise

    async def confirm_action(self, action_id: str, approved: bool) -> dict[str, Any]:
        action = repository.row("SELECT * FROM pending_actions WHERE id=?", (action_id,))
        if not action:
            raise ValueError("Ação pendente não encontrada.")
        result = self.executor.confirm(action_id, approved)
        conversation_id = action["conversation_id"]
        tool_payload = {"tool": action["tool"], **result}
        repository.add_message(conversation_id, "tool", json.dumps(tool_payload, ensure_ascii=False), {"actions": [tool_payload]})
        if not approved:
            message = "A ação foi cancelada e nada foi executado."
            repository.add_message(conversation_id, "assistant", message, {"actions": [tool_payload]})
            return {**result, "conversation_id": conversation_id, "message": message, "context": {"actions": [tool_payload]}}
        built = self.context_builder.build(conversation_id, action["tool"], load_persona())
        verified = {"role": "system", "content": "Resultado verificado da ferramenta. Só agora descreva a ação como executada:\n" + json.dumps(tool_payload, ensure_ascii=False)}
        response = await self.provider.chat(built.messages + [verified])
        message = response.get("message", {}).get("content", "").strip() or "A ação foi executada com sucesso."
        built.evidence["actions"] = [tool_payload]
        repository.add_message(conversation_id, "assistant", message, built.evidence)
        repository.usage(self.settings.model_name, int(response.get("prompt_eval_count", 0)), int(response.get("eval_count", 0)))
        return {**result, "conversation_id": conversation_id, "message": message, "context": built.evidence}

