from datetime import datetime, timezone

import pytest

from backend.app.models import Program, Project, Solution, Space


@pytest.mark.anyio
async def test_public_dashboard_omits_solutions_with_invisible_programs(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="public", name="Public", slug="hierarchy-public", public_program_dashboard_enabled=True),
            Space(space_id="other", name="Other", slug="hierarchy-other"),
            Program(program_id="visible-program", space_id="public", program_name="Visible"),
            Program(program_id="deleted-program", space_id="public", program_name="Deleted", deleted_at=datetime.now(timezone.utc)),
            Program(program_id="other-program", space_id="other", program_name="Other"),
        ])
        session.add_all([
            Project(project_id=f"{kind}-project", space_id="public", program_id=program_id, project_name=f"{kind} project")
            for kind, program_id in (("visible", "visible-program"), ("deleted", "deleted-program"), ("other", "other-program"))
        ])
        session.add_all([
            Solution(solution_id=f"{kind}-solution", space_id="public", project_id=f"{kind}-project", solution_name=f"{kind} solution")
            for kind in ("visible", "deleted", "other")
        ])
        session.commit()

    response = await client.get("/project-manager/api/public/program-dashboard/hierarchy-public")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["project_id"] for item in payload["projects"]] == ["visible-project"]
    assert [item["solution_id"] for item in payload["solutions"]] == ["visible-solution"]
