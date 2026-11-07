from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import httpx
import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MAIN_DIR = Path(__file__).resolve().parents[1]
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SIPM_BCRYPT_ROUNDS", "4")
os.environ.setdefault("SIPM_COORDINATION_BACKEND", "memory")

from backend.app.deps import current_space, current_user, get_db, require_user
from backend.app.services.smart_cache import clear_cache
from backend.app.services.spaces import SpaceContext
from backend.app.services import coordination
from backend.main import app as fastapi_app
from backend.app.models import Base, Space, SpaceMembership, User


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_coordination_runtime():
    asyncio.run(coordination.reset_backend_for_tests())
    yield
    asyncio.run(coordination.reset_backend_for_tests())


@pytest.fixture
def db_sessionmaker(tmp_path):
    db_url = (os.getenv("SIPM_TEST_DATABASE_URL") or "").strip()
    if not db_url:
        db_url = f"sqlite+pysqlite:///{tmp_path / 'sipm-test.db'}"
    engine_kwargs = {}
    if db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(db_url, **engine_kwargs)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def test_user():
    # Keep test requests deterministic while allowing endpoints to default fields
    # (e.g., sponsor/owner/assignee) from the current user.
    return SimpleNamespace(
        user_id="test-user",
        display_name="Test User",
        soeid="tu12345",
        role="global_admin",
        is_active=True,
    )


@pytest.fixture
def seed_space_memberships(db_sessionmaker, test_user):
    def seed(*space_ids):
        with db_sessionmaker() as session:
            if session.get(User, test_user.user_id) is None:
                session.add(User(
                    user_id=test_user.user_id, soeid=test_user.soeid, email="test-user@fixture.invalid",
                    display_name=test_user.display_name, password_hash="unused", role="user", is_active=True,
                ))
            for space_id in space_ids:
                if session.get(Space, space_id) is None:
                    session.add(Space(space_id=space_id, name=space_id, slug=space_id))
                existing = session.query(SpaceMembership).filter_by(space_id=space_id, user_id=test_user.user_id).first()
                if existing is None:
                    session.add(SpaceMembership(space_id=space_id, user_id=test_user.user_id, role="space_admin", status="active"))
            session.commit()
    return seed


@pytest.fixture
def override_dependencies(db_sessionmaker, test_user):
    clear_cache()
    default_space_lock = Lock()
    default_space_ready = False

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    def get_test_current_space(request: Request):
        nonlocal default_space_ready
        space_id = request.headers.get("X-Space-Id") or "test-space"
        if space_id == "test-space" and request.method not in {"GET", "HEAD", "OPTIONS"}:
            with default_space_lock:
                if not default_space_ready:
                    with db_sessionmaker() as session:
                        if session.get(Space, space_id) is None:
                            session.add(Space(space_id=space_id, name="Test Space", slug=space_id))
                        if session.get(User, test_user.user_id) is None:
                            session.add(User(
                                user_id=test_user.user_id,
                                soeid=test_user.soeid,
                                email="test-user@fixture.invalid",
                                display_name=test_user.display_name,
                                password_hash="unused",
                                role="global_admin",
                                is_active=True,
                            ))
                        session.commit()
                    default_space_ready = True
        return SpaceContext(
            space_id=space_id,
            space_name="Test Space",
            space_role="space_admin",
            is_global_admin=True,
        )

    fastapi_app.dependency_overrides[get_db] = get_test_db
    fastapi_app.dependency_overrides[require_user] = lambda: test_user
    fastapi_app.dependency_overrides[current_user] = lambda: test_user
    fastapi_app.dependency_overrides[current_space] = get_test_current_space
    try:
        yield
    finally:
        clear_cache()
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def client(override_dependencies):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client
