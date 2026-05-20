from __future__ import annotations

from sqlalchemy import create_engine, text

from ..runtime import get_ta_connection_env
from .settings import DatabasePoolSettings, load_database_pool_settings


DB_HEALTHCHECK_SQL = text("SELECT 1 FROM DUAL")


def _ta_connection_creator():
    from treasury_analytics import TAConnection

    ta = TAConnection(env=get_ta_connection_env())
    return ta.connect()


def build_engine(settings: DatabasePoolSettings | None = None):
    # Always use TAConnection + Oracle for this application runtime.
    settings = settings or load_database_pool_settings()
    return create_engine(
        "oracle+oracledb://",
        creator=_ta_connection_creator,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_seconds,
        pool_recycle=settings.pool_recycle_seconds,
        pool_pre_ping=settings.pool_pre_ping,
        pool_use_lifo=settings.pool_use_lifo,
    )


__all__ = ["DB_HEALTHCHECK_SQL", "build_engine", "create_engine"]
