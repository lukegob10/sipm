from datetime import date

import pytest

from backend.app.services.pm_command_report_pdf import build_pm_command_report_pdf


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
