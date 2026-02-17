from __future__ import annotations

import json

from backend.app.ai import orchestrator


def test_tool_error_halts_graph(db_sessionmaker):
    with db_sessionmaker() as session:
        state = {
            "pending_tool": {"tool": "unknown_tool", "args": {}},
            "messages": [],
            "steps": 0,
        }
        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert "AI tool failed" in (updates.get("response") or "")
        assert updates.get("pending_tool") is None


def test_run_agentic_chat_uses_react_rag_for_help_requests(db_sessionmaker, monkeypatch):
    calls = {"agent_step": 0}

    def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
        if trace_label == "agent_step":
            calls["agent_step"] += 1
            if calls["agent_step"] == 1:
                return (
                    '{"action":"tool","tool":"explain_app_usage",'
                    '"args":{"question":"How do I add a user to a space and make them space_admin?","max_sections":6}}'
                )
            return '{"action":"final","reply":"Use Admin > Spaces, pick the space, add SOEID, choose role space_admin, then save.","requires_approval":false}'
        raise AssertionError(f"Unexpected LLM call: {trace_label}")

    monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

    with db_sessionmaker() as session:
        result = orchestrator.run_agentic_chat(
            session,
            {
                "message": "How do I add a user to a space and make them space_admin?",
                "history": [],
                "current_user": {"display_name": "Test User", "soeid": "tu12345"},
            },
        )

    assert calls["agent_step"] >= 2
    assert "admin > spaces" in (result.get("reply") or "").lower()
    assert result.get("requires_approval") is False
    assert result.get("next_action") == "done"


def test_agent_repairs_invalid_json(monkeypatch):
    def fake_safe_call(system_prompt: str, user_prompt: str, **_kwargs) -> str:
        if system_prompt == orchestrator.REPAIR_SYSTEM_PROMPT:
            return '{"action": "final", "reply": "ok", "requires_approval": false}'
        return "not json"

    monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)
    state = {
        "messages": [orchestrator._message_from_role("user", "hi")],
        "steps": 0,
        "halt": False,
    }
    updates = orchestrator._agent_step(state)
    assert updates.get("response") == "ok"
    assert updates.get("last_error") is None


