import pytest
from fastapi import HTTPException

from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import users
from backend.app.schemas import UserUpdate
from backend.app.services import user_admin_guards
from backend.app.services.spaces import SpaceContext


def _user(user_id, *, role="user", is_active=True):
    return User(
        user_id=user_id,
        soeid=user_id,
        email=f"{user_id}@example.test",
        display_name=user_id,
        password_hash="unused",
        role=role,
        is_active=is_active,
    )


@pytest.mark.parametrize("lookup", ["id", "soeid"])
@pytest.mark.parametrize("role", [" Space Admin ", " space-admin ", "  SPACE_ADMIN  "])
def test_user_update_preserves_last_space_admin_with_padded_role(db_sessionmaker, lookup, role):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="health-space", name="Health Space", slug="health-space"),
            _user("actor", role="global_admin"),
            _user("target"),
            SpaceMembership(space_id="health-space", user_id="target", role=role, status="active"),
        ])
        session.commit()
        actor = session.get(User, "actor")
        context = SpaceContext(
            space_id="health-space", space_name="Health Space", is_global_admin=True, space_role="space_admin",
        )
        update = users.update_user if lookup == "id" else users.update_user_by_soeid

        with pytest.raises(HTTPException) as error:
            update(
                "target", UserUpdate(is_active=False), session=session, space_ctx=context,
                current_user=actor, _authz=context,
            )

        assert error.value.status_code == 400
        assert error.value.detail == user_admin_guards.LAST_SPACE_ADMIN_ERROR
        session.rollback()

    with db_sessionmaker() as session:
        assert session.get(User, "target").is_active is True


@pytest.mark.parametrize("backup_active", [True, False])
def test_deactivation_counts_active_space_admin_with_padded_role(db_sessionmaker, backup_active):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="health-space", name="Health Space", slug="health-space"),
            _user("target"),
            _user("backup", is_active=backup_active),
            SpaceMembership(space_id="health-space", user_id="target", role="space_admin", status="active"),
            SpaceMembership(space_id="health-space", user_id="backup", role=" Space Admin ", status="active"),
        ])
        session.commit()
        target = session.get(User, "target")

        if backup_active:
            user_admin_guards.ensure_user_can_be_deactivated(session, target)
            target.is_active = False
            session.commit()
        else:
            with pytest.raises(HTTPException) as error:
                user_admin_guards.ensure_user_can_be_deactivated(session, target)
            assert error.value.detail == user_admin_guards.LAST_SPACE_ADMIN_ERROR
            session.rollback()

    with db_sessionmaker() as session:
        assert session.get(User, "target").is_active is not backup_active


def test_global_admin_queries_include_padded_roles_and_keep_active_filter(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            _user("canonical", role="global_admin"),
            _user("padded", role=" Global Admin "),
            _user("inactive", role=" global-admin ", is_active=False),
            _user("regular"),
        ])
        session.commit()
        actor = session.get(User, "canonical")

        assert user_admin_guards.is_global_admin_user(session.get(User, "padded"))
        assert user_admin_guards.count_active_global_admins(session) == 2
        assert [user.user_id for user in users.list_global_admin_users(
            active_only=True, session=session, _admin=actor,
        )] == ["canonical", "padded"]
        assert [user.user_id for user in users.list_global_admin_users(
            active_only=False, session=session, _admin=actor,
        )] == ["canonical", "inactive", "padded"]
        assert list(session.scalars(user_admin_guards._global_admin_lock_statement())) == [
            "canonical", "inactive", "padded",
        ]


def test_global_admin_can_be_revoked_when_padded_backup_remains(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            _user("target", role="global_admin"),
            _user("backup", role=" Global Admin "),
        ])
        session.commit()
        result = users.revoke_global_admin_by_user_id(
            "target", session=session, admin_user=session.get(User, "backup"),
        )
        assert result.role == "user"

    with db_sessionmaker() as session:
        assert session.get(User, "target").role == "user"
        assert user_admin_guards.count_active_global_admins(session) == 1
