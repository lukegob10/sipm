import pytest
from pydantic import ValidationError

from backend.app.schemas import ProjectCreate, ProjectUpdate, SolutionCreate, SolutionUpdate, TaskBatchUpdate, TaskCreate, TaskUpdate
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from test_agent_solution_move_regressions import _seed


@pytest.mark.parametrize("schema,base,fields", [
    (ProjectCreate, {"project_name": "P"}, ("sponsor", "sponsor_user_soeid", "owner", "owner_user_soeid")),
    (ProjectUpdate, {}, ("sponsor", "sponsor_user_soeid", "owner", "owner_user_soeid")),
    (SolutionCreate, {"solution_name": "S"}, ("owner", "owner_user_soeid", "assignee", "assignee_user_soeid", "approver", "approver_user_soeid", "key_stakeholder")),
    (SolutionUpdate, {}, ("owner", "owner_user_soeid", "assignee", "assignee_user_soeid", "approver", "approver_user_soeid", "key_stakeholder")),
    (TaskCreate, {"task_name": "T"}, ("assignee", "assignee_user_soeid")),
    (TaskUpdate, {}, ("assignee", "assignee_user_soeid")),
    (TaskBatchUpdate, {"task_ids": ["task"]}, ("assignee", "assignee_user_soeid")),
])
def test_person_fields_fit_database(schema, base, fields):
    for field in fields:
        assert getattr(schema(**base, **{field: "x" * 255}), field) == "x" * 255
        with pytest.raises(ValidationError):
            schema(**base, **{field: "x" * 256})


@pytest.mark.anyio
@pytest.mark.parametrize("path,header,row", [
    ("projects/import", "project_name,sponsor", "P,{long}"),
    ("projects/import", "project_name,sponsor_user_soeid", "P,{long}"),
    ("projects/import", "project_name,owner", "P,{long}"),
    ("projects/import", "project_name,owner_user_soeid", "P,{long}"),
    *(("solutions/import", f"project_name,solution_name,{field}", "P,S,{long}") for field in ("owner", "owner_user_soeid", "assignee", "assignee_user_soeid", "approver", "approver_user_soeid", "key_stakeholder")),
    *(("tasks/import", f"project_name,solution_name,task_name,{field}", "P,S,T,{long}") for field in ("assignee", "assignee_user_soeid", "solution_owner", "owner")),
])
async def test_csv_person_field_limit_before_creating_parents(client, path, header, row):
    content = header + "\n" + row.format(long="a" * 256) + "\n"
    for suffix in ("?dry_run=true", ""):
        response = await client.post("/project-manager/api/" + path + suffix, content=content, headers={"Content-Type": "text/csv"})
        assert response.status_code == 200, response.text
        assert response.json()["created"] == 0
        assert response.json().get("projects_created", 0) == 0
        assert response.json().get("solutions_created", 0) == 0
        assert "255" in response.json()["errors"][0]


def test_agent_rejects_oversized_person_field(db_sessionmaker):
    with db_sessionmaker() as session:
        _, ctx = _seed(session)
        for entity, fields in (("project", {"project_name": "P", "owner": "a" * 256}),
                               ("solution", {"solution_name": "S", "key_stakeholder": "a" * 256}),
                               ("task", {"task_name": "T", "assignee": "a" * 256})):
            operation = {"client_operation_id": "create", "entity": entity, "op": "create", "fields": fields}
            if entity == "solution":
                operation["project_id"] = "source"
            if entity == "task":
                operation["solution_id"] = "moving"
            result = validate_patch_plan(session, ctx, AgentPatchRequest(dry_run=True, operations=[operation]))
            assert not result.valid
            assert "255" in result.results[0].message
