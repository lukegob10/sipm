import pytest

from backend.app.models import Phase, Program, Project, Solution, SolutionPhase


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_item", [None, "backlog", {}, {"phase_id": "backlog", "is_enabled": "maybe"}])
async def test_malformed_phase_item_returns_validation_error_without_partial_write(
    client, db_sessionmaker, invalid_item
):
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", space_id="test-space", program_name="Program"))
        session.add(Project(project_id="project", program_id="program", space_id="test-space", project_name="Project"))
        session.add(Solution(
            solution_id="solution", project_id="project", space_id="test-space", solution_name="Solution",
        ))
        session.add(Phase(phase_id="backlog", phase_group="Intake", phase_name="Backlog", sequence=1))
        session.add(SolutionPhase(solution_id="solution", phase_id="backlog", is_enabled=True))
        session.commit()

    response = await client.post(
        "/project-manager/api/solutions/solution/phases",
        json={"phases": [{"phase_id": "backlog", "is_enabled": False}, invalid_item]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"][:3] == ["body", "phases", 1]
    with db_sessionmaker() as session:
        assert session.query(SolutionPhase).one().is_enabled is True
