from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.ai import orchestrator, tools
from backend.app.models import (
    AIQueryMetric,
    AIToolCall,
    Project,
    ProjectCardDigest,
    Solution,
    Subcomponent,
)
from backend.app.utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus


def test_list_project_cards_supports_packed_rows_and_cursor(db_sessionmaker):
    with db_sessionmaker() as session:
        p1 = Project(project_name="Atlas", status=ProjectStatus.active, sponsor="User A")
        p2 = Project(project_name="Beacon", status=ProjectStatus.not_started, sponsor="User B")
        p3 = Project(project_name="Comet", status=ProjectStatus.on_hold, sponsor="User C")
        session.add_all([p1, p2, p3])
        session.commit()

        s1 = Solution(project_id=p1.project_id, solution_name="Atlas API", version="0.1.0", status=SolutionStatus.active)
        session.add(s1)
        session.commit()

        t1 = Subcomponent(
            project_id=p1.project_id,
            solution_id=s1.solution_id,
            subcomponent_name="Auth Flow",
            status=SubcomponentStatus.in_progress,
            blocked=False,
        )
        session.add(t1)
        session.commit()

        first = tools.list_project_cards(session, limit=2, response_format="packed")
        assert first.get("entity_type") == "project"
        assert first.get("count") == 2
        assert first.get("has_more") is True
        assert first.get("next_cursor")
        packed = first.get("cards") or {}
        assert packed.get("encoding") == "packed_rows_v1"
        assert len(packed.get("rows") or []) == 2

        second = tools.list_project_cards(
            session,
            limit=2,
            cursor=first.get("next_cursor"),
            response_format="packed",
        )
        assert second.get("count") >= 1


