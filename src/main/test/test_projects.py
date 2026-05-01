import pytest
from sqlalchemy.exc import IntegrityError

from backend.main import app as fastapi_app
from backend.app import deps as deps_module
from backend.app.models import Project
from backend.app.routes import projects as projects_module
from backend.app.services import audit_log as audit_log_module
from backend.app.services.spaces import SpaceContext


def _long_text(prefix: str, repeats: int = 40) -> str:
    return "\n".join(f"{prefix} line {idx}: detailed context and measurable outcomes." for idx in range(1, repeats + 1))


@pytest.mark.anyio
async def test_create_and_list_projects(client):
    resp = await client.post(
        "/project-manager/api/projects/",
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

    list_resp = await client.get("/project-manager/api/projects/")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) == 1
    assert projects[0]["project_name"] == "Data Platform"


@pytest.mark.anyio
async def test_list_and_export_projects_hide_work_allocation_board_project(client):
    board_name = "Work Allocation Board [bfab593b]"
    board_resp = await client.post("/project-manager/api/projects/", json={"project_name": board_name})
    assert board_resp.status_code == 201, board_resp.text

    visible_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Visible Project"})
    assert visible_resp.status_code == 201, visible_resp.text

    list_resp = await client.get("/project-manager/api/projects/")
    assert list_resp.status_code == 200, list_resp.text
    names = {row["project_name"] for row in list_resp.json()}
    assert "Visible Project" in names
    assert board_name not in names

    export_resp = await client.get("/project-manager/api/projects/export")
    assert export_resp.status_code == 200, export_resp.text
    assert "Visible Project" in export_resp.text
    assert board_name not in export_resp.text


@pytest.mark.anyio
async def test_create_project_defaults_sponsor_and_priority(client):
    resp = await client.post("/project-manager/api/projects/", json={"project_name": "Minimal Project"})
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
    assert (await client.post("/project-manager/api/projects/", json=payload)).status_code == 201
    dup_resp = await client.post("/project-manager/api/projects/", json=payload)
    assert dup_resp.status_code == 400
    assert dup_resp.json()["detail"] == "Project name already exists"


@pytest.mark.anyio
async def test_delete_project_releases_name_for_recreate(client, db_sessionmaker):
    create = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Enhancements", "sponsor": "Sponsor A"},
    )
    assert create.status_code == 201, create.text
    project_id = create.json()["project_id"]

    deleted = await client.delete(f"/project-manager/api/projects/{project_id}")
    assert deleted.status_code == 204, deleted.text

    with db_sessionmaker() as session:
        row = session.query(Project).filter(Project.project_id == project_id).first()
        assert row is not None
        assert row.deleted_at is not None
        assert row.project_name != "Enhancements"
        assert "[deleted " in row.project_name

    recreated = await client.post(
        "/project-manager/api/projects/",
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

    exc_new_constraint = IntegrityError(
        statement='INSERT INTO "TB_TA_PM_PROJECTS" (space_id, project_name) VALUES (:space_id, :project_name)',
        params={"space_id": "space-a", "project_name": "Enhancements"},
        orig=Exception("ORA-00001: unique constraint (APP.UIX_PROJECT_SPACE_NAME) violated"),
    )
    assert projects_module._is_project_name_conflict_integrity_error(exc_new_constraint) is True


@pytest.mark.anyio
async def test_create_project_allows_same_name_in_different_spaces(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-a",
            space_name="Space A",
            is_global_admin=False,
            space_role="space_admin",
        )
        first = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Enhancements", "sponsor": "Sponsor A"},
        )
        assert first.status_code == 201, first.text

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-b",
            space_name="Space B",
            is_global_admin=False,
            space_role="space_admin",
        )
        same_name_other_space = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Enhancements", "sponsor": "Sponsor B"},
        )
        assert same_name_other_space.status_code == 201, same_name_other_space.text
        assert same_name_other_space.json()["project_name"] == "Enhancements"
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


@pytest.mark.anyio
async def test_update_project_status_and_description(client):
    create = (
        await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Portal",
            "status": "active",
            "sponsor": "CFO Office",
        },
        )
    ).json()
    project_id = create["project_id"]

    update_resp = await client.patch(
        f"/project-manager/api/projects/{project_id}",
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
async def test_project_create_and_update_support_long_text_fields(client):
    description = _long_text("Project description")
    success_criteria = _long_text("Project success criteria")

    create_resp = await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Long Form Project",
            "description": description,
            "success_criteria": success_criteria,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert len(description) > 255
    assert len(success_criteria) > 255
    assert created["description"] == description
    assert created["success_criteria"] == success_criteria

    update_description = _long_text("Updated project description", repeats=24)
    update_success_criteria = _long_text("Updated project success", repeats=24)
    update_resp = await client.patch(
        f"/project-manager/api/projects/{created['project_id']}",
        json={
            "description": update_description,
            "success_criteria": update_success_criteria,
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["description"] == update_description
    assert updated["success_criteria"] == update_success_criteria


@pytest.mark.anyio
async def test_create_project_with_long_text_succeeds_even_if_audit_logging_fails(client, monkeypatch):
    description = _long_text("Project description")

    def _broken_log_changes(*args, **kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(audit_log_module, "log_changes", _broken_log_changes)

    create_resp = await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Long Text Audit Fallback Project",
            "description": description,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["description"] == description


@pytest.mark.anyio
async def test_delete_project_soft_deletes(client):
    create = (
        await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Billing",
            "sponsor": "CFO Office",
        },
        )
    ).json()
    project_id = create["project_id"]

    delete_resp = await client.delete(f"/project-manager/api/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/project-manager/api/projects/{project_id}")
    assert get_resp.status_code == 404

    list_resp = await client.get("/project-manager/api/projects/")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_member_can_delete_project(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-project",
            space_name="Delete Project Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        create_resp = await client.post(
            "/project-manager/api/projects/",
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
        allowed = await client.delete(f"/project-manager/api/projects/{project_id}")
        assert allowed.status_code == 204, allowed.text
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space
