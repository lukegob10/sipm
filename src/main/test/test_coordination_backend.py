from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from backend.app.services import coordination


def test_coordination_defaults_to_memory_in_tests(monkeypatch):
    monkeypatch.delenv("SIPM_COORDINATION_BACKEND", raising=False)
    monkeypatch.delenv("ENV", raising=False)

    assert coordination.validate_configuration() == "memory"


def test_prod_like_env_requires_redis(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SIPM_COORDINATION_BACKEND", "memory")
    monkeypatch.setattr(coordination, "_running_tests", lambda: False)

    with pytest.raises(
        RuntimeError,
        match="SIPM_COORDINATION_BACKEND must be 'redis' when ENV resolves to uat or prod.",
    ):
        coordination.validate_configuration()


@pytest.mark.anyio
async def test_redis_coordination_uses_bounded_connection_timeouts(monkeypatch):
    monkeypatch.setenv("SIPM_REDIS_TIMEOUT_SECONDS", "2.5")
    backend = coordination.RedisCoordinationBackend("redis://127.0.0.1:6379/0")
    try:
        sync_options = backend._redis.connection_pool.connection_kwargs
        async_options = backend._aredis.connection_pool.connection_kwargs
        assert sync_options["socket_connect_timeout"] == 2.5
        assert sync_options["socket_timeout"] == 2.5
        assert async_options["socket_connect_timeout"] == 2.5
    finally:
        await backend.aclose()


def test_redis_coordination_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("SIPM_REDIS_TIMEOUT_SECONDS", "0")

    with pytest.raises(RuntimeError, match="must be a positive number"):
        coordination.RedisCoordinationBackend("redis://127.0.0.1:6379/0")


@pytest.mark.anyio
@pytest.mark.integration
async def test_redis_coordination_propagates_scope_versions_and_refresh_events(monkeypatch):
    redis_url = str(os.getenv("SIPM_REDIS_URL", "")).strip()
    if not redis_url:
        pytest.skip("SIPM_REDIS_URL is not configured for Redis coordination integration testing.")

    backend_a = coordination.RedisCoordinationBackend(redis_url)
    backend_b = coordination.RedisCoordinationBackend(redis_url)
    scope_token = f"solutions:{uuid4()}"
    event = asyncio.Event()
    received: list[tuple[str, str | None]] = []

    async def handler(entity: str, space_id: str | None) -> None:
        received.append((entity, space_id))
        event.set()

    try:
        await backend_a.start_refresh_listener(handler)
        backend_b.invalidate_scope_tokens([scope_token])
        await asyncio.sleep(0.05)
        assert backend_a.scope_versions([scope_token])[scope_token] >= 1

        assert backend_b.publish_refresh("solutions", space_id="space-redis-test") is True
        await asyncio.wait_for(event.wait(), timeout=2)
        assert received == [("solutions", "space-redis-test")]
    finally:
        await backend_a.aclose()
        await backend_b.aclose()
