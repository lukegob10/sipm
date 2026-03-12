import pytest

from backend.app import deps as deps_module
from backend.app.services.spaces import SpaceContext
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
