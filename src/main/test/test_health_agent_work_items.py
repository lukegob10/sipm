from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, Task
from backend.app.services.agent_work_items import get_agent_project, get_agent_task
from backend.app.services.spaces import SpaceContext


@pytest.fixture
def scoped_items(db_sessionmaker):
    ctx = SpaceContext(
        space_id="detail-space",
        space_name="Detail space",
        is_global_admin=False,
        space_role="member",
    )
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id=ctx.space_id, name=ctx.space_name, slug=ctx.space_id),
            Space(space_id="other-space", name="Other space", slug="other-space"),
            Program(
                program_id="program", space_id=ctx.space_id, program_name="Program context"
            ),
            Project(
                project_id="project", program_id="program", space_id=ctx.space_id,
                project_name="Project", description="Project context",
                success_criteria="Project criteria", priority=2,
            ),
            Solution(
                solution_id="solution", project_id="project", space_id=ctx.space_id,
                solution_name="Solution", github_repo_url="https://github.com/example/solution",
            ),
            Task(
                task_id="task", project_id="project", solution_id="solution",
                space_id=ctx.space_id, task_name="Task", description="Task context",
                done_criteria="Task criteria", priority=1, due_date=date(2020, 1, 1),
            ),
        ])
        session.commit()
    return ctx


def test_agent_project_detail_reads_payload_and_program_in_one_query(db_sessionmaker, scoped_items):
    with db_sessionmaker() as session:
        statements = []
        event.listen(session, "do_orm_execute", statements.append)

        result = get_agent_project(session, "project", scoped_items)

        assert result.project_id == "project"
        assert result.program_name == "Program context"
        assert result.description == "Project context"
        assert result.success_criteria == "Project criteria"
        assert result.priority == 2
        assert len(statements) == 1
        assert statements[0].is_select


@pytest.mark.parametrize(
    ("solution_repo", "task_repo", "effective_repo", "source"),
    [
        ("https://github.com/example/solution", None, "https://github.com/example/solution", "inherited"),
        (None, None, None, "none"),
        ("https://github.com/example/solution", "https://github.com/example/task", "https://github.com/example/task", "override"),
        ("https://github.com/example/solution", "invalid-legacy-url", None, "none"),
    ],
)
def test_agent_task_detail_reads_nullable_repo_and_payload_in_one_query(
    db_sessionmaker, scoped_items, solution_repo, task_repo, effective_repo, source
):
    with db_sessionmaker() as session:
        session.get(Solution, "solution").github_repo_url = solution_repo
        session.get(Task, "task").github_repo_url = task_repo
        session.commit()
    with db_sessionmaker() as session:
        statements = []
        event.listen(session, "do_orm_execute", statements.append)

        result = get_agent_task(session, "task", scoped_items)

        assert result.task_id == "task"
        assert result.effective_github_repo_url == effective_repo
        assert result.repo_source == source
        assert result.description == "Task context"
        assert result.acceptance_criteria == result.done_criteria == "Task criteria"
        assert result.is_overdue is True
        assert result.urgency_score == 100
        assert len(statements) == 1
        assert statements[0].is_select


@pytest.mark.parametrize("hidden_model", [Program, Project, Solution, Task])
@pytest.mark.parametrize("hidden_reason", ["deleted", "other-space"])
def test_agent_detail_join_projections_keep_hierarchy_scoped(
    db_sessionmaker, scoped_items, hidden_model, hidden_reason
):
    with db_sessionmaker() as session:
        item = session.get(hidden_model, hidden_model.__name__.lower())
        if hidden_reason == "deleted":
            item.deleted_at = datetime.now(timezone.utc)
        else:
            item.space_id = "other-space"
        session.commit()

        lookups = [(get_agent_task, "task")]
        if hidden_model in (Program, Project):
            lookups.append((get_agent_project, "project"))
        for get_detail, entity in lookups:
            with pytest.raises(HTTPException) as error:
                get_detail(session, entity, scoped_items)
            assert error.value.status_code == 404
            assert error.value.headers == {"X-Error-Code": f"{entity.upper()}_NOT_FOUND"}


@pytest.mark.parametrize(
    ("get_detail", "entity"), [(get_agent_project, "project"), (get_agent_task, "task")]
)
def test_agent_detail_missing_item_preserves_not_found_contract(
    db_sessionmaker, scoped_items, get_detail, entity
):
    with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as error:
            get_detail(session, "missing", scoped_items)
    assert error.value.status_code == 404
    assert error.value.headers == {"X-Error-Code": f"{entity.upper()}_NOT_FOUND"}
