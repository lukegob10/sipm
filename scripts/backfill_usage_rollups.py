#!/usr/bin/env python3
"""Preview or repair retained analytics rollups while telemetry ingestion is paused."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

from sqlalchemy.orm import Session

MAIN_DIR = Path(__file__).resolve().parents[1] / "src" / "main"
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

def main(argv: list[str] | None = None) -> None:
    from backend.app.db.db import get_engine
    from backend.app.services.analytics_backfill import backfill_usage_rollups

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, choices=(7, 30, 90), default=90,
                        help="Number of complete UTC calendar days ending today (default: 90).")
    parser.add_argument("--apply", action="store_true", help="Commit the backfill; otherwise only preview changes.")
    args = parser.parse_args(argv)
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    until = datetime.combine(tomorrow, datetime.min.time())
    since = until - timedelta(days=args.days)
    with Session(get_engine(), autoflush=False) as session:
        counts = backfill_usage_rollups(session, since=since, until=until, apply=args.apply)
        if args.apply:
            session.commit()
        else:
            session.rollback()
    print(json.dumps({"applied": args.apply, "since_utc": since.isoformat(), "until_utc": until.isoformat(), **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
