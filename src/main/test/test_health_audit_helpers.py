from __future__ import annotations

import pytest
from sqlalchemy import event

from backend.app.models import Phase, Program, Project, Solution, SolutionPhase
from backend.app.phase_catalog import CANONICAL_PHASES
from backend.app.utils import enable_all_phases


@pytest.mark.parametrize("commit", [False, True])
def test_enable_all_phases_batches_reads_and_preserves_transaction_scope(db_sessionmaker, commit):
    solution_id = "health-phase-solution"
    other_solution_id = "health-phase-other"
    with db_sessionmaker() as session:
        session.add(Program(program_id="health-phase-program", program_name="Phase Program"))
        session.flush()
        session.add(Project(
            project_id="health-phase-project", program_id="health-phase-program",
            project_name="Phase Project", sponsor="Sponsor",
        ))
        session.flush()
        session.add_all([
            Solution(
                solution_id=key, project_id="health-phase-project", solution_name=key,
                owner="Owner", assignee="",
            )
            for key in (solution_id, other_solution_id)
        ])
        session.add_all([
            Phase(phase_id=key, phase_group=name, phase_name=name, sequence=sequence)
            for key, name, sequence in (*CANONICAL_PHASES, ("custom", "Custom", 99))
        ])
        session.flush()
        session.add_all([
            SolutionPhase(
                solution_id=solution_id, phase_id=key,
                is_enabled=False, sequence_override=99,
            )
            for key in ("backlog", "custom")
        ])
        session.add(SolutionPhase(
            solution_id=other_solution_id, phase_id="requirements",
            is_enabled=False, sequence_override=88,
        ))
        session.commit()

        reads = []

        def record_reads(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                reads.append(statement)

        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", record_reads)
        try:
            enable_all_phases(session, solution_id)
        finally:
            event.remove(engine, "before_cursor_execute", record_reads)
        assert len(reads) == 2

        session.flush()
        enable_all_phases(session, solution_id)
        session.flush()
        rows = {
            row.phase_id: row
            for row in session.query(SolutionPhase).filter_by(solution_id=solution_id).all()
        }
        assert set(rows) == {key for key, _name, _sequence in CANONICAL_PHASES} | {"custom"}
        for key, _name, _sequence in CANONICAL_PHASES:
            assert rows[key].is_enabled is True
            assert rows[key].sequence_override is None
        assert rows["custom"].is_enabled is False
        assert rows["custom"].sequence_override == 99
        if commit:
            session.commit()
        else:
            session.rollback()

    with db_sessionmaker() as session:
        rows = session.query(SolutionPhase).filter_by(solution_id=solution_id).all()
        if commit:
            assert len(rows) == len(CANONICAL_PHASES) + 1
        else:
            assert {row.phase_id for row in rows} == {"backlog", "custom"}
            assert all(row.is_enabled is False and row.sequence_override == 99 for row in rows)
        other = session.query(SolutionPhase).filter_by(solution_id=other_solution_id).one()
        assert other.is_enabled is False
        assert other.sequence_override == 88


@pytest.mark.anyio
@pytest.mark.parametrize("filter_name", ["since", "until"])
@pytest.mark.parametrize("value", [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59-01:00",
])
async def test_audit_rejects_datetime_bounds_that_overflow_utc(client, filter_name, value):
    response = await client.get("/project-manager/api/audit", params={filter_name: value})
    assert response.status_code == 422
    assert "datetime" in response.json()["detail"].lower()
