import pytest

from backend.app import deps as deps_module
from backend.app.services.spaces import SpaceContext
from backend.app.services.smart_cache import clear_cache
from backend.main import app as fastapi_app


def _set_current_space(space_id: str, name: str):
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
        space_id=space_id,
        space_name=name,
        is_global_admin=False,
        space_role="space_admin",
    )


def _restore_current_space(original):
    if original is None:
        fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
    else:
        fastapi_app.dependency_overrides[deps_module.current_space] = original


@pytest.mark.anyio
async def test_team_name_uniqueness_is_scoped_to_active_space(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space("space-team-a", "Team Space A")
        first = await client.post("/project-manager/api/teams", json={"name": "Platform"})
        assert first.status_code == 201, first.text

        same_space_duplicate = await client.post("/project-manager/api/teams", json={"name": "Platform"})
        assert same_space_duplicate.status_code == 400, same_space_duplicate.text
        assert same_space_duplicate.json()["detail"] == "Team name already exists"

        _set_current_space("space-team-b", "Team Space B")
        other_space_same_name = await client.post("/project-manager/api/teams", json={"name": "Platform"})
        assert other_space_same_name.status_code == 201, other_space_same_name.text
        assert other_space_same_name.json()["name"] == "Platform"
    finally:
        _restore_current_space(original_current_space)


@pytest.mark.anyio
async def test_planning_work_allocation_team_name_is_scoped_to_active_space(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space("space-planning-team-a", "Planning Team Space A")
        first = await client.post(
            "/project-manager/api/planning/work-allocation/teams",
            json={"name": "Delivery Team"},
        )
        assert first.status_code == 201, first.text

        same_space_duplicate = await client.post(
            "/project-manager/api/planning/work-allocation/teams",
            json={"name": "Delivery Team"},
        )
        assert same_space_duplicate.status_code == 400, same_space_duplicate.text
        assert same_space_duplicate.json()["detail"] == "Team already exists"

        _set_current_space("space-planning-team-b", "Planning Team Space B")
        other_space_same_name = await client.post(
            "/project-manager/api/planning/work-allocation/teams",
            json={"name": "Delivery Team"},
        )
        assert other_space_same_name.status_code == 201, other_space_same_name.text
        assert other_space_same_name.json()["name"] == "Delivery Team"
    finally:
        _restore_current_space(original_current_space)


@pytest.mark.anyio
async def test_restoring_soft_deleted_team_invalidates_cached_team_list(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    clear_cache()
    try:
        _set_current_space("space-team-cache", "Team Cache Space")

        created = await client.post("/project-manager/api/teams", json={"name": "Platform"})
        assert created.status_code == 201, created.text
        team_id = created.json()["team_id"]

        listed = await client.get("/project-manager/api/teams")
        assert listed.status_code == 200, listed.text
        assert [row["team_id"] for row in listed.json()] == [team_id]

        deleted = await client.delete(f"/project-manager/api/teams/{team_id}")
        assert deleted.status_code == 204, deleted.text

        empty = await client.get("/project-manager/api/teams")
        assert empty.status_code == 200, empty.text
        assert empty.json() == []

        restored = await client.post("/project-manager/api/teams", json={"name": "Platform"})
        assert restored.status_code == 201, restored.text
        assert restored.json()["team_id"] == team_id

        refreshed = await client.get("/project-manager/api/teams")
        assert refreshed.status_code == 200, refreshed.text
        assert [row["team_id"] for row in refreshed.json()] == [team_id]
    finally:
        clear_cache()
        _restore_current_space(original_current_space)


@pytest.mark.anyio
async def test_team_create_and_read_preserve_configured_default_capacity(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    clear_cache()
    try:
        _set_current_space("space-team-defaults", "Team Defaults Space")

        created = await client.post(
            "/project-manager/api/teams",
            json={
                "name": "Configured Capacity Team",
                "default_capacity_fte_month": 1.5,
            },
        )
        assert created.status_code == 201, created.text
        created_payload = created.json()
        team_id = created_payload["team_id"]
        assert created_payload["default_capacity_fte_month"] == pytest.approx(1.5, abs=1e-6)
        assert created_payload["default_capacity_per_week"] == 60
        created_updated_at = created_payload["updated_at"]

        detail = await client.get(f"/project-manager/api/teams/{team_id}")
        assert detail.status_code == 200, detail.text
        detail_payload = detail.json()
        assert detail_payload["default_capacity_fte_month"] == pytest.approx(1.5, abs=1e-6)
        assert detail_payload["default_capacity_per_week"] == 60
        assert detail_payload["updated_at"] == created_updated_at

        listed = await client.get("/project-manager/api/teams")
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        row = next((item for item in rows if item["team_id"] == team_id), None)
        assert row is not None
        assert row["default_capacity_fte_month"] == pytest.approx(1.5, abs=1e-6)
        assert row["default_capacity_per_week"] == 60
        assert row["updated_at"] == created_updated_at
    finally:
        clear_cache()
        _restore_current_space(original_current_space)
