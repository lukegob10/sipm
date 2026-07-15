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
from backend.app.routes import auth as auth_routes_module
from backend.app.auth.auth import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.app.models import ApiToken, AuthSession, Space, SpaceMembership, User
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


def _encode_test_token(payload: dict[str, object]) -> str:
    return jwt.encode(payload, auth_module.SECRET_KEY, algorithm=auth_module.ALGORITHM)


async def _login_local_session(
    auth_client: httpx.AsyncClient,
    db_sessionmaker,
    *,
    soeid: str,
    display_name: str | None = None,
    password: str = "Password123",
    role: str = "user",
    is_active: bool = True,
):
    soeid_norm = soeid.lower()
    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == soeid_norm).first()
        if user is None:
            user = User(
                soeid=soeid_norm,
                email=f"{soeid_norm}@citi.com",
                display_name=display_name or soeid_norm.upper(),
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
            session.add(user)
            session.flush()
        else:
            user.display_name = display_name or user.display_name
            user.password_hash = hash_password(password)
            user.role = role
            user.is_active = is_active
            session.add(user)
            session.flush()
        space = session.query(Space).filter(Space.slug == "main").first()
        if space is None:
            space = Space(space_id="test-main-space", name="Main", slug="main", is_active=True)
            session.add(space)
            session.flush()
        membership = (
            session.query(SpaceMembership)
            .filter(SpaceMembership.user_id == user.user_id)
            .filter(SpaceMembership.space_id == space.space_id)
            .first()
        )
        if membership is None:
            session.add(
                SpaceMembership(
                    space_id=space.space_id,
                    user_id=user.user_id,
                    role="space_admin" if role == "global_admin" else "member",
                    status="active",
                )
            )
        session.commit()

    response = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": password},
    )
    assert response.status_code == 200, response.text
    return response


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


