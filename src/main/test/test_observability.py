from __future__ import annotations

import json
import logging

import httpx
import pytest
from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import backend.main as main_module
from backend.app.models import User
from backend.main import app as fastapi_app


@pytest.mark.parametrize("detached", [False, True])
def test_request_log_keeps_expired_user_identity_without_database_queries(detached):
    engine = create_engine("sqlite://")
    try:
        User.__table__.create(engine)
        with Session(engine) as session:
            user = User(
                user_id="log-user",
                soeid="loguser",
                email="loguser@example.com",
                display_name="Log User",
                password_hash="synthetic-fixture",
            )
            session.add(user)
            session.commit()  # The request may have committed and expired its user.
            if detached:
                session.expunge(user)

            statements = []
            event.listen(engine, "before_cursor_execute", lambda *args: statements.append(args[2]))
            request = Request({"type": "http", "method": "POST", "path": "/synthetic", "headers": []})
            request.state.user = user

            record = json.loads(main_module._request_log_line(
                request, request_id="log-request", status_code=200, duration_ms=1,
            ))

            assert record["user_id"] == "log-user"
            assert statements == []
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_request_id_is_generated_when_missing(client):
    response = await client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID", "")
    assert request_id
    assert len(request_id) >= 8


@pytest.mark.anyio
async def test_request_id_propagates_when_header_is_sane(client):
    response = await client.get("/health", headers={"X-Request-ID": "req-123.safe"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-123.safe"


@pytest.mark.anyio
async def test_security_headers_are_app_owned_and_frame_compatible(client):
    response = await client.get("/health")

    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "connect-src 'self' ws: wss:" in csp
    assert "frame-ancestors 'self' https:" in csp
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers.get("Permissions-Policy", "")


@pytest.mark.anyio
async def test_readiness_skips_db_check_during_tests(client):
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "auth": {"status": "ok"},
            "coordination": {"status": "ok", "backend": "memory"},
            "frontend": {"status": "ok"},
            "db": {"status": "skipped", "detail": "startup disabled or test mode active"},
        },
    }


@pytest.mark.anyio
async def test_readiness_returns_healthy_when_db_check_passes(client, monkeypatch):
    calls = {"db": 0}

    monkeypatch.setattr(main_module, "_startup_db_disabled", lambda: False)
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module.coordination, "validate_configuration", lambda: "redis")

    def _ok_db_check():
        calls["db"] += 1

    monkeypatch.setattr(main_module, "check_db_connection", _ok_db_check)

    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "auth": {"status": "ok"},
            "coordination": {"status": "ok", "backend": "redis"},
            "frontend": {"status": "ok"},
            "db": {"status": "ok"},
        },
    }
    assert calls == {"db": 1}


@pytest.mark.anyio
async def test_readiness_returns_503_when_db_check_fails(client, monkeypatch):
    monkeypatch.setattr(main_module, "_startup_db_disabled", lambda: False)
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module.coordination, "validate_configuration", lambda: "redis")
    monkeypatch.setattr(main_module, "check_db_connection", lambda: (_ for _ in ()).throw(RuntimeError("db down")))

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "auth": {"status": "ok"},
            "coordination": {"status": "ok", "backend": "redis"},
            "frontend": {"status": "ok"},
            "db": {"status": "error", "detail": "db down"},
        },
    }


@pytest.mark.anyio
async def test_readiness_returns_503_when_coordination_config_fails(client, monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(
        main_module.coordination,
        "validate_configuration",
        lambda: (_ for _ in ()).throw(RuntimeError("redis required")),
    )

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "auth": {"status": "ok"},
            "coordination": {"status": "error", "detail": "redis required"},
            "frontend": {"status": "ok"},
            "db": {"status": "skipped", "detail": "startup disabled or test mode active"},
        },
    }


@pytest.mark.anyio
async def test_readiness_degrades_and_recovers_with_redis_coordination_health(client, monkeypatch):
    coordination_healthy = False

    def check_health() -> None:
        if not coordination_healthy:
            raise RuntimeError("Redis coordination listener is unavailable: redis disconnected")

    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module.coordination, "validate_configuration", lambda: "redis")
    monkeypatch.setattr(main_module.coordination, "check_health", check_health)

    degraded_response = await client.get("/health/ready")

    assert degraded_response.status_code == 503
    assert degraded_response.json()["checks"]["coordination"] == {
        "status": "error",
        "detail": "Redis coordination listener is unavailable: redis disconnected",
    }

    coordination_healthy = True
    recovered_response = await client.get("/health/ready")

    assert recovered_response.status_code == 200
    assert recovered_response.json() == {
        "status": "ok",
        "checks": {
            "auth": {"status": "ok"},
            "coordination": {"status": "ok", "backend": "redis"},
            "frontend": {"status": "ok"},
            "db": {"status": "skipped", "detail": "startup disabled or test mode active"},
        },
    }


@pytest.mark.anyio
async def test_unhandled_exception_logging_includes_request_id_and_redacts_sensitive_headers(client, caplog):
    def _boom():
        raise RuntimeError("boom")

    fastapi_app.add_api_route("/__observability_test__/boom", _boom, methods=["GET"])

    with caplog.at_level(logging.ERROR):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app, raise_app_exceptions=False),
            base_url="http://test",
        ) as error_client:
            response = await error_client.get(
                "/__observability_test__/boom",
                headers={
                    "X-Request-ID": "req-observe-500",
                    "Authorization": "Bearer secret-token",
                    "Cookie": "session=super-secret",
                },
            )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert response.headers["X-Request-ID"] == "req-observe-500"
    assert response.headers["Content-Security-Policy"] == main_module.SECURITY_HEADERS["Content-Security-Policy"]
    assert '"request_id":"req-observe-500"' in caplog.text
    assert '"path":"/__observability_test__/boom"' in caplog.text
    assert '"status":500' in caplog.text
    assert '"error_category":"unhandled_exception"' in caplog.text
    assert "secret-token" not in caplog.text
    assert "session=super-secret" not in caplog.text


@pytest.mark.anyio
async def test_unhandled_exception_preserves_raising_client_behavior(client, caplog):
    def _boom_raise():
        raise RuntimeError("boom-raise")

    fastapi_app.add_api_route("/__observability_test__/boom-raise", _boom_raise, methods=["GET"])

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="boom-raise"):
        await client.get(
            "/__observability_test__/boom-raise",
            headers={
                "X-Request-ID": "req-observe-raise",
                "Authorization": "Bearer secret-token",
                "Cookie": "session=super-secret",
            },
        )

    assert '"request_id":"req-observe-raise"' in caplog.text
    assert '"path":"/__observability_test__/boom-raise"' in caplog.text
    assert '"status":500' in caplog.text
    assert "secret-token" not in caplog.text
    assert "session=super-secret" not in caplog.text
