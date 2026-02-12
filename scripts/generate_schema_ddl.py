#!/usr/bin/env python3
"""Generate SQL DDL files from SQLAlchemy metadata.

This script emits CREATE TABLE and CREATE INDEX statements that match the
application model definitions in `app.models`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.dialects import oracle
from sqlalchemy.schema import CreateIndex, CreateTable


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "src" / "main" / "backend"


def _load_metadata(ta_mode: bool):
    _ = ta_mode
    # Retained for CLI compatibility; table naming no longer depends on runtime user/schema.
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.models import Base

    return Base.metadata


def _render_sql(metadata, dialect_name: str) -> str:
    if dialect_name == "oracle":
        dialect = oracle.dialect()
    else:
        raise ValueError(f"Unsupported dialect: {dialect_name}")

    out: list[str] = []
    if dialect_name == "oracle":
        out.extend(
            [
                "-- Oracle DDL generated from SQLAlchemy models.",
                "-- Table names follow TB_TA_PM_* with no schema qualifier.",
                "",
            ]
        )
    for table in metadata.sorted_tables:
        out.append(f"-- Table: {table.fullname}")
        out.append(str(CreateTable(table).compile(dialect=dialect)).rstrip() + ";")
        out.append("")

    # Emit indexes after tables.
    indexes = []
    for table in metadata.sorted_tables:
        for idx in table.indexes:
            indexes.append((idx.name or "", idx))

    for _, idx in sorted(indexes, key=lambda pair: pair[0]):
        out.append(f"-- Index: {idx.name}")
        out.append(str(CreateIndex(idx).compile(dialect=dialect)).rstrip() + ";")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DB DDL files from ORM models")
    parser.add_argument(
        "--dialect",
        choices=("oracle",),
        required=True,
        help="SQL dialect to generate",
    )
    parser.add_argument(
        "--ta-mode",
        action="store_true",
        help="Compatibility flag (currently no-op)",
    )
    parser.add_argument("--output", required=True, help="Output .sql file path")
    args = parser.parse_args()

    metadata = _load_metadata(ta_mode=args.ta_mode)
    sql = _render_sql(metadata, args.dialect)

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sql, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
