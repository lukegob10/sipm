from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from backend.app import deps as deps_module
from backend.app.models import (
    PerformanceSample,
    Space,
    UsageDailyRollup,
    UsageEvent,
    UsageIdentityDailyRollup,
    UsageRouteIdentityDailyRollup,
)
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


@pytest.fixture
def analytics_enabled(monkeypatch):
    monkeypatch.setenv("SIPM_USAGE_ANALYTICS_ENABLED", "true")


@pytest.fixture
def analytics_auth_overrides(db_sessionmaker, analytics_enabled):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(space_id="space-1", name="Space One", slug="space-one", is_active=True),
                Space(space_id="space-2", name="Space Two", slug="space-two", is_active=True),
            ]
        )
        session.commit()

    fake_user = SimpleNamespace(
        user_id="user-1",
        display_name="Usage Admin",
        soeid="usageadmin",
        role="global_admin",
        is_active=True,
    )
    fake_space = SpaceContext(
        space_id="space-1",
        space_name="Space One",
        is_global_admin=True,
        space_role="space_admin",
    )

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[deps_module.get_db] = get_test_db
    fastapi_app.dependency_overrides[deps_module.require_user] = lambda: fake_user
    fastapi_app.dependency_overrides[deps_module.current_user] = lambda: fake_user
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: fake_space
    fastapi_app.dependency_overrides[deps_module.require_global_admin] = lambda: fake_user
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def analytics_client(analytics_auth_overrides):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client


@pytest.fixture
def member_auth_overrides(db_sessionmaker, analytics_enabled):
    with db_sessionmaker() as session:
        session.add(Space(space_id="space-1", name="Space One", slug="space-one", is_active=True))
        session.commit()

    fake_user = SimpleNamespace(
        user_id="user-member",
        display_name="Usage Member",
        soeid="usagemember",
        role="member",
        is_active=True,
    )
    fake_space = SpaceContext(
        space_id="space-1",
        space_name="Space One",
        is_global_admin=False,
        space_role="member",
    )

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[deps_module.get_db] = get_test_db
    fastapi_app.dependency_overrides[deps_module.require_user] = lambda: fake_user
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: fake_space
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def member_client(member_auth_overrides):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client


@pytest.fixture
def db_only_overrides(db_sessionmaker):
    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[deps_module.get_db] = get_test_db
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def unauthed_client(db_only_overrides):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


