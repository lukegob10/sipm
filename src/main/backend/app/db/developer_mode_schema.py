from __future__ import annotations

from sqlalchemy.engine import Engine

from ..models import UserPreference, UserTaskState
from .db import get_engine


DEVELOPER_MODE_TABLES = (
    UserPreference.__table__,
    UserTaskState.__table__,
)


def ensure_developer_mode_schema(bind: Engine | None = None) -> None:
    """Create the additive Developer Mode tables and indexes when missing."""
    target = bind or get_engine()
    for table in DEVELOPER_MODE_TABLES:
        table.create(bind=target, checkfirst=True)
        for index in table.indexes:
            index.create(bind=target, checkfirst=True)


def main() -> None:
    ensure_developer_mode_schema()
    print("Developer Mode schema is ready.")


if __name__ == "__main__":
    main()
