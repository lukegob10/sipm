from __future__ import annotations

import pytest

from backend.app.models import Task
from backend.app.services.agent_pagination import decode_position_cursor, encode_position_cursor
from test_agent_api import _auth_headers, _seed_work_graph, agent_client, override_db_only  # noqa: F401


@pytest.mark.anyio
async def test_assigned_work_blank_name_cursor_round_trips_and_rejects_malformed_positions(agent_client, db_sessionmaker):  # noqa: F811
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("Oracle represents empty strings as NULL")
    token, space_id, _, _, project_id, solution_id, task_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        task = session.get(Task, task_id)
        task.task_name = ""
        task.assignee_user_soeid = "review-worker"
        task.blocked = True
        session.add(Task(space_id=space_id, project_id=project_id, solution_id=solution_id,
                         task_name="Next", assignee_user_soeid="review-worker", status="to_do"))
        session.commit()
    path = "/project-manager/api/agent/assigned-work"
    headers = _auth_headers(token, space_id)
    params = {"assignee_user_soeid": "review-worker", "limit": 1}
    first = await agent_client.get(path, headers=headers, params=params)
    assert first.status_code == 200, first.text
    assert first.json()["records"][0]["task"]["task_id"] == task_id
    cursor = first.json()["next_cursor"]
    assert cursor
    second = await agent_client.get(path, headers=headers, params={**params, "cursor": cursor})
    assert second.status_code == 200, second.text
    assert second.json()["records"][0]["task"]["task_name"] == "Next"

    filters = {"space_id": space_id, "assignee_user_soeid": "review-worker"}
    position = decode_position_cursor(cursor, scope="agent_assigned_work_v1", filters=filters)
    for changes in ({"task_name": None}, {"task_name": 123}, {"task_id": ""}, {"task_id": None}):
        bad = encode_position_cursor(scope="agent_assigned_work_v1", filters=filters, position={**position, **changes})
        response = await agent_client.get(path, headers=headers, params={**params, "cursor": bad})
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "INVALID_CURSOR"
