from datetime import date, timedelta

from backend.app.models import Program, Project, Solution, Space, Task
from backend.app.services.agent_assigned_work import list_agent_assigned_work
from backend.app.services.spaces import SpaceContext


def test_many_assigned_tasks_keep_full_order_across_pages(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="stream-space", name="Stream Space", slug="stream-space"),
            Program(program_id="stream-program", space_id="stream-space", program_name="Program"),
            Project(project_id="stream-project", space_id="stream-space", program_id="stream-program", project_name="Project"),
            Solution(solution_id="stream-solution", space_id="stream-space", project_id="stream-project", solution_name="Solution"),
        ])
        session.add_all([
            Task(
                task_id=f"task-{i:04d}", task_name=f"Task {i:04d}", space_id="stream-space",
                project_id="stream-project", solution_id="stream-solution", assignee_user_soeid="user",
                status="complete" if i % 31 == 0 else "to_do", blocked=i % 7 == 0,
                priority=(i % 5) + 1,
                due_date=date.today() + timedelta(days=(i % 20) - 10) if i % 4 else None,
            )
            for i in range(641)
        ])
        session.commit()
        ctx = SpaceContext(space_id="stream-space", space_name="Stream", is_global_admin=False, space_role="member")
        cursor = None
        records = []
        while True:
            page = list_agent_assigned_work(session, ctx, assignee_user_soeid="user", cursor=cursor, limit=87)
            records.extend(page.records)
            if not page.has_more:
                assert page.next_cursor is None
                break
            assert page.next_cursor and page.next_cursor != cursor
            cursor = page.next_cursor
        assert len(records) == 641 - len(range(0, 641, 31))
        assert len({item.task.task_id for item in records}) == len(records)
        keys = [
            (not item.needs_attention, -item.task.urgency_score,
             item.task.due_date.isoformat() if item.task.due_date else "9999-12-31",
             item.task.priority, item.task.task_name.casefold(), item.task.task_id)
            for item in records
        ]
        assert keys == sorted(keys)
