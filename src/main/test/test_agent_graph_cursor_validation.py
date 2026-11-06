from __future__ import annotations

import pytest

from backend.app.models import Project
from test_agent_api import _auth_headers, _seed_work_graph, agent_client, override_db_only  # noqa: F401


@pytest.mark.anyio
async def test_graph_validates_cursor_even_when_status_matches_no_entity(agent_client, db_sessionmaker):  # noqa: F811
    token, space_id, _, _, project_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        original = session.get(Project, project_id)
        session.add(Project(space_id=space_id, program_id=original.program_id, project_name="Second", status="active", sponsor="Sponsor"))
        session.commit()

    path = "/project-manager/api/agent/work-graph"
    headers = _auth_headers(token, space_id)
    first = await agent_client.get(path, headers=headers, params={"status": "active", "limit": 1})
    assert first.status_code == 200, first.text
    cursor = first.json()["next_cursor"]
    assert first.json()["has_more"] is True and cursor

    empty = await agent_client.get(path, headers=headers, params={"status": "unknown-status"})
    assert empty.status_code == 200, empty.text
    assert empty.json()["records"] == []
    for invalid_cursor in (cursor, "not-a-valid-cursor"):
        response = await agent_client.get(path, headers=headers, params={"status": "unknown-status", "cursor": invalid_cursor})
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "INVALID_CURSOR"
