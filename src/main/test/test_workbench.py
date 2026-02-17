from __future__ import annotations

import json

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.routes import workbench as workbench_routes


@pytest.mark.anyio
async def test_workbench_template_and_charter_revision_flow(client):
    # Create a project
    res = await client.post(
        "/api/projects",
        json={"project_name": "WB Project", "status": "not_started", "priority": 3, "sponsor": "Test User"},
    )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    tpl = await client.get("/api/workbench/templates/charter")
    assert tpl.status_code == 200
    payload = tpl.json()
    assert payload["doc_type"] == "charter"
    assert "## Overview" in payload["template"]
    assert payload["config"]["doc_type"] == "charter"

    latest = await client.get(f"/api/workbench/docs/charter/latest?project_id={project_id}")
    assert latest.status_code == 204

    content = "\n".join(
        [
            "# Project Charter: WB Project",
            "",
            "## Overview",
            "Overview text.",
            "",
            "## Problem Statement",
            "Problem text.",
            "",
            "## Success Criteria",
            "Criteria text.",
            "",
            "## In Scope",
            "- Thing A",
            "",
            "## Out of Scope",
            "- Thing B",
            "",
        ]
    )
    saved = await client.post(
        "/api/workbench/docs/charter/save",
        json={"project_id": project_id, "title": "Charter v1", "content": content},
    )
    assert saved.status_code == 200
    doc = saved.json()
    assert doc["doc_type"] == "charter"
    assert doc["state"] == "draft"
    assert doc["revision_id"]

    latest = await client.get(f"/api/workbench/docs/charter/latest?project_id={project_id}")
    assert latest.status_code == 200
    latest_doc = latest.json()
    assert latest_doc["revision_id"] == doc["revision_id"]

    revs = await client.get(f"/api/workbench/docs/charter/revisions?project_id={project_id}")
    assert revs.status_code == 200
    assert len(revs.json()["revisions"]) == 1

    finalize = await client.post("/api/workbench/docs/charter/finalize", json={"revision_id": doc["revision_id"]})
    assert finalize.status_code == 200
    assert finalize.json()["state"] == "final"


