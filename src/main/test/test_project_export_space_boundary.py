import csv
from io import StringIO

import pytest

from backend.app.models import Program, Project, Space
from backend.app.routes.projects.import_export import export_projects
from backend.app.services.spaces import SpaceContext


@pytest.mark.anyio
async def test_project_export_does_not_disclose_foreign_program(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="export-home", name="Home", slug="export-home"),
            Space(space_id="export-other", name="Other", slug="export-other"),
        ])
        session.flush()
        session.add_all([
            Program(program_id="home-program", space_id="export-home", program_name="Home Program"),
            Program(program_id="foreign-program", space_id="export-other", program_name="Private Program"),
        ])
        session.flush()
        session.add_all([
            Project(project_id="valid", space_id="export-home", program_id="home-program", project_name="Valid"),
            Project(project_id="mismatched", space_id="export-home", program_id="foreign-program", project_name="Mismatched"),
        ])
        session.commit()
        response = export_projects(session, SpaceContext(
            space_id="export-home", space_name="Home", space_role="member", is_global_admin=False,
        ))
        content = b"".join([chunk.encode() if isinstance(chunk, str) else chunk async for chunk in response.body_iterator])
    rows = list(csv.DictReader(StringIO(content.decode())))
    assert [row["project_name"] for row in rows] == ["Valid"]
    assert "Private Program" not in content.decode()
