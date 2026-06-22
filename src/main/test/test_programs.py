import inspect

import pytest

from backend.app.services import program_dashboard_report_pdf
from backend.app.services.program_dashboard_report_pdf import build_program_dashboard_report_pdf


def test_program_dashboard_report_layout_prioritizes_escalation_column():
    columns = {key: width for key, _label, _x, width in program_dashboard_report_pdf.TABLE_COLUMNS}

    assert columns["escalation"] >= 180
    assert columns["escalation"] > columns["deliverable"] * 0.8
    assert columns["escalation"] > columns["owner"] * 2
    assert columns["phase"] >= 110
    assert columns["progress"] >= 88
    assert columns["start"] <= 48
    assert columns["end"] <= 48
    assert sum(columns.values()) == pytest.approx(798.0)


def test_program_dashboard_report_escalation_blanks_for_program_and_project_rows():
    service_text = inspect.getsource(program_dashboard_report_pdf)

    assert 'title=_text(program.get("program_name"), "Unnamed Program")' in service_text
    assert 'title=_text(project.get("project_name"), "Unnamed Project")' in service_text
    assert 'escalation="",\n            progress=progress' in service_text
    assert 'escalation="",\n                progress=project_progress(project_solutions, project)' in service_text
    assert 'if escalation_text == "-":' in service_text
    assert "_center_text(" in service_text
    assert "value=line" in service_text
    assert "size=7.6" in service_text
    assert "max_lines=3" in service_text
    assert "bar_w = min(44.0, max(28.0, progress_col_w - gap - percent_w - 4.0))" in service_text


