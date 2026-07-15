from datetime import date, timedelta

import pytest

import backend.app.routes.solutions as solutions_route
from backend.main import app as fastapi_app
from backend.app import deps as deps_module
from backend.app.models import Solution
from backend.app.services import audit_log as audit_log_module
from backend.app.services.smart_cache import clear_cache
from backend.app.services.spaces import SpaceContext


def _long_text(prefix: str, repeats: int = 40) -> str:
    return "\n".join(f"{prefix} line {idx}: detailed context and measurable outcomes." for idx in range(1, repeats + 1))


async def create_project(client):
    resp = await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Data Platform",
            "description": "Modernize data stack",
            "sponsor": "CFO Office",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def create_working_space_headers(client, slug: str) -> dict[str, str]:
    resp = await client.post(
        "/project-manager/api/spaces",
        json={"name": slug.replace("-", " ").title(), "slug": slug},
    )
    assert resp.status_code == 201, resp.text
    return {"X-Space-Id": resp.json()["space_id"]}


@pytest.mark.anyio
async def test_create_solution_defaults_owner_and_version(client):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Minimal Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Minimal Solution"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["solution_name"] == "Minimal Solution"
    assert data["version"] == "0.1.0"
    assert data["status"] == "not_started"
    assert data["rag_status"] == "green"
    assert data["owner"] == "Test User"
    assert data["owner_user_soeid"] == "tu12345"
    assert data["assignee"] == "Test User"


@pytest.mark.anyio
async def test_solution_crud_normalizes_required_identifiers(client):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Identifier Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    blank_create = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "   "},
    )
    assert blank_create.status_code == 400, blank_create.text
    assert blank_create.json()["detail"] == "solution_name is required"

    create = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "  Trimmed Solution  ", "version": "  1.0.0  "},
    )
    assert create.status_code == 201, create.text
    solution = create.json()
    assert solution["solution_name"] == "Trimmed Solution"
    assert solution["version"] == "1.0.0"

    blank_name = await client.patch(
        f"/project-manager/api/solutions/{solution['solution_id']}",
        json={"solution_name": "\n"},
    )
    assert blank_name.status_code == 400, blank_name.text
    assert blank_name.json()["detail"] == "solution_name is required"

    blank_version = await client.patch(
        f"/project-manager/api/solutions/{solution['solution_id']}",
        json={"version": "   "},
    )
    assert blank_version.status_code == 400, blank_version.text
    assert blank_version.json()["detail"] == "version is required"


@pytest.mark.anyio
async def test_update_solution_can_move_to_another_project(client):
    headers = await create_working_space_headers(client, "solution-move-space")
    first_project_resp = await client.post(
        "/project-manager/api/projects/",
        headers=headers,
        json={"project_name": "Original Project"},
    )
    assert first_project_resp.status_code == 201, first_project_resp.text
    first_project = first_project_resp.json()
    second_project_resp = await client.post(
        "/project-manager/api/projects/",
        headers=headers,
        json={"project_name": "Target Project"},
    )
    assert second_project_resp.status_code == 201, second_project_resp.text
    second_project = second_project_resp.json()

    create_resp = await client.post(
        f"/project-manager/api/projects/{first_project['project_id']}/solutions",
        headers=headers,
        json={"solution_name": "Movable Solution", "version": "1.0.0"},
    )
    assert create_resp.status_code == 201, create_resp.text
    solution = create_resp.json()

    update_resp = await client.patch(
        f"/project-manager/api/solutions/{solution['solution_id']}",
        headers=headers,
        json={"project_id": second_project["project_id"]},
    )
    assert update_resp.status_code == 200, update_resp.text
    moved = update_resp.json()
    assert moved["project_id"] == second_project["project_id"]

    original_project_solutions = (
        await client.get(f"/project-manager/api/projects/{first_project['project_id']}/solutions", headers=headers)
    ).json()
    target_project_solutions = (
        await client.get(f"/project-manager/api/projects/{second_project['project_id']}/solutions", headers=headers)
    ).json()
    assert all(row["solution_id"] != solution["solution_id"] for row in original_project_solutions)
    assert any(row["solution_id"] == solution["solution_id"] for row in target_project_solutions)


