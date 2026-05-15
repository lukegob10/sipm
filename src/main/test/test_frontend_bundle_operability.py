from __future__ import annotations

import pytest

import backend.main as main_module


def test_index_uses_unpinned_app_and_stylesheet_entrypoints():
    html_text = (main_module.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'href="styles.css"' in html_text
    assert 'src="js/app.js"' in html_text
    assert "styles.css?v=" not in html_text
    assert "js/app.js?v=" not in html_text


def test_shell_buttons_have_explicit_types():
    html_text = (main_module.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert "<button data-view=" not in html_text
    assert '<button id="logout-btn"' not in html_text
    assert '<button id="theme-toggle"' not in html_text


@pytest.mark.anyio
async def test_frontend_root_returns_503_when_frontend_bundle_is_missing(client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_frontend_bundle_error",
        lambda: "Frontend bundle missing required files: ui/index.html",
    )

    response = await client.get("/project-manager/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Frontend bundle missing required files: ui/index.html",
    }


@pytest.mark.anyio
async def test_readiness_reports_frontend_bundle_failure(client, monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module, "_startup_db_disabled", lambda: True)
    monkeypatch.setattr(
        main_module,
        "_frontend_bundle_error",
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
            "db": {"status": "skipped", "detail": "startup disabled or test mode active"},
        },
    }
