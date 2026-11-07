import pytest

from backend.app.models import Solution, Task
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from backend.app.services.github_repo_urls import normalize_github_repo_url, resolve_effective_github_repo_url
from test_agent_solution_move_regressions import _seed


def test_url_limit_applies_after_normalization_without_breaking_legacy_reads():
    prefix = "https://github.com/o/"
    valid = prefix + "a" * (1024 - len(prefix))
    assert normalize_github_repo_url(valid + ".git/") == valid
    with pytest.raises(ValueError, match="1024"):
        normalize_github_repo_url(valid + "x")
    assert resolve_effective_github_repo_url(solution_repo_url=valid + "x", task_repo_url=None)[0] == valid + "x"


@pytest.mark.anyio
async def test_urls_too_long_are_rejected_before_csv_creates_parents(client):
    project = (await client.post("/project-manager/api/projects/", json={"project_name": "URL Project"})).json()
    solution_path = f"/project-manager/api/projects/{project['project_id']}/solutions"
    long_url = "https://github.com/o/" + "a" * 1024
    response = await client.post(solution_path, json={"solution_name": "Long URL", "github_repo_url": long_url})
    assert response.status_code == 400
    solution = (await client.post(solution_path, json={"solution_name": "URL Solution"})).json()
    task_path = f"/project-manager/api/solutions/{solution['solution_id']}/tasks"
    response = await client.post(task_path, json={"task_name": "Long URL", "github_repo_url": long_url})
    assert response.status_code == 400
    for path, header, row in (
        ("solutions/import", "project_name,solution_name,github_repo_url", f"New Project,New Solution,{long_url}"),
        ("tasks/import", "project_name,solution_name,task_name,github_repo_url", f"New Project,New Solution,New Task,{long_url}"),
    ):
        for suffix in ("?dry_run=true", ""):
            response = await client.post("/project-manager/api/" + path + suffix, content=header + "\n" + row + "\n", headers={"Content-Type": "text/csv"})
            assert response.status_code == 200
            assert response.json()["created"] == 0
            assert response.json().get("projects_created", 0) == 0
            assert response.json().get("solutions_created", 0) == 0
            assert "1024" in response.json()["errors"][0]


def test_agent_rejects_oversized_repo_urls(db_sessionmaker):
    with db_sessionmaker() as session:
        _, ctx = _seed(session)
        long_url = "https://github.com/o/" + "a" * 1024
        for entity, model, entity_id in (("solution", Solution, "moving"), ("task", Task, "child")):
            row = session.get(model, entity_id)
            patch = {"client_operation_id": "change", "op": "update", "entity": entity,
                     "id": entity_id, "if_updated_at": row.updated_at, "fields": {"github_repo_url": long_url}}
            result = validate_patch_plan(session, ctx, AgentPatchRequest(dry_run=True, operations=[patch]))
            assert not result.valid
            assert "1024" in result.results[0].message
