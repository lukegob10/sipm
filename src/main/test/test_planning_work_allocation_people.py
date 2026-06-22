from types import SimpleNamespace

import pytest

from backend.app import deps as deps_module
from backend.app.models import Space, SpaceMembership, Team, User
from backend.app.services import mutations as service_mutations
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


def _seed_work_allocation_person(db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(
            space_id="space-planning-people",
            name="Planning People Space",
            slug="planning-people-space",
            is_active=True,
        )
        team = Team(
            team_id="team-alpha-planning",
            space_id=space.space_id,
            name="Alpha Planning Team",
            default_capacity_per_week=0,
            default_capacity_fte_month=0.0,
            capacity_unit="fte_month",
        )
        person = User(
            user_id="planning-person-1",
            soeid="planningperson1",
            email="planningperson1@example.com",
            display_name="Planning Person 1",
            password_hash="x",
            role="user",
            is_active=True,
            team_tag=team.name,
            capacity_fte_month=1.0,
            capacity_hours=40,
        )
        membership = SpaceMembership(
            membership_id="planning-person-membership-1",
            space_id=space.space_id,
            user_id=person.user_id,
            role="member",
            status="active",
        )
        session.add_all([space, team, person, membership])
        session.commit()
        return space.space_id, team.team_id, person.soeid


def _set_current_space_override(space_id: str, role: str = "space_admin"):
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
        space_id=space_id,
        space_name="Planning People Space",
        is_global_admin=False,
        space_role=role,
    )


def _restore_current_space_override(original):
    if original is None:
        fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
    else:
        fastapi_app.dependency_overrides[deps_module.current_space] = original


def _restore_current_user_override(original):
    if original is None:
        fastapi_app.dependency_overrides.pop(deps_module.current_user, None)
    else:
        fastapi_app.dependency_overrides[deps_module.current_user] = original


