from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.app.models import Program, Project, Solution
from backend.app.routes.projects import import_export as project_import


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["project-create", "project-update", "solution-update", "task-create"])
async def test_import_counts_only_committed_rows(client, db_sessionmaker, kind):
    project_response = await client.post(
        "/project-manager/api/projects/", json={"project_name": "Existing Project"}
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["project_id"]
    if kind in {"solution-update", "task-create"}:
        response = await client.post(
            f"/project-manager/api/projects/{project_id}/solutions",
            json={"solution_name": "Existing Solution", "version": "1.0.0"},
        )
        assert response.status_code == 201, response.text
        if kind == "solution-update":
            path = "/project-manager/api/solutions/import"
            csv = "project_name,solution_name,version,description\nExisting Project,Existing Solution,1.0.0,Changed\n"
        else:
            path = "/project-manager/api/tasks/import"
            csv = "project_name,solution_name,version,task_name\nExisting Project,Existing Solution,1.0.0,Task\n"
    else:
        path = "/project-manager/api/projects/import"
        name = "New Project" if kind == "project-create" else "Existing Project"
        csv = f"project_name,description\n{name},Changed\n"

    def fail_outer_commit(session):
        if not session.in_nested_transaction():
            raise RuntimeError("internal database secret")

    event.listen(Session, "before_commit", fail_outer_commit)
    try:
        response = await client.post(path, content=csv, headers={"Content-Type": "text/csv"})
    finally:
        event.remove(Session, "before_commit", fail_outer_commit)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 0
    assert result["updated"] == 0
    entity = kind.split("-")[0]
    assert result["errors"] == [f"Row 2: {entity} could not be saved"]
    with db_sessionmaker() as session:
        assert session.query(Project).filter_by(project_name="New Project").first() is None
        assert session.get(Project, project_id).description is None
        if kind == "solution-update":
            assert session.query(Solution).filter_by(solution_name="Existing Solution").one().description is None


@pytest.mark.anyio
async def test_project_import_counts_later_success_after_failed_commit(client, db_sessionmaker):
    response = await client.post(
        "/project-manager/api/projects/", json={"project_name": "Seed Project"}
    )
    assert response.status_code == 201, response.text
    failures = 0

    def fail_first_outer_commit(session):
        nonlocal failures
        if not session.in_nested_transaction() and failures == 0:
            failures += 1
            raise RuntimeError("simulated commit failure")

    event.listen(Session, "before_commit", fail_first_outer_commit)
    try:
        response = await client.post(
            "/project-manager/api/projects/import",
            content="project_name\nFailed Project\nSuccessful Project\n",
            headers={"Content-Type": "text/csv"},
        )
    finally:
        event.remove(Session, "before_commit", fail_first_outer_commit)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 1
    assert result["updated"] == 0
    assert len(result["errors"]) == 1
    with db_sessionmaker() as session:
        assert session.query(Project).filter_by(project_name="Failed Project").first() is None
        assert session.query(Project).filter_by(project_name="Successful Project").one()


@pytest.mark.anyio
async def test_project_import_recovers_after_program_resolution_database_error(client, db_sessionmaker, monkeypatch):
    seeded = await client.post("/project-manager/api/projects/", json={"project_name": "Seed"})
    assert seeded.status_code == 201
    resolve = project_import._resolve_import_program
    calls = 0

    def fail_second_resolution(session, space_ctx, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            session.add(Program(space_id=space_ctx.space_id, program_name="Default Program"))
            session.flush()
        return resolve(session, space_ctx, **kwargs)

    monkeypatch.setattr(project_import, "_resolve_import_program", fail_second_resolution)
    response = await client.post(
        "/project-manager/api/projects/import",
        content="project_name\nFirst\nFailed\nLast\n",
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 2
    assert result["errors"] == ["Row 3: program could not be resolved"]
    with db_sessionmaker() as session:
        assert session.query(Project).filter_by(project_name="First").one()
        assert session.query(Project).filter_by(project_name="Failed").first() is None
        assert session.query(Project).filter_by(project_name="Last").one()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "detail", "expected"),
    [(404, "Program not found", "404: Program not found"),
     (503, "internal database secret", "program could not be resolved")],
)
async def test_project_import_preserves_only_safe_program_errors(client, monkeypatch, status_code, detail, expected):
    def fail_resolution(*_args, **_kwargs):
        raise HTTPException(status_code=status_code, detail=detail)

    monkeypatch.setattr(project_import, "_resolve_import_program", fail_resolution)
    response = await client.post(
        "/project-manager/api/projects/import",
        content="project_name\nProject\n",
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    assert response.json()["errors"] == [f"Row 2: {expected}"]


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["solution", "task"])
async def test_import_continues_after_auto_project_flush_fails(client, db_sessionmaker, kind):
    response = await client.post(
        "/project-manager/api/projects/", json={"project_name": "Seed Project"}
    )
    assert response.status_code == 201, response.text
    header = "project_name,solution_name"
    rows = ["First Project,First Solution", "Failed Project,Failed Solution", "Last Project,Last Solution"]
    if kind == "task":
        header += ",task_name"
        rows = [f"{row},Task" for row in rows]

    def fail_project_flush(session, _context, _instances):
        if any(isinstance(row, Project) and row.project_name == "Failed Project" for row in session.new):
            raise RuntimeError("simulated project flush failure")

    event.listen(Session, "before_flush", fail_project_flush)
    try:
        response = await client.post(
            f"/project-manager/api/{kind}s/import",
            content="\n".join([header, *rows, ""]),
            headers={"Content-Type": "text/csv"},
        )
    finally:
        event.remove(Session, "before_flush", fail_project_flush)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 2
    assert result["projects_created"] == 2
    assert result["errors"] == ["Row 3: project could not be created"]
    with db_sessionmaker() as session:
        assert session.query(Project).filter_by(project_name="Failed Project").first() is None
        assert session.query(Project).filter_by(project_name="First Project").one()
        assert session.query(Project).filter_by(project_name="Last Project").one()
