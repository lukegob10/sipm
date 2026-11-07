from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models import PerformanceSample, Space, UsageDailyRollup, UsageEvent
from backend.app.services.analytics_backfill import backfill_usage_rollups
from backend.app.services.usage_analytics import (
    build_route_stats_payload,
    build_summary_payload,
    update_usage_rollups,
)


@pytest.mark.parametrize("all_spaces", [False, True])
@pytest.mark.parametrize("writer", ["ingest", "backfill"])
def test_sample_only_identity_rollups_survive_raw_purge(db_sessionmaker, all_spaces, writer):
    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time())
    since, until = today - timedelta(days=6), today + timedelta(days=1)
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space-a", name="A", slug="a", space_kind="collaboration"),
            Space(space_id="space-b", name="B", slug="b", space_kind="collaboration"),
            Space(space_id="personal", name="Personal", slug="personal", space_kind="personal"),
        ])
        samples = [
            PerformanceSample(
                sample_id=str(index), occurred_at=occurred_at, received_at=today,
                session_id=token, user_id=token, space_id=space_id,
                view_key="master", sample_kind="navigation", load_event_ms=100,
            )
            for index, (occurred_at, space_id, token) in enumerate([
                (today - timedelta(hours=1), "space-a", "shared"),
                (today + timedelta(hours=1), "space-a", "shared"),
                (today + timedelta(hours=1), "space-b", "shared"),
                (today, "personal", "private"),
                (until, "space-a", "future"),
                (since - timedelta(seconds=1), "space-a", "old"),
            ])
        ]
        session.add_all(samples)
        if writer == "ingest":
            update_usage_rollups(session, events=[], samples=samples)
        session.commit()
        if writer == "backfill":
            backfill_usage_rollups(session, since=since, until=until, apply=True)
            session.commit()
        assert session.query(UsageDailyRollup).count() == 0
        session.query(PerformanceSample).delete()
        session.commit()

        report = build_summary_payload(
            session, days=7, all_spaces=all_spaces, scope_space_id=None if all_spaces else "space-a",
        )

    assert report["summary"]["sessions"] == 1
    assert report["summary"]["active_users"] == 1
    assert report["summary"]["route_views"] == 0
    assert len(report["daily"]) == 7
    active_days = [row for row in report["daily"] if row["sessions"]]
    assert [row["date"] for row in active_days] == [(today - timedelta(days=1)).date().isoformat(), today.date().isoformat()]
    assert all(row["sessions"] == row["active_users"] == 1 for row in active_days)


def test_retained_sample_identities_combine_with_raw_event_fallback(db_sessionmaker):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_sessionmaker() as session:
        sample = PerformanceSample(
            occurred_at=now, received_at=now, session_id="retained", user_id="retained",
            view_key="master", sample_kind="navigation",
        )
        session.add(sample)
        update_usage_rollups(session, events=[], samples=[sample])
        session.commit()
        session.query(PerformanceSample).delete()
        session.add(UsageEvent(
            occurred_at=now, received_at=now, session_id="shared", user_id="shared", view_key="master",
            category="navigation", feature_key="navigation", action_key="route_view", outcome="success",
        ))
        session.commit()
        report = build_summary_payload(session, days=7, all_spaces=True, scope_space_id=None)

    assert report["summary"]["sessions"] == 2
    assert report["summary"]["active_users"] == 2
    assert report["summary"]["route_views"] == 1


@pytest.mark.parametrize("raw_is_newer", [False, True])
def test_backfill_preserves_larger_counts_and_newest_failure_time(db_sessionmaker, raw_is_newer):
    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time())
    existing_last = today + timedelta(hours=12)
    raw_last = existing_last + timedelta(hours=1 if raw_is_newer else -1)
    with db_sessionmaker() as session:
        session.add(UsageEvent(
            occurred_at=raw_last, received_at=raw_last, session_id="session", user_id="user", view_key="master",
            category="navigation", feature_key="navigation", action_key="route_view", outcome="failure",
        ))
        rollup = UsageDailyRollup(
            rollup_date=today.date(), space_id="__none__", view_key="master", category="navigation",
            feature_key="navigation", action_key="route_view", outcome="failure", event_count=10,
            route_view_count=10, workflow_action_count=0, success_count=0, failure_count=10,
            last_occurred_at=existing_last,
        )
        session.add(rollup)
        session.commit()

        window = {"since": today, "until": today + timedelta(days=1)}
        preview = backfill_usage_rollups(session, **window)
        assert preview["larger_rollups_preserved"] == 1
        assert preview["event_groups_updated"] == int(raw_is_newer)
        assert rollup.last_occurred_at == existing_last
        assert backfill_usage_rollups(session, **window, apply=True) == preview
        assert rollup.last_occurred_at == max(existing_last, raw_last)
        assert (rollup.event_count, rollup.route_view_count, rollup.failure_count) == (10, 10, 10)
        session.rollback()
        assert rollup.last_occurred_at == existing_last

        assert backfill_usage_rollups(session, **window, apply=True) == preview
        session.commit()
        assert backfill_usage_rollups(session, **window, apply=True)["event_groups_updated"] == 0
        routes = build_route_stats_payload(session, days=7, all_spaces=True, scope_space_id=None)
        assert routes["recent_failures"][0]["last_occurred_at"] == max(existing_last, raw_last)
        assert routes["recent_failures"][0]["failure_count"] == 10
