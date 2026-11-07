from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import spaces
from backend.app.schemas import SpaceUpdate
from backend.app.services.spaces import SpaceContext


def _seed(session, *, global_admin=False):
    session.add_all([
        User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor",
             password_hash="unused", role="global_admin" if global_admin else "user", is_active=True),
        User(user_id="backup", soeid="backup", email="backup@example.com", display_name="Backup",
             password_hash="unused", role="global_admin", is_active=True),
        Space(space_id="space", name="Original", slug="space", space_kind="collaboration",
              is_active=True, public_program_dashboard_enabled=False),
        SpaceMembership(space_id="space", user_id="actor", role="space_admin", status="active"),
    ])
    session.commit()


def _change_after_space_read(monkeypatch, db_sessionmaker, change):
    original = spaces._space_or_404
    changed = False

    def read_then_change(session, space_id):
        nonlocal changed
        row = original(session, space_id)
        if not changed:
            changed = True
            with db_sessionmaker() as concurrent:
                change(concurrent)
                concurrent.commit()
        return row

    monkeypatch.setattr(spaces, "_space_or_404", read_then_change)


@pytest.mark.parametrize("change", ["role", "inactive", "removed"])
def test_dashboard_toggle_rechecks_space_admin_after_membership_change(db_sessionmaker, monkeypatch, change):
    with db_sessionmaker() as session:
        _seed(session)

    def demote(concurrent):
        membership = concurrent.query(SpaceMembership).filter_by(space_id="space", user_id="actor").one()
        if change == "role":
            membership.role = "member"
        elif change == "inactive":
            membership.status = "inactive"
        else:
            membership.deleted_at = datetime.now(timezone.utc)

    _change_after_space_read(monkeypatch, db_sessionmaker, demote)
    with db_sessionmaker() as session:
        actor = session.get(User, "actor")
        ctx = SpaceContext(space_id="space", space_name="Original", is_global_admin=False, space_role="space_admin")
        with pytest.raises(HTTPException) as error:
            spaces.update_space("space", SpaceUpdate(public_program_dashboard_enabled=True),
                                session=session, _current_user=actor, ctx=ctx)
        assert error.value.status_code == 403
        session.rollback()
    with db_sessionmaker() as session:
        assert session.get(Space, "space").public_program_dashboard_enabled is False


def test_global_admin_demotion_cannot_rename_even_if_still_space_admin(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        _seed(session, global_admin=True)

    def demote(concurrent):
        concurrent.get(User, "actor").role = "user"

    _change_after_space_read(monkeypatch, db_sessionmaker, demote)
    with db_sessionmaker() as session:
        actor = session.get(User, "actor")
        ctx = SpaceContext(space_id="space", space_name="Original", is_global_admin=True, space_role="space_admin")
        with pytest.raises(HTTPException) as error:
            spaces.update_space("space", SpaceUpdate(name="Unauthorized"), session=session, _current_user=actor, ctx=ctx)
        assert error.value.status_code == 403
        session.rollback()
    with db_sessionmaker() as session:
        assert session.get(Space, "space").name == "Original"


def test_cannot_enable_public_dashboard_after_concurrent_archive(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        _seed(session, global_admin=True)

    def archive(concurrent):
        space = concurrent.get(Space, "space")
        space.is_active = False
        space.archived_at = datetime.now(timezone.utc)

    _change_after_space_read(monkeypatch, db_sessionmaker, archive)
    with db_sessionmaker() as session:
        actor = session.get(User, "actor")
        ctx = SpaceContext(space_id="space", space_name="Original", is_global_admin=True, space_role="space_admin")
        with pytest.raises(HTTPException) as error:
            spaces.update_space("space", SpaceUpdate(public_program_dashboard_enabled=True),
                                session=session, _current_user=actor, ctx=ctx)
        assert error.value.status_code == 400
        session.rollback()
    with db_sessionmaker() as session:
        space = session.get(Space, "space")
        assert space.is_active is False
        assert space.public_program_dashboard_enabled is False


def test_archive_and_reactivation_preserve_existing_public_setting(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed(session, global_admin=True)
        actor = session.get(User, "actor")
        ctx = SpaceContext(space_id="space", space_name="Original", is_global_admin=True, space_role="space_admin")
        spaces.update_space("space", SpaceUpdate(public_program_dashboard_enabled=True),
                            session=session, _current_user=actor, ctx=ctx)
        archived = spaces.update_space("space", SpaceUpdate(is_active=False), session=session, _current_user=actor, ctx=ctx)
        assert archived.is_active is False and archived.public_program_dashboard_enabled is True
        restored = spaces.update_space("space", SpaceUpdate(is_active=True), session=session, _current_user=actor, ctx=ctx)
        assert restored.is_active is True and restored.public_program_dashboard_enabled is True
