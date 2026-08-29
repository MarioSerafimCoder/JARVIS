from app.services.repository import repository
from app.tools.base import RiskLevel
from app.tools.executor import ToolExecutor
from app.tools.implementations import FunctionTool, initial_tools
from app.tools.registry import ToolRegistry


def test_registry_exposes_risk_levels():
    catalog = ToolRegistry(initial_tools()).catalog()
    risks = {item["risk_level"] for item in catalog}
    assert {"SAFE", "CONFIRM"} <= risks


def test_safe_tool_executes_immediately():
    executor = ToolExecutor(ToolRegistry(initial_tools()))
    result = executor.request("get_current_datetime", {})
    assert result["status"] == "success"
    assert "iso" in result["data"]


def test_confirm_tool_waits_and_then_persists():
    executor = ToolExecutor(ToolRegistry(initial_tools()))
    proposal = executor.request("create_task", {"title": "Validar política"})
    assert proposal["status"] == "pending_confirmation"
    assert repository.rows("SELECT * FROM tasks") == []
    result = executor.confirm(proposal["action_id"], True)
    assert result["status"] == "success"
    assert repository.rows("SELECT title FROM tasks") == [{"title": "Validar política"}]


def test_cancelled_tool_does_not_persist():
    executor = ToolExecutor(ToolRegistry(initial_tools()))
    proposal = executor.request("save_memory", {"content": "Não salvar"})
    result = executor.confirm(proposal["action_id"], False)
    assert result["status"] == "cancelled"
    assert repository.rows("SELECT * FROM memories") == []


def test_dangerous_tool_is_blocked():
    dangerous = FunctionTool("shell", "Nunca executar", {"type": "object"}, RiskLevel.DANGEROUS, lambda _: {"bad": True})
    executor = ToolExecutor(ToolRegistry([dangerous]))
    assert executor.request("shell", {})["status"] == "blocked"


def test_unknown_tool_is_blocked():
    executor = ToolExecutor(ToolRegistry([]))
    assert executor.request("invented", {})["status"] == "blocked"

