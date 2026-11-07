from __future__ import annotations

import httpx
import pytest

from backend.app import deps
from backend.app.auth.auth import hash_password
from backend.app.models import Space, SpaceMembership, User
from backend.main import app


@pytest.fixture
async def personal_import_clients(db_sessionmaker):
    with db_sessionmaker() as session:
        owner = User(
            user_id="personal-owner", soeid="personalowner", email="owner@example.com",
            display_name="Owner", password_hash=hash_password("Password123"), role="user", is_active=True,
        )
        other = User(
            user_id="other-user", soeid="otheruser", email="other@example.com",
            display_name="Other", password_hash=hash_password("Password123"), role="user", is_active=True,
        )
        session.add_all([owner, other])
        session.flush()
        session.add_all([
            Space(space_id="personal-space", name="Personal", slug="personal", space_kind="personal", owner_user_id=owner.user_id),
            Space(space_id="other-space", name="Other", slug="other", space_kind="collaboration"),
        ])
        session.flush()
        session.add_all([
            SpaceMembership(space_id="personal-space", user_id=owner.user_id, role="space_admin", status="active"),
            SpaceMembership(space_id="other-space", user_id=other.user_id, role="member", status="active"),
        ])
        session.commit()

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[deps.get_db] = get_test_db
    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as owner_client:
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as other_client:
                    for client, soeid in ((owner_client, "personalowner"), (other_client, "otheruser")):
                        response = await client.post(
                            "/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"},
                        )
                        assert response.status_code == 200, response.text
                    yield owner_client, other_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("soeid", ["otheruser", "newuser"])
async def test_personal_roster_import_cannot_add_nonowners(personal_import_clients, db_sessionmaker, dry_run, soeid):
    owner_client, other_client = personal_import_clients
    response = await owner_client.post(
        f"/project-manager/api/users/import?dry_run={str(dry_run).lower()}",
        headers={"Content-Type": "text/csv", "X-Space-Id": "personal-space"},
        content=f"soeid,display_name\n{soeid},Changed\n".encode(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 0
    assert response.json()["errors"] == ["Row 2: personal spaces cannot add members"]
    with db_sessionmaker() as session:
        assert session.query(SpaceMembership).filter_by(space_id="personal-space", user_id="other-user").count() == 0
        assert session.get(User, "other-user").display_name == "Other"
        assert session.query(User).filter_by(soeid="newuser").count() == 0

    denied = await other_client.get("/project-manager/api/teams", headers={"X-Space-Id": "personal-space"})
    assert denied.status_code == 403, denied.text
    assert denied.headers["X-Error-Code"] == "FORBIDDEN_SPACE"


@pytest.mark.anyio
async def test_personal_roster_import_still_updates_owner(personal_import_clients, db_sessionmaker):
    owner_client, _ = personal_import_clients
    response = await owner_client.post(
        "/project-manager/api/users/import",
        headers={"Content-Type": "text/csv", "X-Space-Id": "personal-space"},
        content=b"soeid,display_name\npersonalowner,Updated Owner\n",
    )
    assert response.status_code == 200, response.text
    assert response.json()["updated"] == 1
    with db_sessionmaker() as session:
        assert session.get(User, "personal-owner").display_name == "Updated Owner"


@pytest.mark.anyio
async def test_personal_space_creation_rolls_back_if_owner_membership_fails(
    personal_import_clients, db_sessionmaker, monkeypatch,
):
    from backend.app.routes import spaces as spaces_route

    _, other_client = personal_import_clients
    original = spaces_route.ensure_space_membership

    def fail_membership(*args, **kwargs):
        raise RuntimeError("membership creation failed")

    monkeypatch.setattr(spaces_route, "ensure_space_membership", fail_membership)
    with pytest.raises(RuntimeError, match="membership creation failed"):
        await other_client.post("/project-manager/api/spaces/personal", json={})

    with db_sessionmaker() as session:
        assert session.query(Space).filter_by(owner_user_id="other-user", space_kind="personal").count() == 0

    monkeypatch.setattr(spaces_route, "ensure_space_membership", original)
    response = await other_client.post("/project-manager/api/spaces/personal", json={})
    assert response.status_code == 201, response.text
    with db_sessionmaker() as session:
        assert session.query(SpaceMembership).filter_by(
            space_id=response.json()["space_id"], user_id="other-user", role="space_admin", status="active",
        ).count() == 1
