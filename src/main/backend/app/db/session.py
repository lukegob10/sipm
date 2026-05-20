from __future__ import annotations

from threading import Lock

from sqlalchemy.orm import sessionmaker

from .engine import DB_HEALTHCHECK_SQL, build_engine


_SESSION_LOCAL_LOCK = Lock()
engine = None
SessionLocal = None


def reset_session_state() -> None:
    global engine, SessionLocal
    with _SESSION_LOCAL_LOCK:
        engine = None
        SessionLocal = None


def _ensure_session_local():
    global engine, SessionLocal
    if SessionLocal is None:
        with _SESSION_LOCAL_LOCK:
            if SessionLocal is None:
                created_engine = build_engine()
                engine = created_engine
                SessionLocal = sessionmaker(
                    autocommit=False, autoflush=False, bind=created_engine
                )
    return SessionLocal


def init_db(create_schema: bool = False) -> None:
    """
    Optional DB bootstrap helper for TA/Oracle deployments.

    - `create_schema=True` runs SQLAlchemy `create_all`.
    Defaults keep startup non-mutating for managed Oracle environments.
    """
    if not create_schema:
        return

    _ensure_session_local()

    from ..models import Base  # imported lazily to avoid circulars

    Base.metadata.create_all(bind=engine)


def check_db_connection() -> None:
    _ensure_session_local()
    with engine.connect() as connection:
        connection.execute(DB_HEALTHCHECK_SQL)
        connection.commit()


def warm_db_pool(connection_count: int = 1) -> None:
    if connection_count < 1:
        raise RuntimeError("connection_count must be >= 1.")
    _ensure_session_local()
    connections = []
    try:
        for _ in range(connection_count):
            connection = engine.connect()
            connection.execute(DB_HEALTHCHECK_SQL)
            connection.commit()
            connections.append(connection)
    finally:
        while connections:
            connections.pop().close()


def get_session():
    local_session = _ensure_session_local()
    db = local_session()
    try:
        yield db
    finally:
        db.close()


__all__ = [
    "DB_HEALTHCHECK_SQL",
    "SessionLocal",
    "_ensure_session_local",
    "check_db_connection",
    "engine",
    "get_session",
    "init_db",
    "reset_session_state",
    "sessionmaker",
    "warm_db_pool",
]
