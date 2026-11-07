from datetime import datetime, timedelta

from backend.app.models import AuthSession, User
from backend.app.services import auth_sessions


def test_delayed_activity_keeps_latest_timestamp_and_deadline(db_sessionmaker, monkeypatch):
    initial = datetime(2026, 1, 1, 12)
    with db_sessionmaker() as session:
        user = User(
            soeid="activity-order",
            email="activity-order@example.com",
            display_name="Activity Order",
            password_hash="unused",
        )
        session.add(user)
        session.flush()
        auth_session = AuthSession(user_id=user.user_id, last_activity_at=initial)
        session.add(auth_session)
        session.commit()
        session_id = auth_session.session_id

    # Both requests have already loaded the same session before either update.
    with db_sessionmaker() as delayed, db_sessionmaker() as newer:
        delayed_session = delayed.get(AuthSession, session_id)
        newer_session = newer.get(AuthSession, session_id)
        later_time = initial + timedelta(seconds=20)
        monkeypatch.setattr(auth_sessions, "utcnow_naive", lambda: later_time)
        expected_deadline = later_time + timedelta(minutes=auth_sessions.SESSION_IDLE_MINUTES)
        assert auth_sessions.record_activity(newer, newer_session) == expected_deadline

        # The delayed request captured its clock before the newer request committed.
        monkeypatch.setattr(auth_sessions, "utcnow_naive", lambda: initial + timedelta(seconds=10))
        assert auth_sessions.record_activity(delayed, delayed_session) == expected_deadline

    with db_sessionmaker() as session:
        assert session.get(AuthSession, session_id).last_activity_at == later_time
