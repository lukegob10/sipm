import pytest

from backend.app.models import ChangeLog, Task


@pytest.mark.anyio
@pytest.mark.parametrize("edge,shift", [("9999-12-31", 1), ("0001-01-01", -1), ("2026-01-01", 1_000_000_000)])
async def test_batch_date_overflow_returns_client_error_without_partial_changes(client, db_sessionmaker, edge, shift):
    project = (await client.post("/project-manager/api/projects/", json={"project_name": "Batch Dates"})).json()
    solution = (await client.post(f"/project-manager/api/projects/{project['project_id']}/solutions", json={"solution_name": "Batch Dates"})).json()
    path = f"/project-manager/api/solutions/{solution['solution_id']}/tasks"
    first = (await client.post(path, json={"task_name": "First", "due_date": "2026-01-01", "priority": 3})).json()
    second = (await client.post(path, json={"task_name": "Second", "due_date": edge, "priority": 3})).json()
    ids = [first["task_id"], second["task_id"]]
    with db_sessionmaker() as session:
        before_logs = session.query(ChangeLog).filter(ChangeLog.entity_id.in_(ids)).count()
    response = await client.patch("/project-manager/api/tasks/actions/batch", json={
        "task_ids": ids, "priority": 1, "due_date_shift_days": shift,
    })
    assert response.status_code == 400, response.text
    assert "date" in response.json()["detail"].lower()
    with db_sessionmaker() as session:
        assert [session.get(Task, task_id).priority for task_id in ids] == [3, 3]
        assert session.get(Task, first["task_id"]).due_date.isoformat() == "2026-01-01"
        assert session.get(Task, second["task_id"]).due_date.isoformat() == edge
        assert session.query(ChangeLog).filter(ChangeLog.entity_id.in_(ids)).count() == before_logs
