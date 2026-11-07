from datetime import date, datetime

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Task
from backend.app.services.agent_work_graph import build_work_graph
from backend.app.services.agent_work_search import search_agent_work_items
from backend.app.services.spaces import SpaceContext


_DETAIL_COLUMNS = (
    "description", "success_criteria", "strategic_objective", "problem_statement",
    "blockers", "risks", "rag_reason", "done_criteria", "blocker_note",
)


def _seed_graph(db_sessionmaker, *, archived=False):
    common = {
        "space_id": "summary-space",
        "created_at": datetime(2026, 11, 1, 12),
        "updated_at": datetime(2026, 11, 2, 12),
        "deleted_at": datetime(2026, 11, 3, 12) if archived else None,
    }
    with db_sessionmaker() as session:
        session.add_all([
            Program(
                program_id="program", program_name="Program", description="Program detail",
                **common,
            ),
            Project(
                project_id="project", program_id="program", project_name="Project",
                status="active", priority=2, owner="Owner", owner_user_soeid="owner",
                sponsor="Sponsor", sponsor_user_soeid="sponsor", description="Project detail",
                success_criteria="Project criteria", strategic_objective="Project objective",
                **common,
            ),
            Solution(
                solution_id="solution", project_id="project", solution_name="Solution",
                version="1", status="active", rag_status="amber", priority=1,
                owner="Owner", owner_user_soeid="owner", assignee="Worker",
                assignee_user_soeid="worker", approver_user_soeid="approver",
                due_date=date(2026, 12, 1), description="Solution detail",
                success_criteria="Solution criteria", problem_statement="Solution problem",
                blockers="Solution blockers", risks="Solution risks", rag_reason="Solution reason",
                github_repo_url="https://github.com/example/project",
                **common,
            ),
            *[
                Task(
                    task_id=task_id, project_id="project", solution_id="solution",
                    task_name=f"Task {task_id}", status="in_progress", priority=1,
                    assignee="Worker", assignee_user_soeid="worker",
                    due_date=date(2026, 12, 1), description="Task detail",
                    done_criteria="Task criteria", blocker_note="Task blocker", **common,
                )
                for task_id in ("task-a", "task-z")
            ],
        ])
        session.commit()
    return SpaceContext(
        space_id="summary-space", space_name="Summary", space_role="member",
        is_global_admin=False,
    )


@pytest.mark.parametrize("projection", ["summary", "full"])
def test_graph_summary_skips_unused_details_without_lazy_queries(db_sessionmaker, projection):
    ctx = _seed_graph(db_sessionmaker)
    statements = []
    engine = db_sessionmaker.kw["bind"]

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with db_sessionmaker() as session:
            result = build_work_graph(session, ctx, projection=projection, limit=1)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(statements) == 4
    assert result.programs[0].description == "Program detail"
    project = result.records[0]
    assert (project.project_id, project.program_name, project.owner_user_soeid) == (
        "project", "Program", "owner",
    )
    solution = project.solutions[0]
    assert (solution.solution_id, solution.version, solution.rag_status) == (
        "solution", "1", "amber",
    )
    assert [task.task_id for task in solution.tasks] == ["task-a", "task-z"]
    assert all(task.assignee_user_soeid == "worker" for task in solution.tasks)
    assert result.has_more is False
    assert result.next_cursor is None
    for statement in statements[1:]:
        assert ("description" in statement.lower()) is (projection == "full")
        if projection == "summary":
            assert all(field not in statement.lower() for field in _DETAIL_COLUMNS)
    if projection == "full":
        assert project.description == "Project detail"
        assert solution.problem_statement == "Solution problem"
        assert solution.tasks[0].done_criteria == "Task criteria"
        assert solution.tasks[0].effective_github_repo_url == "https://github.com/example/project"


@pytest.mark.parametrize("entity_type", ["program", "project", "solution", "task"])
@pytest.mark.parametrize("archived", [False, True])
def test_search_summary_skips_unused_details_and_keeps_cursor_order(
    db_sessionmaker, entity_type, archived,
):
    ctx = _seed_graph(db_sessionmaker, archived=archived)
    statements = []
    engine = db_sessionmaker.kw["bind"]

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with db_sessionmaker() as session:
            kwargs = {
                "entity_type": entity_type,
                "lifecycle": "archived" if archived else "active",
                "limit": 1,
            }
            first = search_agent_work_items(session, ctx, **kwargs)
            pages = [first]
            if first.has_more:
                pages.append(search_agent_work_items(session, ctx, cursor=first.next_cursor, **kwargs))
    finally:
        event.remove(engine, "before_cursor_execute", record)

    records = [record for page in pages for record in page.records]
    assert [record.entity_id for record in records] == (
        ["task-z", "task-a"] if entity_type == "task" else [entity_type]
    )
    assert all(record.lifecycle == kwargs["lifecycle"] for record in records)
    assert all(record.created_at == datetime(2026, 11, 1, 12) for record in records)
    assert all(record.updated_at == datetime(2026, 11, 2, 12) for record in records)
    if entity_type in {"solution", "task"}:
        assert all(record.due_date == date(2026, 12, 1) for record in records)
        assert all(record.assignee_user_soeid == "worker" for record in records)
    if entity_type == "task":
        assert first.has_more is True
        assert first.next_cursor
        assert records[0].solution_id == "solution"
    assert pages[-1].has_more is False
    assert pages[-1].next_cursor is None
    assert len(statements) == len(pages)
    assert all(
        field not in statement.lower()
        for statement in statements
        for field in _DETAIL_COLUMNS
    )