def test_validate_auth_configuration_rejects_negative_access_minutes(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_ACCESS_MINUTES", "-1")
            reloaded = importlib.reload(auth_module)
            with pytest.raises(
                RuntimeError,
                match="SIPM_ACCESS_MINUTES must be greater than or equal to 0.",
            ):
                reloaded.validate_auth_configuration()
    finally:
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


def test_validate_auth_configuration_rejects_negative_refresh_days(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.delenv("SIPM_REFRESH_MINUTES", raising=False)
            env.setenv("SIPM_REFRESH_DAYS", "-7")
            reloaded = importlib.reload(auth_module)
            with pytest.raises(
                RuntimeError,
                match="SIPM_REFRESH_DAYS must be greater than or equal to 0.",
            ):
                reloaded.validate_auth_configuration()
    finally:
        importlib.reload(auth_module)


def test_auth_module_rejects_invalid_access_minutes(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_ACCESS_MINUTES", "sixty")
            with pytest.raises(RuntimeError, match="SIPM_ACCESS_MINUTES must be an integer."):
                importlib.reload(auth_module)
    finally:
        importlib.reload(auth_module)


def test_auth_module_rejects_invalid_bcrypt_rounds(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_BCRYPT_ROUNDS", "twelve")
            with pytest.raises(RuntimeError, match="SIPM_BCRYPT_ROUNDS must be an integer."):
                importlib.reload(auth_module)
    finally:
        importlib.reload(auth_module)


def test_validate_auth_configuration_rejects_invalid_bcrypt_rounds_value(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_BCRYPT_ROUNDS", "0")
            reloaded = importlib.reload(auth_module)
            with pytest.raises(
                RuntimeError,
                match="SIPM_BCRYPT_ROUNDS must be a valid bcrypt rounds value.",
            ):
                reloaded.validate_auth_configuration()
    finally:
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


def test_validate_auth_configuration_rejects_invalid_cookie_samesite(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_COOKIE_SAMESITE", "sideways")
            reloaded = importlib.reload(auth_module)
            with pytest.raises(
                RuntimeError,
                match="SIPM_COOKIE_SAMESITE must be one of: lax, strict, none.",
            ):
                reloaded.validate_auth_configuration()
    finally:
        importlib.reload(auth_module)


def test_validate_auth_configuration_accepts_common_truthy_secure_cookie_values(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("ENV", "prod")
            env.setenv("SIPM_SECRET_KEY", "x" * 40)
            env.setenv("SIPM_SECURE_COOKIES", "yes")
            env.setenv("SIPM_ALLOW_SELF_REGISTER", "false")
            reloaded = importlib.reload(auth_module)
            assert reloaded.SECURE_COOKIES is True
            reloaded.validate_auth_configuration()
    finally:
        importlib.reload(auth_module)


def test_unknown_env_defaults_to_non_dev_auth_safety(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("ENV", "stage")
            env.setenv("SIPM_SECRET_KEY", "x" * 40)
            env.delenv("SIPM_SECURE_COOKIES", raising=False)
            env.delenv("SIPM_ALLOW_SELF_REGISTER", raising=False)
            reloaded = importlib.reload(auth_module)
            assert reloaded.DEPLOYMENT_ENV == "stage"
            assert reloaded.IS_NON_DEV is True
            assert reloaded.SECURE_COOKIES is True
            assert reloaded.ALLOW_SELF_REGISTER is False
            reloaded.validate_auth_configuration()
    finally:
        importlib.reload(auth_module)


def test_validate_auth_configuration_rejects_non_dev_self_registration(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("ENV", "prod")
            env.setenv("SIPM_SECRET_KEY", "x" * 40)
            env.setenv("SIPM_SECURE_COOKIES", "true")
            env.setenv("SIPM_ALLOW_SELF_REGISTER", "true")
            reloaded = importlib.reload(auth_module)
            with pytest.raises(
                RuntimeError,
                match="SIPM_ALLOW_SELF_REGISTER must be false in non-dev environments.",
            ):
                reloaded.validate_auth_configuration()
    finally:
        importlib.reload(auth_module)


def test_auth_module_rejects_invalid_secure_cookie_boolean(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_SECURE_COOKIES", "sometimes")
            with pytest.raises(RuntimeError, match="SIPM_SECURE_COOKIES must be a boolean value."):
                importlib.reload(auth_module)
    finally:
        importlib.reload(auth_module)


def test_validate_auth_configuration_requires_secure_cookies_for_samesite_none(monkeypatch):
    import backend.app.auth.auth as auth_module

    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_COOKIE_SAMESITE", "none")
            env.setenv("SIPM_SECURE_COOKIES", "false")
            reloaded = importlib.reload(auth_module)
            with pytest.raises(
                RuntimeError,
                match="SIPM_COOKIE_SAMESITE=none requires SIPM_SECURE_COOKIES=true.",
            ):
                reloaded.validate_auth_configuration()
    finally:
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
async def test_local_login_sets_session_cookies_and_supports_register_refresh_logout(
    auth_client,
    db_sessionmaker,
):
    resp = await _login_local_session(
        auth_client,
        db_sessionmaker,
        soeid="ABC1",
        display_name="Alice Local",
    )
    logged_in = resp.json()
    assert logged_in["soeid"] == "abc1"
    assert logged_in["email"] == "abc1@citi.com"
    assert logged_in["display_name"] == "Alice Local"

    set_cookies = resp.headers.get_list("set-cookie")
    assert any("access_token=" in cookie for cookie in set_cookies)
    assert any("refresh_token=" in cookie for cookie in set_cookies)
    assert any("active_space_id=" in cookie for cookie in set_cookies)

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "abc1").first()
        assert user is not None
        assert user.email == "abc1@citi.com"
        assert user.external_id is None

    refresh = await auth_client.post("/project-manager/api/auth/refresh")
    assert refresh.status_code == 200, refresh.text

    logout = await auth_client.post("/project-manager/api/auth/logout")
    assert logout.status_code == 204

    auth_client.cookies.clear()
    me_unauth = await auth_client.get("/project-manager/api/auth/me")
    assert me_unauth.status_code == 401

    registered = await auth_client.post(
        "/project-manager/api/auth/register",
        json={"soeid": "newlocal1", "display_name": "New Local", "password": "Password123"},
    )
    assert registered.status_code == 201, registered.text


@pytest.mark.anyio
async def test_interactive_session_policy_activity_refresh_and_logout(
    auth_client,
    db_sessionmaker,
):
    await _login_local_session(auth_client, db_sessionmaker, soeid="idle1")
    access_payload = decode_token(auth_client.cookies.get("access_token"), expected_type="access")
    refresh_payload = decode_token(auth_client.cookies.get("refresh_token"), expected_type="refresh")
    assert access_payload["sid"] == refresh_payload["sid"]

    policy = await auth_client.get("/project-manager/api/auth/session-policy")
    assert policy.status_code == 200
    assert policy.json() == {
        "idle_timeout_seconds": 1800,
        "warning_seconds": 60,
        "activity_heartbeat_seconds": 15,
    }

    with db_sessionmaker() as session:
        auth_session = session.query(AuthSession).filter_by(session_id=access_payload["sid"]).one()
        initial_activity = auth_session.last_activity_at

    refresh = await auth_client.post("/project-manager/api/auth/refresh")
    assert refresh.status_code == 200
    with db_sessionmaker() as session:
        unchanged = session.query(AuthSession).filter_by(session_id=access_payload["sid"]).one()
        assert unchanged.last_activity_at == initial_activity

    activity = await auth_client.post("/project-manager/api/auth/activity")
    assert activity.status_code == 200
    assert datetime.fromisoformat(activity.json()["idle_expires_at"]) > initial_activity

    logout = await auth_client.post("/project-manager/api/auth/logout")
    assert logout.status_code == 204
    with db_sessionmaker() as session:
        revoked = session.query(AuthSession).filter_by(session_id=access_payload["sid"]).one()
        assert revoked.revoked_at is not None


@pytest.mark.anyio
async def test_idle_expired_and_legacy_sessions_are_rejected(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="idle2")
    payload = decode_token(auth_client.cookies.get("access_token"), expected_type="access")
    with db_sessionmaker() as session:
        auth_session = session.query(AuthSession).filter_by(session_id=payload["sid"]).one()
        auth_session.last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=31)
        session.commit()

    expired = await auth_client.get("/project-manager/api/auth/me")
    assert expired.status_code == 401
    assert expired.headers["X-Error-Code"] == "SESSION_IDLE_EXPIRED"

    legacy = create_token(payload["sub"], payload["role"], "access")
    auth_client.cookies.set("access_token", legacy, path="/project-manager")
    legacy_response = await auth_client.get("/project-manager/api/auth/me")
    assert legacy_response.status_code == 401
    assert legacy_response.headers["X-Error-Code"] == "SESSION_REQUIRED"


@pytest.mark.anyio
async def test_local_login_preserves_existing_role(auth_client, db_sessionmaker):
    resp = await _login_local_session(
        auth_client,
        db_sessionmaker,
        soeid="GA2",
        display_name="Global Admin",
        role="global_admin",
    )
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user_id"]

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        assert user is not None
        assert user.role == "global_admin"
        assert user.display_name == "Global Admin"
        assert user.email == "ga2@citi.com"


@pytest.mark.anyio
async def test_me_rejects_invalid_cookie_without_identity_bootstrap(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(
            User(
                soeid="fallback1",
                email="fallback1@citi.com",
                display_name="Fallback User",
                password_hash=hash_password("Password123"),
                role="user",
                is_active=True,
            )
        )
        session.commit()

    auth_client.cookies.set("access_token", "not-a-token")

    resp = await auth_client.get("/project-manager/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "fallback1").first()
        assert user is not None
        assert user.external_id is None


@pytest.mark.anyio
async def test_me_requires_authentication(auth_client):
    resp = await auth_client.get("/project-manager/api/auth/me")

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_local_login_rejects_inactive_existing_user(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(
            User(
                soeid="inactive1",
                email="inactive1@citi.com",
                display_name="Inactive User",
                password_hash=hash_password("OldPassword123"),
                role="user",
                is_active=False,
            )
        )
        session.commit()

    resp = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "inactive1", "password": "OldPassword123"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Login failed. Check your username or password."


@pytest.mark.anyio
async def test_login_performs_password_work_for_missing_and_inactive_users(
    auth_client,
    db_sessionmaker,
    monkeypatch,
):
    calls = []

    def _fake_verify(plain_password, hashed_password):
        calls.append((plain_password, hashed_password))
        return False

    monkeypatch.setattr(auth_routes_module, "verify_password", _fake_verify)

    missing = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "missingtiming1", "password": "Password123"},
    )
    assert missing.status_code == 401

    with db_sessionmaker() as session:
        session.add(
            User(
                soeid="inactivetiming1",
                email="inactivetiming1@citi.com",
                display_name="Inactive Timing",
                password_hash="stored-hash",
                role="user",
                is_active=False,
            )
        )
        session.commit()

    inactive = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "inactivetiming1", "password": "Password123"},
    )
    assert inactive.status_code == 403
    assert len(calls) == 2
    assert calls[0][0] == "Password123"
    assert calls[1] == ("Password123", "stored-hash")


@pytest.mark.anyio
async def test_login_clears_expired_lockout_before_counting_new_failures(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        user = User(
            soeid="lockpast1",
            email="lockpast1@citi.com",
            display_name="Expired Lockout",
            password_hash=hash_password("CorrectPassword123"),
            role="user",
            is_active=True,
            failed_attempts=5,
            locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        space = Space(space_id="lockpast-space", name="Lockpast Space", slug="lockpast-space", is_active=True)
        session.add_all([user, space])
        session.flush()
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=user.user_id,
                role="member",
                status="active",
            )
        )
        session.commit()

    wrong = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "lockpast1", "password": "WrongPassword123"},
    )
    assert wrong.status_code == 401
    assert wrong.headers["X-Error-Code"] == "LOGIN_FAILED"

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "lockpast1").first()
        assert user is not None
        assert user.failed_attempts == 1
        assert user.locked_until is None

    correct = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "lockpast1", "password": "CorrectPassword123"},
    )
    assert correct.status_code == 200, correct.text


@pytest.mark.anyio
async def test_login_only_reports_password_reset_required_after_password_verification(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(
            User(
                soeid="resetgate1",
                email="resetgate1@citi.com",
                display_name="Reset Gate",
                password_hash=hash_password("CorrectPassword123"),
                role="user",
                is_active=True,
                force_password_reset=True,
            )
        )
        session.commit()

    wrong = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "resetgate1", "password": "WrongPassword123"},
    )
    assert wrong.status_code == 401
    assert wrong.headers["X-Error-Code"] == "LOGIN_FAILED"
    assert wrong.json()["detail"] == "Login failed. Check your username or password."

    correct = await auth_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "resetgate1", "password": "CorrectPassword123"},
    )
    assert correct.status_code == 403
    assert correct.headers["X-Error-Code"] == "PASSWORD_RESET_REQUIRED"
    assert correct.json()["detail"] == "Password reset required"


