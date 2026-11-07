import pytest

from backend.app.models import Task
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from test_agent_solution_move_regressions import _seed


@pytest.mark.anyio
async def test_task_name_limit_for_interactive_and_csv(client):
    project = (await client.post("/project-manager/api/projects/", json={"project_name": "Name Limit"})).json()
    solution = (await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions", json={"solution_name": "Name Limit"},
    )).json()
    path = f"/project-manager/api/solutions/{solution['solution_id']}/tasks"
    valid = await client.post(path, json={"task_name": "x" * 255})
    assert valid.status_code == 201, valid.text
    invalid = await client.post(path, json={"task_name": "x" * 256})
    assert invalid.status_code == 400
    updated = await client.patch(f"/project-manager/api/tasks/{valid.json()['task_id']}", json={"task_name": "y" * 256})
    assert updated.status_code == 400
    csv = "project_name,solution_name,task_name\nName Limit,Name Limit," + "z" * 256 + "\n"
    for suffix in ("?dry_run=true", ""):
        imported = await client.post("/project-manager/api/tasks/import" + suffix, content=csv, headers={"Content-Type": "text/csv"})
        assert imported.status_code == 200
        assert imported.json()["created"] == 0
        assert "255" in imported.json()["errors"][0]


def test_agent_validation_rejects_oversized_task_names(db_sessionmaker):
    with db_sessionmaker() as session:
        _, ctx = _seed(session)
        task = session.get(Task, "child")
        for operation in (
            {"client_operation_id": "create", "op": "create", "entity": "task", "solution_id": "moving", "fields": {"task_name": "a" * 256}},
            {"client_operation_id": "update", "op": "update", "entity": "task", "id": "child", "if_updated_at": task.updated_at, "fields": {"task_name": "b" * 256}},
        ):
            result = validate_patch_plan(session, ctx, AgentPatchRequest(dry_run=True, operations=[operation]))
            assert not result.valid
            assert result.results[0].code == "TASK_NAME_TOO_LONG"
