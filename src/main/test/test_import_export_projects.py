from __future__ import annotations

import csv
from io import StringIO

import pytest


@pytest.mark.anyio
async def test_projects_import_updates_creates_and_exports(client):
    existing = (
        await client.post(
            "/api/projects/",
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
        "/api/projects/import",
        content=csv_text.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated"] == 1
    assert data["created"] == 1
    assert data["total_rows"] == 5
    assert len(data["errors"]) == 3

    updated = await client.get(f"/api/projects/{existing['project_id']}")
    assert updated.status_code == 200
    assert updated.json()["status"] == "on_hold"
    assert updated.json()["description"] == "Waiting on vendor"
    assert updated.json()["success_criteria"] == "New criteria"

    export = await client.get("/api/projects/export")
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")
    rows = list(csv.DictReader(StringIO(export.text)))
    assert {row["project_name"] for row in rows} == {"Data Platform", "Risk Platform"}

    filtered = await client.get("/api/projects", params={"status_filter": "on_hold"})
    assert filtered.status_code == 200
    assert [p["project_name"] for p in filtered.json()] == ["Data Platform"]

    sponsor_filtered = await client.get("/api/projects", params={"sponsor": "cfo office"})
    assert sponsor_filtered.status_code == 200
    assert [p["project_name"] for p in sponsor_filtered.json()] == ["Data Platform"]


@pytest.mark.anyio
async def test_update_project_rejects_name_conflict(client):
    p1 = (
        await client.post(
            "/api/projects/",
            json={"project_name": "Project A", "sponsor": "Sponsor A"},
        )
    ).json()
    p2 = (
        await client.post(
            "/api/projects/",
            json={"project_name": "Project B", "sponsor": "Sponsor B"},
        )
    ).json()

    resp = await client.patch(f"/api/projects/{p2['project_id']}", json={"project_name": p1["project_name"]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Project name already exists"
