from __future__ import annotations

import csv
from io import StringIO

import pytest

from backend.main import app as fastapi_app
from backend.app import deps as deps_module
from backend.app.services.spaces import SpaceContext


@pytest.mark.anyio
async def test_projects_import_updates_creates_and_exports(client):
    existing = (
        await client.post(
            "/project-manager/api/projects/",
            json={
                "project_name": "Data Platform",
                "status": "active",
                "description": "Modernize data stack",
                "success_criteria": "Reduce run time by 30%",
                "sponsor": "CFO Office",
            },
        )
    ).json()

    csv_text = "\n".join(
        [
            "project_name,status,description,success_criteria,sponsor,sponsor_user_soeid,strategic_objective,priority",
            # Update existing (status normalization accepts spaces/underscores/case).
            "Data Platform,On Hold,Waiting on vendor,New criteria,CFO Office,,,",
            # Create new.
            "Risk Platform,active,Own risk controls,,COO Office,,,",
            # Missing sponsor => row error.
            "No Sponsor,active,Desc,,,,,",
            # Duplicate project_name in same CSV => row error.
            "Risk Platform,active,Duplicate row,,COO Office,,,",
            # Invalid status => row error.
            "Bad Status,not a status,Desc,,Someone,,,",
            "",
        ]
    )

    resp = await client.post(
        "/project-manager/api/projects/import",
        content=csv_text.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated"] == 1
    assert data["created"] == 1
    assert data["total_rows"] == 5
    assert len(data["errors"]) == 3

    updated = await client.get(f"/project-manager/api/projects/{existing['project_id']}")
    assert updated.status_code == 200
    assert updated.json()["status"] == "on_hold"
    assert updated.json()["description"] == "Waiting on vendor"
    assert updated.json()["success_criteria"] == "New criteria"

    export = await client.get("/project-manager/api/projects/export")
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")
    rows = list(csv.DictReader(StringIO(export.text)))
    assert {row["project_name"] for row in rows} == {"Data Platform", "Risk Platform"}

    filtered = await client.get("/project-manager/api/projects", params={"status_filter": "on_hold"})
    assert filtered.status_code == 200
    assert [p["project_name"] for p in filtered.json()] == ["Data Platform"]

    sponsor_filtered = await client.get("/project-manager/api/projects", params={"sponsor": "cfo office"})
    assert sponsor_filtered.status_code == 200
    assert [p["project_name"] for p in sponsor_filtered.json()] == ["Data Platform"]


@pytest.mark.anyio
async def test_projects_export_is_scoped_to_active_space(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-project-export-a",
            space_name="Project Export A",
            is_global_admin=False,
            space_role="space_admin",
        )
        create_a = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Export Scope Project A", "sponsor": "Sponsor A"},
        )
        assert create_a.status_code == 201, create_a.text

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-project-export-b",
            space_name="Project Export B",
            is_global_admin=False,
            space_role="space_admin",
        )
        create_b = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Export Scope Project B", "sponsor": "Sponsor B"},
        )
        assert create_b.status_code == 201, create_b.text

        export_b = await client.get("/project-manager/api/projects/export")
        assert export_b.status_code == 200, export_b.text
        rows_b = list(csv.DictReader(StringIO(export_b.text)))
        assert {row["project_name"] for row in rows_b} == {"Export Scope Project B"}

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-project-export-a",
            space_name="Project Export A",
            is_global_admin=False,
            space_role="space_admin",
        )
        export_a = await client.get("/project-manager/api/projects/export")
        assert export_a.status_code == 200, export_a.text
        rows_a = list(csv.DictReader(StringIO(export_a.text)))
        assert {row["project_name"] for row in rows_a} == {"Export Scope Project A"}
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


@pytest.mark.anyio
async def test_update_project_rejects_name_conflict(client):
    p1 = (
        await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Project A", "sponsor": "Sponsor A"},
        )
    ).json()
    p2 = (
        await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Project B", "sponsor": "Sponsor B"},
        )
    ).json()

    resp = await client.patch(f"/project-manager/api/projects/{p2['project_id']}", json={"project_name": p1["project_name"]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Project name already exists"
