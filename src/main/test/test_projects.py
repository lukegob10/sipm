import pytest
from sqlalchemy.exc import IntegrityError

from backend.main import app as fastapi_app
from backend.app import deps as deps_module
from backend.app.models import Project
from backend.app.routes import projects as projects_module
from backend.app.services.spaces import SpaceContext


@pytest.mark.anyio
async def test_create_and_list_projects(client):
    resp = await client.post(
        "/api/projects/",
        json={
            "project_name": "Data Platform",
            "description": "Modernize data stack",
            "success_criteria": "Reduce run time by 30% and decommission legacy tooling",
            "sponsor": "CFO Office",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["project_name"] == "Data Platform"
    assert data["status"] == "not_started"
    assert data["success_criteria"] == "Reduce run time by 30% and decommission legacy tooling"

    list_resp = await client.get("/api/projects/")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) == 1
    assert projects[0]["project_name"] == "Data Platform"


@pytest.mark.anyio
async def test_create_project_defaults_sponsor_and_priority(client):
    resp = await client.post("/api/projects/", json={"project_name": "Minimal Project"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["project_name"] == "Minimal Project"
    assert data["status"] == "not_started"
    assert data["priority"] == 3
    assert data["sponsor"] == "Test User"
    assert data["sponsor_user_soeid"] == "tu12345"


@pytest.mark.anyio
async def test_project_name_uniqueness(client):
    payload = {
        "project_name": "Access Controls",
        "status": "active",
        "sponsor": "CFO Office",
    }
    assert (await client.post("/api/projects/", json=payload)).status_code == 201
    dup_resp = await client.post("/api/projects/", json=payload)
    assert dup_resp.status_code == 400
    assert dup_resp.json()["detail"] == "Project name already exists"


@pytest.mark.anyio
async def test_delete_project_releases_name_for_recreate(client, db_sessionmaker):
    create = await client.post(
        "/api/projects/",
        json={"project_name": "Enhancements", "sponsor": "Sponsor A"},
    )
    assert create.status_code == 201, create.text
    project_id = create.json()["project_id"]

    deleted = await client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204, deleted.text

    with db_sessionmaker() as session:
        row = session.query(Project).filter(Project.project_id == project_id).first()
        assert row is not None
        assert row.deleted_at is not None
        assert row.project_name != "Enhancements"
        assert "[deleted " in row.project_name

    recreated = await client.post(
        "/api/projects/",
        json={"project_name": "Enhancements", "sponsor": "Sponsor B"},
    )
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["project_name"] == "Enhancements"
    assert recreated.json()["project_id"] != project_id


def test_project_conflict_detector_handles_oracle_wrapped_unique_error():
    exc = IntegrityError(
        statement='INSERT INTO "TB_TA_PM_PROJECTS" (project_name) VALUES (:project_name)',
        params={"project_name": "Enhancements"},
        orig=Exception(
            "ORA-03301: (ORA-00001 details) row with column values "
            "(PROJECT_NAME:'Enhancements') already exists"
        ),
    )
    assert projects_module._is_project_name_conflict_integrity_error(exc) is True


@pytest.mark.anyio
async def test_create_project_handles_db_unique_conflict_with_helpful_message(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-a",
            space_name="Space A",
            is_global_admin=False,
            space_role="space_admin",
        )
        first = await client.post(
            "/api/projects/",
            json={"project_name": "Enhancements", "sponsor": "Sponsor A"},
        )
        assert first.status_code == 201, first.text

        # Existing schema enforces global project-name uniqueness at the DB level.
        # Creating the same name in another active space must still return a clean
        # API conflict message instead of a 500 error.
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-b",
            space_name="Space B",
            is_global_admin=False,
            space_role="space_admin",
        )
        dup = await client.post(
            "/api/projects/",
            json={"project_name": "Enhancements", "sponsor": "Sponsor B"},
        )
        assert dup.status_code == 400, dup.text
        assert dup.json()["detail"] == "Project name already exists"
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


@pytest.mark.anyio
async def test_update_project_status_and_description(client):
    create = (
        await client.post(
        "/api/projects/",
        json={
            "project_name": "Portal",
            "status": "active",
            "sponsor": "CFO Office",
        },
        )
    ).json()
    project_id = create["project_id"]

    update_resp = await client.patch(
        f"/api/projects/{project_id}",
        json={
            "status": "on_hold",
            "description": "Waiting on vendor",
            "success_criteria": "Pilot with 3 teams and hit >90% satisfaction",
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "on_hold"
    assert updated["description"] == "Waiting on vendor"
    assert updated["success_criteria"] == "Pilot with 3 teams and hit >90% satisfaction"


@pytest.mark.anyio
async def test_delete_project_soft_deletes(client):
    create = (
        await client.post(
        "/api/projects/",
        json={
            "project_name": "Billing",
            "sponsor": "CFO Office",
        },
        )
    ).json()
    project_id = create["project_id"]

    delete_resp = await client.delete(f"/api/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 404

    list_resp = await client.get("/api/projects/")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_member_cannot_delete_project(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-project",
            space_name="Delete Project Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        create_resp = await client.post(
            "/api/projects/",
            json={
                "project_name": "Delete Guard Project",
                "sponsor": "CFO Office",
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        project_id = create_resp.json()["project_id"]

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-project",
            space_name="Delete Project Space",
            is_global_admin=False,
            space_role="member",
        )
        denied = await client.delete(f"/api/projects/{project_id}")
        assert denied.status_code == 403, denied.text

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-project",
            space_name="Delete Project Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        allowed = await client.delete(f"/api/projects/{project_id}")
        assert allowed.status_code == 204, allowed.text
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space
