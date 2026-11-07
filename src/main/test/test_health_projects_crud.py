from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Space


@pytest.mark.anyio
@pytest.mark.parametrize("read", ["list", "detail"])
async def test_project_reads_fetch_only_the_parent_name(client, db_sessionmaker, read):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(space_id="test-space", name="Test Space", slug="test-space"),
                Program(
                    program_id="parent",
                    space_id="test-space",
                    program_name="Parent Program",
                    description="Unused parent description. " * 4000,
                ),
                Project(
                    project_id="child",
                    space_id="test-space",
                    program_id="parent",
                    project_name="Child Project",
                    description="Required project description",
                ),
            ]
        )
        session.commit()

    statements = []

    def capture_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement.replace('"', "").lower())

    engine = db_sessionmaker.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        path = "/project-manager/api/projects/" if read == "list" else "/project-manager/api/projects/child"
        response = await client.get(path)
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200, response.text
    project = response.json()[0] if read == "list" else response.json()
    assert project["project_name"] == "Child Project"
    assert project["program_name"] == "Parent Program"
    assert project["description"] == "Required project description"
    assert len(statements) == (1 if read == "list" else 2)
    parent_table = Program.__tablename__.lower()
    assert any(f"{parent_table}.program_name" in statement for statement in statements)
    assert all(f"{parent_table}.description" not in statement for statement in statements)


@pytest.mark.anyio
@pytest.mark.parametrize("read", ["list", "detail"])
@pytest.mark.parametrize("parent_state", ["deleted", "foreign"])
async def test_project_reads_preserve_hidden_parent_behavior(
    client, db_sessionmaker, read, parent_state
):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(space_id="test-space", name="Test Space", slug="test-space"),
                Space(space_id="foreign-space", name="Foreign Space", slug="foreign-space"),
                Program(
                    program_id="hidden-parent",
                    space_id="foreign-space" if parent_state == "foreign" else "test-space",
                    program_name="Hidden Program Name",
                    deleted_at=datetime.now(timezone.utc) if parent_state == "deleted" else None,
                ),
                Project(
                    project_id="child",
                    space_id="test-space",
                    program_id="hidden-parent",
                    project_name="Child Project",
                ),
            ]
        )
        session.commit()

    path = "/project-manager/api/projects/" if read == "list" else "/project-manager/api/projects/child"
    response = await client.get(path)

    assert response.status_code == 200, response.text
    if read == "list":
        assert response.json() == []
    else:
        assert response.json()["project_name"] == "Child Project"
        assert response.json()["program_name"] is None
    assert "Hidden Program Name" not in response.text
