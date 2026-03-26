from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Iterable, Optional

from .coordination import clear_state as clear_coordination_state
from .coordination import invalidate_scope_tokens as coordinated_invalidate_scope_tokens
from .coordination import scope_versions as coordinated_scope_versions


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float
    created_at: float


_CACHE: dict[str, _CacheEntry] = {}
_LOCK = threading.RLock()


def _bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def _int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _cache_enabled() -> bool:
    return _bool_env("SIPM_SMART_CACHE_ENABLED", True)


def _cache_max_entries() -> int:
    configured = _int_env("SIPM_SMART_CACHE_MAX_ENTRIES", 4096)
    if configured <= 0:
        raise RuntimeError("SIPM_SMART_CACHE_MAX_ENTRIES must be greater than or equal to 1.")
    return max(256, configured)


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def make_scope_token(namespace: str, space_id: str) -> str:
    return f"{namespace}:{space_id}"


def _purge_expired_locked(now: float) -> None:
    expired = [key for key, entry in _CACHE.items() if entry.expires_at <= now]
    for key in expired:
        _CACHE.pop(key, None)


def _evict_if_needed_locked(now: float) -> None:
    max_entries = _cache_max_entries()
    if len(_CACHE) <= max_entries:
        return
    # Evict oldest entries first.
    ordered = sorted(_CACHE.items(), key=lambda item: item[1].created_at)
    over = len(_CACHE) - max_entries
    for key, _entry in ordered[:over]:
        _CACHE.pop(key, None)


def _scope_version_snapshot(scope_tokens: Iterable[str]) -> dict[str, int]:
    return coordinated_scope_versions(scope_tokens)


def build_scoped_cache_key(
    *,
    endpoint: str,
    params: dict[str, Any],
    space_id: str,
    user_id: Optional[str],
    role_scope: str,
    scope_tokens: Iterable[str],
) -> str:
    with _LOCK:
        versions = _scope_version_snapshot(scope_tokens)
    payload = {
        "endpoint": endpoint,
        "params": params or {},
        "space_id": space_id,
        "user_id": user_id or "",
        "role_scope": role_scope or "",
        "versions": versions,
    }
    raw = json.dumps(payload, sort_keys=True, default=_json_default, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached(key: str) -> Any | None:
    if not _cache_enabled():
        return None
    now = time.time()
    with _LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        if entry.expires_at <= now:
            _CACHE.pop(key, None)
            return None
        return copy.deepcopy(entry.value)


def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    if not _cache_enabled() or ttl_seconds <= 0:
        return
    now = time.time()
    expires_at = now + float(ttl_seconds)
    with _LOCK:
        _purge_expired_locked(now)
        _CACHE[key] = _CacheEntry(value=copy.deepcopy(value), expires_at=expires_at, created_at=now)
        _evict_if_needed_locked(now)


def cached_call(
    *,
    endpoint: str,
    params: dict[str, Any],
    space_id: str,
    user_id: Optional[str],
    role_scope: str,
    ttl_seconds: int,
    scope_tokens: Iterable[str],
    loader: Callable[[], Any],
) -> Any:
    if not _cache_enabled():
        return loader()
    key = build_scoped_cache_key(
        endpoint=endpoint,
        params=params,
        space_id=space_id,
        user_id=user_id,
        role_scope=role_scope,
        scope_tokens=scope_tokens,
    )
    cached = get_cached(key)
    if cached is not None:
        return cached
    value = loader()
    set_cached(key, value, ttl_seconds)
    return copy.deepcopy(value)


def invalidate_scope_tokens(scope_tokens: Iterable[str]) -> None:
    coordinated_invalidate_scope_tokens(scope_tokens)


def invalidate_space(space_id: str, namespaces: Iterable[str]) -> None:
    tokens = [make_scope_token(namespace, space_id) for namespace in namespaces]
    invalidate_scope_tokens(tokens)


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
    clear_coordination_state()
