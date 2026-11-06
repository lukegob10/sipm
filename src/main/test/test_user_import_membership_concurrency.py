from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event, local

import pytest
from fastapi import HTTPException

from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import users
from backend.app.services import user_admin_guards
from backend.app.services.spaces import SpaceContext


def _seed(session, state):
    session.add_all([
        Space(space_id="space", name="Space", slug="space"),
        User(user_id="global", soeid="global", email="global@example.com", display_name="Global",
             password_hash="unused", role="global_admin", is_active=True),
        User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor",
             password_hash="unused", role="user", is_active=True),
        User(user_id="target", soeid="target", email="target@example.com", display_name="Target",
             password_hash="unused", role="user", is_active=True),
    ])
    session.flush()
    session.add(SpaceMembership(space_id="space", user_id="actor", role="space_admin", status="active"))
    if state != "missing":
        session.add(SpaceMembership(
            space_id="space", user_id="target", role="space_admin", status="inactive",
            deleted_at=datetime.now(timezone.utc) if state == "deleted" else None,
        ))
    session.commit()


@pytest.mark.parametrize("state", ["missing", "inactive", "deleted"])
def test_concurrent_imports_preserve_one_membership_and_its_role(db_sessionmaker, monkeypatch, state):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("This concurrency test uses SQLite as a local proxy")
    with db_sessionmaker() as session:
        _seed(session, state)

    first_locked = Event()
    second_attempted = Event()
    release_first = Event()
    thread_state = local()
    original_global = user_admin_guards.lock_global_admin_users
    original_space = user_admin_guards.lock_space_admin_spaces
    lock_order = {True: [], False: []}

    def controlled_global(session):
        lock_order[thread_state.first].append("global")
        if not thread_state.first:
            second_attempted.set()
        result = original_global(session)
        if thread_state.first:
            first_locked.set()
            if not release_first.wait(timeout=10):
                raise RuntimeError("Timed out waiting for competing import")
        return result

    def observed_space(session, space_ids):
        lock_order[thread_state.first].append("space")
        return original_space(session, space_ids)

    monkeypatch.setattr(users, "lock_global_admin_users", controlled_global)
    monkeypatch.setattr(users, "lock_space_admin_spaces", observed_space, raising=False)

    def run(first):
        thread_state.first = first
        with db_sessionmaker() as session:
            actor = session.get(User, "actor")
            ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="space_admin")
            return users.import_users(
                b"soeid,display_name\ntarget,Target\n", dry_run=False, session=session,
                space_ctx=ctx, current_user=actor, _authz=ctx,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(run, True)
        try:
            assert first_locked.wait(timeout=2), "Import did not lock global admins"
            second = executor.submit(run, False)
            assert second_attempted.wait(timeout=5)
            assert not second.done()
        finally:
            release_first.set()
        results = [first.result(timeout=10), second.result(timeout=10)]

    assert all(result["updated"] == 1 for result in results)
    assert lock_order == {True: ["global", "space"], False: ["global", "space"]}
    with db_sessionmaker() as session:
        memberships = session.query(SpaceMembership).filter_by(space_id="space", user_id="target").all()
        assert len(memberships) == 1
        assert memberships[0].status == "active" and memberships[0].deleted_at is None
        assert memberships[0].role == ("member" if state == "missing" else "space_admin")


def test_import_rechecks_admin_authorization_after_lock(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed(session, "missing")
        membership = session.query(SpaceMembership).filter_by(space_id="space", user_id="actor").one()
        membership.role = "member"
        session.commit()
        actor = session.get(User, "actor")
        stale_ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="space_admin")
        with pytest.raises(HTTPException) as error:
            users.import_users(
                b"soeid,display_name\ntarget,Changed\n", dry_run=False, session=session,
                space_ctx=stale_ctx, current_user=actor, _authz=stale_ctx,
            )
        assert error.value.status_code == 403
        session.rollback()
        assert session.get(User, "target").display_name == "Target"
        assert session.query(SpaceMembership).filter_by(space_id="space", user_id="target").count() == 0


def test_import_dry_run_does_not_acquire_write_locks(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        _seed(session, "missing")
        actor = session.get(User, "actor")
        ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="space_admin")
        def unexpected_lock(*_args, **_kwargs):
            raise AssertionError("Dry-run import attempted to acquire a write lock")
        monkeypatch.setattr(users, "lock_global_admin_users", unexpected_lock)
        monkeypatch.setattr(users, "lock_space_admin_spaces", unexpected_lock, raising=False)
        result = users.import_users(
            b"soeid,display_name\ntarget,Changed\n", dry_run=True, session=session,
            space_ctx=ctx, current_user=actor, _authz=ctx,
        )
        assert result["updated"] == 1
        assert session.get(User, "target").display_name == "Target"


@pytest.mark.parametrize("state", ["archived", "deleted"])
def test_import_rejects_space_made_unavailable_before_lock(db_sessionmaker, monkeypatch, state):
    with db_sessionmaker() as session:
        _seed(session, "missing")
        actor = session.get(User, "global")
        ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
        original_lock = users.lock_space_admin_spaces

        def make_unavailable_before_lock(session, space_ids):
            updates = {Space.is_active: False} if state == "archived" else {Space.deleted_at: datetime.now(timezone.utc)}
            session.query(Space).filter_by(space_id="space").update(updates, synchronize_session=False)
            return original_lock(session, space_ids)

        monkeypatch.setattr(users, "lock_space_admin_spaces", make_unavailable_before_lock)
        with pytest.raises(HTTPException) as error:
            users.import_users(
                b"soeid,display_name\ntarget,Changed\n", dry_run=False, session=session,
                space_ctx=ctx, current_user=actor, _authz=ctx,
            )
        assert error.value.status_code == 403
        session.rollback()
        assert session.get(User, "target").display_name == "Target"
        assert session.query(SpaceMembership).filter_by(space_id="space", user_id="target").count() == 0


@pytest.mark.parametrize("state", ["missing", "inactive"])
def test_import_rejects_invalid_actor_even_if_context_is_stale(db_sessionmaker, state):
    from types import SimpleNamespace

    with db_sessionmaker() as session:
        _seed(session, "missing")
        actor_id = "nonexistent" if state == "missing" else "actor"
        if state == "inactive":
            session.get(User, actor_id).is_active = False
            session.commit()
        actor = SimpleNamespace(user_id=actor_id, role="global_admin", is_active=True)
        ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
        with pytest.raises(HTTPException) as error:
            users.import_users(
                b"soeid,display_name\ntarget,Changed\n", dry_run=False, session=session,
                space_ctx=ctx, current_user=actor, _authz=ctx,
            )
        assert error.value.status_code == 403
        session.rollback()
        assert session.get(User, "target").display_name == "Target"
