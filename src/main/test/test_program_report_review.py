from __future__ import annotations

import re
from io import BytesIO
from zipfile import ZipFile

import pytest
from sqlalchemy import event, select
from sqlalchemy.dialects import oracle

from backend.app.models import Program, Project, Solution, Space
from backend.app.services.program_dashboard_report_data import (
    _batched_in_filter,
    load_program_dashboard_report_data,
)


@pytest.mark.anyio
async def test_program_name_length_matches_oracle_column_limit(client, db_sessionmaker):
    too_long = await client.post(
        "/project-manager/api/programs",
        json={"program_name": "x" * 256},
    )
    assert too_long.status_code == 400
    assert too_long.json()["detail"] == "program_name must be 255 characters or fewer"

    created = await client.post(
        "/project-manager/api/programs",
        json={"program_name": "Valid Program Name"},
    )
    assert created.status_code == 201, created.text
    program = created.json()

    rejected_update = await client.patch(
        f"/project-manager/api/programs/{program['program_id']}",
        json={"program_name": "y" * 256},
    )
    assert rejected_update.status_code == 400
    unchanged = await client.get(f"/project-manager/api/programs/{program['program_id']}")
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["program_name"] == "Valid Program Name"

    with db_sessionmaker() as session:
        assert session.query(Program).filter(Program.space_id == "test-space").count() == 1


def test_program_report_in_filters_split_large_lists_for_oracle():
    values = [f"program-{index}" for index in range(1001)]
    statement = select(Program.program_id).where(_batched_in_filter(Program.program_id, values))
    compiled = statement.compile(
        dialect=oracle.dialect(),
        compile_kwargs={"render_postcompile": True},
    )

    in_lists = re.findall(r"\bIN\s*\(([^)]*)\)", str(compiled), flags=re.IGNORECASE)
    assert [len(in_list.split(",")) for in_list in in_lists] == [1000, 1]


def test_program_report_skips_unused_phase_query_for_solutionless_program(db_sessionmaker):
    engine = db_sessionmaker.kw["bind"]
    statements: list[str] = []

    def capture_selects(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    with db_sessionmaker() as session:
        program = Program(space_id="test-space", program_name="Solutionless Program")
        session.add(program)
        session.flush()
        program_id = program.program_id
        session.add(
            Project(
                space_id="test-space",
                program_id=program_id,
                project_name="Solutionless Project",
            )
        )
        session.commit()

        event.listen(engine, "before_cursor_execute", capture_selects)
        try:
            report_data = load_program_dashboard_report_data(
                session,
                space_id="test-space",
                selected_program_ids=[program_id],
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture_selects)

    assert len(report_data["programs"]) == 1
    assert len(report_data["projects"]) == 1
    assert report_data["solutions"] == []
    assert report_data["phases"] == []
    assert len(statements) == 3


@pytest.mark.anyio
async def test_all_program_report_routes_use_only_selected_space_rows(
    client,
    db_sessionmaker,
):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(
                    space_id="test-space",
                    name="Private Report Review Space",
                    slug="private-report-review-space",
                    is_active=True,
                ),
                Space(
                    space_id="public-review-space",
                    name="Public Report Review Space",
                    slug="public-review-space",
                    is_active=True,
                    public_program_dashboard_enabled=True,
                ),
            ]
        )
        private_program = Program(
            program_id="private-review-program",
            space_id="test-space",
            program_name="Private Review Program",
        )
        public_program = Program(
            program_id="public-review-program",
            space_id="public-review-space",
            program_name="Public Review Program",
        )
        session.add_all([private_program, public_program])
        session.flush()
        session.add_all(
            [
                Project(
                    project_id="private-review-project",
                    space_id="test-space",
                    program_id=private_program.program_id,
                    project_name="Private Review Project",
                ),
                Project(
                    project_id="public-review-project",
                    space_id="public-review-space",
                    program_id=public_program.program_id,
                    project_name="Public Review Project",
                ),
            ]
        )
        session.add_all(
            [
                Solution(
                    solution_id="private-review-solution",
                    space_id="test-space",
                    project_id="private-review-project",
                    solution_name="Private Review Solution",
                ),
                Solution(
                    solution_id="public-review-solution",
                    space_id="public-review-space",
                    project_id="public-review-project",
                    solution_name="Public Review Solution",
                ),
            ]
        )
        session.commit()

    reports = (
        (
            "/project-manager/api/programs/dashboard/report.pdf",
            ["private-review-program", "public-review-program"],
            "application/pdf",
            "Private Review",
            "Public Review",
        ),
        (
            "/project-manager/api/programs/dashboard/report.xlsx",
            ["private-review-program", "public-review-program"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Private Review",
            "Public Review",
        ),
        (
            "/project-manager/api/public/program-dashboard/public-review-space/report.pdf",
            ["public-review-program", "private-review-program"],
            "application/pdf",
            "Public Review",
            "Private Review",
        ),
        (
            "/project-manager/api/public/program-dashboard/public-review-space/report.xlsx",
            ["public-review-program", "private-review-program"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Public Review",
            "Private Review",
        ),
    )

    for endpoint, selected_ids, content_type, visible_prefix, hidden_prefix in reports:
        response = await client.post(
            endpoint,
            json={"selected_program_ids": selected_ids},
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(content_type)

        if content_type == "application/pdf":
            report_text = response.content.decode("latin-1")
        else:
            with ZipFile(BytesIO(response.content)) as archive:
                report_text = archive.read("xl/sharedStrings.xml").decode("utf-8")

        assert f"{visible_prefix} Program" in report_text
        assert f"{visible_prefix} Project" in report_text
        assert f"{visible_prefix} Solution" in report_text
        assert f"{hidden_prefix} Program" not in report_text
        assert f"{hidden_prefix} Project" not in report_text
        assert f"{hidden_prefix} Solution" not in report_text
