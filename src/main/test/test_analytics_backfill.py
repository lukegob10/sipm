from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.models import PerformanceSample, Space, UsageDailyRollup, UsageEvent, UsageIdentityDailyRollup
from backend.app.routes import analytics
from backend.app.schemas import TelemetryBatchIn
from backend.app.services.analytics_backfill import backfill_usage_rollups
from backend.app.services.spaces import SpaceContext
from backend.app.services.usage_analytics import build_summary_payload


def test_backfill_repairs_partial_coverage_without_double_counting_or_removing_rollup_only_data(db_sessionmaker, monkeypatch):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = datetime.combine(now.date() - timedelta(days=6), datetime.min.time())
    until = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        session.add_all([
            UsageEvent(event_id="legacy", occurred_at=now, received_at=now, session_id="legacy", user_id="user", space_id="space",
                       view_key="master", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"),
            UsageEvent(event_id="old", occurred_at=since - timedelta(seconds=1), received_at=now, session_id="old", user_id="old", space_id="space",
                       view_key="old", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"),
            PerformanceSample(sample_id="legacy-sample", occurred_at=now, received_at=now, session_id="sample", user_id="user", space_id="space",
                              view_key="master", sample_kind="navigation", load_event_ms=100),
            UsageDailyRollup(rollup_date=now.date(), space_id="space", view_key="retained", category="navigation", feature_key="navigation",
                             action_key="route_view", outcome="success", event_count=5, route_view_count=5, workflow_action_count=0,
                             success_count=5, failure_count=0, last_occurred_at=now),
            UsageIdentityDailyRollup(rollup_date=now.date(), space_id="space", token_type="session", token_value="retained"),
        ])
        session.commit()
    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    payload = TelemetryBatchIn(events=[{"occurred_at": now.replace(tzinfo=timezone.utc), "session_id": "new", "view_key": "master",
                                       "category": "navigation", "feature_key": "navigation", "action_key": "route_view", "outcome": "success"}])
    with db_sessionmaker() as session:
        analytics.ingest_usage_analytics(payload, session=session, current_user=SimpleNamespace(user_id="user"), space_ctx=ctx)
    with db_sessionmaker() as session:
        before = build_summary_payload(session, days=7, all_spaces=False, scope_space_id="space")
        assert before["summary"]["route_views"] == 6
        preview = backfill_usage_rollups(session, since=since, until=until)
        assert preview["event_groups_updated"] == 1
        assert preview["identities_created"] == 2
        assert session.query(UsageDailyRollup).filter_by(view_key="master").one().event_count == 1
        session.rollback()
    with db_sessionmaker() as session:
        applied = backfill_usage_rollups(session, since=since, until=until, apply=True)
        session.commit()
        assert applied == preview
        report = build_summary_payload(session, days=7, all_spaces=False, scope_space_id="space")
        assert report["summary"]["route_views"] == 7
        assert report["summary"]["sessions"] == 4
        assert session.query(UsageDailyRollup).filter_by(view_key="retained").one().event_count == 5
        assert session.query(UsageDailyRollup).filter_by(view_key="old").count() == 0
    with db_sessionmaker() as session:
        assert backfill_usage_rollups(session, since=since, until=until, apply=True) == {
            "event_groups_created": 0, "event_groups_updated": 0, "larger_rollups_preserved": 0,
            "identities_created": 0, "route_identities_created": 0,
        }
        session.commit()
        assert build_summary_payload(session, days=7, all_spaces=False, scope_space_id="space")["summary"]["route_views"] == 7


def test_backfill_preserves_existing_larger_group_and_reports_it(db_sessionmaker):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = datetime.combine(now.date() - timedelta(days=1), datetime.min.time())
    until = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    with db_sessionmaker() as session:
        session.add(UsageEvent(event_id="event", occurred_at=now, received_at=now, session_id="session", user_id="user", space_id=None,
                               view_key="master", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"))
        session.add(UsageDailyRollup(rollup_date=now.date(), space_id="__none__", view_key="master", category="navigation", feature_key="navigation",
                                     action_key="route_view", outcome="success", event_count=10, route_view_count=10, workflow_action_count=0,
                                     success_count=10, failure_count=0, last_occurred_at=now))
        session.commit()
        result = backfill_usage_rollups(session, since=since, until=until, apply=True)
        session.commit()
        assert result["larger_rollups_preserved"] == 1
        assert session.query(UsageDailyRollup).one().event_count == 10


def test_backfill_handles_multiple_batches_and_caller_rollback(db_sessionmaker):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = datetime.combine(now.date(), datetime.min.time())
    until = since + timedelta(days=1)
    with db_sessionmaker() as session:
        session.add_all([
            UsageEvent(event_id=f"event-{i}", occurred_at=now, received_at=now, session_id=f"session-{i}", user_id=f"user-{i}",
                       space_id=None, view_key="master", category="navigation", feature_key="navigation", action_key="route_view", outcome="success")
            for i in range(205)
        ])
        session.commit()
        result = backfill_usage_rollups(session, since=since, until=until, apply=True)
        assert result["event_groups_created"] == 1
        assert result["identities_created"] == 410
        assert result["route_identities_created"] == 410
        session.rollback()
    with db_sessionmaker() as session:
        assert session.query(UsageDailyRollup).count() == 0
        assert session.query(UsageIdentityDailyRollup).count() == 0
        result = backfill_usage_rollups(session, since=since, until=until, apply=True)
        session.commit()
        assert result["identities_created"] == 410
        assert session.query(UsageDailyRollup).one().event_count == 205
        assert session.query(UsageIdentityDailyRollup).count() == 410


def test_backfill_requires_complete_utc_day_boundaries(db_sessionmaker):
    import pytest

    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time())
    with db_sessionmaker() as session:
        for since, until in ((today, today), (today + timedelta(hours=1), today + timedelta(days=1)),
                             (today.replace(tzinfo=timezone.utc), (today + timedelta(days=1)).replace(tzinfo=timezone.utc))):
            with pytest.raises(ValueError, match="midnight boundaries"):
                backfill_usage_rollups(session, since=since, until=until, apply=True)


def test_backfill_command_previews_by_default_and_applies_idempotently(db_sessionmaker, monkeypatch, capsys):
    import importlib.util
    import json
    from pathlib import Path

    from backend.app.db import db

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_sessionmaker() as session:
        session.add(UsageEvent(event_id="event", occurred_at=now, received_at=now, session_id="session", user_id="user", space_id=None,
                               view_key="master", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"))
        session.commit()
    monkeypatch.setattr(db, "get_engine", lambda: db_sessionmaker.kw["bind"])
    path = Path(__file__).resolve().parents[3] / "scripts" / "backfill_usage_rollups.py"
    spec = importlib.util.spec_from_file_location("backfill_usage_rollups", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(["--days", "7"])
    preview = json.loads(capsys.readouterr().out)
    assert preview["applied"] is False and preview["event_groups_created"] == 1
    with db_sessionmaker() as session:
        assert session.query(UsageDailyRollup).count() == 0
    module.main(["--days", "7", "--apply"])
    assert json.loads(capsys.readouterr().out)["event_groups_created"] == 1
    module.main(["--days", "7", "--apply"])
    assert json.loads(capsys.readouterr().out)["event_groups_created"] == 0
    with db_sessionmaker() as session:
        assert session.query(UsageDailyRollup).one().event_count == 1


def test_backfill_identity_query_compiles_for_oracle():
    from sqlalchemy import union
    from sqlalchemy.dialects import oracle
    from backend.app.services.analytics_backfill import _event_group_statement, _identity_select

    fake_session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=oracle.dialect()))
    since = datetime(2026, 1, 1)
    until = datetime(2026, 1, 8)
    statement = union(
        _identity_select(fake_session, UsageEvent, "session_id", "session", since=since, until=until, route=False),
        _identity_select(fake_session, PerformanceSample, "session_id", "session", since=since, until=until, route=False),
    )
    sql = str(statement.compile(dialect=oracle.dialect())).upper()
    assert "TRUNC(" in sql
    assert "LENGTH(" in sql
    assert " UNION " in sql
    event_sql = str(_event_group_statement(fake_session, since=since, until=until).compile(dialect=oracle.dialect())).upper()
    assert "TRUNC(" in event_sql
    assert "GROUP BY" in event_sql


def test_backfill_restores_workflow_and_failure_counters(db_sessionmaker):
    from backend.app.services.usage_analytics import build_route_stats_payload

    now = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time()) + timedelta(hours=12)
    since = datetime.combine(now.date(), datetime.min.time())
    until = since + timedelta(days=1)
    with db_sessionmaker() as session:
        session.add_all([
            UsageEvent(event_id=f"event-{i}", occurred_at=now + timedelta(seconds=i), received_at=now, session_id="s", user_id="u", space_id="space",
                       view_key="master", category=category, feature_key=feature, action_key=action, outcome=outcome)
            for i, (category, feature, action, outcome) in enumerate([
                ("workflow", "projects", "create", "success"),
                ("workflow", "projects", "create", "failure"),
                ("navigation", "navigation", "route_view", "failure"),
            ])
        ])
        session.commit()
        backfill_usage_rollups(session, since=since, until=until, apply=True)
        session.commit()
        summary = build_summary_payload(session, days=7, all_spaces=False, scope_space_id="space")["summary"]
        routes = build_route_stats_payload(session, days=7, all_spaces=False, scope_space_id="space")
    assert summary["route_views"] == 1
    assert summary["workflow_actions"] == 2
    assert summary["failure_count"] == 2
    assert routes["top_workflows"][0]["total"] == 2
    assert routes["top_workflows"][0]["success_count"] == 1
    assert routes["top_workflows"][0]["failure_count"] == 1
