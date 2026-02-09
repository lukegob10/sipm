from __future__ import annotations

import json

import pytest


def _long_markdown(title: str) -> str:
    body = " ".join(["grounded" for _ in range(80)])
    return "\n".join(
        [
            f"# {title}",
            "",
            "## Overview",
            body,
            "",
            "## Problem Statement",
            body,
            "",
            "## Success Criteria",
            body,
            "",
            "## In Scope",
            f"- {body}",
            "",
            "## Out of Scope",
            f"- {body}",
            "",
        ]
    )


async def _create_project(client, name: str) -> str:
    resp = await client.post("/api/projects", json={"project_name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["project_id"]


async def _save_charter_and_plan(client, project_id: str) -> None:
    charter = await client.post(
        "/api/workbench/docs/charter/save",
        json={
            "project_id": project_id,
            "title": "Charter",
            "content": _long_markdown("Project Charter"),
        },
    )
    assert charter.status_code == 200, charter.text

    plan = await client.post(
        "/api/workbench/docs/plan/save",
        json={
            "project_id": project_id,
            "title": "Plan",
            "content": _long_markdown("Project Plan"),
        },
    )
    assert plan.status_code == 200, plan.text


@pytest.mark.anyio
async def test_structure_studio_context_reports_missing_and_present_sources(client):
    project_id = await _create_project(client, "Studio Context Project")

    missing = await client.get(f"/api/workbench/structure-studio/context?project_id={project_id}")
    assert missing.status_code == 200, missing.text
    missing_payload = missing.json()
    assert missing_payload["sufficiency"]["status"] == "insufficient"
    assert "Charter content is missing." in missing_payload["sufficiency"]["missing"]
    assert "Plan content is missing." in missing_payload["sufficiency"]["missing"]

    await _save_charter_and_plan(client, project_id)

    present = await client.get(f"/api/workbench/structure-studio/context?project_id={project_id}")
    assert present.status_code == 200, present.text
    present_payload = present.json()
    assert present_payload["sufficiency"]["status"] == "sufficient"
    assert present_payload["sources"]["charter"]["doc_type"] == "charter"
    assert present_payload["sources"]["plan"]["doc_type"] == "plan"


@pytest.mark.anyio
async def test_structure_studio_generate_uses_llm_output(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    project_id = await _create_project(client, "Studio Generate Project")
    await _save_charter_and_plan(client, project_id)

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return json.dumps(
            {
                "solutions": [
                    {
                        "draft_id": "sol-a",
                        "kind": "solution",
                        "name": "Identity Services",
                        "description": "Consolidate authentication and authorization pathways.",
                        "confidence": "medium",
                    }
                ],
                "subcomponents": [
                    {
                        "draft_id": "sub-a",
                        "kind": "subcomponent",
                        "name": "Token Validation API",
                        "description": "Provide token validation endpoint.",
                        "parent_solution_draft_id": "sol-a",
                    }
                ],
                "assumptions": ["Assumption captured."],
                "warnings": ["Warning captured."],
                "minimal_draft": False,
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    response = await client.post(
        "/api/workbench/structure-studio/generate",
        json={"project_id": project_id, "allow_minimal_on_insufficient": False},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sufficiency"]["status"] == "sufficient"
    assert len(payload["draft"]["solutions"]) == 1
    assert len(payload["draft"]["subcomponents"]) == 1
    assert payload["draft"]["solutions"][0]["name"] == "Identity Services"
    assert payload["draft"]["subcomponents"][0]["parent_solution_draft_id"] == "sol-a"


@pytest.mark.anyio
async def test_structure_studio_generate_passes_decomposition_level_into_prompt(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    project_id = await _create_project(client, "Studio Generate Prompt Level")
    await _save_charter_and_plan(client, project_id)
    seen = {"user_prompt": ""}

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        seen["user_prompt"] = user_prompt
        return json.dumps(
            {
                "solutions": [
                    {
                        "draft_id": "sol-a",
                        "kind": "solution",
                        "name": "Identity Services",
                    }
                ],
                "subcomponents": [
                    {
                        "draft_id": "sub-a",
                        "kind": "subcomponent",
                        "name": "Token Validation API",
                        "parent_solution_draft_id": "sol-a",
                    }
                ],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    response = await client.post(
        "/api/workbench/structure-studio/generate",
        json={
            "project_id": project_id,
            "allow_minimal_on_insufficient": False,
            "decomposition_level": "detailed",
        },
    )
    assert response.status_code == 200, response.text
    assert "\"decomposition_level\": \"detailed\"" in seen["user_prompt"]


@pytest.mark.anyio
async def test_structure_studio_generate_bounds_subcomponents_per_solution_for_simple_mode(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    project_id = await _create_project(client, "Studio Generate Bounded")
    await _save_charter_and_plan(client, project_id)

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return json.dumps(
            {
                "solutions": [
                    {"draft_id": "sol-a", "kind": "solution", "name": "Identity Services"},
                    {"draft_id": "sol-b", "kind": "solution", "name": "Data Governance"},
                ],
                "subcomponents": [
                    {"draft_id": "sub-a1", "kind": "subcomponent", "name": "A1", "parent_solution_draft_id": "sol-a"},
                    {"draft_id": "sub-a2", "kind": "subcomponent", "name": "A2", "parent_solution_draft_id": "sol-a"},
                    {"draft_id": "sub-a3", "kind": "subcomponent", "name": "A3", "parent_solution_draft_id": "sol-a"},
                    {"draft_id": "sub-a4", "kind": "subcomponent", "name": "A4", "parent_solution_draft_id": "sol-a"},
                    {"draft_id": "sub-a5", "kind": "subcomponent", "name": "A5", "parent_solution_draft_id": "sol-a"},
                    {"draft_id": "sub-b1", "kind": "subcomponent", "name": "B1", "parent_solution_draft_id": "sol-b"},
                    {"draft_id": "sub-b2", "kind": "subcomponent", "name": "B2", "parent_solution_draft_id": "sol-b"},
                    {"draft_id": "sub-b3", "kind": "subcomponent", "name": "B3", "parent_solution_draft_id": "sol-b"},
                    {"draft_id": "sub-b4", "kind": "subcomponent", "name": "B4", "parent_solution_draft_id": "sol-b"},
                ],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    response = await client.post(
        "/api/workbench/structure-studio/generate",
        json={
            "project_id": project_id,
            "allow_minimal_on_insufficient": False,
            "decomposition_level": "simple",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    subcomponents = payload["draft"]["subcomponents"]
    counts = {}
    for item in subcomponents:
        parent_id = item.get("parent_solution_draft_id")
        counts[parent_id] = counts.get(parent_id, 0) + 1
    assert counts
    assert all(count <= 3 for count in counts.values())


@pytest.mark.anyio
async def test_structure_studio_refine_filters_targets_and_preserves_locked_fields(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    project_id = await _create_project(client, "Studio Refine Project")

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return json.dumps(
            {
                "operations": [
                    {
                        "op": "update_item_fields",
                        "item_id": "sol-a",
                        "fields": {
                            "name": "Identity Platform",
                            "description": "Updated technical description.",
                        },
                        "reason": "Requested update.",
                    },
                    {
                        "op": "update_item_fields",
                        "item_id": "sol-b",
                        "fields": {"description": "This should be filtered out."},
                        "reason": "Out-of-scope update.",
                    },
                ],
                "warnings": [],
                "assumptions": [],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    response = await client.post(
        "/api/workbench/structure-studio/refine",
        json={
            "project_id": project_id,
            "instruction": "Make this more technical.",
            "target_ids": ["sol-a"],
            "allow_full_regeneration": False,
            "locked_fields_by_item": {"sol-a": ["name"]},
            "draft": {
                "solutions": [
                    {
                        "draft_id": "sol-a",
                        "kind": "solution",
                        "name": "Identity Services",
                        "description": "Initial description.",
                    },
                    {
                        "draft_id": "sol-b",
                        "kind": "solution",
                        "name": "Reporting Services",
                        "description": "Initial description.",
                    },
                ],
                "subcomponents": [],
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["operations"]) == 1
    op = payload["operations"][0]
    assert op["item_id"] == "sol-a"
    assert "name" not in op["fields"]
    assert op["fields"]["description"] == "Updated technical description."
    assert any("Protected user-edited fields" in warning for warning in payload["warnings"])


@pytest.mark.anyio
async def test_structure_studio_refine_binds_single_target_when_model_omits_item_id(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    project_id = await _create_project(client, "Studio Refine Bind Target")

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return json.dumps(
            {
                "operations": [
                    {
                        "op": "update_item_fields",
                        "fields": {"description": "Refined selected item scope."},
                        "reason": "Apply user feedback.",
                    }
                ],
                "warnings": [],
                "assumptions": [],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    response = await client.post(
        "/api/workbench/structure-studio/refine",
        json={
            "project_id": project_id,
            "instruction": "Tighten the selected item scope.",
            "target_ids": ["sol-a"],
            "allow_full_regeneration": False,
            "draft": {
                "solutions": [
                    {
                        "draft_id": "sol-a",
                        "kind": "solution",
                        "name": "Identity Services",
                        "description": "Initial description.",
                    }
                ],
                "subcomponents": [],
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["operations"]) == 1
    op = payload["operations"][0]
    assert op["item_id"] == "sol-a"
    assert op["fields"]["description"] == "Refined selected item scope."


@pytest.mark.anyio
async def test_structure_studio_refine_uses_targeted_heuristic_after_filtered_model_ops(monkeypatch, client):
    from backend.app.routes import workbench as workbench_routes

    project_id = await _create_project(client, "Studio Refine Retry")

    def fake_call_chat_completion(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return json.dumps(
            {
                "operations": [
                    {
                        "op": "update_item_fields",
                        "item_id": "sol-b",
                        "fields": {"description": "Wrong target."},
                        "reason": "Model picked the wrong item.",
                    }
                ],
                "warnings": [],
                "assumptions": [],
            }
        )

    monkeypatch.setattr(workbench_routes, "call_chat_completion", fake_call_chat_completion)

    response = await client.post(
        "/api/workbench/structure-studio/refine",
        json={
            "project_id": project_id,
            "instruction": "Make this more technical.",
            "target_ids": ["sol-a"],
            "allow_full_regeneration": False,
            "draft": {
                "solutions": [
                    {
                        "draft_id": "sol-a",
                        "kind": "solution",
                        "name": "Identity Services",
                        "description": "Initial description.",
                    },
                    {
                        "draft_id": "sol-b",
                        "kind": "solution",
                        "name": "Reporting Services",
                        "description": "Initial description.",
                    },
                ],
                "subcomponents": [],
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["operations"]) == 1
    op = payload["operations"][0]
    assert op["item_id"] == "sol-a"
    assert "Technical focus:" in op["fields"]["description"]
    assert any("deterministic targeted fallback" in warning for warning in payload["warnings"])


@pytest.mark.anyio
async def test_structure_studio_commit_persists_only_accepted_items(client):
    project_id = await _create_project(client, "Studio Commit Project")

    response = await client.post(
        "/api/workbench/structure-studio/commit",
        json={
            "project_id": project_id,
            "draft": {
                "solutions": [
                    {
                        "draft_id": "sol-a",
                        "kind": "solution",
                        "name": "Accepted Solution",
                        "description": "Keep this one.",
                    },
                    {
                        "draft_id": "sol-b",
                        "kind": "solution",
                        "name": "Discarded Solution",
                        "description": "Do not commit this.",
                    },
                ],
                "subcomponents": [
                    {
                        "draft_id": "sub-a",
                        "kind": "subcomponent",
                        "name": "Accepted Subcomponent",
                        "description": "Keep this one.",
                        "parent_solution_draft_id": "sol-a",
                    },
                    {
                        "draft_id": "sub-b",
                        "kind": "subcomponent",
                        "name": "Discarded Subcomponent",
                        "description": "Do not commit this.",
                        "parent_solution_draft_id": "sol-b",
                    },
                ],
            },
            "accepted": {
                "solution_ids": ["sol-a"],
                "subcomponent_ids": ["sub-a"],
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["created_solutions"]) == 1
    assert len(payload["created_subcomponents"]) == 1
    assert payload["discarded_count"] == 2

    solutions = await client.get(f"/api/solutions?project_id={project_id}")
    assert solutions.status_code == 200, solutions.text
    solution_items = solutions.json()
    assert len(solution_items) == 1
    assert solution_items[0]["solution_name"] == "Accepted Solution"

    subcomponents = await client.get(f"/api/subcomponents?project_id={project_id}")
    assert subcomponents.status_code == 200, subcomponents.text
    sub_items = subcomponents.json()
    assert len(sub_items) == 1
    assert sub_items[0]["subcomponent_name"] == "Accepted Subcomponent"
