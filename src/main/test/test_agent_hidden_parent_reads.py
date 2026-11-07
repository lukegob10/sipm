from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from backend.app.models import Program, Project, Solution, Task
from backend.app.services.agent_work_items import get_agent_project, get_agent_solution, get_agent_task
from backend.app.services.agent_work_search import search_agent_work_items
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("hidden_program", ["deleted", "other-space"])
def test_agent_active_search_and_details_exclude_hidden_program(db_sessionmaker, hidden_program):
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", program_name="Program",
                            space_id="other" if hidden_program == "other-space" else "space",
                            deleted_at=datetime.now(timezone.utc) if hidden_program == "deleted" else None))
        session.add(Project(project_id="project", program_id="program", space_id="space", project_name="Project"))
        session.add(Solution(solution_id="solution", project_id="project", space_id="space", solution_name="Solution"))
        session.add(Task(task_id="task", solution_id="solution", project_id="project", space_id="space", task_name="Task"))
        session.commit()
        for kind, ident, get_detail in (
            ("project", "project", get_agent_project),
            ("solution", "solution", get_agent_solution),
            ("task", "task", get_agent_task),
        ):
            with pytest.raises(HTTPException) as error:
                get_detail(session, ident, ctx)
            assert error.value.status_code == 404
            assert search_agent_work_items(session, ctx, entity_type=kind).records == []

        session.get(Task, "task").deleted_at = datetime.now(timezone.utc)
        session.commit()
        archived = search_agent_work_items(session, ctx, entity_type="task", lifecycle="archived")
        assert [row.entity_id for row in archived.records] == ["task"]


def test_agent_active_task_search_and_detail_exclude_mismatched_project(db_sessionmaker):
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", space_id="space", program_name="Program"))
        session.add(Project(project_id="project", program_id="program", space_id="space", project_name="Project"))
        session.add(Solution(solution_id="solution", project_id="project", space_id="space", solution_name="Solution"))
        session.add(Task(task_id="task", solution_id="solution", project_id="wrong-project", space_id="space", task_name="Task"))
        session.commit()
        with pytest.raises(HTTPException) as error:
            get_agent_task(session, "task", ctx)
        assert error.value.status_code == 404
        assert search_agent_work_items(session, ctx, entity_type="task").records == []
