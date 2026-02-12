import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

from ..runtime import get_ta_connection_env, is_ta_oracle_mode


def _is_running_tests() -> bool:
    return "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


def _sqlite_allowed() -> bool:
    return _is_running_tests() or str(os.getenv("SIPM_ALLOW_SQLITE", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _validate_database_url(url: str) -> str:
    if url.startswith("sqlite") and not _sqlite_allowed():
        raise RuntimeError(
            "SQLite is disabled for this runtime. Configure Oracle/enterprise DB URL "
            "(SIPM_DATABASE_URL*) or set SIPM_ALLOW_SQLITE=true for local sqlite."
        )
    return url


def _resolve_database_url() -> str:
    explicit = os.getenv("SIPM_DATABASE_URL")
    if explicit:
        return _validate_database_url(explicit)

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
            return _validate_database_url(url)

    # Canonical local database location under src/main/data for tests or explicit opt-in only.
    if _sqlite_allowed():
        db_path = Path(__file__).resolve().parents[3] / "data" / "jira_lite.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    raise RuntimeError(
        "No database URL configured. Set SIPM_DATABASE_URL (or profile-specific URL), "
        "or set SIPM_ALLOW_SQLITE=true for local sqlite."
    )


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

    is_sqlite = engine.dialect.name == "sqlite"
    if is_sqlite:
        from ..services.migrations import migrate_legacy_table_names

        migrate_legacy_table_names(engine)

    Base.metadata.create_all(bind=engine)

    if is_sqlite:
        from ..services.migrations import run_schema_migrations

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
