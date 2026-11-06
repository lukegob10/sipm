from __future__ import annotations

import pytest

from backend.app.models import Project, Solution, Task, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import apply_patch_plan
from backend.app.services.spaces import SpaceContext
from test_agent_api import _auth_headers, _seed_work_graph, agent_client, override_db_only  # noqa: F401


@pytest.mark.anyio
@pytest.mark.parametrize(("entity", "fields"), [
    ("solution", {"rag_status": None}),
    ("solution", {"capacity_hours": None}),
    ("solution", {"escalation": "  "}),
    ("solution", {"rag_reason": "  "}),
    ("solution", {"priority": None}),
    ("task", {"capacity_hours": None}),
    ("task", {"blocked": None}),
    ("task", {"blocked": False, "blocker_note": "ignored"}),
    ("project", {"function": " engineering "}),
    ("project", {"area": " engineering "}),
])
async def test_agent_normalized_noops_are_rejected(agent_client, db_sessionmaker, entity, fields):  # noqa: F811
    token, space_id, _, _, project_id, solution_id, task_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        project = session.get(Project, project_id)
        solution = session.get(Solution, solution_id)
        task = session.get(Task, task_id)
        project.function = "engineering"
        project.area = "engineering"
        solution.capacity_hours = 0
        solution.escalation = None
        solution.rag_reason = None
        solution.priority = 3
        task.capacity_hours = 0
        task.blocked = False
        task.blocker_note = None
        session.commit()
        row = {"project": project, "solution": solution, "task": task}[entity]
        updated_at = row.updated_at.isoformat()
        entity_id = getattr(row, f"{entity}_id")
    response = await agent_client.post("/project-manager/api/agent/patches/validate", headers=_auth_headers(token, space_id), json={
        "operations": [{"client_operation_id": "noop", "entity": entity, "op": "update", "id": entity_id,
                        "if_updated_at": updated_at, "fields": fields}]
    })
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["code"] == "NO_CHANGES", response.text


def test_mixed_updates_preserve_material_changes_and_blocker_clearing(db_sessionmaker):
    _, space_id, _, _, _, solution_id, task_id, *_ = _seed_work_graph(db_sessionmaker)
    context = SpaceContext(space_id=space_id, space_name="Space", space_role="member", is_global_admin=False)
    with db_sessionmaker() as session:
        solution = session.get(Solution, solution_id)
        task = session.get(Task, task_id)
        task.blocked = True
        task.blocker_note = "Waiting"
        session.commit()
        actor = session.query(User).filter_by(soeid="svca").one()
        payload = AgentPatchRequest(dry_run=False, reason="Review test", idempotency_key="mixed", operations=[
            {"client_operation_id": "solution", "entity": "solution", "op": "update", "id": solution_id,
             "if_updated_at": solution.updated_at, "fields": {"rag_status": None, "description": "Updated"}},
            {"client_operation_id": "task", "entity": "task", "op": "update", "id": task_id,
             "if_updated_at": task.updated_at, "fields": {"blocked": None}},
        ])
        result = apply_patch_plan(session, context, actor, payload)
        assert result.valid and result.applied, result.model_dump()
        session.refresh(solution)
        session.refresh(task)
        assert solution.description == "Updated"
        assert solution.rag_status.value == "green"
        assert task.blocked is False and task.blocker_note is None
