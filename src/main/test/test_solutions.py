from datetime import date, timedelta

import pytest

from backend.main import app as fastapi_app
from backend.app import deps as deps_module
from backend.app.services.spaces import SpaceContext


async def create_project(client):
    resp = await client.post(
        "/api/projects/",
        json={
            "project_name": "Data Platform",
            "description": "Modernize data stack",
            "sponsor": "CFO Office",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_create_solution_defaults_owner_and_version(client):
    project_resp = await client.post("/api/projects/", json={"project_name": "Minimal Project"})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    resp = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
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
async def test_create_and_list_solutions(client):
    project = await create_project(client)

    resp = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
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

    list_resp = await client.get(f"/api/projects/{project['project_id']}/solutions")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["solution_name"] == "Access Controls"


@pytest.mark.anyio
async def test_list_and_export_solutions_hide_work_allocation_board_solution(client):
    board_project_resp = await client.post("/api/projects/", json={"project_name": "Work Allocation Board [bfab593b]"})
    assert board_project_resp.status_code == 201, board_project_resp.text
    board_project_id = board_project_resp.json()["project_id"]

    board_solution_resp = await client.post(
        f"/api/projects/{board_project_id}/solutions",
        json={"solution_name": "Backlog", "version": "1.0.0"},
    )
    assert board_solution_resp.status_code == 201, board_solution_resp.text

    normal_project_resp = await client.post("/api/projects/", json={"project_name": "Visible Project"})
    assert normal_project_resp.status_code == 201, normal_project_resp.text
    normal_project_id = normal_project_resp.json()["project_id"]

    visible_solution_resp = await client.post(
        f"/api/projects/{normal_project_id}/solutions",
        json={"solution_name": "Visible Solution", "version": "1.0.0"},
    )
    assert visible_solution_resp.status_code == 201, visible_solution_resp.text
    visible_solution_id = visible_solution_resp.json()["solution_id"]

    list_resp = await client.get("/api/solutions")
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()
    ids = {row["solution_id"] for row in rows}
    assert visible_solution_id in ids
    assert all(not (row["project_id"] == board_project_id and row["solution_name"] == "Backlog") for row in rows)

    by_project_resp = await client.get(f"/api/projects/{board_project_id}/solutions")
    assert by_project_resp.status_code == 200, by_project_resp.text
    assert by_project_resp.json() == []

    export_resp = await client.get("/api/solutions/export")
    assert export_resp.status_code == 200, export_resp.text
    assert "Visible Solution" in export_resp.text
    assert "Backlog" not in export_resp.text


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
        (await client.post(f"/api/projects/{project['project_id']}/solutions", json=payload)).status_code
        == 201
    )
    dup_resp = await client.post(f"/api/projects/{project['project_id']}/solutions", json=payload)
    assert dup_resp.status_code == 400
    assert "already exist" in dup_resp.json()["detail"]

    # Different version should be allowed
    payload["version"] = "0.2.0"
    assert (
        (await client.post(f"/api/projects/{project['project_id']}/solutions", json=payload)).status_code
        == 201
    )


@pytest.mark.anyio
async def test_update_solution_status_and_description(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Portal", "version": "1.0.0", "owner": "Solution Owner"},
        )
    ).json()
    solution_id = created["solution_id"]

    update_resp = await client.patch(
        f"/api/solutions/{solution_id}",
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


@pytest.mark.anyio
async def test_delete_solution_soft_deletes(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Billing", "version": "0.1.0", "owner": "Solution Owner"},
        )
    ).json()
    solution_id = created["solution_id"]

    delete_resp = await client.delete(f"/api/solutions/{solution_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/solutions/{solution_id}")
    assert get_resp.status_code == 404

    list_resp = await client.get(f"/api/projects/{project['project_id']}/solutions")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_member_cannot_delete_solution(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-solution",
            space_name="Delete Solution Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        project_resp = await client.post("/api/projects/", json={"project_name": "Delete Guard Solution Project"})
        assert project_resp.status_code == 201, project_resp.text
        project_id = project_resp.json()["project_id"]
        solution_resp = await client.post(
            f"/api/projects/{project_id}/solutions",
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
        denied = await client.delete(f"/api/solutions/{solution_id}")
        assert denied.status_code == 403, denied.text

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-solution",
            space_name="Delete Solution Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        allowed = await client.delete(f"/api/solutions/{solution_id}")
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
            f"/api/projects/{project['project_id']}/solutions",
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
    updated = (await client.patch(f"/api/solutions/{created['solution_id']}", json={"due_date": past})).json()
    assert updated["rag_status"] == "green"
    assert updated["rag_reason"] is None

    completed = (await client.patch(f"/api/solutions/{created['solution_id']}", json={"status": "complete"})).json()
    assert completed["rag_status"] == "green"


@pytest.mark.anyio
async def test_solution_rag_manual_override_and_reset(client):
    project = await create_project(client)
    created_resp = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
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
        f"/api/solutions/{created['solution_id']}",
        json={"rag_status": "red", "rag_reason": "Escalation approved"},
    )
    assert manual_resp.status_code == 200, manual_resp.text
    manual = manual_resp.json()
    assert manual["rag_status"] == "red"
    assert manual["rag_reason"] == "Escalation approved"

    reset_resp = await client.patch(
        f"/api/solutions/{created['solution_id']}",
        json={"rag_reason": None},
    )
    assert reset_resp.status_code == 200, reset_resp.text
    reset = reset_resp.json()
    assert reset["rag_status"] == "red"
    assert reset["rag_reason"] is None
