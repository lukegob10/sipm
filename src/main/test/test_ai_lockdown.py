from __future__ import annotations

import concurrent.futures
import time
from datetime import datetime, timezone

import pytest

from backend.app.ai import orchestrator, tools
from backend.app.models import AISession, Project, Solution
from backend.app.routes import ai as ai_routes
from backend.app.utils.enums import ProjectStatus, SolutionStatus


def test_load_session_is_scoped_to_user(db_sessionmaker):
    with db_sessionmaker() as session:
        row = AISession(
            session_id="session-1",
            user_id="user-a",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()

        assert ai_routes._load_session(session, "session-1", "user-b") is None
        found = ai_routes._load_session(session, "session-1", "user-a")
        assert found is not None
        assert found.session_id == "session-1"


def test_sanitize_upload_filename_removes_path_segments():
    cleaned = ai_routes._sanitize_upload_filename("../../etc/passwd")
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert ".." not in cleaned
    assert cleaned == "passwd"


def test_tool_catalog_excludes_direct_write_tools():
    names = {entry.get("name") for entry in tools.get_tool_catalog()}
    assert "apply_draft" not in names
    assert "verify_write" not in names
    assert "explain_app_usage" in names


def test_explain_app_usage_returns_detailed_guidance():
    result = tools.explain_app_usage(question="How do I add a user to a space?")
    context = (result.get("guide_context") or "").lower()
    assert result.get("mode") == "usage_rag_context"
    assert "space" in context
    assert "admin" in context
    assert (result.get("retrieval") or {}).get("selected_count", 0) >= 1


def test_tool_dispatch_blocks_direct_write_tools(db_sessionmaker):
    with db_sessionmaker() as session:
        state = {
            "pending_tool": {"tool": "apply_draft", "args": {"entity_type": "project", "action": "update", "fields": {}}},
            "messages": [],
            "steps": 0,
            "trace_enabled": False,
        }
        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is True
        assert updates.get("last_error") == "write_tool_blocked"
        assert "approval" in (updates.get("response") or "").lower()


def test_followup_append_only_runs_for_actual_questions(db_sessionmaker, monkeypatch):
    seen = []

    def fake_safe_call(_sys: str, _usr: str, trace=None, trace_label=None, **_kwargs):
        seen.append(trace_label or "call")
        if trace_label == "agent_step":
            return '{"action": "final", "reply": "ok", "requires_approval": false}'
        return '{"action": "final", "reply": "ok", "requires_approval": false}'

    monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)

    with db_sessionmaker() as session:
        result = orchestrator.run_agentic_chat(
            session,
            {
                "message": "sounds good",
                "history": [
                    {"role": "user", "content": "Create a project called A."},
                    {"role": "assistant", "content": "Saved."},
                ],
                "current_user": {"display_name": "Test User", "soeid": "tu12345"},
            },
        )
        assert result.get("reply") == "ok"
        assert "followup_append" not in seen


def test_validate_draft_rejects_subcomponent_project_solution_mismatch(db_sessionmaker):
    with db_sessionmaker() as session:
        project_a = Project(project_name="P-A", status=ProjectStatus.active, sponsor="User")
        project_b = Project(project_name="P-B", status=ProjectStatus.active, sponsor="User")
        session.add_all([project_a, project_b])
        session.commit()

        solution_b = Solution(
            project_id=project_b.project_id,
            solution_name="S-B",
            version="0.1.0",
            status=SolutionStatus.active,
        )
        session.add(solution_b)
        session.commit()

        result = tools.validate_draft(
            session,
            "subcomponent",
            {
                "project_id": project_a.project_id,
                "solution_id": solution_b.solution_id,
                "subcomponent_name": "Task",
            },
            action="create",
        )
        assert result.get("valid") is False
        assert "solution_project_mismatch" in (result.get("errors") or {}).get("other_errors", [])


def test_safe_call_timeout_is_enforced_without_waiting_for_worker(monkeypatch):
    def slow_call(_system: str, _user: str) -> str:
        time.sleep(1.5)
        return "late"

    monkeypatch.setattr(orchestrator, "call_chat_completion", slow_call)
    monkeypatch.setenv("AI_MODEL_TIMEOUT_SECONDS", "1")
    started = time.monotonic()
    with pytest.raises(concurrent.futures.TimeoutError):
        orchestrator._safe_call("system", "user")
    elapsed = time.monotonic() - started
    # Should fail around the configured timeout, not after the full worker runtime.
    assert elapsed < 1.3
