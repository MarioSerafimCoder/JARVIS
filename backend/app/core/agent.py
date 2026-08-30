import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.cognitive_graph import cognitive_graph_service
from app.core.cognitive_state import CognitiveEventType, CognitiveState, cognitive_state_service
from app.core.config import Settings
from app.core.context import ContextBuilder
from app.core.persona import load_persona
from app.llm.base import LLMProvider
from app.services.agent_runs import agent_run_service
from app.services.domains import conversation_service
from app.services.memory_consolidator import memory_consolidator
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
                try:
                    arguments = json.loads(arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {"_invalid_json": arguments}
            if not isinstance(arguments, dict):
                arguments = {"_invalid_arguments": arguments}
            calls.append((function.get("name", ""), arguments))
        return calls

    @staticmethod
    def _tool_message(name: str, outcome: dict[str, Any]) -> dict[str, Any]:
        return {"role": "tool", "content": "Resultado verificado da ferramenta:\n" + json.dumps({"tool": name, **outcome}, ensure_ascii=False), "tool_name": name}

    @staticmethod
    def _emit_context(evidence: dict[str, Any]) -> None:
        memories = [f"memory:{item['id']}" for item in evidence.get("memories", [])]
        documents = [f"document:{item['document_id']}" for item in evidence.get("documents", [])]
        tasks = [f"task:{item['id']}" for item in evidence.get("tasks", [])]
        if memories:
            cognitive_state_service.set_state(CognitiveState.SEARCHING_MEMORY, reason="context_retrieval")
            cognitive_state_service.emit(CognitiveEventType.MEMORY_RETRIEVED, {"node_ids": memories})
            cognitive_graph_service.record_cooccurrence([item.split(":", 1)[1] for item in memories])
        if documents:
            cognitive_state_service.set_state(CognitiveState.SEARCHING_KNOWLEDGE, reason="context_retrieval")
            cognitive_state_service.emit(CognitiveEventType.DOCUMENT_RETRIEVED, {"node_ids": documents})
        cognitive_state_service.set_state(CognitiveState.THINKING, reason="generation")
        cognitive_state_service.emit("CONTEXT_SELECTED", {"node_ids": memories + documents + tasks})

    @staticmethod
    def _record_network_evidence(name: str, outcome: dict[str, Any], evidence: dict[str, Any], conversation_id: str) -> None:
        if not isinstance(outcome.get("data"), dict) or (outcome.get("status") != "success" and not name.startswith("browser_")):
            return
        data = outcome["data"]
        web = evidence.setdefault("web", {"queries": [], "pages": [], "sources": [], "used": []})
        if name == "web_search":
            web["queries"].append({"query": data.get("query"), "searched_at": data.get("sources", [{}])[0].get("retrieved_at") if data.get("sources") else None, "redactions": data.get("redactions", [])})
            for source in data.get("sources", []):
                if not any(item.get("source_id") == source.get("source_id") for item in web["sources"]):
                    web["sources"].append(source)
                    repository.execute(
                        "INSERT OR REPLACE INTO web_sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (source["source_id"], conversation_id, evidence.get("source_message_id"), data.get("query"), source.get("title", ""), source.get("url", ""), source.get("domain", ""), source.get("published_at"), source.get("retrieved_at"), source.get("excerpt", "")),
                    )
        elif name == "web_read":
            page = {key: data.get(key) for key in ("source_id", "title", "url", "domain", "retrieved_at", "truncated")}
            web["pages"].append(page)
            web["used"].append(data.get("source_id"))
        elif name.startswith("browser_"):
            evidence.setdefault("browser", []).append({"action": name, "site": data.get("site"), "verified": data.get("verified"), "status": data.get("status", outcome.get("status"))})

    def _start(self, message: str, conversation_id: str | None) -> tuple[str, str, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        conversation = self._conversation(conversation_id, message)
        conversation_id = conversation["id"]
        user_message = repository.add_message(conversation_id, "user", message)
        built = self.context_builder.build(conversation_id, message, load_persona())
        built.evidence["source_message_id"] = user_message["id"]
        self._emit_context(built.evidence)
        run = agent_run_service.start(conversation_id, built.messages, built.evidence, self.settings.max_agent_cycles)
        return run["id"], conversation_id, user_message, built.messages, built.evidence

    def _post_turn(self, conversation_id: str, user_message: dict[str, Any]) -> list[dict[str, Any]]:
        conversation_service.maybe_update_summary(conversation_id, self.settings.conversation_summary_interval)
        return memory_consolidator.analyze(user_message["content"], conversation_id=conversation_id, source_message_id=user_message["id"])

    async def _continue_non_stream(self, run_id: str, conversation_id: str, messages: list[dict[str, Any]], evidence: dict[str, Any], step_count: int = 0, actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        actions = list(actions or [])
        total_prompt = total_output = 0
        while step_count < self.settings.max_agent_cycles:
            response = await self.provider.chat(messages, self.registry.schemas())
            total_prompt += int(response.get("prompt_eval_count", 0)); total_output += int(response.get("eval_count", 0))
            model_message = response.get("message", {})
            step_count += 1
            calls = self._calls(model_message)
            agent_run_service.step(run_id, step_count, "model", "tool_requested" if calls else "answered", result={"tool_count": len(calls), "has_content": bool(model_message.get("content", "").strip())})
            if not calls:
                content = model_message.get("content", "").strip() or "Não consegui gerar uma resposta útil. Verifique o modelo local."
                evidence.update({"actions": actions, "agent_run_id": run_id, "agent_steps": step_count})
                assistant = repository.add_message(conversation_id, "assistant", content, evidence)
                agent_run_service.update(run_id, status="completed", messages=messages + [model_message], step_count=step_count, context=evidence)
                repository.usage(self.settings.model_name, total_prompt, total_output)
                cognitive_state_service.emit(CognitiveEventType.GENERATION_FINISHED, {"status": "complete", "agent_run_id": run_id})
                cognitive_state_service.set_state(CognitiveState.IDLE, reason="agent_run_complete")
                return {"conversation_id": conversation_id, "message": content, "message_id": assistant["id"], "context": evidence, "actions": actions, "agent_run_id": run_id, "agent_status": "completed"}
            messages.append(model_message)
            for name, arguments in calls:
                outcome = self.executor.request(name, arguments, conversation_id, run_id)
                actions.append(outcome)
                self._record_network_evidence(name, outcome, evidence, conversation_id)
                agent_run_service.step(run_id, step_count, "tool", outcome["status"], tool_name=name, input_data=arguments, result=outcome)
                if outcome["status"] == "pending_confirmation":
                    evidence.update({"actions": actions, "agent_run_id": run_id, "agent_steps": step_count})
                    agent_run_service.update(run_id, status="waiting_confirmation", messages=messages, step_count=step_count, context=evidence)
                    cognitive_state_service.set_state(CognitiveState.WAITING_CONFIRMATION, reason=name)
                    content = model_message.get("content", "").strip() or f"Preparei a ação {name}. Confirme para continuar exatamente este fluxo."
                    assistant = repository.add_message(conversation_id, "assistant", content, evidence)
                    return {"conversation_id": conversation_id, "message": content, "message_id": assistant["id"], "context": evidence, "actions": actions, "agent_run_id": run_id, "agent_status": "waiting_confirmation"}
                tool_message = self._tool_message(name, outcome)
                messages.append(tool_message)
                repository.add_message(conversation_id, "tool", tool_message["content"], {"actions": [outcome], "agent_run_id": run_id})
        return self._max_loop(run_id, conversation_id, messages, evidence, actions, step_count)

    def _max_loop(self, run_id: str, conversation_id: str, messages: list[dict[str, Any]], evidence: dict[str, Any], actions: list[dict[str, Any]], step_count: int) -> dict[str, Any]:
        message = "Interrompi o fluxo com segurança após atingir o limite de 5 ciclos. Nenhuma nova ferramenta será executada sem uma nova solicitação."
        evidence.update({"actions": actions, "agent_run_id": run_id, "agent_steps": step_count, "limit_reached": True})
        assistant = repository.add_message(conversation_id, "assistant", message, evidence)
        agent_run_service.update(run_id, status="failed", messages=messages, step_count=step_count, context=evidence, error="max_cycles_reached")
        cognitive_state_service.set_state(CognitiveState.ERROR, reason="agent_max_cycles")
        return {"conversation_id": conversation_id, "message": message, "message_id": assistant["id"], "context": evidence, "actions": actions, "agent_run_id": run_id, "agent_status": "failed"}

    async def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]:
        cognitive_state_service.set_state(CognitiveState.THINKING, reason="chat")
        cognitive_state_service.emit(CognitiveEventType.GENERATION_STARTED, {})
        run_id, conversation_id, user_message, messages, evidence = self._start(message, conversation_id)
        try:
            result = await self._continue_non_stream(run_id, conversation_id, messages, evidence)
            result["memory_candidates"] = self._post_turn(conversation_id, user_message)
            return result
        except Exception as exc:
            agent_run_service.update(run_id, status="failed", messages=messages, step_count=0, context=evidence, error=str(exc))
            cognitive_state_service.set_state(CognitiveState.ERROR, reason="agent_run_failed")
            raise

    async def stream(self, message: str, conversation_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        cognitive_state_service.set_state(CognitiveState.THINKING, reason="stream")
        cognitive_state_service.emit(CognitiveEventType.GENERATION_STARTED, {})
        run_id, conversation_id, user_message, messages, evidence = self._start(message, conversation_id)
        actions: list[dict[str, Any]] = []
        step_count = 0
        total_prompt = total_output = 0
        emitted_content = ""
        yield {"type": "start", "conversation_id": conversation_id, "context": evidence, "agent_run_id": run_id}
        try:
            while step_count < self.settings.max_agent_cycles:
                model_message: dict[str, Any] = {"role": "assistant", "content": "", "tool_calls": []}
                content = ""
                async for event in self.provider.stream_chat(messages, self.registry.schemas()):
                    total_prompt += int(event.get("prompt_eval_count", 0)); total_output += int(event.get("eval_count", 0))
                    chunk = event.get("message", {})
                    piece = chunk.get("content", "")
                    if piece:
                        content += piece
                        yield {"type": "token", "content": piece}
                    if chunk.get("tool_calls"):
                        model_message["tool_calls"] = chunk["tool_calls"]
                model_message["content"] = content
                step_count += 1
                calls = self._calls(model_message)
                agent_run_service.step(run_id, step_count, "model", "tool_requested" if calls else "answered", result={"tool_count": len(calls), "has_content": bool(content.strip())})
                if not calls:
                    content = (emitted_content + content).strip() or "Não consegui gerar uma resposta útil. Verifique o modelo local."
                    evidence.update({"actions": actions, "agent_run_id": run_id, "agent_steps": step_count})
                    assistant = repository.add_message(conversation_id, "assistant", content, evidence)
                    agent_run_service.update(run_id, status="completed", messages=messages + [model_message], step_count=step_count, context=evidence)
                    repository.usage(self.settings.model_name, total_prompt, total_output)
                    candidates = self._post_turn(conversation_id, user_message)
                    cognitive_state_service.emit(CognitiveEventType.GENERATION_FINISHED, {"status": "complete", "agent_run_id": run_id})
                    cognitive_state_service.set_state(CognitiveState.IDLE, reason="agent_run_complete")
                    yield {"type": "done", "conversation_id": conversation_id, "message": content, "message_id": assistant["id"], "context": evidence, "actions": actions, "agent_run_id": run_id, "agent_status": "completed", "memory_candidates": candidates}
                    return
                messages.append(model_message)
                for name, arguments in calls:
                    outcome = self.executor.request(name, arguments, conversation_id, run_id)
                    actions.append(outcome)
                    self._record_network_evidence(name, outcome, evidence, conversation_id)
                    agent_run_service.step(run_id, step_count, "tool", outcome["status"], tool_name=name, input_data=arguments, result=outcome)
                    yield {"type": "action", "action": outcome, "agent_run_id": run_id}
                    if outcome["status"] == "pending_confirmation":
                        evidence.update({"actions": actions, "agent_run_id": run_id, "agent_steps": step_count})
                        agent_run_service.update(run_id, status="waiting_confirmation", messages=messages, step_count=step_count, context=evidence)
                        pending_content = (emitted_content + content).strip()
                        if not pending_content:
                            pending_content = f"Preparei a ação {name}. Confirme para continuar exatamente este fluxo."
                            yield {"type": "token", "content": pending_content}
                        assistant = repository.add_message(conversation_id, "assistant", pending_content, evidence)
                        candidates = self._post_turn(conversation_id, user_message)
                        yield {"type": "done", "conversation_id": conversation_id, "message": pending_content, "message_id": assistant["id"], "context": evidence, "actions": actions, "agent_run_id": run_id, "agent_status": "waiting_confirmation", "memory_candidates": candidates}
                        return
                    tool_message = self._tool_message(name, outcome)
                    messages.append(tool_message)
                    repository.add_message(conversation_id, "tool", tool_message["content"], {"actions": [outcome], "agent_run_id": run_id})
                emitted_content += content
            result = self._max_loop(run_id, conversation_id, messages, evidence, actions, step_count)
            yield {"type": "token", "content": result["message"]}
            yield {"type": "done", **result}
        except asyncio.CancelledError:
            agent_run_service.update(run_id, status="cancelled", messages=messages, step_count=step_count, context=evidence)
            cognitive_state_service.emit(CognitiveEventType.GENERATION_FINISHED, {"status": "cancelled", "agent_run_id": run_id})
            cognitive_state_service.set_state(CognitiveState.IDLE, reason="generation_cancelled")
            raise
        except Exception as exc:
            agent_run_service.update(run_id, status="failed", messages=messages, step_count=step_count, context=evidence, error=str(exc))
            cognitive_state_service.set_state(CognitiveState.ERROR, reason="generation_failed")
            cognitive_state_service.emit(CognitiveEventType.ERROR, {"message": str(exc), "agent_run_id": run_id})
            raise

    async def confirm_action(self, action_id: str, approved: bool) -> dict[str, Any]:
        action = repository.row("SELECT * FROM pending_actions WHERE id=?", (action_id,))
        if not action:
            raise ValueError("Ação pendente não encontrada.")
        run_id = action.get("agent_run_id")
        run = agent_run_service.get(run_id) if run_id else None
        if run_id and (not run or run["status"] != "waiting_confirmation"):
            raise ValueError("O fluxo associado não está aguardando confirmação.")
        result = self.executor.confirm(action_id, approved)
        conversation_id = action["conversation_id"]
        tool_message = self._tool_message(action["tool"], result)
        repository.add_message(conversation_id, "tool", tool_message["content"], {"actions": [result], "agent_run_id": run_id})
        if not approved:
            message = "A ação foi cancelada e o fluxo foi encerrado sem executá-la."
            assistant = repository.add_message(conversation_id, "assistant", message, {"actions": [result], "agent_run_id": run_id})
            if run:
                agent_run_service.update(run_id, status="cancelled", messages=run["messages"] + [tool_message], step_count=run["step_count"], context=run["context"])
            cognitive_state_service.set_state(CognitiveState.IDLE, reason="action_cancelled")
            return {**result, "conversation_id": conversation_id, "message": message, "message_id": assistant["id"], "context": {"actions": [result], "agent_run_id": run_id}, "agent_status": "cancelled"}
        if run:
            self._record_network_evidence(action["tool"], result, run["context"], conversation_id)
        if not run:
            built = self.context_builder.build(conversation_id, action["tool"], load_persona())
            response = await self.provider.chat(built.messages + [tool_message])
            message = response.get("message", {}).get("content", "").strip() or "A ação foi executada com sucesso."
            assistant = repository.add_message(conversation_id, "assistant", message, {"actions": [result]})
            return {**result, "conversation_id": conversation_id, "message": message, "message_id": assistant["id"], "context": {"actions": [result]}}
        cognitive_state_service.set_state(CognitiveState.THINKING, reason="agent_run_resume")
        continued = await self._continue_non_stream(run_id, conversation_id, run["messages"] + [tool_message], run["context"], run["step_count"], [result])
        return {**result, **continued}
