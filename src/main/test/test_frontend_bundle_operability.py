from __future__ import annotations

import pytest

from backend.app import config as config_module
from backend.app import frontend as frontend_module
from backend.app import health as health_module


def test_index_uses_unpinned_app_and_stylesheet_entrypoints():
    html_text = (config_module.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'href="styles.css"' in html_text
    assert 'src="js/app.js"' in html_text
    assert "styles.css?v=" not in html_text
    assert "js/app.js?v=" not in html_text


def test_shell_buttons_have_explicit_types():
    html_text = (config_module.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert "<button data-view=" not in html_text
    assert '<button id="logout-btn"' not in html_text
    assert '<button id="theme-toggle"' not in html_text


def test_frontend_bundle_error_accepts_explicit_bundle_paths(tmp_path):
    base_dir = tmp_path / "app"
    frontend_dir = base_dir / "ui"
    js_dir = frontend_dir / "js"
    js_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    required_files = (
        frontend_dir / "index.html",
        frontend_dir / "styles.css",
        js_dir / "app.js",
    )

    assert frontend_module.frontend_bundle_error(
        base_dir=base_dir, required_files=required_files
    ) == ("Frontend bundle missing required files: ui/styles.css, ui/js/app.js")


def test_frontend_server_uses_explicit_paths(tmp_path):
    base_dir = tmp_path / "app"
    frontend_dir = base_dir / "ui"
    frontend_dir.mkdir(parents=True)
    required_files = (frontend_dir / "index.html",)

    server = frontend_module.FrontendServer(
        base_dir=base_dir,
        frontend_dir=frontend_dir,
        required_files=required_files,
    )

    assert server.base_dir == base_dir
    assert server.frontend_dir == frontend_dir
    assert server.required_files == required_files


@pytest.mark.anyio
async def test_frontend_root_returns_503_when_frontend_bundle_is_missing(
    client, monkeypatch
):
    monkeypatch.setattr(
        frontend_module,
        "frontend_bundle_error",
        lambda: "Frontend bundle missing required files: ui/index.html",
    )

    response = await client.get("/project-manager/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Frontend bundle missing required files: ui/index.html",
    }


@pytest.mark.anyio
async def test_readiness_reports_frontend_bundle_failure(client, monkeypatch):
    monkeypatch.setattr(health_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(health_module, "startup_db_disabled", lambda: True)
    monkeypatch.setattr(
        health_module,
        "frontend_bundle_error",
        lambda: "Frontend bundle missing required files: ui/index.html",
    )

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "auth": {"status": "ok"},
            "coordination": {"status": "ok", "backend": "memory"},
            "frontend": {
                "status": "error",
                "detail": "Frontend bundle missing required files: ui/index.html",
            },
            "db": {"status": "skipped", "detail": "startup disabled"},
        },
    }
