import logging

import pytest

import backend.main as main


@pytest.mark.anyio
@pytest.mark.parametrize("failed_check", ["db", "coordination_config", "coordination_health"])
async def test_readiness_does_not_expose_failure_secrets(client, monkeypatch, caplog, failed_check):
    secret = "synthetic-password-DO-NOT-EXPOSE"

    def fail():
        raise RuntimeError(f"connection refused with password={secret}")

    monkeypatch.setattr(main, "_startup_db_disabled", lambda: False)
    monkeypatch.setattr(main, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main.coordination, "validate_configuration", fail if failed_check == "coordination_config" else lambda: "redis")
    monkeypatch.setattr(main.coordination, "check_health", fail if failed_check == "coordination_health" else lambda: None)
    monkeypatch.setattr(main, "check_db_connection", fail if failed_check == "db" else lambda: None)

    with caplog.at_level(logging.WARNING, logger=main.__name__):
        response = await client.get("/health/ready")

    label = "Database" if failed_check == "db" else "Coordination"
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    check_name = "db" if failed_check == "db" else "coordination"
    assert response.json()["checks"][check_name] == {
        "status": "error", "detail": f"{label} readiness check failed",
    }
    assert secret not in response.text
    assert secret not in caplog.text
    assert f"{label} readiness check failed (RuntimeError)" in caplog.text


@pytest.mark.anyio
async def test_readiness_keeps_actionable_auth_configuration_detail(client, monkeypatch):
    def fail():
        raise RuntimeError("SIPM_ALLOW_SELF_REGISTER must be false in non-dev environments.")

    monkeypatch.setattr(main, "validate_auth_configuration", fail)
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["auth"] == {
        "status": "error",
        "detail": "SIPM_ALLOW_SELF_REGISTER must be false in non-dev environments.",
    }