def test_build_program_dashboard_report_pdf_returns_pdf_bytes_for_empty_inputs():
    pdf_bytes = build_program_dashboard_report_pdf(
        space_name="Main",
        selected_program_label="0 selected",
        programs=[],
        projects=[],
        solutions=[],
        phases=[],
        collapsed_program_ids=set(),
        collapsed_project_ids=set(),
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert b"Program Dashboard Report" in pdf_bytes
    assert b"Escalation" in pdf_bytes


def test_build_program_dashboard_report_pdf_includes_solution_escalation():
    pdf_bytes = build_program_dashboard_report_pdf(
        space_name="Main",
        selected_program_label="Report Program",
        programs=[{"program_id": "program-1", "program_name": "Report Program"}],
        projects=[
            {
                "project_id": "project-1",
                "program_id": "program-1",
                "project_name": "Visible Project",
                "status": "active",
                "sponsor": "Visible Sponsor",
            }
        ],
        solutions=[
            {
                "solution_id": "solution-1",
                "project_id": "project-1",
                "solution_name": "Visible Solution",
                "status": "active",
                "owner": "Visible Owner",
                "current_phase": "go_live",
                "escalation": "Needs help",
            }
        ],
        phases=[{"phase_id": "go_live", "phase_name": "Go Live", "sequence": 1}],
        collapsed_program_ids=set(),
        collapsed_project_ids=set(),
    )

    assert b"Escalation" in pdf_bytes
    assert b"Needs help" in pdf_bytes


@pytest.mark.anyio
async def test_program_crud_and_delete_blocked_with_active_projects(client):
    create = await client.post(
        "/project-manager/api/programs",
        json={"program_name": "Transformation", "description": "Portfolio umbrella"},
    )
    assert create.status_code == 201, create.text
    program = create.json()
    assert program["program_name"] == "Transformation"

    project = await client.post(
        "/project-manager/api/projects",
        json={"program_id": program["program_id"], "project_name": "Program Project"},
    )
    assert project.status_code == 201, project.text
    assert project.json()["program_id"] == program["program_id"]
    assert project.json()["program_name"] == "Transformation"

    blocked = await client.delete(f"/project-manager/api/programs/{program['program_id']}")
    assert blocked.status_code == 400
    assert "active projects" in blocked.json()["detail"]

    update = await client.patch(
        f"/project-manager/api/programs/{program['program_id']}",
        json={"description": "Updated umbrella"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["description"] == "Updated umbrella"


@pytest.mark.anyio
async def test_project_can_be_reassigned_between_programs(client):
    first = (
        await client.post("/project-manager/api/programs", json={"program_name": "First Program"})
    ).json()
    second = (
        await client.post("/project-manager/api/programs", json={"program_name": "Second Program"})
    ).json()
    project = (
        await client.post(
            "/project-manager/api/projects",
            json={"program_id": first["program_id"], "project_name": "Movable Project"},
        )
    ).json()

    reassigned = await client.patch(
        f"/project-manager/api/projects/{project['project_id']}",
        json={"program_id": second["program_id"]},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["program_id"] == second["program_id"]
    assert reassigned.json()["program_name"] == "Second Program"

    projects = await client.get(f"/project-manager/api/projects?program_id={second['program_id']}")
    assert projects.status_code == 200, projects.text
    assert [row["project_id"] for row in projects.json()] == [project["project_id"]]


@pytest.mark.anyio
async def test_project_reassignment_rejects_cross_space_program(client):
    program = (
        await client.post("/project-manager/api/programs", json={"program_name": "Visible Program"})
    ).json()
    project = (
        await client.post(
            "/project-manager/api/projects",
            json={"program_id": program["program_id"], "project_name": "Scoped Project"},
        )
    ).json()

    missing = await client.patch(
        f"/project-manager/api/projects/{project['project_id']}",
        json={"program_id": "not-in-this-space"},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Program not found"


@pytest.mark.anyio
async def test_program_dashboard_report_download_returns_visible_pdf_rows(client):
    program = (
        await client.post("/project-manager/api/programs", json={"program_name": "Report Program"})
    ).json()
    collapsed_program = (
        await client.post("/project-manager/api/programs", json={"program_name": "Collapsed Program"})
    ).json()
    project = (
        await client.post(
            "/project-manager/api/projects",
            json={
                "program_id": program["program_id"],
                "project_name": "Visible Project",
                "sponsor": "Visible Sponsor",
            },
        )
    ).json()
    collapsed_project = (
        await client.post(
            "/project-manager/api/projects",
            json={
                "program_id": program["program_id"],
                "project_name": "Collapsed Project",
                "sponsor": "Collapsed Sponsor",
            },
        )
    ).json()
    await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Visible Solution",
            "status": "active",
            "owner": "Visible Owner",
            "current_phase": "plan",
            "escalation": "Needs help",
        },
    )
    await client.post(
        f"/project-manager/api/projects/{collapsed_project['project_id']}/solutions",
        json={
            "solution_name": "Hidden Collapsed Solution",
            "status": "active",
            "owner": "Hidden Owner",
        },
    )
    collapsed_program_project = (
        await client.post(
            "/project-manager/api/projects",
            json={
                "program_id": collapsed_program["program_id"],
                "project_name": "Hidden Program Project",
            },
        )
    ).json()
    await client.post(
        f"/project-manager/api/projects/{collapsed_program_project['project_id']}/solutions",
        json={"solution_name": "Hidden Program Solution"},
    )

    response = await client.post(
        "/project-manager/api/programs/dashboard/report.pdf",
        json={
            "selected_program_ids": [program["program_id"], collapsed_program["program_id"]],
            "collapsed_program_ids": [collapsed_program["program_id"]],
            "collapsed_project_ids": [collapsed_project["project_id"]],
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF-")
    assert b"Report Program" in response.content
    assert b"Collapsed Program" in response.content
    assert b"Visible Project" in response.content
    assert b"Collapsed Project" in response.content
    assert b"Visible Solution" in response.content
    assert b"Escalation" in response.content
    assert b"Hidden Collapsed Solution" not in response.content
    assert b"Hidden Program Project" not in response.content
    assert b"Hidden Program Solution" not in response.content


@pytest.mark.anyio
async def test_program_dashboard_report_ignores_program_ids_outside_active_space(client):
    current_program = (
        await client.post("/project-manager/api/programs", json={"program_name": "Current Space Program"})
    ).json()
    other_space = (
        await client.post("/project-manager/api/spaces", json={"name": "Other Report Space", "slug": "other-report-space"})
    ).json()
    other_program = (
        await client.post(
            "/project-manager/api/programs",
            headers={"X-Space-Id": other_space["space_id"]},
            json={"program_name": "Other Space Program"},
        )
    ).json()

    response = await client.post(
        "/project-manager/api/programs/dashboard/report.pdf",
        json={
            "selected_program_ids": [current_program["program_id"], other_program["program_id"]],
            "collapsed_program_ids": [],
            "collapsed_project_ids": [],
        },
    )

    assert response.status_code == 200, response.text
    assert b"Current Space Program" in response.content
    assert b"Other Space Program" not in response.content
