import pytest

from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from test_agent_solution_move_regressions import _seed


@pytest.mark.anyio
@pytest.mark.parametrize("value", [1e126, -1e126])
async def test_percent_and_confidence_above_database_range_are_rejected(client, value):
    team = (await client.post("/project-manager/api/teams", json={"name": "Float Range"})).json()
    path = f"/project-manager/api/teams/{team['team_id']}/members"
    valid = await client.post(path, json={"member_name": "Valid", "percent_capacity": 1e125})
    assert valid.status_code == 201
    assert (await client.post(path, json={"member_name": "Invalid", "percent_capacity": value})).status_code == 422
    assert (await client.patch(f"{path}/{valid.json()['team_member_id']}", json={"percent_capacity": value})).status_code == 422
    project = (await client.post("/project-manager/api/projects/", json={"project_name": "Float Range"})).json()
    solutions = f"/project-manager/api/projects/{project['project_id']}/solutions"
    valid = await client.post(solutions, json={"solution_name": "Valid", "rag_confidence": 1e125})
    assert valid.status_code == 201
    assert (await client.post(solutions, json={"solution_name": "Invalid", "rag_confidence": value})).status_code == 422
    assert (await client.patch(f"/project-manager/api/solutions/{valid.json()['solution_id']}", json={"rag_confidence": value})).status_code == 422
    for suffix in ("?dry_run=true", ""):
        response = await client.post("/project-manager/api/solutions/import" + suffix,
            content=f"project_name,solution_name,rag_confidence\nNew Project,New Solution,{value}\n",
            headers={"Content-Type": "text/csv"})
        assert response.status_code == 200
        assert response.json()["created"] == 0
        assert response.json()["projects_created"] == 0
        assert "rag_confidence" in response.json()["errors"][0]


def test_agent_confidence_above_database_range_is_rejected(db_sessionmaker):
    with db_sessionmaker() as session:
        _, ctx = _seed(session)
        operation = {"client_operation_id": "new", "op": "create", "entity": "solution", "project_id": "source",
                     "fields": {"solution_name": "New", "rag_confidence": 1e126}}
        result = validate_patch_plan(session, ctx, AgentPatchRequest(dry_run=True, operations=[operation]))
        assert not result.valid
