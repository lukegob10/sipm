import pytest

from backend.app import deps as deps_module
from backend.app.models import Space, SpaceMembership, Team, User
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
