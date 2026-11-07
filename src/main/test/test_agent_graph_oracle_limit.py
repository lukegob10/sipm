from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, Task
from backend.app.services.agent_work_graph import build_work_graph
from backend.app.services.spaces import SpaceContext


def test_work_graph_reads_tasks_for_more_than_1000_solutions(db_sessionmaker):
    """An Oracle-sized graph preserves active descendants and parent filters."""
    with db_sessionmaker() as session:
        session.add(Space(space_id="graph-space", name="Graph", slug="graph"))
        session.add(Program(
            program_id="program", space_id="graph-space", program_name="Program"
        ))
        session.add_all([
            Project(
                project_id=project_id, space_id="graph-space", program_id="program",
                project_name=name, status="active", sponsor="Sponsor",
            )
            for project_id, name in [("project", "Project"), ("other", "Other")]
        ])
        session.add_all([
            Solution(
                solution_id=f"solution-{index:04}", space_id="graph-space",
                project_id="project", solution_name=f"Solution {index:04}",
                version="1", status="active", rag_status="green", priority=1,
            )
            for index in range(1001)
        ])
        session.add_all([
            Solution(
                solution_id="archived", space_id="graph-space", project_id="project",
                solution_name="Archived", version="1", status="active",
                rag_status="green", priority=1, deleted_at=datetime(2020, 1, 1),
            ),
            Solution(
                solution_id="other-solution", space_id="graph-space", project_id="other",
                solution_name="Other", version="1", status="active", rag_status="green",
                priority=1,
            ),
        ])
        session.add_all([
            Task(
                task_id=task_id, space_id="graph-space", project_id=project_id,
                solution_id=solution_id, task_name=name, status=status, priority=1,
                assignee_user_soeid=assignee,
            )
            for task_id, project_id, solution_id, name, status, assignee in [
                ("first", "project", "solution-1000", "A first", "in_progress", None),
                ("second", "project", "solution-1000", "Z second", "in_progress", None),
                ("hidden", "project", "archived", "Hidden", "on_hold", "hidden-user"),
                ("other-task", "other", "other-solution", "Other", "in_progress", None),
                ("mislinked", "other", "solution-1000", "Mislinked", "in_progress", None),
            ]
        ])
        session.commit()
        engine = session.get_bind()
        space_ctx = SpaceContext(
            space_id="graph-space", space_name="Graph", space_role="space_admin",
            is_global_admin=True,
        )

        def enforce_oracle_expression_limit(
            _conn, _cursor, statement, _params, _context, _executemany
        ):
            # SQLite permits this, Oracle 19c rejects an IN list over 1,000 values.
            assert not re.search(r"\bIN\s*\((?:\s*\?\s*,){1000}", statement, re.IGNORECASE)

        event.listen(engine, "before_cursor_execute", enforce_oracle_expression_limit)
        try:
            result = build_work_graph(session, space_ctx, project_id="project", limit=1)
            archived_task = build_work_graph(session, space_ctx, task_id="hidden")
            archived_assignee = build_work_graph(
                session, space_ctx, assignee_user_soeid="hidden-user"
            )
            archived_status = build_work_graph(session, space_ctx, status="on_hold")
        finally:
            event.remove(engine, "before_cursor_execute", enforce_oracle_expression_limit)

    assert len(result.records) == 1
    solutions = result.records[0].solutions
    assert len(solutions) == 1001
    assert [solution.solution_id for solution in solutions] == [
        f"solution-{index:04}" for index in range(1001)
    ]
    assert [task.task_id for task in solutions[-1].tasks] == ["first", "second"]
    assert sum(len(solution.tasks) for solution in solutions) == 2
    assert archived_task.records == []
    assert archived_assignee.records == []
    assert archived_status.records == []
