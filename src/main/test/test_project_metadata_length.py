import pytest

from backend.app.models import Project
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from test_agent_solution_move_regressions import _seed


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["function", "area"])
async def test_project_metadata_limit_interactive_and_import(client, field):
    good = await client.post("/project-manager/api/projects/", json={"project_name": "Metadata", field: "  " + "a" * 255 + "  "})
    assert good.status_code == 201, good.text
    assert good.json()[field] == "a" * 255
    invalid = await client.post("/project-manager/api/projects/", json={"project_name": "Invalid", field: "a" * 256})
    assert invalid.status_code == 422
    invalid = await client.patch(f"/project-manager/api/projects/{good.json()['project_id']}", json={field: "a" * 256})
    assert invalid.status_code == 422
    for suffix in ("?dry_run=true", ""):
        result = await client.post("/project-manager/api/projects/import" + suffix,
            content=f"project_name,{field}\nImported,{'a' * 256}\n", headers={"Content-Type": "text/csv"})
        assert result.status_code == 200
        assert result.json()["created"] == 0
        assert "255" in result.json()["errors"][0]


@pytest.mark.parametrize("field", ["function", "area"])
def test_project_metadata_limit_agent_validation(db_sessionmaker, field):
    with db_sessionmaker() as session:
        _, ctx = _seed(session)
        project = session.get(Project, "source")
        for operation in (
            {"client_operation_id": "create", "op": "create", "entity": "project", "fields": {"project_name": "New", field: "a" * 256}},
            {"client_operation_id": "update", "op": "update", "entity": "project", "id": "source", "if_updated_at": project.updated_at, "fields": {field: "a" * 256}},
        ):
            result = validate_patch_plan(session, ctx, AgentPatchRequest(dry_run=True, operations=[operation]))
            assert not result.valid
            assert "255" in result.results[0].message
