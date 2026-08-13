from __future__ import annotations

import asyncio
import os
from collections import deque
from uuid import uuid4

import pytest

from backend.app.services import coordination


class _FakeSyncRedis:
    def __init__(self) -> None:
        self.ping_error: Exception | None = None
        self.ping_result = True
        self.ping_calls = 0
        self.close_calls = 0

    def ping(self) -> bool:
        self.ping_calls += 1
        if self.ping_error is not None:
            raise self.ping_error
        return self.ping_result

    def close(self) -> None:
        self.close_calls += 1


class _FakePubSub:
    def __init__(
        self,
        *,
        subscribe_error: Exception | None = None,
        listen_error: Exception | None = None,
        messages: tuple[dict, ...] = (),
        wait_before_subscribe: bool = False,
        wait_before_listen_error: bool = False,
    ) -> None:
        self.subscribe_error = subscribe_error
        self.listen_error = listen_error
        self.messages = messages
        self.wait_before_subscribe = wait_before_subscribe
        self.wait_before_listen_error = wait_before_listen_error
        self.subscribe_calls = 0
        self.unsubscribe_calls = 0
        self.close_calls = 0
        self.subscribe_started = asyncio.Event()
        self.release_subscribe = asyncio.Event()
        self.listen_started = asyncio.Event()
        self.release_listen = asyncio.Event()

    async def subscribe(self, channel: str) -> None:
        self.subscribe_calls += 1
        assert channel == coordination._REFRESH_CHANNEL
        self.subscribe_started.set()
        if self.wait_before_subscribe:
            await self.release_subscribe.wait()
        if self.subscribe_error is not None:
            raise self.subscribe_error

    async def listen(self):
        self.listen_started.set()
        for message in self.messages:
            yield message
        if self.wait_before_listen_error or self.listen_error is None:
            await self.release_listen.wait()
        if self.listen_error is not None:
            raise self.listen_error

    async def unsubscribe(self, channel: str) -> None:
        self.unsubscribe_calls += 1
        assert channel == coordination._REFRESH_CHANNEL

    async def aclose(self) -> None:
        self.close_calls += 1
        self.release_listen.set()


class _FakeAsyncRedis:
    def __init__(self, *pubsubs: _FakePubSub) -> None:
        self.pubsubs = deque(pubsubs)
        self.pubsub_calls = 0
        self.close_calls = 0

    def pubsub(self, *, ignore_subscribe_messages: bool):
        assert ignore_subscribe_messages is True
        self.pubsub_calls += 1
        if not self.pubsubs:
            raise AssertionError("No fake PubSub attempt remains")
        return self.pubsubs.popleft()

    async def aclose(self) -> None:
        self.close_calls += 1


class _ControlledSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, delay: float) -> None:
        self.calls.append(delay)
        self.entered.set()
        await self.release.wait()


async def _fake_redis_backend(
    *pubsubs: _FakePubSub,
) -> tuple[coordination.RedisCoordinationBackend, _FakeSyncRedis, _FakeAsyncRedis]:
    backend = coordination.RedisCoordinationBackend("redis://127.0.0.1:6379/0")
    original_sync = backend._redis
    original_async = backend._aredis
    fake_sync = _FakeSyncRedis()
    fake_async = _FakeAsyncRedis(*pubsubs)
    backend._redis = fake_sync
    backend._aredis = fake_async
    await original_async.aclose()
    original_sync.close()
    return backend, fake_sync, fake_async


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
async def test_redis_listener_recovers_from_transient_subscribe_failure():
    failed_pubsub = _FakePubSub(subscribe_error=ConnectionError("subscribe disconnected"))
    recovered_pubsub = _FakePubSub()
    backend, fake_sync, fake_async = await _fake_redis_backend(failed_pubsub, recovered_pubsub)
    controlled_sleep = _ControlledSleep()
    backend._listener_sleep = controlled_sleep

    async def handler(_entity: str, _space_id: str | None) -> None:
        return None

    try:
        await backend.start_refresh_listener(handler)
        await asyncio.wait_for(controlled_sleep.entered.wait(), timeout=1)

        assert backend._listener_live is False
        assert backend._listener_last_error == "ConnectionError: subscribe disconnected"
        assert failed_pubsub.unsubscribe_calls == 1
        assert failed_pubsub.close_calls == 1
        with pytest.raises(RuntimeError, match="listener is unavailable"):
            backend.check_health()
        assert fake_sync.ping_calls == 0

        controlled_sleep.release.set()
        await asyncio.wait_for(recovered_pubsub.listen_started.wait(), timeout=1)

        assert fake_async.pubsub_calls == 2
        assert backend._pubsub is recovered_pubsub
        assert backend._listener_live is True
        assert backend._listener_last_error is None
        backend.check_health()
        assert fake_sync.ping_calls == 1
    finally:
        await backend.aclose()

    assert recovered_pubsub.unsubscribe_calls == 1
    assert recovered_pubsub.close_calls == 1


@pytest.mark.anyio
async def test_redis_listener_reconnects_after_listen_disconnect_and_dispatches_messages():
    disconnected_pubsub = _FakePubSub(
        listen_error=ConnectionError("listen disconnected"),
        wait_before_listen_error=True,
    )
    recovered_pubsub = _FakePubSub(
        messages=(
            {
                "type": "message",
                "data": '{"entity":"tasks","space_id":"space-1"}',
            },
        )
    )
    backend, _, fake_async = await _fake_redis_backend(disconnected_pubsub, recovered_pubsub)
    controlled_sleep = _ControlledSleep()
    backend._listener_sleep = controlled_sleep
    received = asyncio.Event()
    messages: list[tuple[str, str | None]] = []

    async def handler(entity: str, space_id: str | None) -> None:
        messages.append((entity, space_id))
        received.set()

    try:
        await backend.start_refresh_listener(handler)
        await asyncio.wait_for(disconnected_pubsub.listen_started.wait(), timeout=1)
        assert backend._listener_live is True

        disconnected_pubsub.release_listen.set()
        await asyncio.wait_for(controlled_sleep.entered.wait(), timeout=1)
        assert backend._listener_live is False
        assert backend._listener_last_error == "ConnectionError: listen disconnected"
        assert disconnected_pubsub.close_calls == 1

        controlled_sleep.release.set()
        await asyncio.wait_for(received.wait(), timeout=1)
        assert fake_async.pubsub_calls == 2
        assert messages == [("tasks", "space-1")]
        assert backend._listener_live is True
        assert backend._listener_last_error is None
    finally:
        await backend.aclose()


