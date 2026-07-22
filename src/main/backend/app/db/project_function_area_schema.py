from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

from ..models import Project
from .db import get_engine


PROJECT_FUNCTION_AREA_COLUMNS = (
    Project.__table__.c.function,
    Project.__table__.c.area,
)


def ensure_project_function_area_schema(bind: Engine | None = None) -> None:
    """Add the nullable Project function and area columns when they are missing."""
    target = bind or get_engine()
    table = Project.__table__
    inspector = inspect(target)
    if not inspector.has_table(table.name):
        raise RuntimeError(f"Required project table {table.name!r} does not exist.")

    existing_columns = {
        str(column["name"]).lower() for column in inspector.get_columns(table.name)
    }
    table_sql = target.dialect.identifier_preparer.format_table(table)
    with target.begin() as connection:
        for column in PROJECT_FUNCTION_AREA_COLUMNS:
            if column.name.lower() in existing_columns:
                continue
            column_sql = str(CreateColumn(column).compile(dialect=target.dialect))
            if target.dialect.name == "oracle":
                ddl = f"ALTER TABLE {table_sql} ADD ({column_sql})"
            else:
                ddl = f"ALTER TABLE {table_sql} ADD COLUMN {column_sql}"
            connection.execute(text(ddl))


def main() -> None:
    ensure_project_function_area_schema()
    print("Project function and area schema is ready.")


if __name__ == "__main__":
    main()
