from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_root_redirects_to_project_manager_context(client):
    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/project-manager/"


@pytest.mark.anyio
async def test_project_manager_context_serves_spa_shell(client):
    response = await client.get("/project-manager/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "SIPM" in response.text


@pytest.mark.anyio
async def test_project_manager_context_redirects_without_trailing_slash(client):
    response = await client.get("/project-manager", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/project-manager/"


@pytest.mark.anyio
async def test_reset_password_page_lives_under_project_manager_context(client):
    response = await client.get("/project-manager/reset-password")
    assert response.status_code == 200
    assert "Reset Password" in response.text


@pytest.mark.anyio
async def test_named_view_deep_link_serves_spa_shell(client):
    response = await client.get("/project-manager/planning")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "SIPM" in response.text


@pytest.mark.anyio
async def test_named_view_trailing_slash_redirects_to_canonical_path(client):
    response = await client.get("/project-manager/planning/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/project-manager/planning"


@pytest.mark.anyio
async def test_unknown_spa_path_still_serves_shell_for_client_side_fallback(client):
    response = await client.get("/project-manager/not-a-real-view")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "SIPM" in response.text


@pytest.mark.anyio
async def test_health_remains_at_root(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
