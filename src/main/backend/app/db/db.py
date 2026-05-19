from __future__ import annotations

from .engine import DB_HEALTHCHECK_SQL
from .engine import build_engine as _build_engine
from .session import (
    _ensure_session_local,
    check_db_connection,
    get_session,
    init_db,
    reset_session_state,
    warm_db_pool,
)
from .settings import _env_bool, _env_int, _require_min, _require_min_or_disable


def __getattr__(name: str):
    if name in {"engine", "SessionLocal"}:
        from . import session

        return getattr(session, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DB_HEALTHCHECK_SQL",
    "SessionLocal",
    "_build_engine",
    "_ensure_session_local",
    "_env_bool",
    "_env_int",
    "_require_min",
    "_require_min_or_disable",
    "check_db_connection",
    "engine",
    "get_session",
    "init_db",
    "reset_session_state",
    "warm_db_pool",
]
