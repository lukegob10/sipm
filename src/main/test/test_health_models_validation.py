from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.models import ApiToken, PerformanceSample, UsageDailyRollup, UsageEvent, User, UserTaskState
from backend.app.schemas import ApiTokenCreate, PerformanceSampleIn, UsageEventIn, UserTaskStateUpdate
from test_my_work_personal_state import _seed_assigned_task


_OVERFLOW_TIMESTAMPS = [
    "0001-01-01T00:00:00+00:01",
    "9999-12-31T23:59:59-00:01",
]
_EVENT = {
    "session_id": "session",
    "view_key": "home",
    "category": "navigation",
    "feature_key": "navigation",
    "action_key": "route_view",
    "outcome": "success",
}
_SAMPLE = {"session_id": "session", "view_key": "home", "sample_kind": "navigation"}
_INPUT_MODELS = [
    pytest.param(UserTaskStateUpdate, "reminder_at", {}, id="reminder"),
    pytest.param(ApiTokenCreate, "expires_at", {"name": "token"}, id="token"),
    pytest.param(UsageEventIn, "occurred_at", _EVENT, id="event"),
    pytest.param(PerformanceSampleIn, "occurred_at", _SAMPLE, id="sample"),
]


@pytest.mark.parametrize("timestamp", _OVERFLOW_TIMESTAMPS)
@pytest.mark.parametrize("model,field,payload", _INPUT_MODELS)
def test_timestamp_inputs_reject_utc_conversion_overflow(model, field, payload, timestamp):
    with pytest.raises(ValidationError) as error:
        model(**{**payload, field: timestamp})
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "timestamp,utc_value",
    [
        ("0001-01-01T00:01:00+00:01", datetime.min.replace(tzinfo=timezone.utc)),
        ("9999-12-31T23:58:59-00:01", datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
    ],
)
@pytest.mark.parametrize("model,field,payload", _INPUT_MODELS)
def test_timestamp_inputs_preserve_valid_offsets_at_year_boundaries(model, field, payload, timestamp, utc_value):
    value = getattr(model(**{**payload, field: timestamp}), field)
    assert value.isoformat() == timestamp
    assert value.astimezone(timezone.utc) == utc_value


@pytest.mark.anyio
@pytest.mark.parametrize("timestamp", _OVERFLOW_TIMESTAMPS)
async def test_overflow_reminder_request_preserves_existing_private_state(client, db_sessionmaker, timestamp):
    with db_sessionmaker() as session:
        task_id = _seed_assigned_task(session)
    path = f"/project-manager/api/my-work/tasks/{task_id}/state"
    saved = await client.patch(path, json={"private_note": "Existing note"})
    assert saved.status_code == 200, saved.text

    response = await client.patch(path, json={"private_note": "Changed note", "reminder_at": timestamp})
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["body", "reminder_at"]
    with db_sessionmaker() as session:
        state = session.query(UserTaskState).one()
        assert state.private_note == "Existing note"
        assert state.reminder_at is None


@pytest.mark.anyio
@pytest.mark.parametrize("timestamp", _OVERFLOW_TIMESTAMPS)
@pytest.mark.parametrize("collection,payload", [("events", _EVENT), ("performance_samples", _SAMPLE)])
async def test_overflow_telemetry_request_does_not_partially_ingest(
    client, db_sessionmaker, monkeypatch, collection, payload, timestamp
):
    monkeypatch.setenv("SIPM_USAGE_ANALYTICS_ENABLED", "true")
    response = await client.post(
        "/project-manager/api/analytics/ingest",
        json={collection: [
            {**payload, "occurred_at": "2026-11-06T12:00:00Z"},
            {**payload, "occurred_at": timestamp},
        ]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["body", collection, 1, "occurred_at"]
    with db_sessionmaker() as session:
        for model in (UsageEvent, PerformanceSample, UsageDailyRollup):
            assert session.query(model).count() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("timestamp", _OVERFLOW_TIMESTAMPS)
async def test_overflow_token_expiration_request_does_not_issue_token(client, db_sessionmaker, timestamp):
    with db_sessionmaker() as session:
        session.add(User(
            user_id="token-target", soeid="token-target", email="target@example.com",
            display_name="Target", password_hash="unused",
        ))
        session.commit()
    response = await client.post(
        "/project-manager/api/users/token-target/api-tokens",
        json={"name": "token", "expires_at": timestamp},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["body", "expires_at"]
    with db_sessionmaker() as session:
        assert session.query(ApiToken).count() == 0
