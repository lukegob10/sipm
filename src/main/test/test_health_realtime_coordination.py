from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import pytest

from backend.app.routes import sync
from backend.app.services import coordination, smart_cache


@pytest.mark.anyio
async def test_cancelled_websocket_auth_keeps_cancellation_after_worker_failure(monkeypatch):
    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    worker_thread = None

    class Session:
        close_thread = None

        def query(self):
            pass

        def close(self):
            self.close_thread = threading.get_ident()

    class Socket:
        cookies = {"access_token": "token"}
        query_params = {}
        headers = {}
        accepted = False
        closed = False

        async def accept(self):
            self.accepted = True

        async def close(self, **_kwargs):
            self.closed = True

    def failing_auth(_session, _token):
        nonlocal worker_thread
        worker_thread = threading.get_ident()
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise TimeoutError("test did not release auth worker")
        raise RuntimeError("auth query failed after cancellation")

    monkeypatch.setattr(sync, "authenticate_access_token_context", failing_auth)
    session = Session()
    socket = Socket()
    endpoint = asyncio.create_task(sync.websocket_endpoint(socket, session=session))
    try:
        await asyncio.wait_for(started.wait(), 1)
        endpoint.cancel()
        await asyncio.sleep(0)
        assert not endpoint.done()
        endpoint.cancel()
        await asyncio.sleep(0)
        assert not endpoint.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await endpoint

    assert session.close_thread == worker_thread
    assert session.close_thread != threading.get_ident()
    assert not socket.accepted
    assert not socket.closed


@pytest.mark.parametrize("operation", ["get", "set"])
def test_cache_defensive_copy_does_not_block_unrelated_hits(monkeypatch, operation):
    monkeypatch.setenv("SIPM_SMART_CACHE_ENABLED", "true")
    monkeypatch.setattr(smart_cache, "_CACHE", {})
    smart_cache.set_cached("warm", {"ready": True}, ttl_seconds=60)
    value = {"items": [1, 2, 3]}
    if operation == "get":
        smart_cache.set_cached("large", value, ttl_seconds=60)
        copy_target = smart_cache._CACHE["large"].value
    else:
        copy_target = value
    copying_started = threading.Event()
    release_copy = threading.Event()
    original_deepcopy = smart_cache.copy.deepcopy

    def blocked_deepcopy(item, memo=None):
        if item is copy_target:
            copying_started.set()
            if not release_copy.wait(5):
                raise TimeoutError("test did not release cache copy")
        return original_deepcopy(item, memo)

    monkeypatch.setattr(smart_cache.copy, "deepcopy", blocked_deepcopy)
    with ThreadPoolExecutor(max_workers=2) as workers:
        if operation == "get":
            copying = workers.submit(smart_cache.get_cached, "large")
        else:
            copying = workers.submit(smart_cache.set_cached, "large", value, 60)
        independent_hit_finished = False
        try:
            assert copying_started.wait(1)
            warm_hit = workers.submit(smart_cache.get_cached, "warm")
            try:
                assert warm_hit.result(timeout=1) == {"ready": True}
                independent_hit_finished = True
            except FutureTimeoutError:
                pass
        finally:
            release_copy.set()
        copying.result(timeout=1)

    assert independent_hit_finished, "An unrelated cache hit waited for another response's copy"


def test_cache_copy_preserves_snapshot_during_clear_and_replacement(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_ENABLED", "true")
    monkeypatch.setattr(smart_cache, "_CACHE", {})
    original = {"items": [1]}
    smart_cache.set_cached("entry", original, ttl_seconds=60)
    original["items"].append(99)
    copy_target = smart_cache._CACHE["entry"].value
    copying_started = threading.Event()
    release_copy = threading.Event()
    original_deepcopy = smart_cache.copy.deepcopy

    def blocked_deepcopy(item, memo=None):
        if item is copy_target:
            copying_started.set()
            if not release_copy.wait(5):
                raise TimeoutError("test did not release cache copy")
        return original_deepcopy(item, memo)

    def replace_entry():
        smart_cache.clear_cache()
        replacement = {"items": [2]}
        smart_cache.set_cached("entry", replacement, ttl_seconds=60)
        replacement["items"].append(99)
        return smart_cache.get_cached("entry")

    monkeypatch.setattr(smart_cache.copy, "deepcopy", blocked_deepcopy)
    with ThreadPoolExecutor(max_workers=2) as workers:
        snapshot_read = workers.submit(smart_cache.get_cached, "entry")
        try:
            assert copying_started.wait(1)
            replacement = workers.submit(replace_entry).result(timeout=1)
        finally:
            release_copy.set()
        snapshot = snapshot_read.result(timeout=1)

    assert snapshot == {"items": [1]}
    assert replacement == {"items": [2]}
    snapshot["items"].append(3)
    replacement["items"].append(4)
    assert smart_cache.get_cached("entry") == {"items": [2]}


@pytest.mark.anyio
async def test_redis_listener_ignores_non_object_json_without_reconnecting(monkeypatch):
    delivered = asyncio.Event()
    received = []
    subscriptions = []

    class PubSub:
        close_calls = 0

        async def subscribe(self, channel):
            subscriptions.append(channel)

        async def listen(self):
            yield {"type": "subscribe", "channel": coordination._REFRESH_CHANNEL}
            for payload in ("{", "[]", "null", "true", "1", '"text"'):
                yield {"type": "message", "data": payload}
            yield {"type": "message", "data": '{"entity":"tasks","space_id":"space-1"}'}
            await asyncio.Event().wait()

        async def unsubscribe(self, _channel):
            pass

        async def aclose(self):
            self.close_calls += 1

    pubsub = PubSub()
    backend = coordination.RedisCoordinationBackend("redis://127.0.0.1:6379/0")
    monkeypatch.setattr(backend._aredis, "pubsub", lambda **_kwargs: pubsub)

    async def handler(entity, space_id):
        received.append((entity, space_id))
        if entity == "tasks":
            delivered.set()

    try:
        await backend.start_refresh_listener(handler)
        await asyncio.wait_for(delivered.wait(), 1)
        assert received == [("tasks", "space-1")]
        assert subscriptions == [coordination._REFRESH_CHANNEL]
        assert backend._listener_live
        assert pubsub.close_calls == 0
    finally:
        await backend.aclose()
    assert pubsub.close_calls == 1
