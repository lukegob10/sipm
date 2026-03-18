from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from backend.app import deps as deps_module
from backend.app.auth import auth as auth_module
from backend.app.auth.auth import (
    clear_auth_cookies,
    create_token,
    decode_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from backend.app.models import User
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


def _encode_test_token(payload: dict[str, object]) -> str:
    return jwt.encode(payload, auth_module.SECRET_KEY, algorithm=auth_module.ALGORITHM)


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


def test_password_hashing_and_verification_handles_long_passwords_and_bad_hashes():
    password = "correct horse battery staple"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False

    long_password = "x" * 80  # bcrypt truncates at 72 bytes; we pre-hash to avoid silent truncation
    long_hashed = hash_password(long_password)
    assert verify_password(long_password, long_hashed) is True
    assert verify_password(long_password, "not-a-bcrypt-hash") is False


def test_decode_token_errors_and_type_check():
    expired = jwt.encode(
        {
            "sub": "user-1",
            "role": "user",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        auth_module.SECRET_KEY,
        algorithm=auth_module.ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(expired, expected_type="access")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expired"

    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-token", expected_type="access")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"

    wrong_type = _encode_test_token(
        {
            "sub": "user-1",
            "role": "user",
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(wrong_type, expected_type="access")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token type"


def test_refresh_token_default_ttl_is_one_hour(monkeypatch):
    import backend.app.auth.auth as auth_module

    with monkeypatch.context() as env:
        env.delenv("SIPM_REFRESH_MINUTES", raising=False)
        env.delenv("SIPM_REFRESH_DAYS", raising=False)
        reloaded = importlib.reload(auth_module)
        token = reloaded.create_token("user-1", "user", "refresh")
        payload = jwt.decode(
            token,
            reloaded.SECRET_KEY,
            algorithms=[reloaded.ALGORITHM],
            options={"verify_exp": False},
        )
        ttl_seconds = int(payload["exp"]) - int(payload["iat"])
        assert 59 * 60 <= ttl_seconds <= 61 * 60

    importlib.reload(auth_module)


def test_access_token_ttl_supports_explicit_zero_minutes(monkeypatch):
    import backend.app.auth.auth as auth_module

    with monkeypatch.context() as env:
        env.setenv("SIPM_ACCESS_MINUTES", "0")
        reloaded = importlib.reload(auth_module)
        assert reloaded.ACCESS_TOKEN_EXPIRE_MINUTES == 0
        assert reloaded.ACCESS_TOKEN_COOKIE_MAX_AGE_SECONDS == 0

    importlib.reload(auth_module)


def test_refresh_token_ttl_supports_days_env(monkeypatch):
    import backend.app.auth.auth as auth_module

    with monkeypatch.context() as env:
        env.delenv("SIPM_REFRESH_MINUTES", raising=False)
        env.setenv("SIPM_REFRESH_DAYS", "7")
        reloaded = importlib.reload(auth_module)
        token = reloaded.create_token("user-1", "user", "refresh")
        payload = jwt.decode(
            token,
            reloaded.SECRET_KEY,
            algorithms=[reloaded.ALGORITHM],
            options={"verify_exp": False},
        )
        ttl_seconds = int(payload["exp"]) - int(payload["iat"])
        expected = 7 * 24 * 60 * 60
        assert expected - 60 <= ttl_seconds <= expected + 60

    importlib.reload(auth_module)


def test_auth_cookie_helpers_set_lifetimes_and_clear(monkeypatch):
    import backend.app.auth.auth as auth_module

    with monkeypatch.context() as env:
        env.setenv("SIPM_ACCESS_MINUTES", "60")
        env.delenv("SIPM_REFRESH_MINUTES", raising=False)
        env.setenv("SIPM_REFRESH_DAYS", "7")
        reloaded = importlib.reload(auth_module)

        response = Response()
        reloaded.set_auth_cookies(response, "access", "refresh")
        cookies = response.headers.getlist("set-cookie")
        assert any(
            "access_token=" in cookie
            and "Path=/project-manager" in cookie
            and f"Max-Age={reloaded.ACCESS_TOKEN_COOKIE_MAX_AGE_SECONDS}" in cookie
            for cookie in cookies
        )
        assert any(
            "refresh_token=" in cookie
            and "Path=/project-manager" in cookie
            and f"Max-Age={reloaded.REFRESH_TOKEN_COOKIE_MAX_AGE_SECONDS}" in cookie
            for cookie in cookies
        )

        active = Response()
        reloaded.set_active_space_cookie(active, "space-1")
        active_cookies = active.headers.getlist("set-cookie")
        assert any(
            "active_space_id=space-1" in cookie
            and "Path=/project-manager" in cookie
            and f"Max-Age={reloaded.REFRESH_TOKEN_COOKIE_MAX_AGE_SECONDS}" in cookie
            for cookie in active_cookies
        )

        clear = Response()
        reloaded.clear_auth_cookies(clear)
        cleared = clear.headers.getlist("set-cookie")
        assert any(
            "access_token=" in cookie and "Max-Age=0" in cookie and "Path=/project-manager" in cookie
            for cookie in cleared
        )
        assert any(
            "refresh_token=" in cookie and "Max-Age=0" in cookie and "Path=/project-manager" in cookie
            for cookie in cleared
        )

    importlib.reload(auth_module)


def test_require_space_role_normalizes_space_admin_aliases():
    dep = deps_module.require_space_role("space_admin")
    ctx_space = SpaceContext(
        space_id="space-1",
        space_name="Space 1",
        is_global_admin=False,
        space_role="space admin",
    )
    assert dep(ctx_space) is ctx_space

    ctx_hyphen = SpaceContext(
        space_id="space-1",
        space_name="Space 1",
        is_global_admin=False,
        space_role="space-admin",
    )
    assert dep(ctx_hyphen) is ctx_hyphen


def test_require_space_role_rejects_member_for_space_admin_threshold():
    dep = deps_module.require_space_role("space_admin")
    ctx = SpaceContext(
        space_id="space-1",
        space_name="Space 1",
        is_global_admin=False,
        space_role="member",
    )
    with pytest.raises(HTTPException) as exc:
        dep(ctx)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Insufficient space role"


@pytest.mark.anyio
async def test_register_refresh_logout_and_me(auth_client):
    payload = {"soeid": "ABC1", "display_name": "Alice", "password": "Password123"}
    resp = await auth_client.post("/project-manager/api/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["soeid"] == "abc1"
    assert created["email"] == "abc1@citi.com"

    me = await auth_client.get("/project-manager/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["user_id"] == created["user_id"]

    refresh = await auth_client.post("/project-manager/api/auth/refresh")
    assert refresh.status_code == 200, refresh.text

    logout = await auth_client.post("/project-manager/api/auth/logout")
    assert logout.status_code == 204

    auth_client.cookies.clear()
    me_unauth = await auth_client.get("/project-manager/api/auth/me")
    assert me_unauth.status_code == 401

    dup = await auth_client.post("/project-manager/api/auth/register", json=payload)
    assert dup.status_code == 400
    assert dup.json()["detail"] == "SOEID already registered"


@pytest.mark.anyio
async def test_register_uses_reloaded_self_registration_setting(monkeypatch, override_db_only):
    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_ALLOW_SELF_REGISTER", "false")
            importlib.reload(auth_module)
            async with fastapi_app.router.lifespan_context(fastapi_app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=fastapi_app),
                    base_url="http://test",
                ) as client:
                    resp = await client.post(
                        "/project-manager/api/auth/register",
                        json={"soeid": "blocked1", "display_name": "Blocked", "password": "Password123"},
                    )
            assert resp.status_code == 403
            assert resp.json()["detail"] == "Self-registration is disabled"
    finally:
        importlib.reload(auth_module)


@pytest.mark.anyio
async def test_global_admin_can_issue_temp_password_and_user_reset_with_it(auth_client, db_sessionmaker):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "GA2", "display_name": "Global Admin", "password": "Password123"},
    )
    assert register.status_code == 201, register.text

    with db_sessionmaker() as session:
        admin = session.query(User).filter(User.soeid == "ga2").first()
        assert admin is not None
        admin.role = "global_admin"
        target = User(
            soeid="resettarget1",
            email="resettarget1@example.com",
            display_name="Reset Target",
            password_hash=hash_password("OldPassword123"),
            role="user",
            is_active=True,
        )
        session.add_all([admin, target])
        session.commit()

    issued = await auth_client.post(
        "/project-manager/api/users/by-soeid/resettarget1/password-reset-request",
        json={"expires_minutes": 30},
    )
    assert issued.status_code == 201, issued.text
    payload = issued.json()
    assert payload["status"] == "issued"
    assert payload["temp_password"]

    reset = await auth_client.post(
        "/project-manager/api/auth/reset-password",
        json={
            "soeid": "resettarget1",
            "temp_password": payload["temp_password"],
            "new_password": "Password456",
            "confirm_password": "Password456",
        },
    )
    assert reset.status_code == 200, reset.text

    login = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "resettarget1", "password": "Password456"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["soeid"] == "resettarget1"


@pytest.mark.anyio
async def test_refresh_preserves_active_space_selection(auth_client, db_sessionmaker):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "GA1", "display_name": "Global Admin", "password": "Password123"},
    )
    assert register.status_code == 201, register.text

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "ga1").first()
        assert user is not None
        user.role = "global_admin"
        session.add(user)
        session.commit()

    create_space = await auth_client.post(
        "/project-manager/api/spaces",
        json={"name": "Ops Alpha"},
    )
    assert create_space.status_code == 201, create_space.text
    ops_space_id = create_space.json()["space_id"]

    auth_client.cookies.set("active_space_id", ops_space_id)

    before = await auth_client.get("/project-manager/api/auth/active-space")
    assert before.status_code == 200, before.text
    assert before.json()["space_id"] == ops_space_id

    refreshed = await auth_client.post("/project-manager/api/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text

    after = await auth_client.get("/project-manager/api/auth/active-space")
    assert after.status_code == 200, after.text
    assert after.json()["space_id"] == ops_space_id


@pytest.mark.anyio
async def test_refresh_rejects_token_issued_before_password_change(auth_client, db_sessionmaker):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "REVOKE1", "display_name": "Revoke User", "password": "Password123"},
    )
    assert register.status_code == 201, register.text

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "revoke1").first()
        assert user is not None
        user.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
        session.add(user)
        session.commit()

    refreshed = await auth_client.post("/project-manager/api/auth/refresh")
    assert refreshed.status_code == 401
    assert refreshed.json()["detail"] == "Token no longer valid"


