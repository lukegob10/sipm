import os
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..runtime import get_ta_connection_env


_SESSION_LOCAL_LOCK = Lock()


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def _build_engine():
    # Always use TAConnection + Oracle for this application runtime.
    def _ta_creator():
        from treasury_analytics import TAConnection

        ta = TAConnection(env=get_ta_connection_env())
        return ta.connect()

    return create_engine(
        "oracle+oracledb://",
        creator=_ta_creator,
        pool_size=_env_int("SIPM_DB_POOL_SIZE", 5),
        max_overflow=_env_int("SIPM_DB_MAX_OVERFLOW", 10),
        pool_timeout=_env_int("SIPM_DB_POOL_TIMEOUT_SECONDS", 30),
        pool_recycle=_env_int("SIPM_DB_POOL_RECYCLE_SECONDS", 1800),
        pool_pre_ping=_env_bool("SIPM_DB_POOL_PRE_PING", True),
    )


engine = None
SessionLocal = None


def _ensure_session_local():
    global engine, SessionLocal
    if SessionLocal is None:
        with _SESSION_LOCAL_LOCK:
            if SessionLocal is None:
                created_engine = _build_engine()
                engine = created_engine
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=created_engine)
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


def get_session():
    local_session = _ensure_session_local()
    db = local_session()
    try:
        yield db
    finally:
        db.close()
