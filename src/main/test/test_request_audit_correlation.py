from __future__ import annotations

import pytest

from backend.app.models import ChangeLog


@pytest.mark.anyio
async def test_projects_import_reuses_inbound_request_id_for_audit_rows(client, db_sessionmaker):
    request_id = "req-project-import-1"
    csv_text = "\n".join(
        [
            "project_name,status,description,success_criteria,sponsor",
            "Request Scoped Project,active,Desc,Criteria,Finance",
        ]
    )

    response = await client.post(
        "/project-manager/api/projects/import",
        content=csv_text.encode("utf-8"),
        headers={"Content-Type": "text/csv", "X-Request-ID": request_id},
    )
    assert response.status_code == 200, response.text

    with db_sessionmaker() as session:
        rows = (
            session.query(ChangeLog)
            .filter(ChangeLog.request_id == request_id)
            .filter(ChangeLog.entity_type == "project")
            .all()
        )
    assert rows
    assert {row.request_id for row in rows} == {request_id}


@pytest.mark.anyio
async def test_subcomponent_batch_update_reuses_inbound_request_id_for_audit_rows(client, db_sessionmaker):
    project_resp = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Audit Batch Project", "sponsor": "Finance"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    solution_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Audit Batch Solution", "version": "1.0.0", "owner": "Owner"},
    )
    assert solution_resp.status_code == 201, solution_resp.text
    solution = solution_resp.json()

    sub_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={"subcomponent_name": "Audit Batch Task", "status": "to_do", "assignee": "Engineer"},
    )
    assert sub_resp.status_code == 201, sub_resp.text
    subcomponent = sub_resp.json()

    request_id = "req-subcomponent-batch-1"
    batch_resp = await client.patch(
        "/project-manager/api/subcomponents/actions/batch",
        json={"subcomponent_ids": [subcomponent["subcomponent_id"]], "status": "in_progress"},
        headers={"X-Request-ID": request_id},
    )
    assert batch_resp.status_code == 200, batch_resp.text

    with db_sessionmaker() as session:
        rows = (
            session.query(ChangeLog)
            .filter(ChangeLog.request_id == request_id)
            .filter(ChangeLog.entity_type == "subcomponent")
            .all()
        )
    assert rows
    assert any(row.entity_id == subcomponent["subcomponent_id"] for row in rows)
