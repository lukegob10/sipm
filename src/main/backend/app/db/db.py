import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..runtime import get_ta_connection_env


def _build_engine():
    # Always use TAConnection + Oracle for this application runtime.
    def _ta_creator():
        from treasury_analytics import TAConnection

        ta = TAConnection(env=get_ta_connection_env())
        return ta.connect()

    return create_engine(
        "oracle+oracledb://",
        creator=_ta_creator,
        pool_size=int(os.getenv("SIPM_DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("SIPM_DB_MAX_OVERFLOW", "10")),
        pool_timeout=int(os.getenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "30")),
        pool_recycle=int(os.getenv("SIPM_DB_POOL_RECYCLE_SECONDS", "1800")),
        pool_pre_ping=(os.getenv("SIPM_DB_POOL_PRE_PING", "true").strip().lower() != "false"),
    )


engine = None
SessionLocal = None


def _ensure_session_local():
    global engine, SessionLocal
    if SessionLocal is None:
        engine = _build_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
