import pytest

from backend.app.models import Project, Solution
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from test_agent_solution_move_regressions import _seed


@pytest.mark.anyio
async def test_project_and_solution_name_limits_in_interactive_writes(client):
    project = await client.post("/project-manager/api/projects/", json={"project_name": "Project"})
    assert project.status_code == 201, project.text
    project_id = project.json()["project_id"]
    assert (await client.post("/project-manager/api/projects/", json={"project_name": "p" * 255})).status_code == 201
    assert (await client.post("/project-manager/api/projects/", json={"project_name": "x" * 256})).status_code == 400
    assert (await client.patch(f"/project-manager/api/projects/{project_id}", json={"project_name": "x" * 256})).status_code == 400
    path = f"/project-manager/api/projects/{project_id}/solutions"
    valid = await client.post(path, json={"solution_name": "S" * 255, "version": "v" * 255})
    assert valid.status_code == 201, valid.text
    for field in ("solution_name", "version"):
        payload = {"solution_name": "New", field: "z" * 256}
        assert (await client.post(path, json=payload)).status_code == 400
        assert (await client.patch(f"/project-manager/api/solutions/{valid.json()['solution_id']}", json={field: "z" * 256})).status_code == 400


@pytest.mark.anyio
@pytest.mark.parametrize("path,header,row", [
    ("projects/import", "project_name", "{long}"),
    ("solutions/import", "project_name,solution_name,version", "{long},Solution,1"),
    ("solutions/import", "project_name,solution_name,version", "Project,{long},1"),
    ("solutions/import", "project_name,solution_name,version", "Project,Solution,{long}"),
    ("tasks/import", "project_name,solution_name,version,task_name", "{long},Solution,1,Task"),
    ("tasks/import", "project_name,solution_name,version,task_name", "Project,{long},1,Task"),
    ("tasks/import", "project_name,solution_name,version,task_name", "Project,Solution,{long},Task"),
])
async def test_csv_rejects_oversized_hierarchy_before_creating_parents(client, path, header, row):
    body = header + "\n" + row.format(long="a" * 256) + "\n"
    for suffix in ("?dry_run=true", ""):
        response = await client.post("/project-manager/api/" + path + suffix, content=body, headers={"Content-Type": "text/csv"})
        assert response.status_code == 200, response.text
        assert response.json()["created"] == 0
        assert "255" in response.json()["errors"][0]
        assert response.json().get("projects_created", 0) == 0
        assert response.json().get("solutions_created", 0) == 0


def test_agent_rejects_oversized_project_solution_and_version(db_sessionmaker):
    with db_sessionmaker() as session:
        _, ctx = _seed(session)
        project = session.get(Project, "source")
        solution = session.get(Solution, "moving")
        for entity, operation, field, entity_id, timestamp, code in (
            ("project", "create", "project_name", None, None, "PROJECT_NAME_TOO_LONG"),
            ("project", "update", "project_name", "source", project.updated_at, "PROJECT_NAME_TOO_LONG"),
            ("solution", "create", "solution_name", None, None, "SOLUTION_NAME_TOO_LONG"),
            ("solution", "create", "version", None, None, "VERSION_TOO_LONG"),
            ("solution", "update", "solution_name", "moving", solution.updated_at, "SOLUTION_NAME_TOO_LONG"),
            ("solution", "update", "version", "moving", solution.updated_at, "VERSION_TOO_LONG"),
        ):
            fields = {field: "a" * 256}
            if entity == "solution" and operation == "create":
                fields.setdefault("solution_name", "New Solution")
            patch = {"client_operation_id": "change", "entity": entity, "op": operation, "fields": fields}
            if entity_id:
                patch.update(id=entity_id, if_updated_at=timestamp)
            if entity == "solution" and operation == "create":
                patch["project_id"] = "source"
            result = validate_patch_plan(session, ctx, AgentPatchRequest(dry_run=True, operations=[patch]))
            assert not result.valid
            assert result.results[0].code == code
