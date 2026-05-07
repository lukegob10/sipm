#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
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


def configure_sqlite_runtime() -> None:
    temp_dir = REPO_ROOT / ".tmp"
    temp_dir.mkdir(exist_ok=True)
    db_path = temp_dir / "ui-smoke.db"
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)


def main() -> None:
    configure_sqlite_runtime()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
