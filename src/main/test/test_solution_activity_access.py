from datetime import datetime, timezone

import httpx
import pytest

from backend.app import deps
from backend.app.models import ChangeLog, Solution
from backend.app.services.spaces import SpaceContext
from backend.main import app


@pytest.mark.anyio
async def test_solution_activity_requires_authentication(db_sessionmaker):
    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[deps.get_db] = get_test_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/project-manager/api/solutions/example/activity")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(deps.get_db, None)


@pytest.mark.anyio
async def test_member_can_view_only_current_solution_activity(client, db_sessionmaker):
    project = await client.post("/project-manager/api/projects/", json={"project_name": "Activity Project"})
    assert project.status_code == 201, project.text
    solution = await client.post(
        f"/project-manager/api/projects/{project.json()['project_id']}/solutions",
        json={"solution_name": "Activity Solution"},
    )
    assert solution.status_code == 201, solution.text
    solution_id = solution.json()["solution_id"]
    with db_sessionmaker() as session:
        session.add_all([
            ChangeLog(space_id="other-space", entity_type="solution", entity_id=solution_id,
                      user_id="other", action="update", new_value="other-space secret"),
            ChangeLog(space_id="test-space", entity_type="task", entity_id=solution_id,
                      user_id="other", action="update", new_value="other-entity secret"),
        ])
        session.commit()

    original = app.dependency_overrides[deps.current_space]
    try:
        app.dependency_overrides[deps.current_space] = lambda: SpaceContext(
            space_id="test-space", space_name="Test Space", is_global_admin=False, space_role="member"
        )
        audit = await client.get("/project-manager/api/audit", params={"entity_type": "solution", "entity_id": solution_id})
        assert audit.status_code == 403
        response = await client.get(f"/project-manager/api/solutions/{solution_id}/activity")
        assert response.status_code == 200, response.text
        assert response.json()
        assert all(row["space_id"] == "test-space" and row["entity_type"] == "solution" and row["entity_id"] == solution_id
                   for row in response.json())
        assert "secret" not in response.text
        limited = await client.get(f"/project-manager/api/solutions/{solution_id}/activity", params={"limit": 1})
        assert limited.status_code == 200 and len(limited.json()) == 1
        invalid_limit = await client.get(f"/project-manager/api/solutions/{solution_id}/activity", params={"limit": 501})
        assert invalid_limit.status_code == 422

        app.dependency_overrides[deps.current_space] = lambda: SpaceContext(
            space_id="other-space", space_name="Other", is_global_admin=False, space_role="member"
        )
        assert (await client.get(f"/project-manager/api/solutions/{solution_id}/activity")).status_code == 404

        app.dependency_overrides[deps.current_space] = lambda: SpaceContext(
            space_id="test-space", space_name="Test Space", is_global_admin=False, space_role="member"
        )
        with db_sessionmaker() as session:
            session.get(Solution, solution_id).deleted_at = datetime.now(timezone.utc)
            session.commit()
        assert (await client.get(f"/project-manager/api/solutions/{solution_id}/activity")).status_code == 404
    finally:
        app.dependency_overrides[deps.current_space] = original
