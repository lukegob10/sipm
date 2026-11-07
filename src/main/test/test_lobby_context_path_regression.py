from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


_HTTP_SCENARIO = r'''
import json
from types import SimpleNamespace
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import deps
from backend.app.models import Base, Project, Space, SpaceMembership, User
from backend.app.paths import API_PREFIX
from backend.app.services.spaces import SpaceContext
from backend.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
factory = sessionmaker(bind=engine, autoflush=False)
with factory() as session:
    session.add_all([
        Space(space_id="lobby", name="Home", slug="home", space_kind="lobby", is_active=True),
        Space(space_id="work", name="Work", slug="work", space_kind="collaboration", is_active=True),
        User(user_id="user", soeid="user", email="user@example.com", display_name="User", password_hash="unused", role="user", is_active=True),
        SpaceMembership(space_id="work", user_id="user", role="member", status="active"),
    ])
    session.commit()

actor = SimpleNamespace(user_id="user", soeid="user", display_name="User", role="user", is_active=True)

def test_db():
    with factory() as session:
        yield session

def test_space(request: Request):
    space_id = request.headers["X-Space-Id"]
    return SpaceContext(space_id=space_id, space_name=space_id, is_global_admin=False,
                        space_role="member", space_kind="lobby" if space_id == "lobby" else "collaboration")

app.dependency_overrides[deps.get_db] = test_db
app.dependency_overrides[deps.require_user] = lambda: actor
app.dependency_overrides[deps.current_user] = lambda: actor
app.dependency_overrides[deps.current_space] = test_space
client = TestClient(app, raise_server_exceptions=False)
lobby = client.post(f"{API_PREFIX}/projects/", headers={"X-Space-Id": "lobby"},
                    json={"project_name": "Blocked"})
work = client.post(f"{API_PREFIX}/projects/", headers={"X-Space-Id": "work"},
                   json={"project_name": "Allowed"})
with factory() as session:
    projects = sorted((project.space_id, project.project_name) for project in session.query(Project).all())
print(json.dumps({"lobby_status": lobby.status_code, "lobby_code": lobby.headers.get("X-Error-Code"),
                  "work_status": work.status_code, "projects": projects}))
'''


@pytest.mark.parametrize("context_path", ["/project-manager", "/alternate", "/MixedCase", "/", "///"])
def test_lobby_work_write_is_blocked_under_configured_context(context_path):
    env = dict(os.environ, ENV="test", SIPM_CONTEXT_PATH=context_path, SIPM_BCRYPT_ROUNDS="4",
               SIPM_COORDINATION_BACKEND="memory")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [sys.executable, "-c", _HTTP_SCENARIO], env=env, check=True, capture_output=True, text=True,
    )
    outcome = json.loads(result.stdout)
    assert outcome == {
        "lobby_status": 400,
        "lobby_code": "LOBBY_SPACE_READ_ONLY",
        "work_status": 201,
        "projects": [["work", "Allowed"]],
    }