def test_get_entity_fields_returns_requested_subset_only(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(
            project_name="Delta",
            status=ProjectStatus.active,
            sponsor="Owner",
            description="Project description",
            priority=2,
        )
        session.add(project)
        session.commit()

        result = tools.get_entity_fields(
            session,
            "project",
            project.project_id,
            fields=["project_name", "status", "priority", "not_a_real_field"],
        )
        assert result.get("field_pack") == "custom"
        assert result.get("fields") == ["project_name", "status", "priority"]
        data = result.get("data") or {}
        assert set(data.keys()) == {"project_name", "status", "priority"}


def test_get_entity_deltas_uses_incremental_cursor(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(project_name="Echo", status=ProjectStatus.active, sponsor="Owner")
        session.add(project)
        session.commit()

        solution = Solution(
            project_id=project.project_id,
            solution_name="Echo Service",
            version="0.1.0",
            status=SolutionStatus.active,
        )
        session.add(solution)
        session.commit()

        task = Subcomponent(
            project_id=project.project_id,
            solution_id=solution.solution_id,
            subcomponent_name="Implement endpoint",
            status=SubcomponentStatus.to_do,
            blocked=False,
        )
        session.add(task)
        session.commit()

        since = (datetime.now(timezone.utc) - timedelta(days=1)).replace(tzinfo=None).isoformat()
        first = tools.get_entity_deltas(
            session,
            since_cursor=since,
            entity_types=["solution", "subcomponent"],
            project_id=project.project_id,
            limit=20,
            field_pack="minimal",
        )
        assert first.get("count", 0) >= 2
        assert first.get("next_cursor")
        items = first.get("items") or []
        assert any(item.get("entity_type") == "solution" for item in items)
        assert any(item.get("entity_type") == "subcomponent" for item in items)

        second = tools.get_entity_deltas(
            session,
            since_cursor=first.get("next_cursor"),
            entity_types=["solution", "subcomponent"],
            project_id=project.project_id,
            limit=20,
            field_pack="minimal",
        )
        assert second.get("count") == 0


def test_search_entities_can_return_cards(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(project_name="Foxtrot", status=ProjectStatus.active, sponsor="Owner")
        session.add(project)
        session.commit()

        solution = Solution(
            project_id=project.project_id,
            solution_name="Foxtrot Data Sync",
            version="0.1.0",
            status=SolutionStatus.not_started,
        )
        session.add(solution)
        session.commit()

        result = tools.search_entities(
            session,
            query="Foxtrot Data",
            entity_types=["solution"],
            limit=5,
            return_mode="cards",
            fields=["solution_id", "solution_name", "status"],
            response_format="objects",
        )
        assert result.get("mode") == "cards"
        rows = result.get("results") or []
        assert len(rows) == 1
        card = rows[0].get("card") or {}
        assert set(card.keys()) == {"solution_id", "solution_name", "status"}


def test_search_entities_matches_natural_project_phrase(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(project_name="GenAI MRM Document Reviewer Assistant", status=ProjectStatus.active, sponsor="Owner")
        session.add(project)
        session.commit()

        result = tools.search_entities(
            session,
            query="use the MRM project",
            entity_types=["project"],
            limit=5,
        )
        rows = result.get("results") or []
        assert len(rows) == 1
        assert rows[0].get("entity_type") == "project"
        assert rows[0].get("entity_id") == project.project_id


def test_orchestrator_dispatches_new_card_tool(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(project_name="Gamma", status=ProjectStatus.active, sponsor="Owner")
        session.add(project)
        session.commit()

        state = {
            "pending_tool": {"tool": "list_project_cards", "args": {"limit": 1, "response_format": "objects"}},
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": None,
            "trace_enabled": False,
        }
        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is not True
        context = updates.get("context") or {}
        assert "project_cards" in context


def test_orchestrator_dispatches_usage_guide_tool(db_sessionmaker):
    with db_sessionmaker() as session:
        state = {
            "pending_tool": {
                "tool": "explain_app_usage",
                "args": {"question": "How do I grant global admin access?", "max_sections": 3},
            },
            "messages": [],
            "steps": 0,
            "trace_enabled": False,
            "context": {"contracts": orchestrator.contract_hints()},
        }
        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is not True
        assert updates.get("requires_approval") is not True
        context = updates.get("context") or {}
        guide = context.get("usage_guide") or {}
        assert guide.get("mode") == "usage_rag_context"
        assert "global admin" in str(guide.get("guide_context") or "").lower()


def test_list_project_cards_populates_digest_table(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(project_name="Hydra", status=ProjectStatus.active, sponsor="Owner")
        session.add(project)
        session.commit()

        result = tools.list_project_cards(session, limit=5, response_format="objects")
        assert result.get("count") == 1

        digests = session.query(ProjectCardDigest).all()
        assert len(digests) == 1
        assert digests[0].project_id == project.project_id
        assert digests[0].project_name == "Hydra"


def test_tool_and_query_telemetry_is_recorded(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        project = Project(project_name="Ion", status=ProjectStatus.active, sponsor="Owner")
        session.add(project)
        session.commit()

        state = {
            "pending_tool": {"tool": "list_project_cards", "args": {"limit": 1, "response_format": "objects"}},
            "messages": [],
            "steps": 0,
            "entity_type": None,
            "entity_id": None,
            "project_id": None,
            "trace_enabled": False,
            "context": {"contracts": orchestrator.contract_hints()},
            "current_user": {"display_name": "Test User", "soeid": "tu12345"},
        }
        updates = orchestrator._tool_dispatch(state, session)
        assert updates.get("halt") is not True

        tool_row = session.query(AIToolCall).order_by(AIToolCall.created_at.desc()).first()
        assert tool_row is not None
        assert (tool_row.payload_bytes or 0) > 0
        assert (tool_row.output_bytes or 0) > 0
        assert tool_row.drilldown is False

        def fake_safe_call(_system_prompt: str, _user_prompt: str, **_kwargs) -> str:
            return '{"action":"final","reply":"ok","requires_approval":false}'

        monkeypatch.setattr(orchestrator, "_safe_call", fake_safe_call)
        result = orchestrator.run_agentic_chat(
            session,
            {
                "session_id": "session-telemetry",
                "message": "hello",
                "entity_type": "project",
                "entity_id": project.project_id,
                "project_id": project.project_id,
                "current_date": "2026-02-05",
                "current_user": {"display_name": "Test User", "soeid": "tu12345", "user_id": "test-user"},
                "history": [],
            },
        )
        assert result.get("reply") == "ok"

        query_metric = session.query(AIQueryMetric).order_by(AIQueryMetric.created_at.desc()).first()
        assert query_metric is not None
        assert query_metric.session_id == "session-telemetry"
        assert query_metric.bytes_sent >= 0
        assert query_metric.bytes_returned >= 0
