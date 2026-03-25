import pytest

from backend.app import deps as deps_module
from backend.app.models import Space, SpaceMembership, Team, User
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


@pytest.mark.anyio
async def test_team_create_honors_default_capacity_per_week_when_fte_is_omitted(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    clear_cache()
    try:
        _set_current_space("space-team-hours-defaults", "Team Hours Defaults Space")

        created = await client.post(
            "/project-manager/api/teams",
            json={
                "name": "Hours Capacity Team",
                "default_capacity_per_week": 48,
            },
        )
        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["default_capacity_per_week"] == 48
        assert payload["default_capacity_fte_month"] == pytest.approx(1.2, abs=1e-6)
    finally:
        clear_cache()
        _restore_current_space(original_current_space)


@pytest.mark.anyio
async def test_restored_team_honors_default_capacity_per_week_when_fte_is_omitted(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    clear_cache()
    try:
        _set_current_space("space-team-hours-restore", "Team Hours Restore Space")

        created = await client.post("/project-manager/api/teams", json={"name": "Restore Hours Team"})
        assert created.status_code == 201, created.text
        team_id = created.json()["team_id"]

        deleted = await client.delete(f"/project-manager/api/teams/{team_id}")
        assert deleted.status_code == 204, deleted.text

        restored = await client.post(
            "/project-manager/api/teams",
            json={
                "name": "Restore Hours Team",
                "default_capacity_per_week": 52,
            },
        )
        assert restored.status_code == 201, restored.text
        restored_payload = restored.json()
        assert restored_payload["team_id"] == team_id
        assert restored_payload["default_capacity_per_week"] == 52
        assert restored_payload["default_capacity_fte_month"] == pytest.approx(1.3, abs=1e-6)
    finally:
        clear_cache()
        _restore_current_space(original_current_space)


@pytest.mark.anyio
async def test_team_rename_updates_active_space_user_team_tags_and_invalidates_user_cache(client, db_sessionmaker):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    clear_cache()
    try:
        _set_current_space("space-team-rename", "Team Rename Space")
        with db_sessionmaker() as session:
            space = Space(
                space_id="space-team-rename",
                name="Team Rename Space",
                slug="team-rename-space",
                is_active=True,
            )
            user = User(
                user_id="team-rename-user",
                soeid="teamrename1",
                email="teamrename1@example.com",
                display_name="Team Rename User",
                password_hash="x",
                role="user",
                is_active=True,
                team_tag="Platform",
            )
            membership = SpaceMembership(
                membership_id="team-rename-membership",
                space_id=space.space_id,
                user_id=user.user_id,
                role="member",
                status="active",
            )
            team = Team(
                team_id="team-rename-id",
                space_id=space.space_id,
                name="Platform",
                default_capacity_per_week=0,
                default_capacity_fte_month=0.0,
                capacity_unit="fte_month",
            )
            session.add_all([space, user, membership, team])
            session.commit()

        primed = await client.get("/project-manager/api/users")
        assert primed.status_code == 200, primed.text
        assert primed.json()[0]["team_tag"] == "Platform"

        renamed = await client.patch(
            "/project-manager/api/teams/team-rename-id",
            json={"name": "Core Platform"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Core Platform"

        refreshed = await client.get("/project-manager/api/users")
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()[0]["team_tag"] == "Core Platform"
    finally:
        clear_cache()
        _restore_current_space(original_current_space)


@pytest.mark.anyio
async def test_team_delete_clears_active_space_user_team_tags_and_invalidates_user_cache(client, db_sessionmaker):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    clear_cache()
    try:
        _set_current_space("space-team-delete", "Team Delete Space")
        with db_sessionmaker() as session:
            space = Space(
                space_id="space-team-delete",
                name="Team Delete Space",
                slug="team-delete-space",
                is_active=True,
            )
            user = User(
                user_id="team-delete-user",
                soeid="teamdelete1",
                email="teamdelete1@example.com",
                display_name="Team Delete User",
                password_hash="x",
                role="user",
                is_active=True,
                team_tag="Platform",
            )
            membership = SpaceMembership(
                membership_id="team-delete-membership",
                space_id=space.space_id,
                user_id=user.user_id,
                role="member",
                status="active",
            )
            team = Team(
                team_id="team-delete-id",
                space_id=space.space_id,
                name="Platform",
                default_capacity_per_week=0,
                default_capacity_fte_month=0.0,
                capacity_unit="fte_month",
            )
            session.add_all([space, user, membership, team])
            session.commit()

        primed = await client.get("/project-manager/api/users")
        assert primed.status_code == 200, primed.text
        assert primed.json()[0]["team_tag"] == "Platform"

        deleted = await client.delete("/project-manager/api/teams/team-delete-id")
        assert deleted.status_code == 204, deleted.text

        refreshed = await client.get("/project-manager/api/users")
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()[0]["team_tag"] is None
    finally:
        clear_cache()
        _restore_current_space(original_current_space)
