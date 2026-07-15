from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from backend.app import deps as deps_module
from backend.app.auth.auth import hash_password
from backend.app.models import Space, SpaceAccessRequest, SpaceMembership, User
from backend.main import app as fastapi_app


@pytest.fixture
def override_db_only(db_sessionmaker):
    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[deps_module.get_db] = get_test_db
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(override_db_only):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client


async def _register(auth_client: httpx.AsyncClient, *, soeid: str, display_name: str = "New User"):
    response = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": soeid, "display_name": display_name, "password": "Password123"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _login(auth_client: httpx.AsyncClient, *, soeid: str, password: str = "Password123"):
    response = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _seed_user(session, *, user_id: str, soeid: str, role: str = "user") -> User:
    user = User(
        user_id=user_id,
        soeid=soeid,
        email=f"{soeid}@citi.com",
        display_name=soeid.upper(),
        password_hash=hash_password("Password123"),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


@pytest.mark.anyio
async def test_registration_lands_in_lobby_without_personal_space_and_blocks_work_create(auth_client, db_sessionmaker):
    user = await _register(auth_client, soeid="lobbyuser1", display_name="Lobby User")

    active = await auth_client.get("/project-manager/api/auth/active-space")
    assert active.status_code == 200, active.text
    assert active.json()["space_kind"] == "lobby"
    assert active.json()["space_name"] == "Home"

    blocked_writes = [
        ("/projects/", {"project_name": "Should Not Be Created"}),
        ("/solutions/not-real/tasks", {"task_name": "Should Not Be Created"}),
        ("/teams", {"name": "Should Not Be Created"}),
    ]
    for path, payload in blocked_writes:
        blocked = await auth_client.post(f"/project-manager/api{path}", json=payload)
        assert blocked.status_code == 400, blocked.text
        assert blocked.headers["X-Error-Code"] == "LOBBY_SPACE_READ_ONLY"

    with db_sessionmaker() as session:
        spaces = session.query(Space).all()
        memberships = session.query(SpaceMembership).filter(SpaceMembership.user_id == user["user_id"]).all()
        assert len(spaces) == 1
        assert spaces[0].space_kind == "lobby"
        assert spaces[0].slug == "home"
        assert len(memberships) == 1
        assert memberships[0].space_id == spaces[0].space_id
        assert session.query(Space).filter(Space.space_kind == "personal").count() == 0


@pytest.mark.anyio
async def test_existing_main_space_stays_collaboration_when_home_lobby_exists(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        main = Space(
            space_id="existing-main-space",
            name="Main",
            slug="main",
            is_active=True,
            space_kind="collaboration",
        )
        user = _seed_user(session, user_id="main-member-user", soeid="mainmember")
        session.add(main)
        session.flush()
        session.add(SpaceMembership(space_id=main.space_id, user_id=user.user_id, role="member", status="active"))
        session.commit()

    await _login(auth_client, soeid="mainmember")

    active = await auth_client.get("/project-manager/api/auth/active-space")
    assert active.status_code == 200, active.text
    assert active.json()["space_kind"] == "collaboration"
    assert active.json()["space_id"] == "existing-main-space"

    with db_sessionmaker() as session:
        home = session.query(Space).filter(Space.slug == "home").first()
        main = session.query(Space).filter(Space.slug == "main").first()
        assert home is not None
        assert home.space_kind == "lobby"
        assert main is not None
        assert main.space_kind == "collaboration"


@pytest.mark.anyio
async def test_user_can_create_only_one_private_space_and_cannot_add_members(auth_client, db_sessionmaker):
    user = await _register(auth_client, soeid="privateuser1", display_name="Private User")

    created = await auth_client.post(
        "/project-manager/api/spaces/personal",
        json={"name": "Ignored Client Name", "slug": "ignored-client-slug"},
    )
    assert created.status_code == 201, created.text
    personal = created.json()
    assert personal["space_kind"] == "personal"
    assert personal["owner_user_id"] == user["user_id"]
    assert personal["name"] == "PRIVATEUSER1 Personal"
    assert personal["slug"] == "privateuser1-personal"

    duplicate = await auth_client.post(
        "/project-manager/api/spaces/personal",
        json={"name": "Another Private User Space"},
    )
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["detail"] == "User already has a personal space"

    switched = await auth_client.post(
        "/project-manager/api/auth/active-space",
        json={"space_id": personal["space_id"]},
    )
    assert switched.status_code == 200, switched.text

    with db_sessionmaker() as session:
        _seed_user(session, user_id="other-private-user", soeid="otherprivate")
        session.commit()

    add_member = await auth_client.post(
        f"/project-manager/api/spaces/{personal['space_id']}/members/by-soeid",
        json={"soeid": "otherprivate"},
    )
    assert add_member.status_code == 400, add_member.text
    assert add_member.json()["detail"] == "Personal spaces cannot add members"


@pytest.mark.anyio
async def test_access_request_lifecycle_approves_membership(auth_client, db_sessionmaker):
    requester = await _register(auth_client, soeid="requester1", display_name="Requester")
    with db_sessionmaker() as session:
        space = Space(
            space_id="collab-request-space",
            name="Collab Request Space",
            slug="collab-request-space",
            is_active=True,
            space_kind="collaboration",
        )
        admin = _seed_user(session, user_id="collab-space-admin", soeid="collabadmin", role="user")
        session.add(space)
        session.flush()
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=admin.user_id,
                role="space_admin",
                status="active",
            )
        )
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=requester["user_id"],
                role="member",
                status="inactive",
                deleted_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    requestable = await auth_client.get("/project-manager/api/spaces/requestable")
    assert requestable.status_code == 200, requestable.text
    assert [row["space_id"] for row in requestable.json()] == ["collab-request-space"]

    created = await auth_client.post(
        "/project-manager/api/spaces/collab-request-space/access-requests",
        json={"requested_role": "member"},
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["request_id"]

    duplicate = await auth_client.post(
        "/project-manager/api/spaces/collab-request-space/access-requests",
        json={"requested_role": "member"},
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["request_id"] == request_id

    auth_client.cookies.clear()
    await _login(auth_client, soeid="collabadmin")

    reviewable = await auth_client.get("/project-manager/api/spaces/access-requests/reviewable")
    assert reviewable.status_code == 200, reviewable.text
    assert [row["request_id"] for row in reviewable.json()] == [request_id]

    approved = await auth_client.post(
        f"/project-manager/api/spaces/access-requests/{request_id}/approve",
        json={},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    with db_sessionmaker() as session:
        membership = (
            session.query(SpaceMembership)
            .join(User, User.user_id == SpaceMembership.user_id)
            .filter(User.user_id == requester["user_id"])
            .filter(SpaceMembership.space_id == "collab-request-space")
            .filter(SpaceMembership.status == "active")
            .first()
        )
        assert membership is not None
        assert membership.role == "member"
        assert membership.deleted_at is None
        row = session.query(SpaceAccessRequest).filter(SpaceAccessRequest.request_id == request_id).first()
        assert row is not None
        assert row.status == "approved"


@pytest.mark.anyio
async def test_access_request_lifecycle_cancel_and_reject(auth_client, db_sessionmaker):
    await _register(auth_client, soeid="requester2", display_name="Requester Two")
    with db_sessionmaker() as session:
        space = Space(
            space_id="collab-cancel-reject-space",
            name="Cancel Reject Space",
            slug="collab-cancel-reject-space",
            is_active=True,
            space_kind="collaboration",
        )
        admin = _seed_user(session, user_id="reject-space-admin", soeid="rejectadmin", role="user")
        session.add(space)
        session.flush()
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=admin.user_id,
                role="space_admin",
                status="active",
            )
        )
        session.commit()

    created = await auth_client.post(
        "/project-manager/api/spaces/collab-cancel-reject-space/access-requests",
        json={"requested_role": "member"},
    )
    assert created.status_code == 201, created.text
    first_request_id = created.json()["request_id"]

    canceled = await auth_client.delete(f"/project-manager/api/spaces/access-requests/{first_request_id}")
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"

    second = await auth_client.post(
        "/project-manager/api/spaces/collab-cancel-reject-space/access-requests",
        json={"requested_role": "member"},
    )
    assert second.status_code == 201, second.text
    second_request_id = second.json()["request_id"]
    assert second_request_id != first_request_id
    assert second.json()["status"] == "pending"

    auth_client.cookies.clear()
    await _login(auth_client, soeid="rejectadmin")

    rejected = await auth_client.post(
        f"/project-manager/api/spaces/access-requests/{second_request_id}/reject",
        json={"decision_note": "No project assignment yet."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["decision_note"] == "No project assignment yet."

    with db_sessionmaker() as session:
        statuses = {
            row.request_id: row.status
            for row in session.query(SpaceAccessRequest)
            .filter(SpaceAccessRequest.space_id == "collab-cancel-reject-space")
            .all()
        }
        assert statuses[first_request_id] == "canceled"
        assert statuses[second_request_id] == "rejected"
