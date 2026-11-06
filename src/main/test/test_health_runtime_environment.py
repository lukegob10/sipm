from __future__ import annotations

import json
import os

import pytest
from fastapi import Request

import backend.main as main
from backend.app import environment


@pytest.mark.parametrize(
    ("encoding", "value"),
    [("utf-8", "caf\u00e9-\u6771\u4eac"), ("utf-8-sig", "dev"), ("utf-8-sig", "caf\u00e9-\u6771\u4eac")],
)
def test_environment_files_preserve_utf8_values_and_first_key(monkeypatch, tmp_path, encoding, value):
    key = "SIPM_HEALTH_ENV_VALUE"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{key}={value}\n", encoding=encoding)
    monkeypatch.setenv(key, "")

    environment._load_env_file(env_file, override_existing=False)

    assert os.environ[key] == value


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_file", ["index.html", "styles.css", "js/app.js"])
async def test_frontend_directories_fail_readiness_and_serving(monkeypatch, tmp_path, invalid_file):
    frontend_dir = tmp_path / "ui"
    required_files = tuple(frontend_dir / name for name in ("index.html", "styles.css", "js/app.js"))
    for path in required_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path == frontend_dir / invalid_file:
            path.mkdir()
        else:
            path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)
    monkeypatch.setattr(main, "FRONTEND_DIR", frontend_dir)
    monkeypatch.setattr(main, "FRONTEND_REQUIRED_FILES", required_files)
    monkeypatch.setattr(main, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main.coordination, "validate_configuration", lambda: "memory")
    monkeypatch.setattr(main.coordination, "check_health", lambda: None)
    monkeypatch.setattr(main, "_startup_db_disabled", lambda: True)
    expected_detail = f"Frontend bundle missing required files: ui/{invalid_file}"

    status_code, payload = main._readiness_payload()

    assert status_code == 503
    assert payload["status"] == "not_ready"
    assert payload["checks"]["frontend"] == {"status": "error", "detail": expected_detail}

    request = Request({"type": "http", "method": "GET", "path": "/project-manager/", "headers": []})
    response = await main._serve_frontend(request)

    assert response.status_code == 503
    assert json.loads(response.body) == {"detail": expected_detail}
