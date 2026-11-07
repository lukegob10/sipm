from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.dialects import oracle

from backend.app.models import Space, SpaceAccessRequest, SpaceMembership, User
from backend.app.routes import spaces
from backend.app.services.spaces import SpaceContext


def _seed(session):
    session.add_all([
        User(user_id="requester", soeid="requester", email="requester@example.com",
             display_name="Requester", password_hash="unused", role="user", is_active=True),
        User(user_id="reviewer", soeid="reviewer", email="reviewer@example.com",
             display_name="Reviewer", password_hash="unused", role="global_admin", is_active=True),
        Space(space_id="space", name="Space", slug="space", space_kind="collaboration", is_active=True),
        SpaceAccessRequest(request_id="request", space_id="space", requester_user_id="requester",
                           requested_role="member", status="pending"),
    ])
    session.commit()


def _decide(session, action):
    actor = session.get(User, "requester" if action == "cancel" else "reviewer")
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
    if action == "cancel":
        return spaces.cancel_space_access_request("request", session=session, current_user=actor, _ctx=ctx)
    handler = spaces.approve_space_access_request if action == "approve" else spaces.reject_space_access_request
    return handler("request", payload=None, session=session, current_user=actor, ctx=ctx)


@pytest.mark.parametrize("winner,loser", [
    ("approve", "reject"), ("reject", "approve"),
    ("approve", "cancel"), ("cancel", "approve"),
])
def test_decision_loser_cannot_overwrite_first_committed_decision(db_sessionmaker, winner, loser):
    with db_sessionmaker() as session:
        _seed(session)
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("This concurrency test uses SQLite as a local proxy")

    winner_claimed = Event()
    loser_attempted = Event()
    release_winner = Event()

    def is_decision_update(statement):
        return (statement.lstrip().upper().startswith("UPDATE")
                and SpaceAccessRequest.__tablename__.lower() in statement.lower())

    def run(action, is_winner):
        with db_sessionmaker() as session:
            connection = session.connection()

            def before_execute(_conn, _cursor, statement, _params, _context, _many):
                if not is_winner and statement.lstrip().upper().startswith("UPDATE"):
                    loser_attempted.set()

            def after_execute(_conn, _cursor, statement, _params, _context, _many):
                if is_winner and is_decision_update(statement):
                    winner_claimed.set()
                    if not release_winner.wait(timeout=10):
                        raise RuntimeError("Timed out waiting for competing decision")

            event.listen(connection, "before_cursor_execute", before_execute)
            event.listen(connection, "after_cursor_execute", after_execute)
            try:
                try:
                    result = _decide(session, action)
                    return 200, result.status
                except HTTPException as exc:
                    return exc.status_code, exc.detail
            finally:
                event.remove(connection, "before_cursor_execute", before_execute)
                event.remove(connection, "after_cursor_execute", after_execute)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(run, winner, True)
        try:
            assert winner_claimed.wait(timeout=10)
            second = executor.submit(run, loser, False)
            assert loser_attempted.wait(timeout=10)
        finally:
            release_winner.set()
        first_result, second_result = first.result(timeout=15), second.result(timeout=15)

    winner_status = {"approve": "approved", "reject": "rejected", "cancel": "canceled"}[winner]
    loser_status = {"approve": "approved", "reject": "rejected", "cancel": "canceled"}[loser]
    assert first_result == (200, winner_status)
    assert second_result == (400, f"Only pending requests can be {loser_status}")
    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "request").status == winner_status
        membership_count = session.query(SpaceMembership).filter_by(space_id="space", user_id="requester").count()
        assert membership_count == (1 if winner == "approve" else 0)


def test_decision_update_compiles_for_oracle_with_pending_guard(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed(session)
        request = session.get(SpaceAccessRequest, "request")
        statements = []

        def capture(state):
            if state.is_update:
                statements.append(state.statement)

        event.listen(session, "do_orm_execute", capture)
        spaces._decide_pending_request(session, request, decision="approved", actor_user_id="reviewer")
        assert len(statements) == 1
        sql = str(statements[0].compile(dialect=oracle.dialect(), compile_kwargs={"literal_binds": True}))
        sql = " ".join(sql.replace('"', "").lower().split())
        assert "where tb_ta_pm_space_access_requests.request_id = 'request'" in sql
        assert "tb_ta_pm_space_access_requests.status = 'pending'" in sql
        session.rollback()
