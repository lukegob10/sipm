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
        if self._listener_task is not None:
            return
        self._handler = handler
        self._pubsub = self._aredis.pubsub(ignore_subscribe_messages=True)
        try:
            await asyncio.wait_for(
                self._pubsub.subscribe(_REFRESH_CHANNEL),
                timeout=self._timeout_seconds,
            )
        except BaseException:
            with suppress(Exception):
                await asyncio.wait_for(self._pubsub.aclose(), timeout=self._timeout_seconds)
            self._pubsub = None
            self._handler = None
            raise
        self._listener_task = asyncio.create_task(self._listen(), name="sipm-redis-refresh-listener")

    async def _listen(self) -> None:
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if not isinstance(message, dict) or message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message.get("data") or "{}")
                except json.JSONDecodeError:
                    logger.warning("Ignoring invalid realtime coordination payload: %r", message.get("data"))
                    continue
                entity = str(payload.get("entity") or "all")
                space_id = str(payload.get("space_id") or "").strip() or None
                if self._handler is not None:
                    await self._handler(entity, space_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis realtime coordination listener stopped unexpectedly.")
            raise

    async def stop_refresh_listener(self) -> None:
        task = self._listener_task
        self._listener_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self._pubsub is not None:
            with suppress(Exception):
                await asyncio.wait_for(
                    self._pubsub.unsubscribe(_REFRESH_CHANNEL),
                    timeout=self._timeout_seconds,
                )
            with suppress(Exception):
                await asyncio.wait_for(self._pubsub.aclose(), timeout=self._timeout_seconds)
            self._pubsub = None
        self._handler = None

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
