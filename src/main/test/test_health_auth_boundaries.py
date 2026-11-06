from __future__ import annotations

import httpx
import pytest

from backend.app import deps
from backend.app.auth.auth import create_token
from backend.app.models import ApiToken, Space, Team, User
from backend.app.paths import API_PREFIX, COOKIE_PATH
from backend.app.services.api_tokens import hash_api_token
from backend.app.services.auth_sessions import create_auth_session
from backend.main import app


@pytest.fixture
async def boundary_client(db_sessionmaker):
    api_token = "sipm_pat_health-auth-boundaries"
    with db_sessionmaker() as session:
        cookie_user = User(
            user_id="health-cookie-user", soeid="healthcookie", email="cookie@example.invalid",
            display_name="Cookie User", password_hash="unused", role="global_admin", is_active=True,
        )
        api_user = User(
            user_id="health-api-user", soeid="healthapi", email="api@example.invalid",
            display_name="API User", password_hash="unused", role="global_admin", is_active=True,
        )
        session.add_all([
            cookie_user, api_user,
            Space(space_id="health-auth-space", name="Auth Space", slug="health-auth-space"),
        ])
        session.flush()
        auth_session = create_auth_session(session, cookie_user)
        access_token = create_token(
            cookie_user.user_id, cookie_user.role, "access", session_id=auth_session.session_id,
        )
        session.add(ApiToken(
            user_id=api_user.user_id, name="Health review", token_hash=hash_api_token(api_token),
            created_by_user_id=cookie_user.user_id,
        ))
        session.commit()

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[deps.get_db] = get_test_db
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test",
            ) as client:
                client.cookies.set("access_token", access_token, path=COOKIE_PATH)
                client.cookies.set("active_space_id", "health-auth-space", path=COOKIE_PATH)
                yield client, api_token
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.mark.anyio
@pytest.mark.parametrize(("authorization", "code"), [
    ("Bearer", "AUTH_REQUIRED"),
    ("Bearer   ", "AUTH_REQUIRED"),
    ("bEaReR", "AUTH_REQUIRED"),
    ("Bearer\tinvalid-token", "API_TOKEN_INVALID"),
])
@pytest.mark.parametrize(("method", "path"), [("GET", "/auth/me"), ("POST", "/teams")])
async def test_malformed_bearer_does_not_authenticate_as_cookie_user(
    boundary_client, db_sessionmaker, authorization, code, method, path,
):
    client, _api_token = boundary_client
    response = await client.request(
        method, f"{API_PREFIX}{path}", headers={"Authorization": authorization},
        **({"json": {"name": "Must not be created"}} if method == "POST" else {}),
    )

    assert response.status_code == 401, response.text
    assert response.headers["X-Error-Code"] == code
    assert not response.headers.get_list("set-cookie")
    with db_sessionmaker() as session:
        assert session.query(Team).count() == 0

    cookie_identity = await client.get(f"{API_PREFIX}/auth/me")
    assert cookie_identity.status_code == 200, cookie_identity.text
    assert cookie_identity.json()["user_id"] == "health-cookie-user"


@pytest.mark.anyio
@pytest.mark.parametrize("separator", [" ", "    ", "\t"])
async def test_cookie_and_valid_bearer_keep_distinct_write_authorization(
    boundary_client, db_sessionmaker, separator,
):
    client, api_token = boundary_client
    headers = {"Authorization": f"Bearer{separator}{api_token}"}
    api_identity = await client.get(f"{API_PREFIX}/auth/me", headers=headers)
    assert api_identity.status_code == 200, api_identity.text
    assert api_identity.json()["user_id"] == "health-api-user"

    api_write = await client.post(f"{API_PREFIX}/teams", headers=headers, json={"name": "Blocked"})
    assert api_write.status_code == 403, api_write.text
    assert api_write.headers["X-Error-Code"] == "AGENT_APPROVAL_REQUIRED"
    with db_sessionmaker() as session:
        assert session.query(Team).count() == 0

    cookie_write = await client.post(f"{API_PREFIX}/teams", json={"name": "Interactive"})
    assert cookie_write.status_code == 201, cookie_write.text
    with db_sessionmaker() as session:
        assert [team.name for team in session.query(Team).all()] == ["Interactive"]