@pytest.mark.anyio
async def test_update_solution_move_rejects_name_version_conflict_in_target_project(client):
    headers = await create_working_space_headers(client, "solution-move-conflict-space")
    first_project_resp = await client.post(
        "/project-manager/api/projects/",
        headers=headers,
        json={"project_name": "Source Project"},
    )
    assert first_project_resp.status_code == 201, first_project_resp.text
    first_project = first_project_resp.json()
    second_project_resp = await client.post(
        "/project-manager/api/projects/",
        headers=headers,
        json={"project_name": "Conflict Target Project"},
    )
    assert second_project_resp.status_code == 201, second_project_resp.text
    second_project = second_project_resp.json()

    source_solution_resp = await client.post(
        f"/project-manager/api/projects/{first_project['project_id']}/solutions",
        headers=headers,
        json={"solution_name": "Duplicate Solution", "version": "1.0.0"},
    )
    assert source_solution_resp.status_code == 201, source_solution_resp.text
    source_solution = source_solution_resp.json()
    target_solution_resp = await client.post(
        f"/project-manager/api/projects/{second_project['project_id']}/solutions",
        headers=headers,
        json={"solution_name": "Duplicate Solution", "version": "1.0.0"},
    )
    assert target_solution_resp.status_code == 201, target_solution_resp.text

    update_resp = await client.patch(
        f"/project-manager/api/solutions/{source_solution['solution_id']}",
        headers=headers,
        json={"project_id": second_project["project_id"]},
    )
    assert update_resp.status_code == 400, update_resp.text
    assert update_resp.json()["detail"] == "Solution name and version already exist for this project"


@pytest.mark.anyio
async def test_create_solution_with_long_text_succeeds_even_if_audit_logging_fails(client, monkeypatch):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Audit Fallback Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    description = "\n".join(f"Solution description line {idx}" for idx in range(1, 60))

    def _broken_log_changes(*args, **kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(audit_log_module, "log_changes", _broken_log_changes)

    resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Long Text Audit Fallback Solution",
            "description": description,
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["description"] == description


@pytest.mark.anyio
async def test_create_solution_rolls_back_when_phase_enablement_fails(client, db_sessionmaker, monkeypatch):
    project = await create_project(client)

    def _fail_enable_all_phases(*_args, **_kwargs):
        raise RuntimeError("phase seed failed")

    monkeypatch.setattr(solutions_route, "enable_all_phases", _fail_enable_all_phases)

    with pytest.raises(RuntimeError, match="phase seed failed"):
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Atomic Failure Solution"},
        )

    with db_sessionmaker() as session:
        count = (
            session.query(Solution)
            .filter(Solution.project_id == project["project_id"])
            .count()
        )
        assert count == 0


