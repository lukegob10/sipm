from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from typing import Optional


logger = logging.getLogger(__name__)

_PROFILE_ALIASES = {
    "": "dev",
    "dev": "dev",
    "development": "dev",
    "local": "dev",
    "test": "dev",
    "uat": "uat",
    "prod": "prod",
    "production": "prod",
}
_REFRESH_CHANNEL = "sipm:realtime:refresh"
_SCOPE_VERSION_KEY_PREFIX = "sipm:cache:scope:"
_LISTENER_RECONNECT_INITIAL_DELAY_SECONDS = 0.25
_LISTENER_RECONNECT_MAX_DELAY_SECONDS = 5.0


def _running_tests() -> bool:
    return "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


def _normalized_profile() -> str:
    raw = str(os.getenv("ENV", "")).strip().lower()
    return _PROFILE_ALIASES.get(raw, raw or "dev")


def _configured_backend_name() -> str:
    raw = str(os.getenv("SIPM_COORDINATION_BACKEND", "")).strip().lower()
    profile = _normalized_profile()
    if _running_tests():
        return raw or "memory"
    if profile in {"uat", "prod"}:
        if raw and raw != "redis":
            raise RuntimeError("SIPM_COORDINATION_BACKEND must be 'redis' when ENV resolves to uat or prod.")
        return "redis"
    if not raw:
        return "memory"
    if raw not in {"memory", "redis"}:
        raise RuntimeError("SIPM_COORDINATION_BACKEND must be either 'memory' or 'redis'.")
    return raw


def _redis_url(required: bool) -> str:
    value = str(os.getenv("SIPM_REDIS_URL", "")).strip()
    if required and not value:
        raise RuntimeError("SIPM_REDIS_URL is required when SIPM_COORDINATION_BACKEND=redis.")
    return value


def _redis_timeout_seconds() -> float:
    raw = str(os.getenv("SIPM_REDIS_TIMEOUT_SECONDS", "5")).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError("SIPM_REDIS_TIMEOUT_SECONDS must be a positive number.") from exc
    if value <= 0:
        raise RuntimeError("SIPM_REDIS_TIMEOUT_SECONDS must be a positive number.")
    return value


