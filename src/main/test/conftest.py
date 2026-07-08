from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
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
from backend.app.models import Base


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
def override_dependencies(db_sessionmaker, test_user):
    clear_cache()

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    def get_test_current_space(request: Request):
        space_id = request.headers.get("X-Space-Id") or "test-space"
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