@pytest.mark.anyio
async def test_workbench_delete_revision(client):
    # Create a project
    res = await client.post(
        "/api/projects",
        json={"project_name": "WB Delete Project", "status": "not_started", "priority": 3, "sponsor": "Test User"},
    )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    content = "\n".join(
        [
            "# Project Charter: WB Delete Project",
            "",
            "## Overview",
            "Overview.",
            "",
            "## Problem Statement",
            "Problem.",
            "",
            "## Success Criteria",
            "Criteria.",
            "",
            "## In Scope",
            "- A",
            "",
            "## Out of Scope",
            "- B",
            "",
        ]
    )
    v1 = await client.post("/api/workbench/docs/charter/save", json={"project_id": project_id, "title": "v1", "content": content})
    assert v1.status_code == 200
    v2 = await client.post("/api/workbench/docs/charter/save", json={"project_id": project_id, "title": "v2", "content": content + "\nExtra."})
    assert v2.status_code == 200

    rid1 = v1.json()["revision_id"]
    rid2 = v2.json()["revision_id"]
    assert rid1 != rid2

    # Delete v1
    deleted = await client.delete(f"/api/workbench/docs/charter/revisions/{rid1}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    revs = await client.get(f"/api/workbench/docs/charter/revisions?project_id={project_id}")
    assert revs.status_code == 200
    ids = [r["revision_id"] for r in revs.json()["revisions"]]
    assert rid1 not in ids
    assert rid2 in ids


@pytest.mark.anyio
async def test_workbench_sow_approval_required_for_finalize(client):
    # Create a project
    res = await client.post(
        "/api/projects",
        json={"project_name": "WB SOW Project", "status": "active", "priority": 3, "sponsor": "Test User"},
    )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    content = "\n".join(
        [
            "# Statement of Work (SOW): WB SOW Project",
            "",
            "## Purpose",
            "Purpose text.",
            "",
            "## Scope",
            "Scope text.",
            "",
            "## Deliverables",
            "- Deliverable A",
            "",
            "## Roles & Responsibilities (RACI)",
            "- Sponsor: Test User",
            "",
            "## Timeline & Milestones",
            "- 2026-02-10: Kickoff",
            "",
            "## Acceptance Criteria",
            "Acceptance text.",
            "",
            "## Change Control",
            "Change control text.",
            "",
            "## Approvals",
            "- Sponsor: Test User",
            "",
        ]
    )
    saved = await client.post(
        "/api/workbench/docs/sow/save",
        json={"project_id": project_id, "title": "SOW v1", "content": content},
    )
    assert saved.status_code == 200
    sow = saved.json()

    finalize = await client.post("/api/workbench/docs/sow/finalize", json={"revision_id": sow["revision_id"]})
    assert finalize.status_code == 400
    assert finalize.json()["detail"] == "approval_required"

    approved = await client.post("/api/workbench/docs/sow/approve", json={"revision_id": sow["revision_id"], "note": "OK"})
    assert approved.status_code == 200
    assert approved.json()["approval_state"] == "approved"

    finalize2 = await client.post("/api/workbench/docs/sow/finalize", json={"revision_id": sow["revision_id"]})
    assert finalize2.status_code == 200
    assert finalize2.json()["state"] == "final"


@pytest.mark.anyio
async def test_workbench_checklist_save_and_read(client):
    res = await client.post(
        "/api/projects",
        json={"project_name": "WB Checklist Project", "status": "not_started", "priority": 3, "sponsor": "Test User"},
    )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    save = await client.post(
        "/api/workbench/checklist/save",
        json={"project_id": project_id, "month_key": "2026-02", "items": ["Item A", "Item B"]},
    )
    assert save.status_code == 200
    assert save.json()["saved"] == 2

    read = await client.get(f"/api/workbench/checklist?project_id={project_id}&month_key=2026-02")
    assert read.status_code == 200
    payload = read.json()
    titles = [it["title"] for it in payload["items"]]
    assert titles == ["Item A", "Item B"]


def test_workbench_generate_checklist_prompt_renders_without_format_errors():
    from backend.app.ai.prompt_loader import render_prompt

    rendered = render_prompt(
        "workbench/generate_checklist.md",
        month_key="2026-02",
        project_context_json="{}",
        deltas_json="{}",
    )
    assert '"month": "2026-02"' in rendered


def test_workbench_data_too_large_detector_handles_oracle_error():
    exc = IntegrityError(
        statement='INSERT INTO "TB_TA_PM_SOW_DOCUMENTS" (content) VALUES (:content)',
        params={"content": "x" * 300},
        orig=Exception('ORA-12899: value too large for column "SIPM"."TB_TA_PM_SOW_DOCUMENTS"."CONTENT"'),
    )
    assert workbench_routes._is_data_too_large_integrity_error(exc) is True


def test_workbench_data_too_large_detector_ignores_other_integrity_errors():
    exc = IntegrityError(
        statement='INSERT INTO "TB_TA_PM_PROJECTS" (project_name) VALUES (:project_name)',
        params={"project_name": "Duplicate"},
        orig=Exception("ORA-00001: unique constraint violated"),
    )
    assert workbench_routes._is_data_too_large_integrity_error(exc) is False


@pytest.mark.anyio
async def test_workbench_refine_heavy_retries_gap_fill_for_missing_required_sections(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    created = await client.post(
        "/api/projects",
        json={"project_name": "WB Refine Heavy", "status": "active", "priority": 3, "sponsor": "Test User"},
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    first_pass_content = "\n".join(
        [
            "# Project Charter: WB Refine Heavy",
            "",
            "## Overview",
            "Overview only.",
            "",
        ]
    )
    second_pass_content = "\n".join(
        [
            "# Project Charter: WB Refine Heavy",
            "",
            "## Overview",
            "Overview text.",
            "",
            "## Problem Statement",
            "Problem text.",
            "",
            "## Success Criteria",
            "Criteria text.",
            "",
            "## In Scope",
            "- Scope A",
            "",
            "## Out of Scope",
            "- Scope B",
            "",
        ]
    )

    calls = {"count": 0}

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(
                {
                    "patches": [{"op": "replace_document", "content": first_pass_content}],
                    "summary": "Primary pass",
                    "questions": ["Who is the sponsor?"],
                    "warnings": [],
                }
            )
        return json.dumps(
            {
                "patches": [{"op": "replace_document", "content": second_pass_content}],
                "summary": "Gap-fill pass",
                "questions": [],
                "warnings": [],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    refined = await client.post(
        "/api/workbench/refine",
        json={
            "doc_type": "charter",
            "project_id": project_id,
            "content": first_pass_content,
            "assist_level": "heavy",
        },
    )
    assert refined.status_code == 200, refined.text
    payload = refined.json()
    assert calls["count"] == 2
    patch = payload["patches"][0]
    text = patch["content"]
    assert "## Problem Statement" in text
    assert "## Success Criteria" in text
    assert "## In Scope" in text
    assert "## Out of Scope" in text
    assert payload["questions"] == []


@pytest.mark.anyio
async def test_workbench_refine_light_does_not_retry_gap_fill(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    created = await client.post(
        "/api/projects",
        json={"project_name": "WB Refine Light", "status": "active", "priority": 3, "sponsor": "Test User"},
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    first_pass_content = "\n".join(
        [
            "# Project Charter: WB Refine Light",
            "",
            "## Overview",
            "Overview only.",
            "",
        ]
    )

    calls = {"count": 0}

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        calls["count"] += 1
        return json.dumps(
            {
                "patches": [{"op": "replace_document", "content": first_pass_content}],
                "summary": "Primary pass",
                "questions": ["Need more details"],
                "warnings": [],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    refined = await client.post(
        "/api/workbench/refine",
        json={
            "doc_type": "charter",
            "project_id": project_id,
            "content": first_pass_content,
            "assist_level": "light",
        },
    )
    assert refined.status_code == 200, refined.text
    payload = refined.json()
    assert calls["count"] == 1
    assert payload["questions"] == ["Need more details"]