@pytest.mark.anyio
async def test_get_active_space_repairs_missing_active_space_cookie(auth_client):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "COOKIE1", "display_name": "Cookie User", "password": "Password123"},
    )
    assert register.status_code == 201, register.text

    auth_client.cookies.pop("active_space_id", None)

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    active_space_id = resp.json()["space_id"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(f"active_space_id={active_space_id}" in cookie for cookie in set_cookies)


@pytest.mark.anyio
async def test_get_active_space_repairs_stale_active_space_cookie(auth_client):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "COOKIE2", "display_name": "Stale Cookie User", "password": "Password123"},
    )
    assert register.status_code == 201, register.text

    auth_client.cookies.set("active_space_id", "stale-space-id")

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    active_space_id = resp.json()["space_id"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(f"active_space_id={active_space_id}" in cookie for cookie in set_cookies)
    assert all("active_space_id=stale-space-id" not in cookie for cookie in set_cookies)


@pytest.mark.anyio
async def test_login_lockout_and_unlock(auth_client, db_sessionmaker):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "LOCK1", "display_name": "Locker", "password": "Password123"},
    )
    assert register.status_code == 201, register.text
    auth_client.cookies.clear()

    for _ in range(5):
        bad = await auth_client.post(
            "/project-manager/api/auth/login", json={"soeid": "lock1", "password": "wrong-password"}
        )
        assert bad.status_code == 401

    locked = await auth_client.post(
        "/project-manager/api/auth/login", json={"soeid": "lock1", "password": "wrong-password"}
    )
    assert locked.status_code == 423

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "lock1").first()
        assert user is not None
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(user)
        session.commit()

    ok = await auth_client.post(
        "/project-manager/api/auth/login", json={"soeid": "lock1", "password": "Password123"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["last_login_at"] is not None

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "lock1").first()
        assert user is not None
        assert user.failed_attempts == 0
        assert user.locked_until is None


@pytest.mark.anyio
async def test_require_user_rejects_invalid_or_missing_subject_and_locked_users(auth_client, db_sessionmaker):
    register = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "AUTH1", "display_name": "Auth", "password": "Password123"},
    )
    assert register.status_code == 201

    auth_client.cookies.clear()
    missing_cookie = await auth_client.get("/project-manager/api/auth/me")
    assert missing_cookie.status_code == 401

    auth_client.cookies.set("access_token", "not-a-token")
    invalid = await auth_client.get("/project-manager/api/auth/me")
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid token"

    auth_client.cookies.clear()
    auth_client.cookies.set(
        "access_token",
        _encode_test_token(
            {
                "sub": "missing-user",
                "role": "user",
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            }
        ),
    )
    missing_user = await auth_client.get("/project-manager/api/auth/me")
    assert missing_user.status_code == 401
    assert missing_user.json()["detail"] == "User inactive or missing"

    auth_client.cookies.clear()
    auth_client.cookies.set(
        "access_token",
        _encode_test_token(
            {"role": "user", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        ),
    )
    no_subject = await auth_client.get("/project-manager/api/auth/me")
    assert no_subject.status_code == 401
    assert no_subject.json()["detail"] == "Invalid token subject"

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "auth1").first()
        assert user is not None
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        session.add(user)
        session.commit()
        user_id = user.user_id

    auth_client.cookies.clear()
    auth_client.cookies.set(
        "access_token",
        _encode_test_token(
            {
                "sub": user_id,
                "role": "user",
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            }
        ),
    )
    locked = await auth_client.get("/project-manager/api/auth/me")
    assert locked.status_code == 423
    assert locked.json()["detail"] == "Account locked"


def test_current_user_dependency_requires_state_user():
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    with pytest.raises(HTTPException) as exc:
        deps_module.current_user(request)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


def test_get_db_yields_from_get_session(monkeypatch):
    sentinel = object()

    def fake_get_session():
        yield sentinel

    monkeypatch.setattr(deps_module, "get_session", fake_get_session)
    gen = deps_module.get_db()
    assert next(gen) is sentinel
    gen.close()
