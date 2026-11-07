from __future__ import annotations

import csv
from io import BytesIO, StringIO

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query, attributes

from backend.app.models import Program, Project


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("failed_lookup", [1, 2])
async def test_project_import_recovers_from_project_lookup_failure(
    client, db_sessionmaker, monkeypatch, dry_run, failed_lookup
):
    original_first = Query.first
    lookup_count = 0

    def fail_one_project_lookup(query):
        nonlocal lookup_count
        if query.column_descriptions[0].get("entity") is Project:
            lookup_count += 1
            if lookup_count == failed_lookup:
                raise OperationalError("SELECT internal database secret", {}, RuntimeError("lookup failed"))
        return original_first(query)

    names = ["Lookup First", "Lookup Second", "Lookup Last"]
    with monkeypatch.context() as patch:
        patch.setattr(Query, "first", fail_one_project_lookup)
        response = await client.post(
            f"/project-manager/api/projects/import?dry_run={str(dry_run).lower()}",
            content="\n".join(["project_name", *names, ""]),
            headers={"Content-Type": "text/csv"},
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "created": 2,
        "updated": 0,
        "errors": [f"Row {failed_lookup + 1}: project could not be saved"],
        "total_rows": 3,
        "dry_run": dry_run,
    }
    expected_names = set() if dry_run else set(names) - {names[failed_lookup - 1]}
    with db_sessionmaker() as session:
        assert {row.project_name for row in session.query(Project).all()} == expected_names
        assert session.query(Program).count() == (0 if dry_run else 1)


@pytest.mark.anyio
@pytest.mark.parametrize("binary_lob", [False, True])
async def test_project_export_reads_strategic_objective_lob(client, binary_lob):
    objective = 'Expand "coverage", safely\nMeasure café outcomes'
    created = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Objective Export", "strategic_objective": objective},
    )
    assert created.status_code == 201, created.text

    def load_objective_lob(project, _context):
        value = BytesIO(objective.encode("utf-8")) if binary_lob else StringIO(objective)
        attributes.set_committed_value(project, "strategic_objective", value)

    event.listen(Project, "load", load_objective_lob)
    try:
        response = await client.get("/project-manager/api/projects/export")
    finally:
        event.remove(Project, "load", load_objective_lob)

    assert response.status_code == 200, response.text
    rows = list(csv.DictReader(StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["strategic_objective"] == objective
