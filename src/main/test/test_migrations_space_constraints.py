from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.table_names import physical_table_name
from backend.app.models import Base, Project, Space, SpaceMembership, User
from backend.app.services.migrations import run_schema_migrations
from backend.app.utils.enums import ProjectStatus


def _build_sqlite_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


T_PROJECTS = physical_table_name("projects")
T_SPACES = physical_table_name("spaces")
T_SPACE_MEMBERSHIPS = physical_table_name("space_memberships")
T_USERS = physical_table_name("users")


def test_run_schema_migrations_backfills_null_project_space_id():
    engine = _build_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as session:
        session.add(
            Project(
                project_name="Legacy Null Space Project",
                status=ProjectStatus.not_started,
                sponsor="Legacy Sponsor",
                space_id=None,
            )
        )
        session.commit()

    run_schema_migrations(engine)

    with engine.begin() as conn:
        null_count = conn.execute(text(f"SELECT COUNT(*) FROM {T_PROJECTS} WHERE space_id IS NULL")).scalar_one()
    assert null_count == 0


def test_run_schema_migrations_enforces_non_null_project_space_id_for_new_rows():
    engine = _build_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    run_schema_migrations(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with engine.begin() as conn:
        default_space_id = conn.execute(
            text(
                f"SELECT space_id FROM {T_SPACES} "
                "WHERE slug = :slug AND deleted_at IS NULL "
                "ORDER BY created_at ASC LIMIT 1"
            ),
            {"slug": "main"},
        ).scalar_one()

    with SessionLocal() as session:
        session.add(
            Project(
                project_name="Trigger Enforced OK",
                status=ProjectStatus.active,
                sponsor="Sponsor",
                space_id=default_space_id,
            )
        )
        session.commit()

    with SessionLocal() as session:
        session.add(
            Project(
                project_name="Trigger Enforced Reject",
                status=ProjectStatus.active,
                sponsor="Sponsor",
                space_id=None,
            )
        )
        with pytest.raises((IntegrityError, OperationalError)):
            session.commit()
        session.rollback()


def test_run_schema_migrations_reactivates_soft_deleted_default_membership():
    engine = _build_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with SessionLocal() as session:
        user = User(
            soeid="legacy_user",
            email="legacy_user@example.com",
            display_name="Legacy User",
            password_hash="hashed",
            role="member",
        )
        space = Space(name="Main", slug="main", is_active=True)
        session.add_all([user, space])
        session.flush()
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=user.user_id,
                role="member",
                status="inactive",
                deleted_at=now,
            )
        )
        session.commit()

    # Should not raise IntegrityError; migration should reactivate existing membership.
    run_schema_migrations(engine)

    with engine.begin() as conn:
        total = conn.execute(
            text(
                "SELECT COUNT(*) "
                f"FROM {T_SPACE_MEMBERSHIPS} sm "
                f"JOIN {T_SPACES} s ON s.space_id = sm.space_id "
                f"JOIN {T_USERS} u ON u.user_id = sm.user_id "
                "WHERE s.slug = :slug AND u.soeid = :soeid"
            ),
            {"slug": "main", "soeid": "legacy_user"},
        ).scalar_one()
        row = conn.execute(
            text(
                "SELECT sm.role, sm.status, sm.deleted_at "
                f"FROM {T_SPACE_MEMBERSHIPS} sm "
                f"JOIN {T_SPACES} s ON s.space_id = sm.space_id "
                f"JOIN {T_USERS} u ON u.user_id = sm.user_id "
                "WHERE s.slug = :slug AND u.soeid = :soeid"
            ),
            {"slug": "main", "soeid": "legacy_user"},
        ).first()
    assert row is not None
    assert total == 1
    assert row[1] == "active"
    assert row[2] is None
