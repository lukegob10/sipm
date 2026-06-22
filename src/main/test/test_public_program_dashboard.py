import pytest

from backend.app.models import Program, Project, Solution, Space


@pytest.mark.anyio
async def test_public_program_dashboard_spa_page_uses_app_root_base(client):
    response = await client.get("/project-manager/public/program-dashboard/main")

    assert response.status_code == 200, response.text
    assert '<base href="/project-manager/" />' in response.text
    assert '<script type="module" src="js/app.js"></script>' in response.text


@pytest.mark.anyio
async def test_public_program_dashboard_returns_404_when_unpublished_or_missing(client):
    created = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Private Dashboard Space", "slug": "private-dashboard-space"},
    )
    assert created.status_code == 201, created.text

    unpublished = await client.get("/project-manager/api/public/program-dashboard/private-dashboard-space")
    assert unpublished.status_code == 404

    missing = await client.get("/project-manager/api/public/program-dashboard/not-a-space")
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_public_program_dashboard_returns_404_for_archived_space(client):
    created = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Archived Public Space", "slug": "archived-public-space"},
    )
    assert created.status_code == 201, created.text
    space_id = created.json()["space_id"]
    enabled = await client.patch(
        f"/project-manager/api/spaces/{space_id}",
        json={"public_program_dashboard_enabled": True},
    )
    assert enabled.status_code == 200, enabled.text
    archived = await client.patch(f"/project-manager/api/spaces/{space_id}", json={"is_active": False})
    assert archived.status_code == 200, archived.text

    response = await client.get("/project-manager/api/public/program-dashboard/archived-public-space")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_public_program_dashboard_returns_enabled_space_data_without_auth(client, db_sessionmaker):
    with db_sessionmaker() as session:
        public_space = Space(
            space_id="public-space",
            name="Public Space",
            slug="public-space",
            is_active=True,
            public_program_dashboard_enabled=True,
        )
        other_space = Space(
            space_id="other-public-space",
            name="Other Public Space",
            slug="other-public-space",
            is_active=True,
            public_program_dashboard_enabled=True,
        )
        session.add_all([public_space, other_space])
        public_program = Program(
            program_id="public-program",
            space_id=public_space.space_id,
            program_name="Visible Program",
        )
        other_program = Program(
            program_id="other-program",
            space_id=other_space.space_id,
            program_name="Hidden Program",
        )
        public_project = Project(
            project_id="public-project",
            space_id=public_space.space_id,
            program_id=public_program.program_id,
            project_name="Visible Project",
            sponsor="Visible Sponsor",
        )
        other_project = Project(
            project_id="other-project",
            space_id=other_space.space_id,
            program_id=other_program.program_id,
            project_name="Hidden Project",
            sponsor="Hidden Sponsor",
        )
        public_solution = Solution(
            solution_id="public-solution",
            space_id=public_space.space_id,
            project_id=public_project.project_id,
            solution_name="Visible Solution",
            owner="Visible Owner",
            escalation="Visible escalation",
        )
        other_solution = Solution(
            solution_id="other-solution",
            space_id=other_space.space_id,
            project_id=other_project.project_id,
            solution_name="Hidden Solution",
            owner="Hidden Owner",
        )
        session.add_all([
            public_program,
            other_program,
            public_project,
            other_project,
            public_solution,
            other_solution,
        ])
        session.commit()

    response = await client.get("/project-manager/api/public/program-dashboard/public-space")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["space"]["slug"] == "public-space"
    assert [row["program_name"] for row in payload["programs"]] == ["Visible Program"]
    assert [row["project_name"] for row in payload["projects"]] == ["Visible Project"]
    assert [row["solution_name"] for row in payload["solutions"]] == ["Visible Solution"]
    assert payload["solutions"][0]["escalation"] == "Visible escalation"


@pytest.mark.anyio
async def test_public_program_dashboard_report_pdf_is_scoped_to_enabled_space(client, db_sessionmaker):
    with db_sessionmaker() as session:
        public_space = Space(
            space_id="public-report-space",
            name="Public Report Space",
            slug="public-report-space",
            is_active=True,
            public_program_dashboard_enabled=True,
        )
        private_space = Space(
            space_id="private-report-space",
            name="Private Report Space",
            slug="private-report-space",
            is_active=True,
            public_program_dashboard_enabled=True,
        )
        session.add_all([public_space, private_space])
        public_program = Program(
            program_id="public-report-program",
            space_id=public_space.space_id,
            program_name="Visible Report Program",
        )
        private_program = Program(
            program_id="private-report-program",
            space_id=private_space.space_id,
            program_name="Hidden Report Program",
        )
        public_project = Project(
            project_id="public-report-project",
            space_id=public_space.space_id,
            program_id=public_program.program_id,
            project_name="Visible Report Project",
            sponsor="Visible Sponsor",
        )
        private_project = Project(
            project_id="private-report-project",
            space_id=private_space.space_id,
            program_id=private_program.program_id,
            project_name="Hidden Report Project",
            sponsor="Hidden Sponsor",
        )
        public_solution = Solution(
            solution_id="public-report-solution",
            space_id=public_space.space_id,
            project_id=public_project.project_id,
            solution_name="Visible Report Solution",
            owner="Visible Owner",
            escalation="Visible escalation",
        )
        private_solution = Solution(
            solution_id="private-report-solution",
            space_id=private_space.space_id,
            project_id=private_project.project_id,
            solution_name="Hidden Report Solution",
            owner="Hidden Owner",
        )
        session.add_all([
            public_program,
            private_program,
            public_project,
            private_project,
            public_solution,
            private_solution,
        ])
        session.commit()

    response = await client.post(
        "/project-manager/api/public/program-dashboard/public-report-space/report.pdf",
        json={
            "selected_program_ids": ["public-report-program", "private-report-program"],
            "collapsed_program_ids": [],
            "collapsed_project_ids": [],
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF-")
    assert b"Visible Report Program" in response.content
    assert b"Visible Report Project" in response.content
    assert b"Visible Report Solution" in response.content
    assert b"Visible escalation" in response.content
    assert b"Hidden Report Program" not in response.content
    assert b"Hidden Report Project" not in response.content
    assert b"Hidden Report Solution" not in response.content
