from __future__ import annotations

import csv
from datetime import date
from io import StringIO

import pytest


@pytest.mark.anyio
async def test_subcomponents_import_updates_creates_and_exports(client):
    project = (
        await client.post(
            "/api/projects/",
            json={"project_name": "Data Platform", "sponsor": "CFO Office"},
        )
    ).json()
    solution = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Access Controls", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()

    created = (
        await client.post(
            f"/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Task A", "assignee": "Engineer A"},
        )
    ).json()

    buf = StringIO()
    fieldnames = [
        "project_name",
        "solution_name",
        "version",
        "subcomponent_name",
        "status",
        "priority",
        "due_date",
        "assignee",
        "solution_owner",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Access Controls",
            "version": "0.1.0",
            "subcomponent_name": "Task A",
            "status": "complete",
            "priority": "1",
            "due_date": date.today().isoformat(),
            "assignee": "Engineer Updated",
            "solution_owner": "Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Auto Project",
            "solution_name": "Auto Solution",
            "version": "0.1.0",
            "subcomponent_name": "Auto Task",
            "status": "to_do",
            "priority": "3",
            "due_date": "",
            "assignee": "Engineer B",
            "solution_owner": "Auto Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Access Controls",
            "version": "0.1.0",
            "subcomponent_name": "Bad Status",
            "status": "bogus",
            "priority": "3",
            "due_date": "",
            "assignee": "Engineer A",
            "solution_owner": "Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Auto Project",
            "solution_name": "Auto Solution",
            "version": "0.1.0",
            "subcomponent_name": "Auto Task",
            "status": "to_do",
            "priority": "3",
            "due_date": "",
            "assignee": "Engineer B",
            "solution_owner": "Auto Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Access Controls",
            "version": "0.1.0",
            "subcomponent_name": "Missing Assignee",
            "status": "to_do",
            "priority": "3",
            "due_date": "",
            "assignee": "",
            "solution_owner": "Owner",
        }
    )

    resp = await client.post(
        "/api/subcomponents/import",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated"] == 1
    assert data["created"] == 1
    assert data["projects_created"] == 1
    assert data["solutions_created"] == 1
    assert data["total_rows"] == 5
    assert len(data["errors"]) == 3

    updated = await client.get(f"/api/subcomponents/{created['subcomponent_id']}")
    assert updated.status_code == 200
    updated_json = updated.json()
    assert updated_json["status"] == "complete"
    assert updated_json["completed_at"] is not None
    assert updated_json["assignee"] == "Engineer Updated"

    exported = await client.get("/api/subcomponents/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers.get("content-type", "")
    rows = list(csv.DictReader(StringIO(exported.text)))
    assert any(r["subcomponent_name"] == "Task A" and r["assignee"] == "Engineer Updated" for r in rows)
    assert any(r["project_name"] == "Auto Project" and r["subcomponent_name"] == "Auto Task" for r in rows)


@pytest.mark.anyio
async def test_update_subcomponent_sets_completed_at_and_rejects_name_conflict(client):
    project = (
        await client.post(
            "/api/projects/",
            json={"project_name": "Project Subcomponents", "sponsor": "CFO Office"},
        )
    ).json()
    solution = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "S", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()
    a = (
        await client.post(
            f"/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "A", "assignee": "Engineer"},
        )
    ).json()
    b = (
        await client.post(
            f"/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "B", "assignee": "Engineer"},
        )
    ).json()

    complete = await client.patch(f"/api/subcomponents/{b['subcomponent_id']}", json={"status": "complete"})
    assert complete.status_code == 200
    assert complete.json()["completed_at"] is not None

    conflict = await client.patch(
        f"/api/subcomponents/{b['subcomponent_id']}",
        json={"subcomponent_name": a["subcomponent_name"]},
    )
    assert conflict.status_code == 400
    assert conflict.json()["detail"] == "Subcomponent name already exists in this solution"