class CoordinationBackend:
    backend_name = "memory"

    def scope_versions(self, scope_tokens: Iterable[str]) -> dict[str, int]:
        raise NotImplementedError

    def invalidate_scope_tokens(self, scope_tokens: Iterable[str]) -> None:
        raise NotImplementedError

    def publish_refresh(self, entity: str, *, space_id: str | None = None) -> bool:
        raise NotImplementedError

    async def start_refresh_listener(
        self,
        _handler: Callable[[str, str | None], Awaitable[None]],
    ) -> None:
        return None

    async def stop_refresh_listener(self) -> None:
        return None

    def check_health(self) -> None:
        return None

    def clear_state(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


class MemoryCoordinationBackend(CoordinationBackend):
    backend_name = "memory"

    def __init__(self) -> None:
        self._scope_versions: dict[str, int] = {}
        self._lock = threading.RLock()

    def scope_versions(self, scope_tokens: Iterable[str]) -> dict[str, int]:
        with self._lock:
            return {token: self._scope_versions.get(token, 0) for token in scope_tokens}

    def invalidate_scope_tokens(self, scope_tokens: Iterable[str]) -> None:
        with self._lock:
            for token in scope_tokens:
                self._scope_versions[token] = self._scope_versions.get(token, 0) + 1

    def publish_refresh(self, entity: str, *, space_id: str | None = None) -> bool:
        return False

    def clear_state(self) -> None:
        with self._lock:
            self._scope_versions.clear()


class RedisCoordinationBackend(CoordinationBackend):
    backend_name = "redis"

    def __init__(self, redis_url: str) -> None:
        try:
            import redis
            import redis.asyncio as redis_asyncio
        except ImportError as exc:
            raise RuntimeError(
                "Redis coordination requires the `redis` package. Add it to requirements.in."
            ) from exc

        self._timeout_seconds = _redis_timeout_seconds()
        self._redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=self._timeout_seconds,
            socket_timeout=self._timeout_seconds,
        )
        self._aredis = redis_asyncio.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=self._timeout_seconds,
        )
        self._listener_task: Optional[asyncio.Task] = None
        self._pubsub = None
        self._handler: Optional[Callable[[str, str | None], Awaitable[None]]] = None
        self._listener_live = False
        self._listener_last_error: str | None = None
        self._listener_lifecycle_lock = asyncio.Lock()
        self._listener_sleep = asyncio.sleep
        self._fallback_scope_versions: dict[str, int] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _scope_key(token: str) -> str:
        return f"{_SCOPE_VERSION_KEY_PREFIX}{token}"

    def scope_versions(self, scope_tokens: Iterable[str]) -> dict[str, int]:
        tokens = [token for token in scope_tokens if token]
        if not tokens:
            return {}
        try:
            raw_values = self._redis.mget([self._scope_key(token) for token in tokens])
            values: dict[str, int] = {}
            with self._lock:
                for token, raw_value in zip(tokens, raw_values):
                    value = int(raw_value or 0)
                    self._fallback_scope_versions[token] = value
                    values[token] = value
            return values
        except Exception:
            logger.warning("Redis scope-version read failed; using local fallback versions.", exc_info=True)
            with self._lock:
                return {token: self._fallback_scope_versions.get(token, 0) for token in tokens}

    def invalidate_scope_tokens(self, scope_tokens: Iterable[str]) -> None:
        tokens = [token for token in scope_tokens if token]
        if not tokens:
            return
        with self._lock:
            for token in tokens:
                self._fallback_scope_versions[token] = self._fallback_scope_versions.get(token, 0) + 1
        try:
            pipeline = self._redis.pipeline()
            for token in tokens:
                pipeline.incr(self._scope_key(token))
            pipeline.execute()
        except Exception:
            logger.warning("Redis scope invalidation publish failed; continuing with local fallback.", exc_info=True)

    def publish_refresh(self, entity: str, *, space_id: str | None = None) -> bool:
        payload = json.dumps({"entity": entity, "space_id": space_id or ""})
        try:
            self._redis.publish(_REFRESH_CHANNEL, payload)
            return True
        except Exception:
            logger.warning("Redis realtime publish failed; falling back to local broadcast.", exc_info=True)
            return False

    async def start_refresh_listener(
        self,
        handler: Callable[[str, str | None], Awaitable[None]],
    ) -> None:
        first_attempt_done: asyncio.Event | None = None
        listener_task: asyncio.Task | None = None
        async with self._listener_lifecycle_lock:
            with self._lock:
                existing_task = self._listener_task
            if existing_task is not None and not existing_task.done():
                return
            if existing_task is not None:
                self._consume_task_result(existing_task)

            stale_pubsub = self._detach_listener_state(existing_task)
            if stale_pubsub is not None:
                await self._close_pubsub(stale_pubsub)

            first_attempt_done = asyncio.Event()
            with self._lock:
                self._handler = handler
                listener_task = asyncio.create_task(
                    self._supervise_refresh_listener(handler, first_attempt_done),
                    name="sipm-redis-refresh-listener",
                )
                self._listener_task = listener_task
            listener_task.add_done_callback(lambda _task: first_attempt_done.set())

        try:
            await first_attempt_done.wait()
        except asyncio.CancelledError:
            await self._stop_listener_if_current(listener_task)
            raise

    @staticmethod
    def _consume_task_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass

    @staticmethod
    def _error_detail(exc: BaseException) -> str:
        message = " ".join(str(exc).split())
        if not message:
            return type(exc).__name__
        return f"{type(exc).__name__}: {message}"[:500]

    def _detach_listener_state(self, expected_task: asyncio.Task | None = None):
        with self._lock:
            if expected_task is not None and self._listener_task is not expected_task:
                return None
            pubsub = self._pubsub
            self._listener_task = None
            self._pubsub = None
            self._listener_live = False
            return pubsub

    async def _close_pubsub(self, pubsub) -> None:
        with suppress(Exception):
            await asyncio.wait_for(
                pubsub.unsubscribe(_REFRESH_CHANNEL),
                timeout=self._timeout_seconds,
            )
        with suppress(Exception):
            await asyncio.wait_for(pubsub.aclose(), timeout=self._timeout_seconds)

    def _record_listener_failure(self, pubsub, exc: BaseException) -> str:
        detail = self._error_detail(exc)
        with self._lock:
            if self._pubsub is pubsub or pubsub is None:
                self._listener_live = False
                self._listener_last_error = detail
        return detail

    async def _supervise_refresh_listener(
        self,
        handler: Callable[[str, str | None], Awaitable[None]],
        first_attempt_done: asyncio.Event,
    ) -> None:
        delay = _LISTENER_RECONNECT_INITIAL_DELAY_SECONDS
        current_task = asyncio.current_task()
        try:
            while True:
                pubsub = None
                received_message = False
                try:
                    pubsub = self._aredis.pubsub(ignore_subscribe_messages=True)
                    with self._lock:
                        if self._listener_task is not current_task:
                            return
                        self._pubsub = pubsub
                        self._listener_live = False
                    await asyncio.wait_for(
                        pubsub.subscribe(_REFRESH_CHANNEL),
                        timeout=self._timeout_seconds,
                    )
                    with self._lock:
                        if self._listener_task is not current_task or self._pubsub is not pubsub:
                            return
                        self._listener_live = True
                        self._listener_last_error = None
                    first_attempt_done.set()

                    async for message in pubsub.listen():
                        if not isinstance(message, dict) or message.get("type") != "message":
                            continue
                        received_message = True
                        try:
                            payload = json.loads(message.get("data") or "{}")
                        except json.JSONDecodeError:
                            logger.warning(
                                "Ignoring invalid realtime coordination payload: %r",
                                message.get("data"),
                            )
                            continue
                        entity = str(payload.get("entity") or "all")
                        space_id = str(payload.get("space_id") or "").strip() or None
                        await handler(entity, space_id)
                    raise RuntimeError("Redis realtime coordination subscription ended.")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    detail = self._record_listener_failure(pubsub, exc)
                    first_attempt_done.set()
                    logger.warning(
                        "Redis realtime coordination listener failed; retrying in %.2f seconds: %s",
                        delay,
                        detail,
                        exc_info=True,
                    )
                finally:
                    if pubsub is not None:
                        await self._close_pubsub(pubsub)
                    with self._lock:
                        if self._pubsub is pubsub:
                            self._pubsub = None
                            self._listener_live = False

                if received_message:
                    delay = _LISTENER_RECONNECT_INITIAL_DELAY_SECONDS
                await self._listener_sleep(delay)
                delay = min(delay * 2, _LISTENER_RECONNECT_MAX_DELAY_SECONDS)
        finally:
            first_attempt_done.set()
            with self._lock:
                if self._listener_task is current_task:
                    self._listener_live = False

    async def _stop_listener_if_current(self, expected_task: asyncio.Task | None) -> None:
        async with self._listener_lifecycle_lock:
            with self._lock:
                task = self._listener_task
            if task is not expected_task:
                return
            await self._stop_listener_locked(task)

    async def _stop_listener_locked(self, task: asyncio.Task | None) -> None:
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        pubsub = self._detach_listener_state(task)
        if pubsub is not None:
            await self._close_pubsub(pubsub)
        with self._lock:
            if self._listener_task is None:
                self._handler = None
                self._listener_last_error = None

    async def stop_refresh_listener(self) -> None:
        async with self._listener_lifecycle_lock:
            with self._lock:
                task = self._listener_task
            await self._stop_listener_locked(task)

    def check_health(self) -> None:
        with self._lock:
            task = self._listener_task
            listener_live = self._listener_live
            last_error = self._listener_last_error
        if task is None or task.done() or not listener_live:
            detail = last_error or "listener is not subscribed"
            raise RuntimeError(f"Redis coordination listener is unavailable: {detail}")
        try:
            redis_live = self._redis.ping()
        except Exception as exc:
            raise RuntimeError(f"Redis coordination ping failed: {self._error_detail(exc)}") from exc
        if not redis_live:
            raise RuntimeError("Redis coordination ping failed: Redis returned an unhealthy response")
        with self._lock:
            if self._listener_task is not task or task.done() or not self._listener_live:
                detail = self._listener_last_error or "listener is not subscribed"
                raise RuntimeError(f"Redis coordination listener is unavailable: {detail}")

    def clear_state(self) -> None:
        with self._lock:
            self._fallback_scope_versions.clear()

    async def aclose(self) -> None:
        await self.stop_refresh_listener()
        with suppress(Exception):
            await self._aredis.aclose()
        with suppress(Exception):
            self._redis.close()