@pytest.mark.anyio
async def test_redis_listener_stop_cancels_backoff_without_another_attempt():
    failed_pubsub = _FakePubSub(subscribe_error=ConnectionError("redis unavailable"))
    unused_pubsub = _FakePubSub()
    backend, _, fake_async = await _fake_redis_backend(failed_pubsub, unused_pubsub)
    controlled_sleep = _ControlledSleep()
    backend._listener_sleep = controlled_sleep

    async def handler(_entity: str, _space_id: str | None) -> None:
        return None

    await backend.start_refresh_listener(handler)
    await asyncio.wait_for(controlled_sleep.entered.wait(), timeout=1)
    listener_task = backend._listener_task

    await backend.stop_refresh_listener()

    assert listener_task is not None
    assert listener_task.cancelled()
    assert fake_async.pubsub_calls == 1
    assert backend._listener_task is None
    assert backend._pubsub is None
    assert backend._handler is None
    assert backend._listener_live is False
    assert backend._listener_last_error is None
    assert failed_pubsub.close_calls == 1
    await backend.aclose()


@pytest.mark.anyio
async def test_cancelling_redis_listener_start_cleans_blocked_subscription():
    blocked_pubsub = _FakePubSub(wait_before_subscribe=True)
    backend, _, fake_async = await _fake_redis_backend(blocked_pubsub)

    async def handler(_entity: str, _space_id: str | None) -> None:
        return None

    start_task = asyncio.create_task(backend.start_refresh_listener(handler))
    await asyncio.wait_for(blocked_pubsub.subscribe_started.wait(), timeout=1)

    start_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start_task

    assert fake_async.pubsub_calls == 1
    assert blocked_pubsub.unsubscribe_calls == 1
    assert blocked_pubsub.close_calls == 1
    assert backend._listener_task is None
    assert backend._pubsub is None
    assert backend._handler is None
    assert backend._listener_live is False
    assert backend._listener_last_error is None
    await backend.aclose()


@pytest.mark.anyio
async def test_redis_listener_restarts_a_completed_task_and_cleans_stale_pubsub():
    stale_pubsub = _FakePubSub()
    replacement_pubsub = _FakePubSub()
    backend, _, fake_async = await _fake_redis_backend(replacement_pubsub)

    async def fail() -> None:
        raise ConnectionError("completed listener failed")

    completed_task = asyncio.create_task(fail())
    await asyncio.sleep(0)
    assert completed_task.done()
    backend._listener_task = completed_task
    backend._pubsub = stale_pubsub
    backend._handler = None

    async def handler(_entity: str, _space_id: str | None) -> None:
        return None

    try:
        await backend.start_refresh_listener(handler)
        await asyncio.wait_for(replacement_pubsub.listen_started.wait(), timeout=1)

        assert backend._listener_task is not completed_task
        assert backend._listener_task is not None
        assert not backend._listener_task.done()
        assert backend._pubsub is replacement_pubsub
        assert backend._handler is handler
        assert backend._listener_live is True
        assert stale_pubsub.unsubscribe_calls == 1
        assert stale_pubsub.close_calls == 1
        assert fake_async.pubsub_calls == 1
    finally:
        await backend.aclose()


@pytest.mark.anyio
async def test_redis_listener_backoff_is_exponential_and_bounded():
    pubsubs = tuple(
        _FakePubSub(subscribe_error=ConnectionError(f"failure-{index}")) for index in range(7)
    )
    backend, _, _ = await _fake_redis_backend(*pubsubs)
    blocked = asyncio.Event()
    delays: list[float] = []

    async def controlled_sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) == len(pubsubs):
            blocked.set()
            await asyncio.Event().wait()

    backend._listener_sleep = controlled_sleep

    async def handler(_entity: str, _space_id: str | None) -> None:
        return None

    await backend.start_refresh_listener(handler)
    await asyncio.wait_for(blocked.wait(), timeout=1)
    await backend.stop_refresh_listener()

    assert delays == [0.25, 0.5, 1.0, 2.0, 4.0, 5.0, 5.0]
    assert all(pubsub.close_calls == 1 for pubsub in pubsubs)
    await backend.aclose()


@pytest.mark.anyio
async def test_redis_health_degrades_and_recovers_with_bounded_ping():
    pubsub = _FakePubSub()
    backend, fake_sync, _ = await _fake_redis_backend(pubsub)

    async def handler(_entity: str, _space_id: str | None) -> None:
        return None

    try:
        await backend.start_refresh_listener(handler)
        await asyncio.wait_for(pubsub.listen_started.wait(), timeout=1)
        backend.check_health()

        fake_sync.ping_error = ConnectionError("ping disconnected")
        with pytest.raises(
            RuntimeError,
            match="Redis coordination ping failed: ConnectionError: ping disconnected",
        ):
            backend.check_health()

        fake_sync.ping_error = None
        backend.check_health()
        assert fake_sync.ping_calls == 3
    finally:
        await backend.aclose()


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
