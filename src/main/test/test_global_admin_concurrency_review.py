from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import oracle

from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import users as users_routes
from backend.app.schemas import UserUpdate
from backend.app.services import user_admin_guards
from backend.app.services.spaces import SpaceContext


def test_global_admin_guard_uses_ordered_oracle_row_locks():
    statement = user_admin_guards._global_admin_lock_statement()
    sql = " ".join(str(statement.compile(
        dialect=oracle.dialect(), compile_kwargs={"literal_binds": True},
    )).replace('"', "").split()).lower()
    assert "where" in sql and "'global_admin'" in sql
    assert sql.endswith("order by tb_ta_pm_users.user_id asc for update")


def test_deactivation_reloads_role_after_concurrent_promotion(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(User(
            user_id="promoted", soeid="promoted", email="promoted@example.com",
            display_name="Promoted", password_hash="unused", role="user", is_active=True,
        ))
        session.commit()

    with db_sessionmaker() as stale_session:
        target = stale_session.get(User, "promoted")
        assert target.role == "user"
        with db_sessionmaker() as competing_session:
            user = competing_session.get(User, "promoted")
            user.role = "global_admin"
            competing_session.commit()
        with pytest.raises(HTTPException, match="At least one active global_admin is required"):
            user_admin_guards.ensure_user_can_be_deactivated(stale_session, target)


@pytest.mark.parametrize("by_soeid", [False, True])
def test_space_admin_cannot_deactivate_user_promoted_after_initial_read(db_sessionmaker, by_soeid):
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        for user_id, role in [("target", "user"), ("admin", "global_admin")]:
            session.add(User(
                user_id=user_id, soeid=user_id, email=f"{user_id}@example.com", display_name=user_id,
                password_hash="unused", role=role, is_active=True,
            ))
        session.add(SpaceMembership(space_id="space", user_id="target", role="member", status="active"))
        session.commit()

    with db_sessionmaker() as stale_session:
        stale_target = stale_session.get(User, "target")
        assert stale_target.role == "user"
        with db_sessionmaker() as competing_session:
            current = competing_session.get(User, "target")
            current.role = "global_admin"
            competing_session.commit()
        ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="space_admin")
        update = users_routes.update_user_by_soeid if by_soeid else users_routes.update_user
        with pytest.raises(HTTPException) as exc:
            update(
                "target", UserUpdate(is_active=False), session=stale_session, space_ctx=ctx,
                current_user=SimpleNamespace(user_id="actor", role="user"), _authz=ctx,
            )
        assert exc.value.status_code == 403

    with db_sessionmaker() as session:
        assert session.get(User, "target").is_active is True


@pytest.mark.parametrize("operations", [("demote", "demote"), ("demote", "deactivate"), ("deactivate", "deactivate")])
def test_concurrent_admin_removals_retain_one_active_global_admin(db_sessionmaker, monkeypatch, operations):
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        for index in range(2):
            session.add(User(
                user_id=f"admin-{index}", soeid=f"admin{index}", email=f"admin{index}@example.com",
                display_name=f"Admin {index}", password_hash="unused", role="global_admin", is_active=True,
            ))
            session.add(SpaceMembership(space_id="space", user_id=f"admin-{index}", role="member", status="active"))
        session.commit()

    first_counted = Event()
    release_first = Event()
    second_started = Event()
    second_counted = Event()
    real_count = user_admin_guards.count_active_global_admins

    def count_then_pause_first(session):
        count = real_count(session)
        if session.info["mutation_index"] == 0:
            first_counted.set()
            assert release_first.wait(timeout=10)
        else:
            second_counted.set()
        return count

    monkeypatch.setattr(users_routes, "_count_active_global_admins", count_then_pause_first)
    monkeypatch.setattr(user_admin_guards, "count_active_global_admins", count_then_pause_first)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
    actor = SimpleNamespace(user_id="admin-0", role="global_admin")

    def remove_admin(index):
        with db_sessionmaker() as session:
            session.info["mutation_index"] = index
            if index == 1:
                second_started.set()
            try:
                if operations[index] == "demote":
                    users_routes.revoke_global_admin_by_user_id(f"admin-{index}", session=session, admin_user=actor)
                else:
                    users_routes.update_user(
                        f"admin-{index}", UserUpdate(is_active=False), session=session,
                        space_ctx=ctx, current_user=actor, _authz=ctx,
                    )
            except HTTPException as exc:
                session.rollback()
                return exc.status_code, exc.detail
            return 200, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(remove_admin, 0)
        second = None
        try:
            assert first_counted.wait(timeout=10)
            second = executor.submit(remove_admin, 1)
            assert second_started.wait(timeout=10)
            # A guarded second request waits for the first transaction. On the
            # old path both requests count two admins before either commits.
            second_counted.wait(timeout=0.5)
        finally:
            release_first.set()
        results = [first.result(timeout=10), second.result(timeout=10)]

    assert sorted(results, key=lambda value: value[0]) == [
        (200, None), (400, "At least one active global_admin is required"),
    ]
    with db_sessionmaker() as session:
        assert real_count(session) == 1
