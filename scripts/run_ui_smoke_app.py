#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_DIR = REPO_ROOT / "src" / "main"
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SIPM_COORDINATION_BACKEND", "memory")
os.environ.setdefault("SIPM_DISABLE_STARTUP", "true")
os.environ.setdefault("SIPM_KEEPALIVE_TASK", "false")

from backend.app.models import Base  # noqa: E402
import backend.app.db.db as db_module  # noqa: E402
from backend.main import app  # noqa: E402


def configure_sqlite_runtime(temp_dir: Path) -> None:
    db_path = temp_dir / "ui-smoke.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sipm-ui-smoke-") as temp_dir:
        configure_sqlite_runtime(Path(temp_dir))
        port = int(os.getenv("SIPM_UI_SMOKE_PORT", "8000"))
        try:
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        finally:
            db_module.engine.dispose()
            db_module.engine = None
            db_module.SessionLocal = None


if __name__ == "__main__":
    main()