@pytest.mark.anyio
async def test_space_admin_can_move_work_allocation_person_to_unassigned(client, db_sessionmaker):
    space_id, team_id, person_id = _seed_work_allocation_person(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")

        listed = await client.get("/project-manager/api/planning/work-allocation/people")
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["id"] == person_id
        assert rows[0]["team_id"] == team_id

        moved = await client.patch(
            f"/project-manager/api/planning/work-allocation/people/{person_id}",
            json={"team_id": None},
        )
        assert moved.status_code == 200, moved.text
        payload = moved.json()
        assert payload["id"] == person_id
        assert payload["team_id"] is None

        refreshed = await client.get("/project-manager/api/planning/work-allocation/people")
        assert refreshed.status_code == 200, refreshed.text
        refreshed_rows = refreshed.json()
        assert len(refreshed_rows) == 1
        assert refreshed_rows[0]["team_id"] is None
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_space_admin_can_create_work_allocation_person_with_zero_capacity(client, db_sessionmaker):
    space_id, team_id, _person_id = _seed_work_allocation_person(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")

        created = await client.post(
            "/project-manager/api/planning/work-allocation/people",
            json={
                "name": "No Capacity Yet",
                "team_id": team_id,
                "capacity_fte_months": 0,
            },
        )
        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["name"] == "No Capacity Yet"
        assert payload["team_id"] == team_id
        assert payload["capacity_fte_months"] == pytest.approx(0.0, abs=1e-6)
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_planning_mutations_broadcast_live_refresh(client, db_sessionmaker, monkeypatch):
    space_id, _team_id, _person_id = _seed_work_allocation_person(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    broadcasts: list[tuple[str, str | None]] = []

    monkeypatch.setattr(
        service_mutations,
        "schedule_broadcast",
        lambda entity="all", *, space_id=None: broadcasts.append((entity, space_id)),
    )
    try:
        _set_current_space_override(space_id, role="space_admin")

        created = await client.post(
            "/project-manager/api/planning/work-allocation/people",
            json={"name": "Live Refresh Person", "capacity_fte_months": 1.0},
        )
        assert created.status_code == 201, created.text
        assert broadcasts == [("all", space_id)]
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_space_admin_cannot_modify_global_admin_through_planning_people(client, db_sessionmaker):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    original_current_user = fastapi_app.dependency_overrides.get(deps_module.current_user)
    try:
        with db_sessionmaker() as session:
            space = Space(
                space_id="space-planning-global-admin",
                name="Planning Global Admin Space",
                slug="planning-global-admin-space",
                is_active=True,
            )
            target = User(
                user_id="planning-global-admin-user",
                soeid="planningglobaladmin",
                email="planningglobaladmin@example.com",
                display_name="Planning Global Admin",
                password_hash="x",
                role="global-admin",
                is_active=True,
            )
            membership = SpaceMembership(
                membership_id="planning-global-admin-membership",
                space_id=space.space_id,
                user_id=target.user_id,
                role="space_admin",
                status="active",
            )
            session.add_all([space, target, membership])
            session.commit()

        actor = SimpleNamespace(
            user_id="planning-space-admin-actor",
            display_name="Planning Space Admin",
            soeid="planningactor1",
            role="user",
            is_active=True,
        )
        _set_current_space_override("space-planning-global-admin", role="space_admin")
        fastapi_app.dependency_overrides[deps_module.current_user] = lambda: actor

        resp = await client.patch(
            "/project-manager/api/planning/work-allocation/people/planningglobaladmin",
            json={"name": "Renamed Global Admin"},
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"] == "Only global admin can modify global admin accounts"
    finally:
        _restore_current_space_override(original_current_space)
        _restore_current_user_override(original_current_user)


@pytest.mark.anyio
async def test_planning_people_update_cannot_deactivate_last_active_space_admin(client, db_sessionmaker):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    original_current_user = fastapi_app.dependency_overrides.get(deps_module.current_user)
    try:
        with db_sessionmaker() as session:
            space = Space(
                space_id="space-planning-last-admin",
                name="Planning Last Admin Space",
                slug="planning-last-admin-space",
                is_active=True,
            )
            target = User(
                user_id="planning-last-admin-user",
                soeid="planninglastadmin",
                email="planninglastadmin@example.com",
                display_name="Planning Last Admin",
                password_hash="x",
                role="user",
                is_active=True,
            )
            membership = SpaceMembership(
                membership_id="planning-last-admin-membership",
                space_id=space.space_id,
                user_id=target.user_id,
                role="space_admin",
                status="active",
            )
            session.add_all([space, target, membership])
            session.commit()

        actor = SimpleNamespace(
            user_id="planning-space-admin-actor",
            display_name="Planning Space Admin",
            soeid="planningactor2",
            role="user",
            is_active=True,
        )
        _set_current_space_override("space-planning-last-admin", role="space_admin")
        fastapi_app.dependency_overrides[deps_module.current_user] = lambda: actor

        resp = await client.patch(
            "/project-manager/api/planning/work-allocation/people/planninglastadmin",
            json={"active": False},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "Space must retain at least one active space_admin"
    finally:
        _restore_current_space_override(original_current_space)
        _restore_current_user_override(original_current_user)


@pytest.mark.anyio
async def test_planning_people_delete_cannot_deactivate_last_global_admin(client, db_sessionmaker):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    original_current_user = fastapi_app.dependency_overrides.get(deps_module.current_user)
    try:
        with db_sessionmaker() as session:
            space = Space(
                space_id="space-planning-last-global-admin",
                name="Planning Last Global Admin Space",
                slug="planning-last-global-admin-space",
                is_active=True,
            )
            target = User(
                user_id="planning-last-global-admin-user",
                soeid="planninglastglobaladmin",
                email="planninglastglobaladmin@example.com",
                display_name="Planning Last Global Admin",
                password_hash="x",
                role="global-admin",
                is_active=True,
            )
            membership = SpaceMembership(
                membership_id="planning-last-global-admin-membership",
                space_id=space.space_id,
                user_id=target.user_id,
                role="member",
                status="active",
            )
            session.add_all([space, target, membership])
            session.commit()

        actor = SimpleNamespace(
            user_id="planning-global-admin-actor",
            display_name="Planning Global Admin",
            soeid="planningactor3",
            role="global_admin",
            is_active=True,
        )
        _set_current_space_override("space-planning-last-global-admin", role="space_admin")
        fastapi_app.dependency_overrides[deps_module.current_user] = lambda: actor

        resp = await client.delete(
            "/project-manager/api/planning/work-allocation/people/planninglastglobaladmin"
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "At least one active global_admin is required"
    finally:
        _restore_current_space_override(original_current_space)
        _restore_current_user_override(original_current_user)
