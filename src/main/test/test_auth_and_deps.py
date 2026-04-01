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
from backend.app.auth import proxy_auth as proxy_auth_module
from backend.app.auth.auth import (
    clear_auth_cookies,
    create_token,
    decode_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from backend.app.models import Space, User
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


def _encode_test_token(payload: dict[str, object]) -> str:
    return jwt.encode(payload, auth_module.SECRET_KEY, algorithm=auth_module.ALGORITHM)


def _proxy_headers(soeid: str, *, display_name: str | None = None) -> dict[str, str]:
    config = proxy_auth_module.load_proxy_auth_config()
    headers = {config.soeid_header: soeid}
    if config.name_header and display_name is not None:
        headers[config.name_header] = display_name
    return headers


async def _bootstrap_proxy_session(
    auth_client: httpx.AsyncClient,
    *,
    soeid: str,
    display_name: str | None = None,
):
    response = await auth_client.get(
        "/project-manager/api/auth/me",
        headers=_proxy_headers(soeid, display_name=display_name),
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


@pytest.fixture(autouse=True)
def stable_proxy_auth_env(monkeypatch):
    monkeypatch.setenv("SIPM_PROXY_AUTH_ENABLED", "true")
    monkeypatch.setenv("SIPM_PROXY_AUTH_SOEID_HEADER", "SM_USER")
    monkeypatch.setenv("SIPM_PROXY_AUTH_NAME_HEADER", "name")
    monkeypatch.setenv("SIPM_PROXY_AUTH_DEV_MOCK_ENABLED", "false")


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


def test_proxy_auth_defaults_to_sm_user_and_name_headers():
    config = proxy_auth_module.load_proxy_auth_config()
    assert config.soeid_header == "SM_USER"
    assert config.name_header == "name"


def test_validate_proxy_auth_configuration_rejects_invalid_name_header(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("SIPM_PROXY_AUTH_ENABLED", "true")
        env.setenv("SIPM_PROXY_AUTH_NAME_HEADER", "bad header")
        with pytest.raises(
            RuntimeError,
            match="SIPM_PROXY_AUTH_NAME_HEADER must be a valid HTTP header name.",
        ):
            proxy_auth_module.validate_proxy_auth_configuration()


def test_validate_proxy_auth_configuration_rejects_dev_mock_in_non_dev(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("ENV", "prod")
        env.setenv("SIPM_PROXY_AUTH_ENABLED", "true")
        env.setenv("SIPM_PROXY_AUTH_DEV_MOCK_ENABLED", "true")
        env.setenv("SIPM_PROXY_AUTH_DEV_MOCK_SOEID", "devuser1")
        with pytest.raises(
            RuntimeError,
            match="SIPM_PROXY_AUTH_DEV_MOCK_ENABLED is only allowed in dev/test environments.",
        ):
            proxy_auth_module.validate_proxy_auth_configuration()


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
async def test_proxy_auth_bootstraps_session_sets_cookies_and_blocks_local_auth_routes(auth_client, db_sessionmaker):
    resp = await _bootstrap_proxy_session(
        auth_client,
        soeid="ABC1",
        display_name="Alice Proxy",
    )
    created = resp.json()
    assert created["soeid"] == "abc1"
    assert created["email"] == "abc1@citi.com"
    assert created["display_name"] == "Alice Proxy"

    set_cookies = resp.headers.get_list("set-cookie")
    assert any("access_token=" in cookie for cookie in set_cookies)
    assert any("refresh_token=" in cookie for cookie in set_cookies)
    assert any("active_space_id=" in cookie for cookie in set_cookies)

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "abc1").first()
        assert user is not None
        assert user.email == "abc1@citi.com"
        assert user.external_id == "abc1"

    refresh = await auth_client.post("/project-manager/api/auth/refresh")
    assert refresh.status_code == 200, refresh.text

    logout = await auth_client.post("/project-manager/api/auth/logout")
    assert logout.status_code == 204

    auth_client.cookies.clear()
    me_unauth = await auth_client.get("/project-manager/api/auth/me")
    assert me_unauth.status_code == 401

    for path, payload in [
        ("/project-manager/api/auth/register", {"soeid": "blocked1", "display_name": "Blocked", "password": "Password123"}),
        ("/project-manager/api/auth/login", {"soeid": "blocked1", "password": "Password123"}),
        (
            "/project-manager/api/auth/reset-password",
            {
                "soeid": "blocked1",
                "temp_password": "temp-password",
                "new_password": "Password123",
                "confirm_password": "Password123",
            },
        ),
    ]:
        disabled = await auth_client.post(path, json=payload)
        assert disabled.status_code == 410, disabled.text
        assert disabled.json()["detail"] == "Authentication is managed by the company portal."


@pytest.mark.anyio
async def test_proxy_auth_updates_existing_user_without_overwriting_role(auth_client, db_sessionmaker):
    with db_sessionmaker() as session:
        user = User(
            soeid="ga2",
            email="old-ga2@example.com",
            display_name="Old Admin",
            password_hash=hash_password("OldPassword123"),
            role="global_admin",
            is_active=True,
        )
        session.add(user)
        session.commit()
        user_id = user.user_id

    resp = await _bootstrap_proxy_session(
        auth_client,
        soeid="GA2",
        display_name="Global Admin",
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user_id"] == user_id

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        assert user is not None
        assert user.role == "global_admin"
        assert user.display_name == "Global Admin"
        assert user.email == "ga2@citi.com"


@pytest.mark.anyio
async def test_proxy_auth_falls_back_to_bootstrap_when_access_cookie_is_invalid(auth_client, db_sessionmaker):
    auth_client.cookies.set("access_token", "not-a-token")

    resp = await _bootstrap_proxy_session(
        auth_client,
        soeid="fallback1",
        display_name="Fallback User",
    )
    assert resp.json()["soeid"] == "fallback1"

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "fallback1").first()
        assert user is not None


@pytest.mark.anyio
async def test_refresh_preserves_active_space_selection(auth_client, db_sessionmaker):
    await _bootstrap_proxy_session(auth_client, soeid="GA1", display_name="Global Admin")

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
    await _bootstrap_proxy_session(auth_client, soeid="LEGACYGA1", display_name="Legacy Global Admin")

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
    await _bootstrap_proxy_session(auth_client, soeid="REVOKE1", display_name="Revoke User")

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
    await _bootstrap_proxy_session(auth_client, soeid="COOKIE1", display_name="Cookie User")

    auth_client.cookies.pop("active_space_id", None)

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    active_space_id = resp.json()["space_id"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(f"active_space_id={active_space_id}" in cookie for cookie in set_cookies)


@pytest.mark.anyio
async def test_get_active_space_repairs_stale_active_space_cookie(auth_client):
    await _bootstrap_proxy_session(auth_client, soeid="COOKIE2", display_name="Stale Cookie User")

    auth_client.cookies.set("active_space_id", "stale-space-id")

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    active_space_id = resp.json()["space_id"]
    set_cookies = resp.headers.get_list("set-cookie")
    assert any(f"active_space_id={active_space_id}" in cookie for cookie in set_cookies)
    assert all("active_space_id=stale-space-id" not in cookie for cookie in set_cookies)


@pytest.mark.anyio
async def test_active_space_reports_usage_analytics_flag(auth_client, monkeypatch):
    monkeypatch.setenv("SIPM_USAGE_ANALYTICS_ENABLED", "true")
    await _bootstrap_proxy_session(auth_client, soeid="ANALYTICSFLAG1", display_name="Flag User")

    resp = await auth_client.get("/project-manager/api/auth/active-space")
    assert resp.status_code == 200, resp.text
    assert resp.json()["usage_analytics_enabled"] is True


@pytest.mark.anyio
async def test_space_scoped_route_rejects_inaccessible_explicit_space_selection(auth_client):
    await _bootstrap_proxy_session(auth_client, soeid="SPACEFAIL1", display_name="Space Fail")

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
    await _bootstrap_proxy_session(auth_client, soeid="AUTH1", display_name="Auth")

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
