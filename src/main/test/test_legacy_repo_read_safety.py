from __future__ import annotations

import pytest

from backend.app.models import Solution, Task
from test_agent_api import _auth_headers, _seed_work_graph, agent_client, override_db_only  # noqa: F401


@pytest.mark.anyio
@pytest.mark.parametrize("task_url,solution_url,expected_source,expected_effective", [
    ("https://malicious.example/owner/repo", "https://github.com/example/valid", "none", None),
    (None, "https://malicious.example/owner/repo", "none", None),
    ("https://github.com/example/valid", "https://malicious.example/owner/repo", "override", "https://github.com/example/valid"),
])
async def test_legacy_invalid_repo_does_not_break_task_and_agent_reads(
    agent_client, db_sessionmaker, task_url, solution_url, expected_source, expected_effective  # noqa: F811
):
    token, space_id, _, _, _, solution_id, task_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        task = session.get(Task, task_id)
        task.github_repo_url = task_url
        task.assignee_user_soeid = "legacy-assignee"
        session.get(Solution, solution_id).github_repo_url = solution_url
        session.commit()
    headers = _auth_headers(token, space_id)
    response = await agent_client.get(
        "/project-manager/api/agent/assigned-work", headers=headers,
        params={"assignee_user_soeid": "legacy-assignee"},
    )
    assert response.status_code == 200, response.text
    agent_task = response.json()["records"][0]["task"]
    assert agent_task["github_repo_url"] == task_url
    assert agent_task["effective_github_repo_url"] == expected_effective
    assert agent_task["repo_source"] == expected_source

    task_response = await agent_client.get(f"/project-manager/api/tasks/{task_id}", headers=headers)
    assert task_response.status_code == 200, task_response.text
    task = task_response.json()
    assert task["github_repo_url"] == task_url
    assert task["effective_github_repo_url"] == expected_effective
    assert task["repo_source"] == expected_source

    graph_response = await agent_client.get(
        "/project-manager/api/agent/work-graph", headers=headers, params={"projection": "full"},
    )
    assert graph_response.status_code == 200, graph_response.text
    graph_tasks = [item for project in graph_response.json()["records"]
                   for solution in project["solutions"] for item in solution["tasks"]]
    graph_task = next(item for item in graph_tasks if item["task_id"] == task_id)
    assert graph_task.get("github_repo_url") == task_url
    assert graph_task.get("effective_github_repo_url") == expected_effective
    assert graph_task["repo_source"] == expected_source
