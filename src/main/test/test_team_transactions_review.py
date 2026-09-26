import pytest
from sqlalchemy import event

from backend.app.models import Team, TeamMember


def _inject_capacity_aggregate_failure(engine):
    def fail_capacity_aggregate(_connection, _cursor, statement, _parameters, _context, _executemany):
        sql = statement.lower()
        if "sum(" in sql and TeamMember.__tablename__.lower() in sql:
            raise RuntimeError("injected team capacity aggregate failure")

    event.listen(engine, "before_cursor_execute", fail_capacity_aggregate)
    return fail_capacity_aggregate


def _remove_capacity_aggregate_failure(engine, listener):
    event.remove(engine, "before_cursor_execute", listener)


def _team_payload(rows, team_id):
    return next(row for row in rows if row["team_id"] == team_id)


@pytest.mark.anyio
async def test_team_member_capacity_totals_follow_create_update_and_delete(
    client, db_sessionmaker
):
    team_response = await client.post(
        "/project-manager/api/teams",
        json={"name": "Atomic Capacity Team"},
    )
    assert team_response.status_code == 201, team_response.text
    team_id = team_response.json()["team_id"]

    member_response = await client.post(
        f"/project-manager/api/teams/{team_id}/members",
        json={"member_name": "Capacity Member", "hours_capacity": 20},
    )
    assert member_response.status_code == 201, member_response.text
    member_id = member_response.json()["team_member_id"]

    team = (
        await client.get(f"/project-manager/api/teams/{team_id}")
    ).json()
    assert team["default_capacity_per_week"] == 20
    assert team["default_capacity_fte_month"] == pytest.approx(0.5)

    updated = await client.patch(
        f"/project-manager/api/teams/{team_id}/members/{member_id}",
        json={"capacity_fte_month": 1.25},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["hours_capacity"] == 50
    assert updated.json()["capacity_fte_month"] == pytest.approx(1.25)
    with db_sessionmaker() as session:
        persisted_member = (
            session.query(TeamMember)
            .filter(TeamMember.team_member_id == member_id)
            .one()
        )
        assert updated.json()["updated_at"] == persisted_member.updated_at.isoformat()

    team = (
        await client.get(f"/project-manager/api/teams/{team_id}")
    ).json()
    assert team["default_capacity_per_week"] == 50
    assert team["default_capacity_fte_month"] == pytest.approx(1.25)

    deleted = await client.delete(
        f"/project-manager/api/teams/{team_id}/members/{member_id}"
    )
    assert deleted.status_code == 204, deleted.text

    team = (
        await client.get(f"/project-manager/api/teams/{team_id}")
    ).json()
    assert team["default_capacity_per_week"] == 0
    assert team["default_capacity_fte_month"] == pytest.approx(0.0)
    assert team["members"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
async def test_team_member_change_rolls_back_if_capacity_aggregate_fails(
    operation, client, db_sessionmaker
):
    team_response = await client.post(
        "/project-manager/api/teams",
        json={"name": f"Atomic Failure Team {operation}"},
    )
    assert team_response.status_code == 201, team_response.text
    team_id = team_response.json()["team_id"]

    member_id = None
    if operation != "create":
        member_response = await client.post(
            f"/project-manager/api/teams/{team_id}/members",
            json={"member_name": "Existing Member", "hours_capacity": 20},
        )
        assert member_response.status_code == 201, member_response.text
        member_id = member_response.json()["team_member_id"]

    before_response = await client.get("/project-manager/api/teams")
    assert before_response.status_code == 200, before_response.text
    before_team = _team_payload(before_response.json(), team_id)

    engine = db_sessionmaker.kw["bind"]
    listener = _inject_capacity_aggregate_failure(engine)
    try:
        with pytest.raises(RuntimeError, match="injected team capacity aggregate failure"):
            if operation == "create":
                await client.post(
                    f"/project-manager/api/teams/{team_id}/members",
                    json={"member_name": "New Member", "hours_capacity": 40},
                )
            elif operation == "update":
                await client.patch(
                    f"/project-manager/api/teams/{team_id}/members/{member_id}",
                    json={"hours_capacity": 40},
                )
            else:
                await client.delete(
                    f"/project-manager/api/teams/{team_id}/members/{member_id}"
                )
    finally:
        _remove_capacity_aggregate_failure(engine, listener)

    with db_sessionmaker() as session:
        team = session.query(Team).filter(Team.team_id == team_id).one()
        members = (
            session.query(TeamMember)
            .filter(TeamMember.team_id == team_id)
            .all()
        )

    expected_hours = 0 if operation == "create" else 20
    assert team.default_capacity_per_week == expected_hours
    assert team.default_capacity_fte_month == pytest.approx(expected_hours / 40)
    if operation == "create":
        assert members == []
    else:
        assert len(members) == 1
        assert members[0].deleted_at is None
        assert members[0].hours_capacity == 20

    after_response = await client.get("/project-manager/api/teams")
    assert after_response.status_code == 200, after_response.text
    assert _team_payload(after_response.json(), team_id) == before_team