@pytest.mark.anyio
async def test_solution_github_repo_url_is_normalized_and_can_be_cleared(client):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Repo Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    create_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Repo Solution",
            "github_repo_url": "https://github.com/ExampleOrg/example-repo.git/",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["github_repo_url"] == "https://github.com/ExampleOrg/example-repo"

    update_resp = await client.patch(
        f"/project-manager/api/solutions/{created['solution_id']}",
        json={"github_repo_url": ""},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["github_repo_url"] is None

    audit_resp = await client.get(
        "/project-manager/api/audit",
        params={
            "entity_type": "solution",
            "entity_id": created["solution_id"],
            "field": "github_repo_url",
        },
    )
    assert audit_resp.status_code == 200, audit_resp.text
    rows = audit_resp.json()
    assert len(rows) >= 2


@pytest.mark.anyio
async def test_solution_escalation_is_short_text_and_can_be_cleared(client):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Escalation Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()
    escalation = "Escalated request for steering review"

    create_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Escalated Solution",
            "escalation": f"  {escalation}  ",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["escalation"] == escalation

    too_long = await client.patch(
        f"/project-manager/api/solutions/{created['solution_id']}",
        json={"escalation": "x" * 256},
    )
    assert too_long.status_code == 422, too_long.text

    cleared = await client.patch(
        f"/project-manager/api/solutions/{created['solution_id']}",
        json={"escalation": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["escalation"] is None


@pytest.mark.anyio
async def test_solution_rejects_invalid_github_repo_url(client):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Invalid Repo Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    bad_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Bad Repo",
            "github_repo_url": "https://github.com/example-org/example-repo/issues/1",
        },
    )
    assert bad_resp.status_code == 400, bad_resp.text
    assert "github_repo_url" in bad_resp.json()["detail"]


@pytest.mark.anyio
async def test_create_and_list_solutions(client):
    project = await create_project(client)

    resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Access Controls",
            "version": "0.1.0",
            "status": "active",
            "description": "RBAC and audit",
            "success_criteria": "Enforce RBAC for top 10 apps and pass audit",
            "owner": "Solution Owner",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["solution_name"] == "Access Controls"
    assert data["version"] == "0.1.0"
    assert data["priority"] == 3
    assert data["success_criteria"] == "Enforce RBAC for top 10 apps and pass audit"

    list_resp = await client.get(f"/project-manager/api/projects/{project['project_id']}/solutions")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["solution_name"] == "Access Controls"


@pytest.mark.anyio
async def test_list_and_export_solutions_include_all_user_solutions(client):
    normal_project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Visible Project"})
    assert normal_project_resp.status_code == 201, normal_project_resp.text
    normal_project_id = normal_project_resp.json()["project_id"]

    visible_solution_resp = await client.post(
        f"/project-manager/api/projects/{normal_project_id}/solutions",
        json={"solution_name": "Visible Solution", "version": "1.0.0"},
    )
    assert visible_solution_resp.status_code == 201, visible_solution_resp.text
    visible_solution_id = visible_solution_resp.json()["solution_id"]

    list_resp = await client.get("/project-manager/api/solutions")
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()
    ids = {row["solution_id"] for row in rows}
    assert visible_solution_id in ids

    export_resp = await client.get("/project-manager/api/solutions/export")
    assert export_resp.status_code == 200, export_resp.text
    assert "Visible Solution" in export_resp.text


@pytest.mark.anyio
async def test_solution_uniqueness_per_project_version(client):
    project = await create_project(client)
    payload = {
        "solution_name": "Access Controls",
        "version": "0.1.0",
        "status": "active",
        "owner": "Solution Owner",
    }
    assert (
        (await client.post(f"/project-manager/api/projects/{project['project_id']}/solutions", json=payload)).status_code
        == 201
    )
    dup_resp = await client.post(f"/project-manager/api/projects/{project['project_id']}/solutions", json=payload)
    assert dup_resp.status_code == 400
    assert "already exist" in dup_resp.json()["detail"]

    # Different version should be allowed
    payload["version"] = "0.2.0"
    assert (
        (await client.post(f"/project-manager/api/projects/{project['project_id']}/solutions", json=payload)).status_code
        == 201
    )


@pytest.mark.anyio
async def test_update_solution_status_and_description(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Portal", "version": "1.0.0", "owner": "Solution Owner"},
        )
    ).json()
    solution_id = created["solution_id"]

    update_resp = await client.patch(
        f"/project-manager/api/solutions/{solution_id}",
        json={
            "status": "complete",
            "description": "Shipped",
            "success_criteria": "100% traffic migrated; no Sev1 incidents for 30 days",
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "complete"
    assert updated["description"] == "Shipped"
    assert updated["success_criteria"] == "100% traffic migrated; no Sev1 incidents for 30 days"
    assert updated["completed_at"] is not None

    audit_resp = await client.get(
        "/project-manager/api/audit",
        params={
            "entity_type": "solution",
            "entity_id": solution_id,
            "field": "completed_at",
        },
    )
    assert audit_resp.status_code == 200, audit_resp.text
    rows = audit_resp.json()
    assert any(row["new_value"] for row in rows)


@pytest.mark.anyio
async def test_reopening_solution_clears_completed_at(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={
                "solution_name": "Reopenable Solution",
                "version": "1.0.0",
                "status": "complete",
                "owner": "Solution Owner",
            },
        )
    ).json()
    solution_id = created["solution_id"]
    assert created["completed_at"] is not None

    reopened = await client.patch(
        f"/project-manager/api/solutions/{solution_id}",
        json={"status": "active"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "active"
    assert reopened.json()["completed_at"] is None


@pytest.mark.anyio
async def test_solution_create_and_update_support_long_text_fields(client):
    project = await create_project(client)
    description = _long_text("Solution description")
    problem_statement = _long_text("Solution problem statement")
    success_criteria = _long_text("Solution success criteria")

    create_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Long Form Solution",
            "description": description,
            "problem_statement": problem_statement,
            "success_criteria": success_criteria,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert len(description) > 255
    assert len(problem_statement) > 255
    assert len(success_criteria) > 255
    assert created["description"] == description
    assert created["problem_statement"] == problem_statement
    assert created["success_criteria"] == success_criteria

    update_description = _long_text("Updated solution description", repeats=24)
    update_problem_statement = _long_text("Updated solution problem", repeats=24)
    update_success_criteria = _long_text("Updated solution success", repeats=24)
    update_resp = await client.patch(
        f"/project-manager/api/solutions/{created['solution_id']}",
        json={
            "description": update_description,
            "problem_statement": update_problem_statement,
            "success_criteria": update_success_criteria,
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["description"] == update_description
    assert updated["problem_statement"] == update_problem_statement
    assert updated["success_criteria"] == update_success_criteria


@pytest.mark.anyio
async def test_delete_solution_soft_deletes(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Billing", "version": "0.1.0", "owner": "Solution Owner"},
        )
    ).json()
    solution_id = created["solution_id"]

    delete_resp = await client.delete(f"/project-manager/api/solutions/{solution_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/project-manager/api/solutions/{solution_id}")
    assert get_resp.status_code == 404

    list_resp = await client.get(f"/project-manager/api/projects/{project['project_id']}/solutions")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_soft_deleted_project_hides_solution_reads_and_clears_solution_cache(client):
    clear_cache()
    try:
        project = await create_project(client)
        create_resp = await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Hidden With Project", "version": "1.0.0", "owner": "Solution Owner"},
        )
        assert create_resp.status_code == 201, create_resp.text
        solution = create_resp.json()

        primed_list = await client.get("/project-manager/api/solutions")
        assert primed_list.status_code == 200, primed_list.text
        assert [row["solution_id"] for row in primed_list.json()] == [solution["solution_id"]]

        primed_detail = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}")
        assert primed_detail.status_code == 200, primed_detail.text

        primed_export = await client.get("/project-manager/api/solutions/export")
        assert primed_export.status_code == 200, primed_export.text
        assert "Hidden With Project" in primed_export.text

        delete_resp = await client.delete(f"/project-manager/api/projects/{project['project_id']}")
        assert delete_resp.status_code == 204, delete_resp.text

        list_resp = await client.get("/project-manager/api/solutions")
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json() == []

        detail_resp = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}")
        assert detail_resp.status_code == 404, detail_resp.text
        assert detail_resp.json()["detail"] == "Solution not found"

        export_resp = await client.get("/project-manager/api/solutions/export")
        assert export_resp.status_code == 200, export_resp.text
        assert "Hidden With Project" not in export_resp.text
    finally:
        clear_cache()


@pytest.mark.anyio
async def test_member_can_delete_solution(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-solution",
            space_name="Delete Solution Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Delete Guard Solution Project"})
        assert project_resp.status_code == 201, project_resp.text
        project_id = project_resp.json()["project_id"]
        solution_resp = await client.post(
            f"/project-manager/api/projects/{project_id}/solutions",
            json={"solution_name": "Delete Guard Solution"},
        )
        assert solution_resp.status_code == 201, solution_resp.text
        solution_id = solution_resp.json()["solution_id"]

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-solution",
            space_name="Delete Solution Space",
            is_global_admin=False,
            space_role="member",
        )
        allowed = await client.delete(f"/project-manager/api/solutions/{solution_id}")
        assert allowed.status_code == 204, allowed.text
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


