import pytest

from backend.app.models import Space, SpaceMembership, User


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/users/capacity-user", "/users/by-soeid/capacityuser"])
@pytest.mark.parametrize("value", ["1e309", "1e308", "-1e309", "1e100"])
async def test_user_capacity_rejects_nonfinite_hours(client, db_sessionmaker, path, value):
    with db_sessionmaker() as session:
        session.add(Space(space_id="test-space", name="Test", slug="test"))
        session.add(User(
            user_id="capacity-user", soeid="capacityuser", email="capacity@example.com",
            display_name="Capacity User", password_hash="unused", role="user", is_active=True,
        ))
        session.flush()
        session.add(SpaceMembership(space_id="test-space", user_id="capacity-user", role="member", status="active"))
        session.commit()

    response = await client.patch(
        f"/project-manager/api{path}",
        content=f'{{"capacity_fte_month": {value}}}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    with db_sessionmaker() as session:
        assert session.get(User, "capacity-user").capacity_hours == 40


def test_capacity_hours_overflow_is_rejected_before_mutation():
    from fastapi import HTTPException
    from backend.app.routes.users import _set_user_capacity_fields

    user = User(capacity_hours=40, capacity_fte_month=1.0)
    with pytest.raises(HTTPException) as exc:
        _set_user_capacity_fields(user, capacity_hours=10**400)
    assert exc.value.status_code == 422
    assert (user.capacity_hours, user.capacity_fte_month) == (40, 1.0)
