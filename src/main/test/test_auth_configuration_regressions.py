from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.auth import auth


@pytest.mark.parametrize("secret", ["", " " * 32, "x" * 31, auth.DEFAULT_DEV_SECRET])
def test_non_dev_auth_rejects_missing_or_short_signing_secrets(monkeypatch, secret):
    monkeypatch.setattr(auth, "IS_NON_DEV", True)
    monkeypatch.setattr(auth, "SECRET_KEY", secret)
    monkeypatch.setattr(auth, "SECURE_COOKIES", True)
    monkeypatch.setattr(auth, "ALLOW_SELF_REGISTER", False)

    with pytest.raises(RuntimeError, match="SIPM_SECRET_KEY"):
        auth.validate_auth_configuration()


def test_non_dev_auth_accepts_a_32_byte_signing_secret(monkeypatch):
    monkeypatch.setattr(auth, "IS_NON_DEV", True)
    monkeypatch.setattr(auth, "SECRET_KEY", "x" * 32)
    monkeypatch.setattr(auth, "SECURE_COOKIES", True)
    monkeypatch.setattr(auth, "ALLOW_SELF_REGISTER", False)
    auth.validate_auth_configuration()


def test_dev_auth_keeps_existing_default_secret(monkeypatch):
    monkeypatch.setattr(auth, "IS_NON_DEV", False)
    monkeypatch.setattr(auth, "SECRET_KEY", auth.DEFAULT_DEV_SECRET)
    auth.validate_auth_configuration()


@pytest.mark.parametrize("environment", ["uat", "prod"])
def test_non_dev_auth_rejects_cross_site_cookies(monkeypatch, environment):
    monkeypatch.setattr(auth, "DEPLOYMENT_ENV", environment)
    monkeypatch.setattr(auth, "IS_NON_DEV", True)
    monkeypatch.setattr(auth, "SECRET_KEY", "x" * 32)
    monkeypatch.setattr(auth, "SECURE_COOKIES", True)
    monkeypatch.setattr(auth, "ALLOW_SELF_REGISTER", False)
    monkeypatch.setattr(auth, "COOKIE_SAMESITE", "none")

    with pytest.raises(RuntimeError, match="SIPM_COOKIE_SAMESITE"):
        auth.validate_auth_configuration()


def test_dev_auth_keeps_secure_cross_site_cookie_configuration(monkeypatch):
    monkeypatch.setattr(auth, "IS_NON_DEV", False)
    monkeypatch.setattr(auth, "SECURE_COOKIES", True)
    monkeypatch.setattr(auth, "COOKIE_SAMESITE", "none")
    auth.validate_auth_configuration()


@pytest.mark.parametrize("minutes, warning", [(1, 30), (2, 60), (30, 60)])
def test_session_policy_warning_fits_configured_timeout(minutes, warning):
    env = dict(os.environ, SIPM_SESSION_IDLE_MINUTES=str(minutes))
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from backend.app.routes.auth import session_policy; "
            "print(json.dumps(session_policy().model_dump()))",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    policy = json.loads(result.stdout)
    assert policy["idle_timeout_seconds"] == minutes * 60
    assert policy["warning_seconds"] == warning
    assert 0 < policy["warning_seconds"] < policy["idle_timeout_seconds"]
