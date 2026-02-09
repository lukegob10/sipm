import pytest


@pytest.mark.anyio
async def test_create_allocation_with_fte_months_sets_legacy_fields(client):
    window_resp = await client.post(
        "/api/planning/windows",
        json={"name": "FY26-Q1", "start_date": "2026-01-01", "end_date": "2026-03-31"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    created = await client.post(
        "/api/resource-allocations",
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
        "/api/planning/windows",
        json={"name": "FY26-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    created = await client.post(
        "/api/resource-allocations",
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
async def test_allocations_summary_groups_by_month_and_returns_fte(client):
    window_resp = await client.post(
        "/api/planning/windows",
        json={"name": "FY26-Q3", "start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert window_resp.status_code == 201, window_resp.text
    window_id = window_resp.json()["window_id"]

    first = await client.post(
        "/api/resource-allocations",
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
        "/api/resource-allocations",
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

    summary = await client.get(f"/api/resource-allocations/summary?window_id={window_id}")
    assert summary.status_code == 200, summary.text
    rows = summary.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["month_start"] == "2026-07-01"
    assert row["week_start"] == "2026-07-01"
    assert row["fte_months"] == pytest.approx(0.65, abs=1e-3)
    assert row["hours"] == 104