@pytest.mark.anyio
async def test_usage_analytics_ingest_persists_server_identity_and_sanitizes_details(
    analytics_client,
    db_sessionmaker,
):
    now = datetime.now(timezone.utc)
    response = await analytics_client.post(
        "/project-manager/api/analytics/ingest",
        json={
            "events": [
                {
                    "occurred_at": _iso(now - timedelta(seconds=4)),
                    "session_id": "tab-1",
                    "view_key": "master",
                    "category": "workflow",
                    "feature_key": "projects",
                    "action_key": "create",
                    "outcome": "success",
                    "duration_ms": 240,
                    "status_code": 201,
                    "details": {
                        "source": "ui",
                        "path": "/projects",
                        "title": "should-not-persist",
                    },
                    "user_id": "spoofed-user",
                    "space_id": "spoofed-space",
                }
            ],
            "performance_samples": [
                {
                    "occurred_at": _iso(now - timedelta(seconds=3)),
                    "session_id": "tab-1",
                    "view_key": "master",
                    "sample_kind": "navigation",
                    "navigation_type": "navigate",
                    "load_event_ms": 1100,
                    "first_contentful_paint_ms": 420,
                    "largest_contentful_paint_ms": 680,
                    "cls_score": 0.03,
                    "long_task_count": 2,
                    "long_task_total_ms": 140,
                    "user_id": "spoofed-user",
                    "space_id": "spoofed-space",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "events_ingested": 1,
        "performance_samples_ingested": 1,
    }

    with db_sessionmaker() as session:
        event = session.query(UsageEvent).one()
        sample = session.query(PerformanceSample).one()

    assert event.user_id == "user-1"
    assert event.space_id == "space-1"
    assert event.details_json == '{"path":"/projects","source":"ui"}'
    assert sample.user_id == "user-1"
    assert sample.space_id == "space-1"
    assert sample.load_event_ms == 1100

    with db_sessionmaker() as session:
        rollup = session.query(UsageDailyRollup).one()
        identities = session.query(UsageIdentityDailyRollup).all()

    assert rollup.space_id == "space-1"
    assert rollup.view_key == "master"
    assert rollup.event_count == 1
    assert rollup.workflow_action_count == 1
    assert rollup.success_count == 1
    assert rollup.failure_count == 0
    assert {(row.token_type, row.token_value) for row in identities} == {
        ("session", "tab_1"),
        ("user", "user-1"),
    }


@pytest.mark.anyio
async def test_usage_analytics_ingest_rejects_large_batch(analytics_client):
    now = datetime.now(timezone.utc)
    events = [
        {
            "occurred_at": _iso(now - timedelta(seconds=index)),
            "session_id": "tab-1",
            "view_key": "master",
            "category": "navigation",
            "feature_key": "navigation",
            "action_key": "route_view",
            "outcome": "success",
        }
        for index in range(101)
    ]

    response = await analytics_client.post(
        "/project-manager/api/analytics/ingest",
        json={"events": events, "performance_samples": []},
    )

    assert response.status_code == 400, response.text
    assert response.headers["X-Error-Code"] == "ANALYTICS_BATCH_TOO_LARGE"


@pytest.mark.anyio
async def test_usage_analytics_summary_and_route_totals_use_exact_rollups(analytics_client, db_sessionmaker):
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    response = await analytics_client.post(
        "/project-manager/api/analytics/ingest",
        json={
            "events": [
                {
                    "occurred_at": _iso(yesterday),
                    "session_id": "session-a",
                    "view_key": "master",
                    "category": "navigation",
                    "feature_key": "navigation",
                    "action_key": "route_view",
                    "outcome": "success",
                },
                {
                    "occurred_at": _iso(yesterday + timedelta(seconds=10)),
                    "session_id": "session-a",
                    "view_key": "master",
                    "category": "navigation",
                    "feature_key": "navigation",
                    "action_key": "route_view",
                    "outcome": "success",
                },
                {
                    "occurred_at": _iso(yesterday + timedelta(seconds=20)),
                    "session_id": "session-b",
                    "view_key": "master",
                    "category": "workflow",
                    "feature_key": "projects",
                    "action_key": "create",
                    "outcome": "server_error",
                    "status_code": 500,
                },
            ],
            "performance_samples": [
                {
                    "occurred_at": _iso(yesterday + timedelta(seconds=30)),
                    "session_id": "session-b",
                    "view_key": "master",
                    "sample_kind": "route_transition",
                    "data_load_ms": 300,
                    "render_ms": 100,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text

    with db_sessionmaker() as session:
        assert session.query(UsageDailyRollup).count() == 2
        assert session.query(UsageIdentityDailyRollup).count() == 3
        assert session.query(UsageRouteIdentityDailyRollup).count() == 2

    summary = await analytics_client.get("/project-manager/api/analytics/summary?days=30")
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload["summary"]["sessions"] == 2
    assert summary_payload["summary"]["active_users"] == 1
    assert summary_payload["summary"]["route_views"] == 2
    assert summary_payload["summary"]["workflow_actions"] == 1
    assert summary_payload["summary"]["failure_count"] == 1

    daily_points = [point for point in summary_payload["daily"] if point["route_views"] or point["failure_count"]]
    assert daily_points == [
        {
            "date": yesterday.date().isoformat(),
            "sessions": 2,
            "active_users": 1,
            "route_views": 2,
            "workflow_actions": 1,
            "failure_count": 1,
            "median_load_ms": 400,
            "p95_load_ms": 400,
        }
    ]

    routes = await analytics_client.get("/project-manager/api/analytics/routes?days=30")
    assert routes.status_code == 200, routes.text
    route_payload = routes.json()
    assert route_payload["top_routes"][0] == {
        "view_key": "master",
        "route_views": 2,
        "unique_sessions": 1,
        "active_users": 1,
        "failure_count": 1,
    }
    assert route_payload["top_workflows"][0] == {
        "feature_key": "projects",
        "action_key": "create",
        "total": 1,
        "success_count": 0,
        "failure_count": 1,
    }
    assert route_payload["recent_failures"][0]["failure_count"] == 1


@pytest.mark.anyio
async def test_usage_analytics_ingest_requires_auth(unauthed_client, analytics_enabled):
    response = await unauthed_client.post(
        "/project-manager/api/analytics/ingest",
        json={
            "events": [
                {
                    "occurred_at": _iso(datetime.now(timezone.utc)),
                    "session_id": "tab-1",
                    "view_key": "master",
                    "category": "navigation",
                    "feature_key": "navigation",
                    "action_key": "route_view",
                    "outcome": "success",
                }
            ],
            "performance_samples": [],
        },
    )

    assert response.status_code == 401, response.text


@pytest.mark.anyio
async def test_usage_analytics_reads_are_global_admin_only(member_client):
    response = await member_client.get("/project-manager/api/analytics/summary")

    assert response.status_code == 403, response.text
    assert response.headers["X-Error-Code"] == "FORBIDDEN_ROLE"


@pytest.mark.anyio
async def test_usage_analytics_aggregates_scope_and_math(analytics_client, db_sessionmaker):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    with db_sessionmaker() as session:
        session.add_all(
            [
                UsageEvent(
                    event_id="evt-1",
                    occurred_at=two_days_ago,
                    received_at=two_days_ago,
                    session_id="session-a",
                    user_id="user-1",
                    space_id="space-1",
                    view_key="master",
                    category="navigation",
                    feature_key="navigation",
                    action_key="route_view",
                    outcome="success",
                ),
                UsageEvent(
                    event_id="evt-2",
                    occurred_at=yesterday,
                    received_at=yesterday,
                    session_id="session-a",
                    user_id="user-1",
                    space_id="space-1",
                    view_key="planning",
                    category="workflow",
                    feature_key="planning",
                    action_key="assignment_create",
                    outcome="success",
                ),
                UsageEvent(
                    event_id="evt-3",
                    occurred_at=yesterday,
                    received_at=yesterday,
                    session_id="session-b",
                    user_id="user-2",
                    space_id="space-2",
                    view_key="analytics",
                    category="navigation",
                    feature_key="navigation",
                    action_key="route_view",
                    outcome="server_error",
                    status_code=500,
                ),
                PerformanceSample(
                    sample_id="perf-1",
                    occurred_at=two_days_ago,
                    received_at=two_days_ago,
                    session_id="session-a",
                    user_id="user-1",
                    space_id="space-1",
                    view_key="master",
                    sample_kind="navigation",
                    navigation_type="navigate",
                    load_event_ms=1200,
                    first_contentful_paint_ms=400,
                ),
                PerformanceSample(
                    sample_id="perf-2",
                    occurred_at=yesterday,
                    received_at=yesterday,
                    session_id="session-a",
                    user_id="user-1",
                    space_id="space-1",
                    view_key="planning",
                    sample_kind="route_transition",
                    data_load_ms=300,
                    render_ms=120,
                ),
                PerformanceSample(
                    sample_id="perf-3",
                    occurred_at=yesterday,
                    received_at=yesterday,
                    session_id="session-b",
                    user_id="user-2",
                    space_id="space-2",
                    view_key="analytics",
                    sample_kind="route_transition",
                    data_load_ms=900,
                    render_ms=200,
                ),
            ]
        )
        session.commit()

    summary = await analytics_client.get("/project-manager/api/analytics/summary?days=30")
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload["scope_space_id"] == "space-1"
    assert summary_payload["summary"]["sessions"] == 1
    assert summary_payload["summary"]["active_users"] == 1
    assert summary_payload["summary"]["route_views"] == 1
    assert summary_payload["summary"]["workflow_actions"] == 1
    assert summary_payload["summary"]["failure_count"] == 0
    assert summary_payload["summary"]["median_load_ms"] == 810
    assert summary_payload["summary"]["p95_load_ms"] == 1200

    routes = await analytics_client.get("/project-manager/api/analytics/routes?days=30&all_spaces=true")
    assert routes.status_code == 200, routes.text
    route_payload = routes.json()
    assert route_payload["scope_space_id"] is None
    assert route_payload["top_routes"][0]["view_key"] == "analytics"
    assert route_payload["top_routes"][0]["failure_count"] == 1
    assert route_payload["top_workflows"][0]["feature_key"] == "planning"
    assert route_payload["recent_failures"][0]["view_key"] == "analytics"
    assert "user_display_name" not in route_payload["top_routes"][0]

    performance = await analytics_client.get("/project-manager/api/analytics/performance?days=30&space_id=space-2")
    assert performance.status_code == 200, performance.text
    perf_payload = performance.json()
    assert perf_payload["scope_space_id"] == "space-2"
    assert perf_payload["summary"]["navigation_samples"] == 0
    assert perf_payload["summary"]["route_transition_samples"] == 1
    assert perf_payload["summary"]["median_load_ms"] == 1100
    assert perf_payload["routes"][0]["view_key"] == "analytics"
    assert perf_payload["routes"][0]["median_load_ms"] == 1100
