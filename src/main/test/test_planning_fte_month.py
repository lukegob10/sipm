import csv
from io import StringIO

import pytest


@pytest.mark.anyio
async def test_create_allocation_with_fte_months_sets_legacy_fields(client):
    window_resp = await client.post(
        "/project-manager/api/planning/windows",
        json={"name": "FY26-Q1", "start_date": "2026-01-01", "end_date": "2026-03-31"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    created = await client.post(
        "/project-manager/api/resource-allocations",
        json={
            "work_item_type": "solution",
            "work_item_id": "sol-1",
            "assignee": "Test User",
            "assignee_user_soeid": "tu12345",
            "month_start": "2026-03-01",
            "fte_months": 0.5,
            "window_id": window_id,
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["month_start"] == "2026-03-01"
    assert payload["week_start"] == "2026-03-01"
    assert payload["fte_months"] == pytest.approx(0.5, abs=1e-6)
    assert payload["hours"] == 80


@pytest.mark.anyio
async def test_create_allocation_legacy_hours_backfills_fte_months(client):
    window_resp = await client.post(
        "/project-manager/api/planning/windows",
        json={"name": "FY26-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    created = await client.post(
        "/project-manager/api/resource-allocations",
        json={
            "work_item_type": "subcomponent",
            "work_item_id": "task-1",
            "assignee": "Test User",
            "assignee_user_soeid": "tu12345",
            "week_start": "2026-04-15",
            "hours": 40,
            "window_id": window_id,
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["week_start"] == "2026-04-15"
    assert payload["month_start"] == "2026-04-01"
    assert payload["fte_months"] == pytest.approx(0.25, abs=1e-6)
    assert payload["hours"] == 40


@pytest.mark.anyio
async def test_create_allocation_without_assignee_soeid_keeps_identity_field_empty(client):
    window_resp = await client.post(
        "/project-manager/api/planning/windows",
        json={"name": "FY26-Q2B", "start_date": "2026-04-01", "end_date": "2026-06-30"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    created = await client.post(
        "/project-manager/api/resource-allocations",
        json={
            "work_item_type": "solution",
            "work_item_id": "sol-no-soeid",
            "assignee": "Display Name Only",
            "month_start": "2026-05-01",
            "fte_months": 0.25,
            "window_id": window_id,
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["assignee"] == "Display Name Only"
    assert payload["assignee_user_soeid"] is None

    listed = await client.get("/project-manager/api/resource-allocations")
    assert listed.status_code == 200, listed.text
    created_row = next((row for row in listed.json() if row["allocation_id"] == payload["allocation_id"]), None)
    assert created_row is not None
    assert created_row["assignee"] == "Display Name Only"
    assert created_row["assignee_user_soeid"] is None


@pytest.mark.anyio
async def test_allocations_summary_groups_by_month_and_returns_fte(client):
    window_resp = await client.post(
        "/project-manager/api/planning/windows",
        json={"name": "FY26-Q3", "start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    first = await client.post(
        "/project-manager/api/resource-allocations",
        json={
            "work_item_type": "solution",
            "work_item_id": "sol-a",
            "assignee": "Test User",
            "assignee_user_soeid": "tu12345",
            "month_start": "2026-07-01",
            "fte_months": 0.35,
            "window_id": window_id,
        },
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/project-manager/api/resource-allocations",
        json={
            "work_item_type": "subcomponent",
            "work_item_id": "task-b",
            "assignee": "Test User",
            "assignee_user_soeid": "tu12345",
            "week_start": "2026-07-20",
            "hours": 48,
            "window_id": window_id,
        },
    )
    assert second.status_code == 201, second.text

    summary = await client.get(f"/project-manager/api/resource-allocations/summary?window_id={window_id}")
    assert summary.status_code == 200, summary.text
    rows = summary.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["month_start"] == "2026-07-01"
    assert row["week_start"] == "2026-07-01"
    assert row["fte_months"] == pytest.approx(0.65, abs=1e-3)
    assert row["hours"] == 104


@pytest.mark.anyio
async def test_planning_windows_csv_import_export_updates_by_name(client):
    created = await client.post(
        "/project-manager/api/planning/windows",
        json={"name": "FY26 Migration", "start_date": "2026-01-01", "end_date": "2026-03-31"},
    )
    assert created.status_code == 201, created.text

    exported = await client.get("/project-manager/api/planning/windows/export")
    assert exported.status_code == 200, exported.text
    rows = list(csv.DictReader(StringIO(exported.text)))
    row = next(row for row in rows if row["window_name"] == "FY26 Migration")
    row["end_date"] = "2026-04-30"
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=["window_name", "start_date", "end_date"])
    writer.writeheader()
    writer.writerow(row)

    dry_run = await client.post(
        "/project-manager/api/planning/windows/import?dry_run=true",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert dry_run.status_code == 200, dry_run.text
    assert dry_run.json()["updated"] == 1
    assert dry_run.json()["dry_run"] is True

    imported = await client.post(
        "/project-manager/api/planning/windows/import",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["updated"] == 1

    listed = await client.get("/project-manager/api/planning/windows")
    assert listed.status_code == 200, listed.text
    updated = next(row for row in listed.json() if row["name"] == "FY26 Migration")
    assert updated["end_date"] == "2026-04-30"


@pytest.mark.anyio
async def test_resource_allocations_csv_import_resolves_natural_work_item_keys(client):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": "Allocation Project"})
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["project_id"]
    solution_resp = await client.post(
        f"/project-manager/api/projects/{project_id}/solutions",
        json={"solution_name": "Allocation Solution", "version": "1.0.0"},
    )
    assert solution_resp.status_code == 201, solution_resp.text
    solution_id = solution_resp.json()["solution_id"]
    subcomponent_resp = await client.post(
        f"/project-manager/api/solutions/{solution_id}/subcomponents",
        json={"subcomponent_name": "Allocation Task", "estimate_hours": 80},
    )
    assert subcomponent_resp.status_code == 201, subcomponent_resp.text

    window_resp = await client.post(
        "/project-manager/api/planning/windows",
        json={"name": "Allocation Window", "start_date": "2026-05-01", "end_date": "2026-05-31"},
    )
    assert window_resp.status_code == 201, window_resp.text
    team_resp = await client.post("/project-manager/api/planning/work-allocation/teams", json={"name": "Allocation Team"})
    assert team_resp.status_code == 201, team_resp.text

    buf = StringIO()
    fieldnames = [
        "work_item_type",
        "work_item_id",
        "project_name",
        "solution_name",
        "version",
        "subcomponent_name",
        "assignee",
        "assignee_user_soeid",
        "team_name",
        "month_start",
        "fte_months",
        "hours",
        "window_name",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(
        {
            "work_item_type": "subcomponent",
            "project_name": "Allocation Project",
            "solution_name": "Allocation Solution",
            "version": "1.0.0",
            "subcomponent_name": "Allocation Task",
            "team_name": "Allocation Team",
            "month_start": "2026-05-01",
            "fte_months": "0.5",
            "window_name": "Allocation Window",
        }
    )

    imported = await client.post(
        "/project-manager/api/resource-allocations/import",
        content=buf.getvalue().encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 1

    exported = await client.get("/project-manager/api/resource-allocations/export")
    assert exported.status_code == 200, exported.text
    rows = list(csv.DictReader(StringIO(exported.text)))
    row = next(row for row in rows if row["subcomponent_name"] == "Allocation Task")
    assert row["project_name"] == "Allocation Project"
    assert row["solution_name"] == "Allocation Solution"
    assert row["team_name"] == "Allocation Team"
    assert row["window_name"] == "Allocation Window"
    assert row["fte_months"] == "0.5"
