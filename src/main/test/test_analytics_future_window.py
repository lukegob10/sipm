from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models import PerformanceSample, Space, UsageEvent
from backend.app.services.usage_analytics import build_dashboard_payload, update_usage_rollups


@pytest.mark.parametrize("use_rollups", [False, True])
@pytest.mark.parametrize("all_spaces", [False, True])
def test_analytics_excludes_future_dates_from_reports(db_sessionmaker, use_rollups, all_spaces):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    future = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    old = now - timedelta(days=9)
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space", space_kind="collaboration"))
        events = [
            UsageEvent(event_id="current", occurred_at=now, received_at=now, session_id="current", user_id="user-current",
                       space_id="space", view_key="master", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"),
            UsageEvent(event_id="future", occurred_at=future, received_at=now, session_id="future", user_id="user-future",
                       space_id="space", view_key="dashboard", category="navigation", feature_key="navigation", action_key="route_view", outcome="failure"),
            UsageEvent(event_id="old", occurred_at=old, received_at=now, session_id="old", user_id="user-old",
                       space_id="space", view_key="old", category="navigation", feature_key="navigation", action_key="route_view", outcome="failure"),
        ]
        samples = [
            PerformanceSample(sample_id="current", occurred_at=now, received_at=now, session_id="current", user_id="user-current",
                              space_id="space", view_key="master", sample_kind="navigation", load_event_ms=100),
            PerformanceSample(sample_id="future", occurred_at=future, received_at=now, session_id="future", user_id="user-future",
                              space_id="space", view_key="dashboard", sample_kind="navigation", load_event_ms=900),
            PerformanceSample(sample_id="old", occurred_at=old, received_at=now, session_id="old", user_id="user-old",
                              space_id="space", view_key="old", sample_kind="navigation", load_event_ms=800),
        ]
        session.add_all(events + samples)
        if use_rollups:
            update_usage_rollups(session, events=events, samples=samples)
        session.commit()
        report = build_dashboard_payload(session, days=7, all_spaces=all_spaces, scope_space_id=None if all_spaces else "space")
    summary = report["summary"]
    assert summary["summary"]["route_views"] == 1
    assert summary["summary"]["failure_count"] == 0
    assert summary["summary"]["sessions"] == 1
    assert summary["summary"]["active_users"] == 1
    assert summary["summary"]["median_load_ms"] == 100
    assert len(summary["daily"]) == 7
    assert max(row["date"] for row in summary["daily"]) == now.date().isoformat()
    assert [row["view_key"] for row in report["routes"]["top_routes"]] == ["master"]
    assert report["routes"]["recent_failures"] == []
    assert report["performance"]["summary"]["navigation_samples"] == 1
    assert [row["view_key"] for row in report["performance"]["routes"]] == ["master"]