@pytest.mark.anyio
async def test_solution_rag_auto_rules(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={
                "solution_name": "RAG Demo",
                "version": "0.1.0",
                "status": "active",
                "owner": "Solution Owner",
            },
        )
    ).json()

    assert created["rag_status"] == "green"
    assert created["rag_reason"] is None

    past = (date.today() - timedelta(days=1)).isoformat()
    updated = (await client.patch(f"/project-manager/api/solutions/{created['solution_id']}", json={"due_date": past})).json()
    assert updated["rag_status"] == "green"
    assert updated["rag_reason"] is None

    completed = (await client.patch(f"/project-manager/api/solutions/{created['solution_id']}", json={"status": "complete"})).json()
    assert completed["rag_status"] == "green"


@pytest.mark.anyio
async def test_solution_rag_manual_override_and_reset(client):
    project = await create_project(client)
    created_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Manual RAG",
            "version": "0.1.0",
            "status": "active",
            "rag_status": "amber",
            "rag_reason": "Initial",
            "owner": "Solution Owner",
        },
    )
    assert created_resp.status_code == 201, created_resp.text
    created = created_resp.json()
    assert created["rag_status"] == "amber"
    assert created["rag_reason"] == "Initial"

    manual_resp = await client.patch(
        f"/project-manager/api/solutions/{created['solution_id']}",
        json={"rag_status": "red", "rag_reason": "Escalation approved"},
    )
    assert manual_resp.status_code == 200, manual_resp.text
    manual = manual_resp.json()
    assert manual["rag_status"] == "red"
    assert manual["rag_reason"] == "Escalation approved"

    reset_resp = await client.patch(
        f"/project-manager/api/solutions/{created['solution_id']}",
        json={"rag_reason": None},
    )
    assert reset_resp.status_code == 200, reset_resp.text
    reset = reset_resp.json()
    assert reset["rag_status"] == "red"
    assert reset["rag_reason"] is None
