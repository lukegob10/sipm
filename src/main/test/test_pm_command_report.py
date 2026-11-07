from datetime import date

import pytest

from backend.app.services.pm_command_report_pdf import build_pm_command_report_pdf
from backend.app.services import pm_command_report_pdf


def test_build_pm_command_report_pdf_highlights_current_issues():
    pdf_bytes = build_pm_command_report_pdf(
        space_name="Leadership Space",
        today=date(2026, 7, 7),
        projects=[
            {"project_id": "project-1", "project_name": "Customer Migration"},
        ],
        solutions=[
            {
                "solution_id": "solution-1",
                "project_id": "project-1",
                "solution_name": "Cutover Workstream",
                "status": "active",
                "rag_status": "red",
                "due_date": date(2026, 7, 1),
                "owner": "Delivery Lead",
                "blockers": "Vendor access",
                "risks": "Environment instability",
            }
        ],
        tasks=[
            {
                "task_id": "task-1",
                "project_id": "project-1",
                "solution_id": "solution-1",
                "task_name": "Resolve Access Blocker",
                "status": "in_progress",
                "due_date": date(2026, 7, 2),
                "assignee": "Engineer One",
                "blocked": True,
            }
        ],
        users=[],
        allocations=[],
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert b"PM Command Center Report" in pdf_bytes
    assert b"Customer Migration" in pdf_bytes
    assert b"Cutover Workstream" in pdf_bytes
    assert b"Overdue Items" in pdf_bytes
    assert b"Watch Items" in pdf_bytes
    assert b"Engineer One" in pdf_bytes
    assert b"Delivery Lead" in pdf_bytes
    assert b"RAG red" in pdf_bytes
    assert b"Blocked deliverables" in pdf_bytes


def test_distinct_versions_with_the_same_name_remain_distinct_watch_items(monkeypatch):
    cards = {}
    monkeypatch.setattr(
        pm_command_report_pdf, "_draw_report_card", lambda _painter, **card: cards.update({card["title"]: card["value"]})
    )
    build_pm_command_report_pdf(
        space_name="Space",
        today=date(2026, 7, 7),
        projects=[{"project_id": "project", "project_name": "Project"}],
        solutions=[
            {"solution_id": "first", "project_id": "project", "solution_name": "Workstream", "rag_status": "red"},
            {"solution_id": "second", "project_id": "project", "solution_name": "Workstream", "rag_status": "red"},
        ],
        tasks=[], users=[], allocations=[],
    )
    assert cards["Watch Items"] == "2"


def test_report_builder_excludes_task_with_mismatched_parent(monkeypatch):
    cards = {}
    monkeypatch.setattr(
        pm_command_report_pdf, "_draw_report_card", lambda _painter, **card: cards.update({card["title"]: card["value"]})
    )
    build_pm_command_report_pdf(
        space_name="Space",
        today=date(2026, 7, 7),
        projects=[{"project_id": "p1"}, {"project_id": "p2"}],
        solutions=[{"solution_id": "s1", "project_id": "p1"}],
        tasks=[
            {"task_id": "valid", "project_id": "p1", "solution_id": "s1"},
            {"task_id": "mismatch", "project_id": "p2", "solution_id": "s1"},
        ],
        users=[], allocations=[],
    )
    assert cards["Open Deliverables"] == "1"


def test_report_health_rounds_half_points_like_dashboard(monkeypatch):
    cards = {}
    monkeypatch.setattr(
        pm_command_report_pdf, "_draw_report_card", lambda _painter, **card: cards.update({card["title"]: card["value"]})
    )
    build_pm_command_report_pdf(
        space_name="Space", today=date(2026, 7, 7),
        projects=[{"project_id": "p1"}],
        solutions=[{"solution_id": "s1", "project_id": "p1", "status": "complete"}],
        tasks=[{"task_id": str(index), "project_id": "p1", "solution_id": "s1", "assignee": "Owner" if index == 0 else ""}
               for index in range(4)],
        users=[], allocations=[],
    )
    assert cards["Portfolio Health"] == "63"


def test_report_indicates_when_a_section_omits_rows():
    pdf = build_pm_command_report_pdf(
        space_name="Space", today=date(2026, 7, 7),
        projects=[{"project_id": "p1"}],
        solutions=[{"solution_id": "s1", "project_id": "p1"}],
        tasks=[{"task_id": str(index), "project_id": "p1", "solution_id": "s1", "due_date": "2026-07-01"}
               for index in range(19)],
        users=[], allocations=[],
    )
    assert b"Showing 18 of 19 items" in pdf


def test_empty_oracle_lob_does_not_create_a_risk_signal():
    class EmptyLob:
        def read(self):
            return ""

    pdf = build_pm_command_report_pdf(
        space_name="Space", today=date(2026, 7, 7),
        projects=[{"project_id": "p1"}],
        solutions=[{"solution_id": "s1", "project_id": "p1", "owner": "Owner", "blockers": EmptyLob()}],
        tasks=[], users=[], allocations=[],
    )
    assert b"No elevated workstream risks detected." in pdf


@pytest.mark.anyio
async def test_pm_command_report_download_returns_scoped_pdf(client):
    current_project = (
        await client.post("/project-manager/api/projects/", json={"project_name": "Visible PM Report Project"})
    ).json()
    current_solution = (
        await client.post(
            f"/project-manager/api/projects/{current_project['project_id']}/solutions",
            json={
                "solution_name": "Visible Risk Workstream",
                "rag_status": "red",
                "due_date": "2026-07-01",
                "blockers": "Dependency waiting",
            },
        )
    ).json()
    await client.post(
        f"/project-manager/api/solutions/{current_solution['solution_id']}/tasks",
        json={
            "task_name": "Visible Blocked Deliverable",
            "status": "in_progress",
            "due_date": "2026-07-02",
            "blocked": True,
        },
    )

    other_space = (
        await client.post(
            "/project-manager/api/spaces",
            json={"name": "Other PM Report Space", "slug": "other-pm-report-space"},
        )
    ).json()
    other_project = (
        await client.post(
            "/project-manager/api/projects/",
            headers={"X-Space-Id": other_space["space_id"]},
            json={"project_name": "Hidden PM Report Project"},
        )
    ).json()
    await client.post(
        f"/project-manager/api/projects/{other_project['project_id']}/solutions",
        headers={"X-Space-Id": other_space["space_id"]},
        json={"solution_name": "Hidden Risk Workstream", "rag_status": "red"},
    )

    response = await client.get("/project-manager/api/pm-dashboard/report.pdf")

    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF-")
    assert b"Visible PM Report Project" in response.content
    assert b"Visible Risk Workstream" in response.content
    assert b"Visible Blocked Deliverable" in response.content
    assert b"Hidden PM Report Project" not in response.content
    assert b"Hidden Risk Workstream" not in response.content
