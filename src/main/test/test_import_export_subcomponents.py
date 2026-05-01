from __future__ import annotations

import csv
from datetime import date
from io import StringIO

import pytest

import backend.app.routes.subcomponents as subcomponents_route
from backend.app.models import Project, Solution, Subcomponent
from backend.app.services.smart_cache import clear_cache

@pytest.mark.anyio
async def test_subcomponents_import_updates_creates_and_exports(client):
    project = (
        await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Data Platform", "sponsor": "CFO Office"},
        )
    ).json()
    solution = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Access Controls", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()

    created = (
        await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
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
        "github_repo_url",
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
            "github_repo_url": "https://github.com/example-org/platform-worker.git/",
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
        "/project-manager/api/subcomponents/import",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated"] == 1
    assert data["created"] == 2
    assert data["projects_created"] == 1
    assert data["solutions_created"] == 1
    assert data["total_rows"] == 5
    assert len(data["errors"]) == 2

    updated = await client.get(f"/project-manager/api/subcomponents/{created['subcomponent_id']}")
    assert updated.status_code == 200
    updated_json = updated.json()
    assert updated_json["status"] == "complete"
    assert updated_json["completed_at"] is not None
    assert updated_json["assignee"] == "Engineer Updated"
    assert updated_json["github_repo_url"] == "https://github.com/example-org/platform-worker"
    assert updated_json["effective_github_repo_url"] == "https://github.com/example-org/platform-worker"
    assert updated_json["repo_source"] == "override"

    reopen_buf = StringIO()
    reopen_writer = csv.DictWriter(reopen_buf, fieldnames=fieldnames)
    reopen_writer.writeheader()
    reopen_writer.writerow(
        {
            "project_name": "Data Platform",
            "solution_name": "Access Controls",
            "version": "0.1.0",
            "subcomponent_name": "Task A",
            "status": "in_progress",
            "priority": "1",
            "due_date": date.today().isoformat(),
            "assignee": "Engineer Updated",
            "github_repo_url": "https://github.com/example-org/platform-worker",
            "solution_owner": "Owner",
        }
    )
    reopen_resp = await client.post(
        "/project-manager/api/subcomponents/import",
        content=reopen_buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert reopen_resp.status_code == 200, reopen_resp.text

    reopened = await client.get(f"/project-manager/api/subcomponents/{created['subcomponent_id']}")
    assert reopened.status_code == 200
    reopened_json = reopened.json()
    assert reopened_json["status"] == "in_progress"
    assert reopened_json["completed_at"] is None

    fallback_assignee = await client.get(
        "/project-manager/api/subcomponents",
        params={"assignee_user_soeid": "tu12345"},
    )
    assert fallback_assignee.status_code == 200
    assert [row["subcomponent_name"] for row in fallback_assignee.json()] == ["Missing Assignee"]
    assert fallback_assignee.json()[0]["assignee"] == "Test User"

    exported = await client.get("/project-manager/api/subcomponents/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers.get("content-type", "")
    rows = list(csv.DictReader(StringIO(exported.text)))
    assert any(
        r["subcomponent_name"] == "Task A"
        and r["assignee"] == "Engineer Updated"
        and r["github_repo_url"] == "https://github.com/example-org/platform-worker"
        for r in rows
    )
    assert any(
        r["subcomponent_name"] == "Missing Assignee"
        and r["assignee"] == "Test User"
        and r["assignee_user_soeid"] == "tu12345"
        for r in rows
    )
    assert any(r["project_name"] == "Auto Project" and r["subcomponent_name"] == "Auto Task" for r in rows)


@pytest.mark.anyio
async def test_subcomponents_import_auto_created_parents_refresh_project_solution_and_subcomponent_lists(client):
    clear_cache()
    try:
        primed_projects = await client.get("/project-manager/api/projects/")
        assert primed_projects.status_code == 200, primed_projects.text
        assert primed_projects.json() == []

        primed_solutions = await client.get("/project-manager/api/solutions")
        assert primed_solutions.status_code == 200, primed_solutions.text
        assert primed_solutions.json() == []

        primed_subcomponents = await client.get("/project-manager/api/subcomponents")
        assert primed_subcomponents.status_code == 200, primed_subcomponents.text
        assert primed_subcomponents.json() == []

        csv_text = "\n".join(
            [
                "project_name,solution_name,version,subcomponent_name,status,priority,due_date,assignee,solution_owner",
                "Imported Project,Imported Solution,0.1.0,Imported Task,to_do,3,,Engineer A,Owner",
            ]
        )
        imported = await client.post(
            "/project-manager/api/subcomponents/import",
            content=csv_text.encode("utf-8"),
            headers={"Content-Type": "text/csv"},
        )
        assert imported.status_code == 200, imported.text
        payload = imported.json()
        assert payload["projects_created"] == 1
        assert payload["solutions_created"] == 1
        assert payload["created"] == 1

        projects = await client.get("/project-manager/api/projects/")
        assert projects.status_code == 200, projects.text
        assert [row["project_name"] for row in projects.json()] == ["Imported Project"]

        solutions = await client.get("/project-manager/api/solutions")
        assert solutions.status_code == 200, solutions.text
        assert [row["solution_name"] for row in solutions.json()] == ["Imported Solution"]

        subcomponents = await client.get("/project-manager/api/subcomponents")
        assert subcomponents.status_code == 200, subcomponents.text
        assert [row["subcomponent_name"] for row in subcomponents.json()] == ["Imported Task"]
    finally:
        clear_cache()


@pytest.mark.anyio
async def test_subcomponents_import_auto_created_parents_use_current_user_accountability(client):
    csv_text = "\n".join(
        [
            "project_name,solution_name,version,subcomponent_name,status,priority,due_date,assignee,solution_owner",
            "Current User Project,Current User Workstream,0.1.0,Current User Deliverable,to_do,3,,,",
        ]
    )

    imported = await client.post(
        "/project-manager/api/subcomponents/import",
        content=csv_text.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    assert payload["projects_created"] == 1
    assert payload["solutions_created"] == 1
    assert payload["created"] == 1
    assert payload["errors"] == []

    projects = await client.get("/project-manager/api/projects/")
    assert projects.status_code == 200, projects.text
    project = next(row for row in projects.json() if row["project_name"] == "Current User Project")
    assert project["sponsor"] == "Test User"
    assert project["sponsor_user_soeid"] == "tu12345"

    solutions = await client.get("/project-manager/api/solutions", params={"owner_user_soeid": "tu12345"})
    assert solutions.status_code == 200, solutions.text
    solution = next(row for row in solutions.json() if row["solution_name"] == "Current User Workstream")
    assert solution["owner"] == "Test User"
    assert solution["owner_user_soeid"] == "tu12345"

    subcomponents = await client.get("/project-manager/api/subcomponents", params={"assignee_user_soeid": "tu12345"})
    assert subcomponents.status_code == 200, subcomponents.text
    subcomponent = next(row for row in subcomponents.json() if row["subcomponent_name"] == "Current User Deliverable")
    assert subcomponent["assignee"] == "Test User"
    assert subcomponent["assignee_user_soeid"] == "tu12345"


@pytest.mark.anyio
async def test_update_subcomponent_sets_completed_at_and_rejects_name_conflict(client):
    project = (
        await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Project Subcomponents", "sponsor": "CFO Office"},
        )
    ).json()
    solution = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "S", "version": "0.1.0", "owner": "Owner"},
        )
    ).json()
    a = (
        await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "A", "assignee": "Engineer"},
        )
    ).json()
    b = (
        await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "B", "assignee": "Engineer"},
        )
    ).json()

    complete = await client.patch(f"/project-manager/api/subcomponents/{b['subcomponent_id']}", json={"status": "complete"})
    assert complete.status_code == 200
    assert complete.json()["completed_at"] is not None

    reopened = await client.patch(
        f"/project-manager/api/subcomponents/{b['subcomponent_id']}",
        json={"status": "in_progress"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["completed_at"] is None

    conflict = await client.patch(
        f"/project-manager/api/subcomponents/{b['subcomponent_id']}",
        json={"subcomponent_name": a["subcomponent_name"]},
    )
    assert conflict.status_code == 400
    assert conflict.json()["detail"] == "Subcomponent name already exists in this solution"


@pytest.mark.anyio
async def test_subcomponents_import_rolls_back_auto_created_rows_when_phase_enablement_fails(
    client,
    db_sessionmaker,
    monkeypatch,
):
    def _fail_enable_all_phases(*_args, **_kwargs):
        raise RuntimeError("phase seed failed")

    monkeypatch.setattr(subcomponents_route, "enable_all_phases", _fail_enable_all_phases)

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
            "project_name": "Atomic Subcomponent Project",
            "solution_name": "Atomic Subcomponent Solution",
            "version": "0.1.0",
            "subcomponent_name": "Atomic Subcomponent Task",
            "status": "to_do",
            "priority": "3",
            "due_date": "",
            "assignee": "Engineer",
            "solution_owner": "Owner",
        }
    )

    resp = await client.post(
        "/project-manager/api/subcomponents/import",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["created"] == 0
    assert payload["updated"] == 0
    assert payload["projects_created"] == 0
    assert payload["solutions_created"] == 0
    assert payload["total_rows"] == 1
    assert len(payload["errors"]) == 1
    assert "phase seed failed" in payload["errors"][0]

    with db_sessionmaker() as session:
        assert session.query(Project).filter(Project.project_name == "Atomic Subcomponent Project").count() == 0
        assert session.query(Solution).filter(Solution.solution_name == "Atomic Subcomponent Solution").count() == 0
        assert session.query(Subcomponent).filter(Subcomponent.subcomponent_name == "Atomic Subcomponent Task").count() == 0