def test_draft_create_solution_resolves_project_reference(db_sessionmaker, monkeypatch):
    from backend.app.models import Project
    from backend.app.utils.enums import ProjectStatus

    with db_sessionmaker() as session:
        project = Project(project_name="MRM Productivity Tool", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
            if trace_label == "extract_references":
                return '{"project_name": "MRM Productivity Tool"}'
            if trace_label == "draft_solution_create":
                return '{"fields": {"solution_name": "Add entitlements"}}'
            raise AssertionError(f"Unexpected LLM call: {trace_label}")

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

        state = {
            "pending_tool": {
                "tool": "draft_create_solution",
                "args": {
                    "instruction": "Create a solution about adding entitlements for the MRM Productivity Tool project.",
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": None,
            "current_date": "2026-02-01",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "solution_create"
        assert updates.get("entity_type") == "project"
        assert updates.get("entity_id") == project.project_id
        assert updates.get("project_id") == project.project_id


def test_draft_create_solution_resolves_for_project_phrase(db_sessionmaker, monkeypatch):
    from backend.app.models import Project
    from backend.app.utils.enums import ProjectStatus

    with db_sessionmaker() as session:
        project = Project(project_name="Feb 2026 AI Deliverables", status=ProjectStatus.not_started, sponsor="Luke")
        session.add(project)
        session.commit()

        def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
            if trace_label == "extract_references":
                return '{"project_name": "Feb 2026 AI Deliverables"}'
            if trace_label == "draft_solution_create":
                return '{"fields": {"solution_name": "Agentic PM Tool Build"}}'
            raise AssertionError(f"Unexpected LLM call: {trace_label}")

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

        state = {
            "pending_tool": {
                "tool": "draft_create_solution",
                "args": {
                    "instruction": "New solution named Agentic PM Tool Build for project Feb 2026 AI Deliverables, status not_started, priority 3.",
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": None,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "solution_create"
        assert updates.get("entity_type") == "project"
        assert updates.get("entity_id") == project.project_id
        assert updates.get("project_id") == project.project_id


def test_draft_create_subcomponent_resolves_solution_reference(db_sessionmaker, monkeypatch):
    from backend.app.models import Project, Solution
    from backend.app.utils.enums import ProjectStatus, SolutionStatus

    with db_sessionmaker() as session:
        project = Project(project_name="MRM Productivity Tool", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        solution = Solution(
            project_id=project.project_id,
            solution_name="Add Entitlements",
            version="0.1.0",
            status=SolutionStatus.active,
        )
        session.add(solution)
        session.commit()

        def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
            if trace_label == "extract_references":
                return '{"solution_name": "Add Entitlements"}'
            if trace_label == "draft_subcomponent_create":
                return '{"fields": {"subcomponent_name": "Entitlement matrix"}}'
            raise AssertionError(f"Unexpected LLM call: {trace_label}")

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

        state = {
            "pending_tool": {
                "tool": "draft_create_subcomponent",
                "args": {
                    "instruction": "Create a subcomponent called Entitlement matrix for solution Add Entitlements.",
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": None,
            "current_date": "2026-02-01",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "subcomponent_create"
        assert updates.get("entity_type") == "solution"
        assert updates.get("entity_id") == solution.solution_id
        assert updates.get("project_id") == project.project_id


def test_followup_answer_is_appended_and_routed_through_agent_step(db_sessionmaker, monkeypatch):
    from backend.app.models import Project
    from backend.app.utils.enums import ProjectStatus

    with db_sessionmaker() as session:
        project = Project(project_name="Data quality", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        seen = []

        def fake_safe_call(system_prompt: str, user_prompt: str, trace=None, trace_label=None):
            seen.append(trace_label or "call")
            if trace_label == "followup_append":
                return '{"append": "Project: Data quality"}'
            if trace_label == "agent_step":
                return '{"action": "tool", "tool": "draft_create_solution", "args": {}}'
            if trace_label == "extract_references":
                return '{"project_name": "Data quality"}'
            if trace_label == "draft_solution_create":
                return '{"fields": {"solution_name": "Data Pipeline"}}'
            return '{"action": "final", "reply": "ok", "requires_approval": false}'

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

        result = orchestrator.run_agentic_chat(
            session,
            {
                "message": "Data quality",
                "entity_type": None,
                "entity_id": None,
                "project_id": None,
                "current_date": "2026-02-02",
                "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
                "history": [
                    {
                        "role": "user",
                        "content": "Create a solution called Data Pipeline. the project is to deliver data.",
                    },
                    {
                        "role": "assistant",
                        "content": "Which project should this solution belong to?",
                    },
                ],
            },
        )

        assert "followup_append" in seen
        assert "agent_step" in seen
        assert "draft_solution_create" in seen
        assert result.get("request_type") == "solution_create"
        assert result.get("requires_approval") is True
        assert result.get("entity_type") == "project"
        assert result.get("entity_id") == project.project_id


def test_run_agentic_chat_builds_fallback_reply_when_entity_selected_and_model_reply_is_empty(db_sessionmaker, monkeypatch):
    from backend.app.models import Project
    from backend.app.utils.enums import ProjectStatus

    with db_sessionmaker() as session:
        project = Project(project_name="GenAI MRM Document Reviewer Assistant", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        agent_calls = {"count": 0}

        def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
            if trace_label == "agent_step":
                agent_calls["count"] += 1
                if agent_calls["count"] == 1:
                    return (
                        '{"action":"tool","tool":"search_entities",'
                        '"args":{"query":"use the MRM project","entity_types":["project"],"limit":5}}'
                    )
                return '{"action":"final","requires_approval":false}'
            raise AssertionError(f"Unexpected LLM call: {trace_label}")

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

        result = orchestrator.run_agentic_chat(
            session,
            {
                "message": "use the MRM project",
                "entity_type": None,
                "entity_id": None,
                "project_id": None,
                "current_date": "2026-02-06",
                "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
                "history": [],
            },
        )

        assert result.get("entity_type") == "project"
        assert result.get("entity_id") == project.project_id
        assert result.get("reply") == (
            "I selected project 'GenAI MRM Document Reviewer Assistant'. What would you like to do next?"
        )


def test_draft_update_parses_simple_due_date_without_llm(db_sessionmaker, monkeypatch):
    from backend.app.models import Project, Solution
    from backend.app.utils.enums import ProjectStatus, SolutionStatus

    with db_sessionmaker() as session:
        project = Project(project_name="MRM Productivity Tool", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        solution = Solution(
            project_id=project.project_id,
            solution_name="Agentic PM Tool Build",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        session.add(solution)
        session.commit()

        # Ensure we don't call the LLM for a simple "set due_date to YYYY-MM-DD" instruction.
        monkeypatch.setattr(orchestrator, "_safe_call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

        state = {
            "pending_tool": {
                "tool": "draft_update",
                "args": {
                    "entity_type": "solution",
                    "entity_id": solution.solution_id,
                    "instruction": "Set due_date to 2026-02-06",
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": project.project_id,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "autofill"
        output = updates.get("output") or ""
        assert "\"due_date\"" in output
        assert "2026-02-06" in output


def test_draft_update_parses_simple_project_status_without_llm(db_sessionmaker, monkeypatch):
    from backend.app.models import Project
    from backend.app.utils.enums import ProjectStatus

    with db_sessionmaker() as session:
        project = Project(project_name="MRM Productivity Tool", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        monkeypatch.setattr(orchestrator, "_safe_call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

        state = {
            "pending_tool": {
                "tool": "draft_update",
                "args": {
                    "entity_type": "project",
                    "entity_id": project.project_id,
                    "instruction": "Set status to on_hold",
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": project.project_id,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "autofill"
        output = updates.get("output") or ""
        assert "\"status\"" in output
        assert "on_hold" in output


def test_draft_update_parses_simple_subcomponent_blocked_without_llm(db_sessionmaker, monkeypatch):
    from backend.app.models import Project, Solution, Subcomponent
    from backend.app.utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus

    with db_sessionmaker() as session:
        project = Project(project_name="MRM Productivity Tool", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        solution = Solution(
            project_id=project.project_id,
            solution_name="Agentic PM Tool Build",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        session.add(solution)
        session.commit()

        sub = Subcomponent(
            project_id=project.project_id,
            solution_id=solution.solution_id,
            subcomponent_name="Task A",
            status=SubcomponentStatus.to_do,
            priority=3,
            blocked=False,
        )
        session.add(sub)
        session.commit()

        monkeypatch.setattr(orchestrator, "_safe_call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

        state = {
            "pending_tool": {
                "tool": "draft_update",
                "args": {
                    "entity_type": "subcomponent",
                    "entity_id": sub.subcomponent_id,
                    "instruction": "Set blocked to true",
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": project.project_id,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "autofill"
        output = updates.get("output") or ""
        assert "\"blocked\"" in output
        assert "true" in output.lower()


def test_draft_update_expands_bulk_project_updates(db_sessionmaker, monkeypatch):
    from backend.app.models import Project
    from backend.app.utils.enums import ProjectStatus

    with db_sessionmaker() as session:
        p1 = Project(project_name="Bulk Project One", status=ProjectStatus.active, sponsor="Luke")
        p2 = Project(project_name="Bulk Project Two", status=ProjectStatus.active, sponsor="Luke")
        session.add_all([p1, p2])
        session.commit()

        monkeypatch.setattr(orchestrator, "_safe_call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

        state = {
            "pending_tool": {
                "tool": "draft_update",
                "args": {
                    "entity_type": "project",
                    "entity_id": p1.project_id,
                    "instruction": "Set status to on_hold",
                },
            },
            "messages": [orchestrator._message_from_role("user", "Please set all projects to on_hold")],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": None,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "autofill"
        payload = json.loads(updates.get("output") or "{}")
        assert isinstance(payload.get("updates"), list)
        ids = {item.get("entity_id") for item in payload.get("updates") or []}
        assert p1.project_id in ids
        assert p2.project_id in ids
        assert all(item.get("fields", {}).get("status") == "on_hold" for item in payload.get("updates") or [])


def test_draft_update_expands_bulk_solution_updates_with_project_scope(db_sessionmaker, monkeypatch):
    from backend.app.models import Project, Solution
    from backend.app.utils.enums import ProjectStatus, SolutionStatus

    with db_sessionmaker() as session:
        project = Project(project_name="Scoped Bulk Solution Project", status=ProjectStatus.active, sponsor="Luke")
        other_project = Project(project_name="Other Solution Project", status=ProjectStatus.active, sponsor="Luke")
        session.add_all([project, other_project])
        session.commit()

        s1 = Solution(project_id=project.project_id, solution_name="S1", version="0.1.0", status=SolutionStatus.not_started)
        s2 = Solution(project_id=project.project_id, solution_name="S2", version="0.1.0", status=SolutionStatus.not_started)
        s_other = Solution(
            project_id=other_project.project_id,
            solution_name="S-Other",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        session.add_all([s1, s2, s_other])
        session.commit()

        monkeypatch.setattr(orchestrator, "_safe_call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

        state = {
            "pending_tool": {
                "tool": "draft_update",
                "args": {
                    "entity_type": "solution",
                    "entity_id": s1.solution_id,
                    "project_id": project.project_id,
                    "instruction": "Set owner to Gustavo Rubim",
                },
            },
            "messages": [orchestrator._message_from_role("user", "Set all solutions under this project to Gustavo Rubim")],
            "steps": 0,
            "entity_type": "project",
            "entity_id": project.project_id,
            "project_id": project.project_id,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "autofill"
        payload = json.loads(updates.get("output") or "{}")
        ids = {item.get("entity_id") for item in payload.get("updates") or []}
        assert ids == {s1.solution_id, s2.solution_id}
        assert s_other.solution_id not in ids
        assert all(item.get("fields", {}).get("owner") == "Gustavo Rubim" for item in payload.get("updates") or [])


def test_draft_update_expands_bulk_subcomponent_updates_with_solution_scope(db_sessionmaker, monkeypatch):
    from backend.app.models import Project, Solution, Subcomponent
    from backend.app.utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus

    with db_sessionmaker() as session:
        project = Project(project_name="Scoped Bulk Subcomponent Project", status=ProjectStatus.active, sponsor="Luke")
        session.add(project)
        session.commit()

        solution = Solution(
            project_id=project.project_id,
            solution_name="Subcomponent Scope",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        other_solution = Solution(
            project_id=project.project_id,
            solution_name="Other Scope",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        session.add_all([solution, other_solution])
        session.commit()

        sc1 = Subcomponent(
            project_id=project.project_id,
            solution_id=solution.solution_id,
            subcomponent_name="Task 1",
            status=SubcomponentStatus.to_do,
            priority=3,
            blocked=False,
        )
        sc2 = Subcomponent(
            project_id=project.project_id,
            solution_id=solution.solution_id,
            subcomponent_name="Task 2",
            status=SubcomponentStatus.to_do,
            priority=3,
            blocked=False,
        )
        sc_other = Subcomponent(
            project_id=project.project_id,
            solution_id=other_solution.solution_id,
            subcomponent_name="Task Other",
            status=SubcomponentStatus.to_do,
            priority=3,
            blocked=False,
        )
        session.add_all([sc1, sc2, sc_other])
        session.commit()

        monkeypatch.setattr(orchestrator, "_safe_call", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

        state = {
            "pending_tool": {
                "tool": "draft_update",
                "args": {
                    "entity_type": "subcomponent",
                    "entity_id": sc1.subcomponent_id,
                    "project_id": project.project_id,
                    "instruction": "Set blocked to true",
                },
            },
            "messages": [orchestrator._message_from_role("user", "Please mark all subcomponents as blocked")],
            "steps": 0,
            "entity_type": "solution",
            "entity_id": solution.solution_id,
            "project_id": project.project_id,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "autofill"
        payload = json.loads(updates.get("output") or "{}")
        ids = {item.get("entity_id") for item in payload.get("updates") or []}
        assert ids == {sc1.subcomponent_id, sc2.subcomponent_id}
        assert sc_other.subcomponent_id not in ids
        assert all(item.get("fields", {}).get("blocked") is True for item in payload.get("updates") or [])


def test_draft_subcomponents_resolves_solution_with_project_scope(db_sessionmaker, monkeypatch):
    from backend.app.models import Project, Solution
    from backend.app.utils.enums import ProjectStatus, SolutionStatus

    with db_sessionmaker() as session:
        p1 = Project(project_name="MRM Productivity Tool", status=ProjectStatus.on_hold, sponsor="Luke")
        p2 = Project(project_name="Feb 2026 AI Deliverables", status=ProjectStatus.not_started, sponsor="Luke")
        session.add_all([p1, p2])
        session.commit()

        s1 = Solution(
            project_id=p1.project_id,
            solution_name="Agentic PM Tool Build",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        s2 = Solution(
            project_id=p2.project_id,
            solution_name="Agentic PM Tool Build",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        session.add_all([s1, s2])
        session.commit()

        def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
            if trace_label == "extract_references":
                return '{"project_name": "MRM Productivity Tool", "solution_name": "Agentic PM Tool Build"}'
            if trace_label == "draft_subcomponents":
                return '{"subcomponents":[{"name":"intake","priority":3,"assignee":"lg22254"}]}'
            raise AssertionError(f"Unexpected LLM call: {trace_label}")

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

        state = {
            "pending_tool": {
                "tool": "draft_subcomponents",
                "args": {
                    "instruction": (
                        "Draft subcomponents for solution Agentic PM Tool Build: intake, design, build, test.\n"
                        "Project: MRM Productivity Tool"
                    ),
                },
            },
            "messages": [],
            "steps": 0,
            "entity_type": "project",
            "entity_id": p1.project_id,
            "project_id": p1.project_id,
            "current_date": "2026-02-03",
            "current_user": {"display_name": "Luke Goblirsch", "soeid": "lg22254"},
            "context": {"contracts": orchestrator.contract_hints()},
            "trace_enabled": False,
        }

        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("requires_approval") is True
        assert updates.get("request_type") == "subcomponents"
        assert updates.get("entity_type") == "solution"
        assert updates.get("entity_id") == s1.solution_id
