from __future__ import annotations

import logging

import httpx
import pytest

import backend.main as main_module
from backend.main import app as fastapi_app


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
async def test_api_responses_are_not_browser_or_proxy_cached(client):
    response = await client.get("/project-manager/api/projects/")

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("Pragma") == "no-cache"
    assert response.headers.get("Expires") == "0"


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