_BACKEND_LOCK = threading.RLock()
_BACKEND: CoordinationBackend | None = None
_BACKEND_CONFIG: tuple[str, str] | None = None


def _close_backend(backend: CoordinationBackend) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(backend.aclose())
    else:
        loop.create_task(backend.aclose())


def _current_config() -> tuple[str, str]:
    backend_name = _configured_backend_name()
    redis_url = _redis_url(required=backend_name == "redis")
    return (backend_name, redis_url)


def _build_backend(config: tuple[str, str]) -> CoordinationBackend:
    backend_name, redis_url = config
    if backend_name == "redis":
        return RedisCoordinationBackend(redis_url)
    return MemoryCoordinationBackend()


def get_backend() -> CoordinationBackend:
    global _BACKEND, _BACKEND_CONFIG
    config = _current_config()
    with _BACKEND_LOCK:
        if _BACKEND is not None and _BACKEND_CONFIG == config:
            return _BACKEND
    candidate = _build_backend(config)
    with _BACKEND_LOCK:
        if _BACKEND is not None and _BACKEND_CONFIG == config:
            _close_backend(candidate)
            return _BACKEND
        previous = _BACKEND
        _BACKEND = candidate
        _BACKEND_CONFIG = config
    if previous is not None:
        _close_backend(previous)
    return candidate


def validate_configuration() -> str:
    return get_backend().backend_name


def backend_name() -> str:
    return get_backend().backend_name


def uses_redis() -> bool:
    return backend_name() == "redis"


def scope_versions(scope_tokens: Iterable[str]) -> dict[str, int]:
    return get_backend().scope_versions(scope_tokens)


def invalidate_scope_tokens(scope_tokens: Iterable[str]) -> None:
    get_backend().invalidate_scope_tokens(scope_tokens)


def publish_refresh(entity: str, *, space_id: str | None = None) -> bool:
    return get_backend().publish_refresh(entity, space_id=space_id)


def check_health() -> None:
    get_backend().check_health()


async def start_refresh_listener(
    handler: Callable[[str, str | None], Awaitable[None]],
) -> None:
    await get_backend().start_refresh_listener(handler)


async def stop_refresh_listener() -> None:
    await get_backend().stop_refresh_listener()


def clear_state() -> None:
    get_backend().clear_state()


async def reset_backend_for_tests() -> None:
    global _BACKEND, _BACKEND_CONFIG
    with _BACKEND_LOCK:
        backend = _BACKEND
        _BACKEND = None
        _BACKEND_CONFIG = None
    if backend is not None:
        await backend.aclose()
