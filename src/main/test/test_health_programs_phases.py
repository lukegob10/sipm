from collections import Counter

import pytest
from sqlalchemy import event

from backend.app.models import ChangeLog, Phase, Program, Project, Solution, SolutionPhase, Space, User
from backend.app.phase_catalog import CANONICAL_PHASES, CANONICAL_PHASE_IDS
from backend.app.routes import phases
from backend.app.services.spaces import SpaceContext


@pytest.fixture
def phase_context(db_sessionmaker, test_user):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="test-space", name="Test Space", slug="test-space"),
            User(
                user_id=test_user.user_id, soeid=test_user.soeid, email="phase-test@example.com",
                display_name=test_user.display_name, password_hash="unused", role="global_admin", is_active=True,
            ),
            Program(program_id="program", space_id="test-space", program_name="Program"),
            Project(project_id="project", program_id="program", space_id="test-space", project_name="Project"),
            Solution(
                solution_id="solution", project_id="project", space_id="test-space",
                solution_name="Solution", current_phase="requirements",
            ),
            Solution(
                solution_id="other", project_id="project", space_id="test-space", solution_name="Other",
            ),
        ])
        for phase_id, phase_name, sequence in CANONICAL_PHASES:
            session.add(Phase(
                phase_id=phase_id, phase_group=phase_name, phase_name=phase_name, sequence=sequence,
            ))
            for solution_id in ("solution", "other"):
                session.add(SolutionPhase(solution_id=solution_id, phase_id=phase_id, is_enabled=True))
        session.commit()
    return test_user, SpaceContext(
        space_id="test-space", space_name="Test Space", space_role="space_admin", is_global_admin=True,
    )


@pytest.mark.parametrize("item_count", [1, 7, 35])
def test_phase_upsert_read_queries_do_not_scale_with_payload(db_sessionmaker, phase_context, item_count):
    actor, ctx = phase_context
    payload_items = [
        {
            "phase_id": CANONICAL_PHASE_IDS[index % len(CANONICAL_PHASE_IDS)],
            "is_enabled": False,
            "sequence_override": index,
        }
        for index in range(item_count)
    ]
    reads = Counter()

    def count_reads(execute_state):
        if execute_state.is_select:
            entity = execute_state.statement.column_descriptions[0].get("entity")
            if entity in (Phase, SolutionPhase, Solution):
                reads[entity] += 1

    with db_sessionmaker() as session:
        event.listen(session, "do_orm_execute", count_reads)
        try:
            rows = phases.set_solution_phases(
                "solution", {"phases": payload_items}, session=session, current_user=actor, space_ctx=ctx,
            )
        finally:
            event.remove(session, "do_orm_execute", count_reads)
        assert reads == {Phase: 1, SolutionPhase: 2, Solution: 1}
        expected_sequences = {item["phase_id"]: item["sequence_override"] for item in payload_items}
        assert len(rows) == len(CANONICAL_PHASE_IDS)
        for row in rows:
            assert row.is_enabled is (row.phase_id not in expected_sequences)
            assert row.sequence_override == expected_sequences.get(row.phase_id)
        expected_current = None if "requirements" in expected_sequences else "requirements"
        assert session.get(Solution, "solution").current_phase == expected_current
        assert all(row.is_enabled for row in session.query(SolutionPhase).filter_by(solution_id="other"))


def test_duplicate_new_phase_preserves_last_value_and_audit_chain(db_sessionmaker, phase_context):
    actor, ctx = phase_context
    with db_sessionmaker() as session:
        session.query(SolutionPhase).filter_by(solution_id="solution", phase_id="backlog").delete()
        session.get(Solution, "solution").current_phase = "backlog"
        session.commit()
        rows = phases.set_solution_phases(
            "solution",
            {"phases": [
                {"phase_id": "backlog", "is_enabled": True, "sequence_override": 9},
                {"phase_id": "backlog", "is_enabled": False, "sequence_override": 2},
                {"phase_id": "backlog", "is_enabled": True, "sequence_override": 4},
            ]},
            session=session, current_user=actor, space_ctx=ctx,
        )
        backlog = [row for row in rows if row.phase_id == "backlog"]
        assert len(backlog) == 1
        assert backlog[0].is_enabled is True
        assert backlog[0].sequence_override == 4
        assert session.get(Solution, "solution").current_phase == "backlog"
        changes = session.query(ChangeLog).filter_by(
            entity_type="solution_phase", entity_id=backlog[0].solution_phase_id,
        ).all()
        assert Counter((row.action, row.old_value, row.new_value) for row in changes if row.field == "is_enabled") == {
            ("create", None, "True"): 1,
            ("update", "True", "False"): 1,
            ("update", "False", "True"): 1,
        }
        assert Counter((row.old_value, row.new_value) for row in changes if row.field == "sequence_override") == {
            (None, "9"): 1, ("9", "2"): 1, ("2", "4"): 1,
        }


@pytest.mark.parametrize("current_phase", [None, "requirements", "missing-phase"])
def test_empty_phase_payload_preserves_current_phase_validation(db_sessionmaker, phase_context, current_phase):
    actor, ctx = phase_context
    with db_sessionmaker() as session:
        session.get(Solution, "solution").current_phase = current_phase
        session.commit()
        rows = phases.set_solution_phases(
            "solution", {}, session=session, current_user=actor, space_ctx=ctx,
        )
        assert len(rows) == len(CANONICAL_PHASE_IDS)
        assert all(row.is_enabled and row.sequence_override is None for row in rows)
        expected_current = None if current_phase == "missing-phase" else current_phase
        assert session.get(Solution, "solution").current_phase == expected_current


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_items,status_code", [
    ([{"phase_id": "missing-phase"}, None], 400),
    ([None, {"phase_id": "missing-phase"}], 422),
])
async def test_phase_validation_keeps_first_error_and_rolls_back_audit(
    client, db_sessionmaker, phase_context, invalid_items, status_code,
):
    response = await client.post(
        "/project-manager/api/solutions/solution/phases",
        json={"phases": [{"phase_id": "backlog", "is_enabled": False}, *invalid_items]},
    )
    assert response.status_code == status_code, response.text
    if status_code == 400:
        assert response.json()["detail"] == "Phase missing-phase does not exist"
    else:
        assert response.json()["detail"][0]["loc"] == ["body", "phases", 1]
    with db_sessionmaker() as session:
        assert all(row.is_enabled for row in session.query(SolutionPhase))
        assert session.query(ChangeLog).count() == 0
        assert session.get(Solution, "solution").current_phase == "requirements"
