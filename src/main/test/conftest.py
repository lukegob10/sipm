from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MAIN_DIR = Path(__file__).resolve().parents[1]
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from backend.app.deps import current_user, get_db, require_user
from backend.main import app as fastapi_app
from backend.app.models import Base


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_sessionmaker():
    db_url = (os.getenv("SIPM_TEST_DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("SIPM_TEST_DATABASE_URL must be set for test database initialization.")
    engine = create_engine(db_url)
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
    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = get_test_db
    fastapi_app.dependency_overrides[require_user] = lambda: test_user
    fastapi_app.dependency_overrides[current_user] = lambda: test_user
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def client(override_dependencies):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client
