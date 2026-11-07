import pytest

from backend.app.models import Task
from backend.app.routes.tasks.common import _task_actionability
from backend.app.services.work_items import task_actionability
from backend.app.utils.enums import TaskStatus


def test_priority_zero_has_the_highest_urgency():
    task = Task(task_name="Task", status=TaskStatus.to_do, priority=0)
    assert task_actionability(task)["urgency_score"] == 75
    assert _task_actionability(task)["urgency_score"] == 75


@pytest.mark.anyio
async def test_priority_zero_is_preserved_in_task_api(client):
    project = await client.post("/project-manager/api/projects/", json={"project_name": "Priority project"})
    assert project.status_code == 201
    solution = await client.post(
        f"/project-manager/api/projects/{project.json()['project_id']}/solutions", json={"solution_name": "Solution"}
    )
    assert solution.status_code == 201
    task = await client.post(
        f"/project-manager/api/solutions/{solution.json()['solution_id']}/tasks",
        json={"task_name": "Task", "priority": 0},
    )
    assert task.status_code == 201
    assert task.json()["priority"] == 0
    assert task.json()["urgency_score"] == 75


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["status", "priority"])
async def test_task_rejects_null_for_required_fields_without_mutation(client, field):
    project = await client.post("/project-manager/api/projects/", json={"project_name": "Project"})
    assert project.status_code == 201
    solution = await client.post(
        f"/project-manager/api/projects/{project.json()['project_id']}/solutions", json={"solution_name": "Solution"}
    )
    assert solution.status_code == 201
    task = await client.post(
        f"/project-manager/api/solutions/{solution.json()['solution_id']}/tasks",
        json={"task_name": "Task", "status": "in_progress", "priority": 2, "due_date": "2026-12-01"},
    )
    assert task.status_code == 201
    task_id = task.json()["task_id"]
    response = await client.patch(f"/project-manager/api/tasks/{task_id}", json={field: None})
    assert response.status_code == 422
    unchanged = await client.get(f"/project-manager/api/tasks/{task_id}")
    assert unchanged.json()[field] == task.json()[field]
    clear_date = await client.patch(f"/project-manager/api/tasks/{task_id}", json={"due_date": None})
    assert clear_date.status_code == 200
    assert clear_date.json()["due_date"] is None
