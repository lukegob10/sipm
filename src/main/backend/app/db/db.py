import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

from ..runtime import get_ta_connection_env, is_ta_oracle_mode


def _resolve_database_url() -> str:
    explicit = os.getenv("SIPM_DATABASE_URL")
    if explicit:
        return explicit

    profile = (os.getenv("SIPM_DB_PROFILE") or "").strip().lower()
    profile_aliases = {
        "production": "prod",
        "prod": "prod",
        "uat": "uat",
        "dev": "dev",
        "development": "dev",
    }
    profile = profile_aliases.get(profile, profile)
    env_map = {
        "dev": "SIPM_DATABASE_URL_DEV",
        "uat": "SIPM_DATABASE_URL_UAT",
        "prod": "SIPM_DATABASE_URL_PROD",
    } 
    if profile in env_map:
        url = os.getenv(env_map[profile])
        if url:
            return url

    # Canonical local database location under src/main/data.
    db_path = Path(__file__).resolve().parents[3] / "data" / "jira_lite.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = _resolve_database_url()


def _build_engine():
    if is_ta_oracle_mode():
        # Use treasury_analytics to create Oracle connections in TA Oracle mode.
        def _ta_creator():
            from treasury_analytics import TAConnection

            ta = TAConnection(env=get_ta_connection_env())
            return ta.connect()

        return create_engine(
            "oracle+oracledb://",
            creator=_ta_creator,
            poolclass=NullPool,
        )

    # Default to configured DATABASE_URL when TA Oracle mode is not enabled.
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    return create_engine(DATABASE_URL, connect_args=connect_args)


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(run_seed: bool = True) -> None:
    """Create database tables and optionally run seed routines."""
    from ..models import Base  # imported here to avoid circulars
    from ..services.migrations import run_schema_migrations

    Base.metadata.create_all(bind=engine)
    if not is_ta_oracle_mode():
        run_schema_migrations(engine)

    if not run_seed:
        return

    # Imported here to avoid circulars and keep seed routines isolated from startup wiring.
    from ..services.seed import seed_phases
    from ..services.sample_seed import seed_sample_data

    with SessionLocal() as session:
        seed_phases(session)
        seed_sample_data(session)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
