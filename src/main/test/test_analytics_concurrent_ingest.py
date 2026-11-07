from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event, local
from types import SimpleNamespace

import pytest

from backend.app.models import Space, UsageDailyRollup, UsageEvent, UsageIdentityDailyRollup, UsageRouteIdentityDailyRollup
from backend.app.routes import analytics
from backend.app.schemas import TelemetryBatchIn
from backend.app.services import usage_analytics
from backend.app.services.spaces import SpaceContext


def batch(now, session_id):
    return TelemetryBatchIn(events=[{
        "occurred_at": now, "session_id": session_id, "view_key": "master",
        "category": "navigation", "feature_key": "navigation", "action_key": "route_view", "outcome": "success",
    }])


@pytest.mark.parametrize("existing", [False, True])
def test_concurrent_ingest_preserves_raw_events_and_rollups(db_sessionmaker, monkeypatch, existing):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    now = datetime.now(timezone.utc)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    actor = SimpleNamespace(user_id="user")
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        session.commit()
    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    if existing:
        with db_sessionmaker() as session:
            analytics.ingest_usage_analytics(batch(now, "seed"), session=session, current_user=actor, space_ctx=ctx)

    barrier, first_done, state = Barrier(2), Event(), local()
    original = usage_analytics._load_existing_rollups

    def synchronize_reads(session, model, **kwargs):
        rows = original(session, model, **kwargs)
        if model is UsageRouteIdentityDailyRollup and not getattr(state, "waited", False):
            state.waited = True
            barrier.wait(timeout=10)
            if state.order == "second":
                assert first_done.wait(10)
        return rows

    monkeypatch.setattr(usage_analytics, "_load_existing_rollups", synchronize_reads)

    def ingest(order):
        state.order = order
        try:
            with db_sessionmaker() as session:
                return analytics.ingest_usage_analytics(batch(now, "shared"), session=session, current_user=actor, space_ctx=ctx)
        finally:
            if order == "first":
                first_done.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(ingest, "first")
        second = executor.submit(ingest, "second")
        assert first.result(timeout=20).events_ingested == 1
        assert second.result(timeout=20).events_ingested == 1
    with db_sessionmaker() as session:
        expected = 3 if existing else 2
        assert session.query(UsageEvent).count() == expected
        row = session.query(UsageDailyRollup).one()
        assert row.event_count == expected
        assert row.route_view_count == expected
        assert row.success_count == expected
        assert session.query(UsageIdentityDailyRollup).count() == (3 if existing else 2)
        assert session.query(UsageRouteIdentityDailyRollup).count() == (3 if existing else 2)


def test_rollup_updates_are_visible_to_existing_session_objects(db_sessionmaker):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def make_event(event_id):
        return UsageEvent(event_id=event_id, occurred_at=now, received_at=now, session_id="shared", user_id="user",
                          space_id=None, view_key="master", category="navigation", feature_key="navigation",
                          action_key="route_view", outcome="success")

    with db_sessionmaker() as session:
        first = make_event("first")
        session.add(first)
        usage_analytics.update_usage_rollups(session, events=[first], samples=[])
        session.commit()
        rollup = session.query(UsageDailyRollup).one()
        second = make_event("second")
        session.add(second)
        usage_analytics.update_usage_rollups(session, events=[second], samples=[])
        assert rollup.event_count == 2
        assert rollup.route_view_count == 2


def test_concurrent_sample_only_ingest_preserves_shared_identities(db_sessionmaker, monkeypatch):
    from backend.app.models import PerformanceSample

    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    now = datetime.now(timezone.utc)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    actor = SimpleNamespace(user_id="user")
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        session.commit()
    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    barrier, first_done, state = Barrier(2), Event(), local()
    original = usage_analytics._load_existing_rollups

    def synchronize_reads(session, model, **kwargs):
        rows = original(session, model, **kwargs)
        if model is UsageRouteIdentityDailyRollup and not getattr(state, "waited", False):
            state.waited = True
            barrier.wait(timeout=10)
            if state.order == "second":
                assert first_done.wait(10)
        return rows

    monkeypatch.setattr(usage_analytics, "_load_existing_rollups", synchronize_reads)
    payload = TelemetryBatchIn(performance_samples=[{
        "occurred_at": now, "session_id": "shared", "view_key": "master", "sample_kind": "navigation",
    }])

    def ingest(order):
        state.order = order
        try:
            with db_sessionmaker() as session:
                return analytics.ingest_usage_analytics(payload, session=session, current_user=actor, space_ctx=ctx)
        finally:
            if order == "first":
                first_done.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(ingest, "first"), executor.submit(ingest, "second")
        assert first.result(timeout=20).performance_samples_ingested == 1
        assert second.result(timeout=20).performance_samples_ingested == 1
    with db_sessionmaker() as session:
        assert session.query(PerformanceSample).count() == 2
        assert session.query(UsageIdentityDailyRollup).count() == 2
        assert session.query(UsageDailyRollup).count() == 0
        assert session.query(UsageRouteIdentityDailyRollup).count() == 0


