from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from backend.app.models import PerformanceSample, UsageEvent
from backend.app.services.usage_analytics import _daily_distinct_token_counts, _distinct_token_count


def test_raw_analytics_identity_counts_handle_oracle_empty_string_nulls(db_sessionmaker):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_sessionmaker() as session:
        session.add_all([
            UsageEvent(occurred_at=now, received_at=now, session_id="one", user_id="alice", space_id="analytics-space",
                       view_key="home", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"),
            PerformanceSample(occurred_at=now, received_at=now, session_id="two", user_id="alice", space_id="analytics-space",
                              view_key="home", sample_kind="navigation"),
            UsageEvent(occurred_at=now, received_at=now, session_id="", user_id="", space_id="analytics-space",
                       view_key="home", category="navigation", feature_key="navigation", action_key="route_view", outcome="success"),
        ])
        session.commit()

    engine = db_sessionmaker.kw["bind"]

    def oracle_empty_string_bind(_connection, _cursor, statement, parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            parameters = tuple(None if value == "" else value for value in parameters)
        return statement, parameters

    event.listen(engine, "before_cursor_execute", oracle_empty_string_bind, retval=True)
    try:
        with db_sessionmaker() as session:
            since = now - timedelta(days=1)
            assert _distinct_token_count(session, token_name="session_id", since=since, scope_space_id="analytics-space") == 2
            assert _distinct_token_count(session, token_name="user_id", since=since, scope_space_id="analytics-space") == 1
            assert _daily_distinct_token_counts(session, token_name="session_id", since=since, scope_space_id="analytics-space") == {now.date(): 2}
            assert _daily_distinct_token_counts(session, token_name="user_id", since=since, scope_space_id="analytics-space") == {now.date(): 1}
    finally:
        event.remove(engine, "before_cursor_execute", oracle_empty_string_bind)