@pytest.mark.anyio
async def test_temp_password_reset_attempts_lock_account_after_repeated_failures(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(
            User(
                soeid="tempfail1",
                email="tempfail1@citi.com",
                display_name="Temp Fail",
                password_hash=hash_password("OldPassword123"),
                role="user",
                is_active=True,
                force_password_reset=True,
                temp_password_hash=hash_password("TempPassword123"),
                temp_password_expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        )
        session.commit()

    for attempt in range(5):
        resp = await auth_client.post(
            "/project-manager/api/auth/reset-password",
            json={
                "soeid": "tempfail1",
                "temp_password": "WrongTempPassword123",
                "new_password": "NewPassword123",
                "confirm_password": "NewPassword123",
            },
        )
        assert resp.status_code == 401, attempt
        assert resp.headers["X-Error-Code"] == "TEMP_PASSWORD_INVALID"

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "tempfail1").first()
        assert user is not None
        assert user.failed_attempts == 5
        assert user.locked_until is not None

    locked = await auth_client.post(
        "/project-manager/api/auth/reset-password",
        json={
            "soeid": "tempfail1",
            "temp_password": "TempPassword123",
            "new_password": "NewPassword123",
            "confirm_password": "NewPassword123",
        },
    )
    assert locked.status_code == 423
    assert locked.headers["X-Error-Code"] == "ACCOUNT_LOCKED"


@pytest.mark.anyio
async def test_temp_password_reset_clears_expired_lockout_for_valid_reset(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(
            User(
                soeid="temppast1",
                email="temppast1@citi.com",
                display_name="Temp Past",
                password_hash=hash_password("OldPassword123"),
                role="user",
                is_active=True,
                force_password_reset=True,
                temp_password_hash=hash_password("TempPassword123"),
                temp_password_expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                failed_attempts=5,
                locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        session.commit()

    resp = await auth_client.post(
        "/project-manager/api/auth/reset-password",
        json={
            "soeid": "temppast1",
            "temp_password": "TempPassword123",
            "new_password": "NewPassword123",
            "confirm_password": "NewPassword123",
        },
    )
    assert resp.status_code == 200, resp.text

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "temppast1").first()
        assert user is not None
        assert user.failed_attempts == 0
        assert user.locked_until is None
        assert user.force_password_reset is False
        assert user.temp_password_hash is None
        assert verify_password("NewPassword123", user.password_hash) is True


@pytest.mark.anyio
async def test_admin_issued_service_account_api_token_authenticates_api(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="ADMINPAT1", display_name="Admin PAT", role="global_admin")
    with db_sessionmaker() as session:
        admin = session.query(User).filter(User.soeid == "adminpat1").first()
        assert admin is not None
        admin.role = "global_admin"
        service_user = User(
            soeid="svcpat1",
            email="svcpat1@citi.com",
            display_name="Service PAT",
            password_hash=hash_password("ServicePassword123"),
            role="global_admin",
            is_active=True,
            is_service_account=True,
        )
        session.add_all([admin, service_user])
        session.commit()
        service_user_id = service_user.user_id

    issued = await auth_client.post(
        f"/project-manager/api/users/{service_user_id}/api-tokens",
        json={"name": "Automation"},
    )
    assert issued.status_code == 201, issued.text
    token_value = issued.json()["token"]
    assert token_value.startswith("sipm_pat_")

    auth_client.cookies.clear()
    me = await auth_client.get(
        "/project-manager/api/auth/active-space",
        headers={"Authorization": f"Bearer {token_value}"},
    )
    assert me.status_code == 200, me.text

    bearer_me = await auth_client.get(
        "/project-manager/api/auth/me",
        headers={"Authorization": f"Bearer {token_value}"},
    )
    assert bearer_me.status_code == 200, bearer_me.text
    assert bearer_me.json()["soeid"] == "svcpat1"

    with db_sessionmaker() as session:
        token_rows = session.query(ApiToken).all()
        assert len(token_rows) == 1
        assert token_rows[0].token_hash != token_value
        assert token_rows[0].last_used_at is not None
        first_last_used_at = token_rows[0].last_used_at

    repeat = await auth_client.get(
        "/project-manager/api/auth/active-space",
        headers={"Authorization": f"Bearer {token_value}"},
    )
    assert repeat.status_code == 200, repeat.text

    with db_sessionmaker() as session:
        token_row = session.query(ApiToken).one()
        assert token_row.last_used_at == first_last_used_at


@pytest.mark.anyio
async def test_bearer_api_token_takes_precedence_over_browser_cookie(auth_client, db_sessionmaker):
    await _login_local_session(
        auth_client,
        db_sessionmaker,
        soeid="COOKIEPAT1",
        display_name="Cookie User",
        role="global_admin",
    )
    with db_sessionmaker() as session:
        cookie_user = session.query(User).filter(User.soeid == "cookiepat1").first()
        assert cookie_user is not None
        cookie_user.role = "global_admin"
        service_user = User(
            soeid="svcmixed1",
            email="svcmixed1@citi.com",
            display_name="Service Mixed",
            password_hash=hash_password("ServicePassword123"),
            role="global_admin",
            is_active=True,
            is_service_account=True,
        )
        session.add_all([cookie_user, service_user])
        session.commit()
        service_user_id = service_user.user_id

    issued = await auth_client.post(
        f"/project-manager/api/users/{service_user_id}/api-tokens",
        json={"name": "Mixed credentials"},
    )
    assert issued.status_code == 201, issued.text
    token_value = issued.json()["token"]

    auth_client.cookies.set("access_token", "not-a-valid-cookie-token")
    resp = await auth_client.get(
        "/project-manager/api/auth/me",
        headers={"Authorization": f"Bearer {token_value}"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["soeid"] == "svcmixed1"


@pytest.mark.anyio
async def test_non_sipm_bearer_token_is_rejected_as_api_token(auth_client):
    resp = await auth_client.get(
        "/project-manager/api/auth/me",
        headers={"Authorization": "Bearer eyJnot-a-sipm-token"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API token"


@pytest.mark.anyio
async def test_api_token_lifecycle_requires_service_account_and_rejects_revoked_token(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="ADMINPAT2", display_name="Admin PAT", role="global_admin")
    with db_sessionmaker() as session:
        admin = session.query(User).filter(User.soeid == "adminpat2").first()
        assert admin is not None
        admin.role = "global_admin"
        normal_user = User(
            soeid="normalpat1",
            email="normalpat1@citi.com",
            display_name="Normal PAT",
            password_hash=hash_password("NormalPassword123"),
            role="user",
            is_active=True,
        )
        service_user = User(
            soeid="svcpat2",
            email="svcpat2@citi.com",
            display_name="Service PAT 2",
            password_hash=hash_password("ServicePassword123"),
            role="user",
            is_active=True,
            is_service_account=True,
        )
        session.add_all([admin, normal_user, service_user])
        session.commit()
        normal_user_id = normal_user.user_id
        service_user_id = service_user.user_id

    denied = await auth_client.post(
        f"/project-manager/api/users/{normal_user_id}/api-tokens",
        json={"name": "Denied"},
    )
    assert denied.status_code == 400

    issued = await auth_client.post(
        f"/project-manager/api/users/{service_user_id}/api-tokens",
        json={"name": "Revoke me"},
    )
    assert issued.status_code == 201, issued.text
    body = issued.json()
    listed = await auth_client.get(f"/project-manager/api/users/{service_user_id}/api-tokens")
    assert listed.status_code == 200
    assert "sipm_pat_" not in listed.text
    assert "token_hash" not in listed.text

    revoked = await auth_client.delete(
        f"/project-manager/api/users/{service_user_id}/api-tokens/{body['token_id']}"
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"]

    auth_client.cookies.clear()
    rejected = await auth_client.get(
        "/project-manager/api/auth/active-space",
        headers={"Authorization": f"Bearer {body['token']}"},
    )
    assert rejected.status_code == 401


@pytest.mark.anyio
async def test_refresh_preserves_active_space_selection(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="GA1", display_name="Global Admin")

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
async def test_active_space_accepts_legacy_global_admin_role_format(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="LEGACYGA1", display_name="Legacy Global Admin")

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "legacyga1").first()
        assert user is not None
        user.role = "Global Admin"
        session.add_all(
            [
                user,
                Space(space_id="legacy-space-a", name="Legacy Space A", slug="legacy-space-a", is_active=True),
                Space(space_id="legacy-space-b", name="Legacy Space B", slug="legacy-space-b", is_active=True),
            ]
        )
        session.commit()

    auth_client.cookies.set("active_space_id", "legacy-space-b")

    active_space = await auth_client.get("/project-manager/api/auth/active-space")
    assert active_space.status_code == 200, active_space.text
    payload = active_space.json()
    assert payload["space_id"] == "legacy-space-b"
    assert payload["is_global_admin"] is True


@pytest.mark.anyio
async def test_refresh_rejects_token_issued_before_password_change(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="REVOKE1", display_name="Revoke User")

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
async def test_get_active_space_repairs_missing_active_space_cookie(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="COOKIE1", display_name="Cookie User")

    auth_client.cookies.pop("active_space_id", None)

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    active_space_id = resp.json()["space_id"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(f"active_space_id={active_space_id}" in cookie for cookie in set_cookies)


@pytest.mark.anyio
async def test_get_active_space_repairs_stale_active_space_cookie(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="COOKIE2", display_name="Stale Cookie User")

    auth_client.cookies.set("active_space_id", "stale-space-id")

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    active_space_id = resp.json()["space_id"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(f"active_space_id={active_space_id}" in cookie for cookie in set_cookies)
    assert all("active_space_id=stale-space-id" not in cookie for cookie in set_cookies)


@pytest.mark.anyio
async def test_active_space_reports_usage_analytics_flag(auth_client, db_sessionmaker, monkeypatch):
    monkeypatch.setenv("SIPM_USAGE_ANALYTICS_ENABLED", "true")
    await _login_local_session(auth_client, db_sessionmaker, soeid="ANALYTICSFLAG1", display_name="Flag User")

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    assert resp.json()["usage_analytics_enabled"] is True


@pytest.mark.anyio
async def test_space_scoped_route_rejects_inaccessible_explicit_space_selection(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="SPACEFAIL1", display_name="Space Fail")

    ok = await auth_client.get("/project-manager/api/projects/")
    assert ok.status_code == 200, ok.text

    denied = await auth_client.get(
        "/project-manager/api/projects/",
        headers={"X-Space-Id": "stale-space-id"},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "Space is not accessible"


@pytest.mark.anyio
async def test_require_user_rejects_invalid_or_missing_subject_and_locked_users(auth_client, db_sessionmaker):
    await _login_local_session(auth_client, db_sessionmaker, soeid="AUTH1", display_name="Auth")

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
