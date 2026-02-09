from __future__ import annotations

import csv
from io import StringIO

import pytest

from backend.app.models import Phase


async def create_project(client, name: str = "Data Platform"):
    resp = await client.post(
        "/api/projects/",
        json={
            "project_name": name,
            "description": "Modernize data stack",
            "sponsor": "CFO Office",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def seed_minimal_phases(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Phase(phase_id="backlog", phase_group="Backlog", phase_name="Backlog", sequence=1),
                Phase(phase_id="requirements", phase_group="Planning", phase_name="Requirements", sequence=2),
            ]
        )
        session.commit()


@pytest.mark.anyio
async def test_solutions_import_updates_creates_and_exports(client, db_sessionmaker):
    seed_minimal_phases(db_sessionmaker)

    project = await create_project(client)

    sol_phase = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Update Phase", "version": "0.1.0", "status": "active", "owner": "Owner"},
        )
    ).json()
    sol_complete = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Mark Complete", "version": "0.1.0", "status": "active", "owner": "Owner"},
        )
    ).json()

    fieldnames = [
        "project_name",
        "solution_name",
        "version",
        "status",
        "rag_status",
        "rag_reason",
        "priority",
        "due_date",
        "planned_start_date",
        "current_phase",
        "description",
        "success_criteria",
        "impact_confidence",
        "owner",
        "assignee",
        "approver",
        "key_stakeholder",
        "blockers",
        "risks",
    ]
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Update Phase",
            "version": "0.1.0",
            "status": "active",
            "priority": "2",
            "current_phase": "requirements",
            "description": "Desc",
            "owner": "Owner",
            "assignee": "Assignee",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Mark Complete",
            "version": "0.1.0",
            "status": "complete",
            "priority": "3",
            "current_phase": "",
            "owner": "Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Manual RAG",
            "version": "0.1.0",
            "status": "active",
            "rag_status": "green",
            "rag_reason": "Escalation approved",
            "priority": "3",
            "current_phase": "requirements",
            "owner": "Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Auto Project",
            "solution_name": "Auto Solution",
            "version": "0.1.0",
            "status": "not_started",
            "priority": "3",
            "owner": "Auto Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Bad Impact Confidence",
            "version": "0.1.0",
            "status": "active",
            "priority": "3",
            "impact_confidence": "bogus",
            "owner": "Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Bad Phase",
            "version": "0.1.0",
            "status": "active",
            "priority": "3",
            "current_phase": "does_not_exist",
            "owner": "Owner",
        }
    )
    writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Missing Owner",
            "version": "0.1.0",
            "status": "active",
            "priority": "3",
            "owner": "",
        }
    )

    resp = await client.post(
        "/api/solutions/import",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated"] == 2
    assert data["created"] == 2
    assert data["projects_created"] == 1
    assert data["total_rows"] == 7
    assert len(data["errors"]) == 3

    updated_phase = (await client.get(f"/api/solutions/{sol_phase['solution_id']}")).json()
    assert updated_phase["current_phase"] == "requirements"
    assert updated_phase["priority"] == 2

    updated_complete = (await client.get(f"/api/solutions/{sol_complete['solution_id']}")).json()
    assert updated_complete["status"] == "complete"
    assert updated_complete["completed_at"] is not None
    assert updated_complete["current_phase"] == "requirements"

    exported = await client.get("/api/solutions/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers.get("content-type", "")
    rows = list(csv.DictReader(StringIO(exported.text)))
    assert any(r["solution_name"] == "Manual RAG" for r in rows)
    assert any(r["project_name"] == "Auto Project" for r in rows)

    list_complete = await client.get("/api/solutions", params={"status": "complete"})
    assert list_complete.status_code == 200
    assert [s["solution_name"] for s in list_complete.json()] == ["Mark Complete"]


@pytest.mark.anyio
async def test_create_solution_rejects_unknown_project_and_current_phase(client, db_sessionmaker):
    seed_minimal_phases(db_sessionmaker)

    missing_project = await client.get("/api/projects/does-not-exist/solutions")
    assert missing_project.status_code == 404
    assert missing_project.json()["detail"] == "Project not found"

    project = await create_project(client)
    bad_phase = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "S",
            "version": "0.1.0",
            "status": "active",
            "owner": "Owner",
            "current_phase": "does_not_exist",
        },
    )
    assert bad_phase.status_code == 400
    assert "current_phase" in bad_phase.json()["detail"]


@pytest.mark.anyio
async def test_create_solution_accepts_rag_reason(client):
    project = await create_project(client)

    created = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Manual Reason",
            "version": "0.1.0",
            "status": "active",
            "rag_reason": "Because",
            "owner": "Owner",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["rag_reason"] == "Because"
    assert body["rag_status"] == "green"


@pytest.mark.anyio
async def test_update_solution_sets_manual_when_rag_fields_provided_without_source(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "S", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()

    resp = await client.patch(
        f"/api/solutions/{created['solution_id']}",
        json={"rag_status": "green", "rag_reason": "Approved"},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["rag_status"] == "green"
    assert updated["rag_reason"] == "Approved"


@pytest.mark.anyio
async def test_update_solution_allows_empty_patch(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "S", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()

    resp = await client.patch(
        f"/api/solutions/{created['solution_id']}",
        json={},
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_update_solution_rejects_name_version_conflict(client):
    project = await create_project(client)
    s1 = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "A", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()
    s2 = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "B", "version": "0.2.0", "owner": "Owner"},
        )
    ).json()

    resp = await client.patch(
        f"/api/solutions/{s2['solution_id']}",
        json={"solution_name": s1["solution_name"], "version": s1["version"]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Solution name and version already exist for this project"


@pytest.mark.anyio
async def test_solution_auto_rag_marks_abandoned_as_red(client):
    project = await create_project(client)
    created = (
        await client.post(
            f"/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Abandoned", "version": "0.1.0", "status": "abandoned", "owner": "Owner"},
        )
    ).json()
    assert created["rag_status"] == "green"
