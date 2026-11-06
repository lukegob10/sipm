from concurrent.futures import ThreadPoolExecutor
from threading import Event, local

import pytest

from backend.app.models import Space, SpaceAccessRequest, User
from backend.app.routes import spaces
from backend.app.schemas import SpaceAccessRequestCreate
from backend.app.services.spaces import SpaceContext


def test_concurrent_duplicate_requests_return_one_pending_request(db_sessionmaker, monkeypatch):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("This concurrency test uses SQLite as a local proxy")
    with db_sessionmaker() as session:
        session.add_all([
            User(user_id="requester", soeid="requester", email="requester@example.com",
                 display_name="Requester", password_hash="unused", role="user", is_active=True),
            Space(space_id="target", name="Target", slug="target", space_kind="collaboration", is_active=True),
        ])
        session.commit()

    first_locked = Event()
    second_attempted = Event()
    release_first = Event()
    thread_state = local()
    original_lock = spaces.lock_space_admin_spaces

    def controlled_lock(session, space_ids):
        if not thread_state.first:
            second_attempted.set()
        result = original_lock(session, space_ids)
        if thread_state.first:
            first_locked.set()
            if not release_first.wait(timeout=10):
                raise RuntimeError("Timed out waiting for competing request")
        return result

    monkeypatch.setattr(spaces, "lock_space_admin_spaces", controlled_lock)

    def create(first):
        thread_state.first = first
        with db_sessionmaker() as session:
            user = session.get(User, "requester")
            ctx = SpaceContext(space_id="home", space_name="Home", is_global_admin=False, space_role="member")
            return spaces.request_space_access(
                "target", SpaceAccessRequestCreate(), session=session, current_user=user, _ctx=ctx,
            ).request_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(create, True)
        try:
            assert first_locked.wait(timeout=2), "Request creation did not lock the target space"
            second = executor.submit(create, False)
            assert second_attempted.wait(timeout=5)
            assert not second.done()
        finally:
            release_first.set()
        assert first.result(timeout=10) == second.result(timeout=10)

    with db_sessionmaker() as session:
        assert session.query(SpaceAccessRequest).filter_by(
            space_id="target", requester_user_id="requester", status="pending",
        ).count() == 1
