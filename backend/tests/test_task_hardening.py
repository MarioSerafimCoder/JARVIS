from app.services.domains import task_service
from app.services.schemas import TaskInput, TaskPatch


def test_reopening_task_clears_completed_at(isolated_data):
    task = task_service.create(TaskInput(title="Reabrir", status="done"))
    assert task["completed_at"]
    reopened = task_service.update(task["id"], TaskPatch(status="doing"))
    assert reopened["status"] == "doing"
    assert reopened["completed_at"] is None
