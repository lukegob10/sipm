from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import event

from backend.app import deps as deps_module
from backend.app.auth.auth import hash_password
from backend.app.models import AuthSession, Space, SpaceMembership, User, UserPreference
from backend.app.routes import auth as auth_routes_module
from backend.main import app as fastapi_app


@pytest.fixture
async def login_client(db_sessionmaker):
    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[deps_module.get_db] = get_test_db
    try:
        async with fastapi_app.router.lifespan_context(fastapi_app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=fastapi_app),
                base_url="http://test",
            ) as client:
                yield client
    finally:
        fastapi_app.dependency_overrides.clear()


def _add_member_login(session, *, user_id: str, soeid: str, password: str) -> User:
    user = User(
        user_id=user_id,
        soeid=soeid,
        email=f"{soeid}@example.com",
        display_name=soeid,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
    )
    space = Space(
        space_id=f"{user_id}-space",
        name=f"{soeid} Space",
        slug=f"{user_id}-space",
        is_active=True,
    )
    session.add_all([user, space])
    session.flush()
    session.add(
        SpaceMembership(
            membership_id=f"{user_id}-membership",
            space_id=space.space_id,
            user_id=user.user_id,
            role="member",
            status="active",
        )
    )
    return user


@pytest.mark.anyio
async def test_login_returns_saved_preferences_with_six_sql_statements(
    login_client,
    db_sessionmaker,
):
    with db_sessionmaker() as session:
        user = _add_member_login(
            session,
            user_id="perf-login-user",
            soeid="perflogin1",
            password="Password123",
        )
        session.add(
            UserPreference(
                user_id=user.user_id,
                developer_mode_enabled=True,
                theme="light",
            )
        )
        session.commit()

    engine = db_sessionmaker.kw["bind"]
    metrics = {"sql": 0, "checkout": 0, "commit": 0}

    def count_sql(*_args):
        metrics["sql"] += 1

    def count_checkout(*_args):
        metrics["checkout"] += 1

    def count_commit(*_args):
        metrics["commit"] += 1

    event.listen(engine, "before_cursor_execute", count_sql)
    event.listen(engine.pool, "checkout", count_checkout)
    event.listen(engine, "commit", count_commit)
    try:
        response = await login_client.post(
            "/project-manager/api/auth/login",
            json={"soeid": "PERFLOGIN1", "password": "Password123"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_sql)
        event.remove(engine.pool, "checkout", count_checkout)
        event.remove(engine, "commit", count_commit)

    assert response.status_code == 200, response.text
    assert response.json()["preferences"] == {
        "developer_mode_enabled": True,
        "theme": "light",
        "has_saved_preferences": True,
    }
    assert metrics == {"sql": 6, "checkout": 1, "commit": 1}


@pytest.mark.anyio
async def test_valid_login_clears_an_expired_lockout(
    login_client,
    db_sessionmaker,
):
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    with db_sessionmaker() as session:
        user = _add_member_login(
            session,
            user_id="expired-lockout-user",
            soeid="expiredlockout1",
            password="Password123",
        )
        user.failed_attempts = 5
        user.locked_until = expired_at
        session.commit()

    response = await login_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "EXPIREDLOCKOUT1", "password": "Password123"},
    )

    assert response.status_code == 200, response.text
    response_user = response.json()
    response_last_login_at = datetime.fromisoformat(response_user["last_login_at"])
    response_updated_at = datetime.fromisoformat(response_user["updated_at"])
    with db_sessionmaker() as session:
        user = session.get(User, "expired-lockout-user")
        assert user is not None
        assert user.failed_attempts == 0
        assert user.locked_until is None
        assert user.last_login_at is not None
        assert response_last_login_at.replace(tzinfo=None) == user.last_login_at
        assert response_updated_at.replace(tzinfo=None) == user.updated_at


@pytest.mark.anyio
async def test_login_rejects_service_account_conversion_during_password_check(
    login_client,
    db_sessionmaker,
    monkeypatch,
):
    with db_sessionmaker() as session:
        _add_member_login(
            session,
            user_id="converted-login-race-user",
            soeid="convertedrace1",
            password="Password123",
        )
        session.commit()

    def verify_after_conversion(plain_password, _hashed_password):
        with db_sessionmaker() as conversion_session:
            user = conversion_session.get(User, "converted-login-race-user")
            assert user is not None
            user.is_service_account = True
            conversion_session.commit()
        return plain_password == "Password123"

    monkeypatch.setattr(auth_routes_module, "verify_password", verify_after_conversion)
    response = await login_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "CONVERTEDRACE1", "password": "Password123"},
    )

    assert response.status_code == 403, response.text
    assert response.headers["X-Error-Code"] == "INTERACTIVE_USER_REQUIRED"
    assert response.headers.get_list("set-cookie") == []
    with db_sessionmaker() as session:
        user = session.get(User, "converted-login-race-user")
        assert user is not None
        assert user.is_service_account is True
        assert user.last_login_at is None
        assert session.query(AuthSession).filter_by(user_id=user.user_id).count() == 0


@pytest.mark.anyio
async def test_failed_login_bootstrap_rolls_back_session_and_login_state(
    login_client,
    db_sessionmaker,
):
    with db_sessionmaker() as session:
        session.add(
            User(
                user_id="login-without-space-user",
                soeid="nospaceuser1",
                email="nospaceuser1@example.com",
                display_name="No Space User",
                password_hash=hash_password("Password123"),
                role="user",
                is_active=True,
                failed_attempts=2,
            )
        )
        session.commit()

    response = await login_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": "NOSPACEUSER1", "password": "Password123"},
    )

    assert response.status_code == 403, response.text
    assert response.headers["X-Error-Code"] == "NO_ACTIVE_SPACE"
    assert response.headers.get_list("set-cookie") == []
    with db_sessionmaker() as session:
        user = session.get(User, "login-without-space-user")
        assert user is not None
        assert user.failed_attempts == 2
        assert user.last_login_at is None
        assert session.query(AuthSession).filter_by(user_id=user.user_id).count() == 0
        assert session.query(Space).filter_by(slug="home").count() == 0
