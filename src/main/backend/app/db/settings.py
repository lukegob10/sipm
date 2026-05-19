from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DatabasePoolSettings:
    pool_size: int
    max_overflow: int
    pool_timeout_seconds: int
    pool_recycle_seconds: int
    pool_pre_ping: bool
    pool_use_lifo: bool


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _require_min(name: str, value: int, minimum: int) -> int:
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}.")
    return value


def _require_min_or_disable(name: str, value: int, disable_value: int, minimum: int) -> int:
    if value == disable_value:
        return value
    if value < minimum:
        raise RuntimeError(f"{name} must be {disable_value} or >= {minimum}.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def load_database_pool_settings() -> DatabasePoolSettings:
    return DatabasePoolSettings(
        pool_size=_require_min("SIPM_DB_POOL_SIZE", _env_int("SIPM_DB_POOL_SIZE", 5), 0),
        max_overflow=_require_min_or_disable(
            "SIPM_DB_MAX_OVERFLOW",
            _env_int("SIPM_DB_MAX_OVERFLOW", 10),
            -1,
            0,
        ),
        pool_timeout_seconds=_require_min(
            "SIPM_DB_POOL_TIMEOUT_SECONDS",
            _env_int("SIPM_DB_POOL_TIMEOUT_SECONDS", 30),
            0,
        ),
        pool_recycle_seconds=_require_min_or_disable(
            "SIPM_DB_POOL_RECYCLE_SECONDS",
            _env_int("SIPM_DB_POOL_RECYCLE_SECONDS", 1800),
            -1,
            0,
        ),
        pool_pre_ping=_env_bool("SIPM_DB_POOL_PRE_PING", True),
        pool_use_lifo=_env_bool("SIPM_DB_POOL_USE_LIFO", False),
    )


__all__ = [
    "DatabasePoolSettings",
    "_env_bool",
    "_env_int",
    "_require_min",
    "_require_min_or_disable",
    "load_database_pool_settings",
]
