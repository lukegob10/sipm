from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from backend.app.models import ApiToken, User
from backend.app.services import api_tokens


@pytest.fixture
def api_token_state(db_sessionmaker, monkeypatch):
    now = datetime(2026, 11, 6, 15)
    raw_token = "sipm_pat_health-auth-sessions"
    monkeypatch.setattr(api_tokens, "_utc_now_naive", lambda: now)
    with db_sessionmaker() as session:
        session.add(User(
            user_id="health-token-user",
            soeid="health-token-user",
            email="health-token-user@example.com",
            display_name="Token User",
            password_hash="unused",
            is_active=True,
        ))
        session.flush()
        session.add(ApiToken(
            token_id="health-token",
            user_id="health-token-user",
            name="Health review",
            token_hash=api_tokens.hash_api_token(raw_token),
            created_by_user_id="health-token-user",
            last_used_at=now - timedelta(seconds=1),
        ))
        session.commit()
    return now, raw_token


def test_recent_api_token_authentication_uses_one_read_without_writing(
    db_sessionmaker, api_token_state,
):
    _, raw_token = api_token_state
    engine = db_sessionmaker.kw["bind"]
    statements = []
    commits = []

    def capture_statement(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement.lstrip().split(None, 1)[0].upper())

    def capture_commit(_conn):
        commits.append(True)

    with db_sessionmaker() as session:
        event.listen(engine, "before_cursor_execute", capture_statement)
        event.listen(engine, "commit", capture_commit)
        try:
            user = api_tokens.authenticate_api_token(session, raw_token)
            assert user.user_id == "health-token-user"
            assert user.is_active is True
        finally:
            event.remove(engine, "before_cursor_execute", capture_statement)
            event.remove(engine, "commit", capture_commit)

    assert statements == ["SELECT"]
    assert commits == []


@pytest.mark.parametrize(
    ("last_used_offset", "expect_update"),
    [
        (None, True),
        (-api_tokens.LAST_USED_WRITE_INTERVAL, True),
        (-api_tokens.LAST_USED_WRITE_INTERVAL + timedelta(microseconds=1), False),
    ],
)
def test_api_token_lookup_preserves_last_used_write_throttle(
    db_sessionmaker, api_token_state, last_used_offset, expect_update,
):
    now, raw_token = api_token_state
    original_last_used = None if last_used_offset is None else now + last_used_offset
    with db_sessionmaker() as session:
        token = session.get(ApiToken, "health-token")
        token.last_used_at = original_last_used
        session.commit()

    with db_sessionmaker() as session:
        user = api_tokens.authenticate_api_token(session, raw_token)
        assert user.user_id == "health-token-user"

    with db_sessionmaker() as session:
        token = session.get(ApiToken, "health-token")
        assert token.last_used_at == (now if expect_update else original_last_used)


@pytest.mark.parametrize(
    ("token_state", "user_active", "expected_error"),
    [
        ("missing", True, "API_TOKEN_INVALID"),
        ("expired", True, "API_TOKEN_INVALID"),
        ("revoked", True, "API_TOKEN_INVALID"),
        ("expired", False, "API_TOKEN_INVALID"),
        ("revoked", False, "API_TOKEN_INVALID"),
        ("active", False, "API_TOKEN_USER_INVALID"),
    ],
)
def test_api_token_lookup_preserves_rejection_codes_and_last_used(
    db_sessionmaker, api_token_state, token_state, user_active, expected_error,
):
    now, raw_token = api_token_state
    with db_sessionmaker() as session:
        user = session.get(User, "health-token-user")
        user.is_active = user_active
        token = session.get(ApiToken, "health-token")
        original_last_used = token.last_used_at
        if token_state == "missing":
            session.delete(token)
        elif token_state == "expired":
            token.expires_at = now
        elif token_state == "revoked":
            token.revoked_at = now
        session.commit()

    with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as exc_info:
            api_tokens.authenticate_api_token(session, raw_token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.headers["X-Error-Code"] == expected_error

    if token_state != "missing":
        with db_sessionmaker() as session:
            assert session.get(ApiToken, "health-token").last_used_at == original_last_used


def test_api_token_for_missing_user_keeps_specific_rejection(
    db_sessionmaker, api_token_state,
):
    _, raw_token = api_token_state
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("The orphaned-token case requires SQLite's disabled foreign keys")
    with db_sessionmaker() as session:
        session.delete(session.get(User, "health-token-user"))
        session.commit()

    with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as exc_info:
            api_tokens.authenticate_api_token(session, raw_token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.headers["X-Error-Code"] == "API_TOKEN_USER_INVALID"