def test_existing_rollup_updates_use_one_batched_atomic_statement(db_sessionmaker):
    from sqlalchemy import event
    from sqlalchemy.dialects import oracle

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [UsageEvent(event_id=str(i), occurred_at=now, received_at=now, session_id=f"s-{i}", user_id=f"u-{i}",
                         space_id=None, view_key=f"route-{i}", category="navigation", feature_key="navigation",
                         action_key="route_view", outcome="success") for i in range(100)]
    with db_sessionmaker() as session:
        usage_analytics.update_usage_rollups(session, events=events, samples=[])
        session.commit()
    updates = []

    def record_update(_conn, clauseelement, multiparams, _params, _execution_options):
        if getattr(clauseelement, "is_update", False) and clauseelement.table.name == UsageDailyRollup.__tablename__:
            updates.append((str(clauseelement.compile(dialect=oracle.dialect())), len(multiparams)))

    engine = db_sessionmaker.kw["bind"]
    event.listen(engine, "before_execute", record_update)
    try:
        with db_sessionmaker() as session:
            usage_analytics.update_usage_rollups(session, events=events, samples=[])
            session.commit()
    finally:
        event.remove(engine, "before_execute", record_update)
    assert len(updates) == 1
    assert updates[0][1] == 100
    assert "event_count +" in updates[0][0]
    with db_sessionmaker() as session:
        assert all(row.event_count == 2 for row in session.query(UsageDailyRollup).all())


def test_nonretryable_integrity_error_is_not_retried(db_sessionmaker, monkeypatch):
    import sqlite3
    from sqlalchemy.exc import IntegrityError

    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    attempts = []

    def fail(_session, **_kwargs):
        attempts.append(1)
        raise IntegrityError("insert", {}, sqlite3.IntegrityError("NOT NULL constraint failed"))

    monkeypatch.setattr(analytics, "update_usage_rollups", fail)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        with pytest.raises(IntegrityError):
            analytics.ingest_usage_analytics(batch(datetime.now(timezone.utc), "shared"), session=session,
                                             current_user=SimpleNamespace(user_id="user"), space_ctx=ctx)
        assert len(attempts) == 1
        assert session.query(UsageEvent).count() == 0


@pytest.mark.parametrize("existing", [False, True])
def test_retryable_lock_failure_retries_whole_batch(db_sessionmaker, monkeypatch, existing):
    import sqlite3
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    monkeypatch.setattr(analytics.time, "sleep", lambda _delay: None)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    actor = SimpleNamespace(user_id="user")
    if existing:
        with db_sessionmaker() as session:
            analytics.ingest_usage_analytics(batch(datetime.now(timezone.utc), "shared"), session=session,
                                             current_user=actor, space_ctx=ctx)
    original = analytics.update_usage_rollups
    attempts = []

    def fail_once(session, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            original(session, **kwargs)
            session.flush()
            raise OperationalError("update", {}, sqlite3.OperationalError("database is locked"))
        return original(session, **kwargs)

    monkeypatch.setattr(analytics, "update_usage_rollups", fail_once)
    with db_sessionmaker() as session:
        result = analytics.ingest_usage_analytics(batch(datetime.now(timezone.utc), "shared"), session=session,
                                                  current_user=actor, space_ctx=ctx)
        assert result.events_ingested == 1
        assert len(attempts) == 2
        expected = 2 if existing else 1
        assert session.query(UsageEvent).count() == expected
        assert session.query(UsageDailyRollup).one().event_count == expected


def test_ingest_retry_is_bounded_and_rolls_back(db_sessionmaker, monkeypatch):
    import sqlite3
    from sqlalchemy.exc import IntegrityError

    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    delays, attempts = [], []
    monkeypatch.setattr(analytics.time, "sleep", delays.append)

    def fail(session, **_kwargs):
        attempts.append(1)
        session.flush()
        raise IntegrityError("insert", {}, sqlite3.IntegrityError("UNIQUE constraint failed: rollup"))

    monkeypatch.setattr(analytics, "update_usage_rollups", fail)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        with pytest.raises(IntegrityError):
            analytics.ingest_usage_analytics(batch(datetime.now(timezone.utc), "shared"), session=session,
                                             current_user=SimpleNamespace(user_id="user"), space_ctx=ctx)
        assert len(attempts) == 3
        assert delays == [0.01, 0.02]
        assert session.query(UsageEvent).count() == 0


@pytest.mark.parametrize("code, retryable", [(1, True), (60, True), (8177, True), (1400, False)])
def test_oracle_ingest_error_codes_are_classified(code, retryable):
    from sqlalchemy.exc import DBAPIError

    detail = SimpleNamespace(code=code)
    original = Exception(detail)
    assert analytics._retryable_ingest_conflict(DBAPIError("insert", {}, original)) is retryable


def test_parallel_existing_rollup_updates_do_not_lose_counts_or_latest_time(db_sessionmaker, monkeypatch):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    now = datetime.now(timezone.utc)
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    actor = SimpleNamespace(user_id="user")
    monkeypatch.setattr(analytics, "ensure_usage_analytics_available", lambda _session: None)
    with db_sessionmaker() as session:
        analytics.ingest_usage_analytics(batch(now, "shared"), session=session, current_user=actor, space_ctx=ctx)

    barrier, state = Barrier(8), local()
    original = usage_analytics._load_existing_rollups

    def synchronize_reads(session, model, **kwargs):
        rows = original(session, model, **kwargs)
        if model is UsageRouteIdentityDailyRollup and not getattr(state, "waited", False):
            state.waited = True
            barrier.wait(timeout=15)
        return rows

    monkeypatch.setattr(usage_analytics, "_load_existing_rollups", synchronize_reads)

    def ingest(index):
        with db_sessionmaker() as session:
            return analytics.ingest_usage_analytics(batch(now - timedelta(seconds=index + 1), "shared"), session=session, current_user=actor, space_ctx=ctx)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = [executor.submit(ingest, index) for index in range(8)]
        assert all(result.result(timeout=30).events_ingested == 1 for result in results)
    with db_sessionmaker() as session:
        assert session.query(UsageEvent).count() == 9
        row = session.query(UsageDailyRollup).one()
        assert row.event_count == row.route_view_count == row.success_count == 9
        assert row.last_occurred_at == now.replace(tzinfo=None)
