from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, Task, User, UserTaskState
from backend.app.routes.my_work import list_my_work, list_repository_inventory
from backend.app.services.spaces import SpaceContext


def _seed_work(db_sessionmaker):
    actor = SimpleNamespace(user_id="health-user", soeid="health")
    space_ctx = SpaceContext(
        space_id="health-space", space_name="Health", space_role="member", is_global_admin=False
    )
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="health-space", name="Health", slug="health"),
            Space(space_id="other-space", name="Other", slug="other"),
            User(user_id="health-user", soeid="health", display_name="Health User",
                 email="health@example.test", password_hash="unused"),
            User(user_id="other-user", soeid="other", display_name="Other User",
                 email="other@example.test", password_hash="unused"),
            Program(program_id="health-program", space_id="health-space", program_name="Program"),
            Project(project_id="health-project", program_id="health-program", space_id="health-space",
                    project_name="Project"),
            Solution(solution_id="health-solution", project_id="health-project", space_id="health-space",
                     solution_name="Solution", github_repo_url="https://github.com/example/inherited"),
        ])
        for task_id, name, assignee, repo_url in [
            ("private", "Private", "health", None),
            ("default", "Default", "health", None),
            ("wrong-space", "Wrong space", "health", "https://github.com/example/override"),
            ("other", "Other", "other", None),
        ]:
            session.add(Task(
                task_id=task_id, task_name=name, project_id="health-project", solution_id="health-solution",
                space_id="health-space", assignee_user_soeid=assignee, github_repo_url=repo_url,
            ))
        session.add_all([
            UserTaskState(user_id="health-user", task_id="private", space_id="health-space",
                          bucket="today", sort_rank=7, reminder_at=datetime(2020, 1, 1), private_note="Owner note"),
            UserTaskState(user_id="other-user", task_id="default", space_id="health-space",
                          bucket="today", private_note="Another user's note"),
            UserTaskState(user_id="health-user", task_id="wrong-space", space_id="other-space",
                          bucket="today", private_note="Another space's note"),
        ])
        session.commit()
    return actor, space_ctx


@contextmanager
def _select_statements(db_sessionmaker):
    engine = db_sessionmaker.kw["bind"]
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().lower().startswith("select"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_my_work_reads_hierarchy_and_scoped_private_state_in_one_query(db_sessionmaker):
    actor, space_ctx = _seed_work(db_sessionmaker)
    with _select_statements(db_sessionmaker) as statements, db_sessionmaker() as session:
        records = list_my_work(session=session, space_ctx=space_ctx, current_user=actor)

    assert [record.task.task_id for record in records] == ["private", "default", "wrong-space"]
    by_id = {record.task.task_id: record for record in records}
    private = by_id["private"]
    assert private.private_bucket == "today"
    assert private.private_sort_rank == 7
    assert private.private_note == "Owner note"
    assert private.private_reminder_at == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert private.reminder_due is True
    assert private.needs_attention is True
    for task_id in ("default", "wrong-space"):
        record = by_id[task_id]
        assert record.private_bucket == "later"
        assert record.private_sort_rank == 0
        assert record.private_note is None
        assert record.private_reminder_at is None
        assert record.reminder_due is False
        assert record.needs_attention is False
    for record in records:
        assert record.program_id == "health-program"
        assert (record.program_name, record.project_name, record.solution_name) == ("Program", "Project", "Solution")
    assert by_id["default"].task.effective_github_repo_url == "https://github.com/example/inherited"
    assert by_id["wrong-space"].task.effective_github_repo_url == "https://github.com/example/override"
    assert len(statements) == 1


def test_repository_inventory_reuses_joined_hierarchy_context(db_sessionmaker):
    actor, space_ctx = _seed_work(db_sessionmaker)
    with _select_statements(db_sessionmaker) as statements, db_sessionmaker() as session:
        records = list_repository_inventory(session=session, space_ctx=space_ctx, _current_user=actor)

    assert [record.repository_name for record in records] == ["example/inherited", "example/override"]
    inherited, override = records
    assert (inherited.task_count, inherited.solution_count) == (3, 1)
    assert (inherited.solution_attachment_count, inherited.task_override_count) == (1, 0)
    assert (override.task_count, override.solution_count) == (1, 1)
    assert (override.solution_attachment_count, override.task_override_count) == (0, 1)
    for record in records:
        assert record.program_names == ["Program"]
        assert record.project_names == ["Project"]
        assert record.solution_names == ["Solution"]
        assert record.last_updated_at is not None
    assert len(statements) == 2
