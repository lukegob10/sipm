"""Centralized physical table naming for all DB dialects.

Convention:
- Default: ``TB_TA_PM_{LOGICAL_TABLE_NAME}`` (uppercase)
"""

from __future__ import annotations

from typing import Final

_PREFIX: Final[str] = "TB_TA_PM_"


def physical_table_name(logical_name: str) -> str:
    """Return the physical table name for a logical ORM table name."""
    key = logical_name.strip().lower()
    if not key:
        raise ValueError("logical_name must not be empty")
    return f"{_PREFIX}{key.upper()}"


def fk_target(logical_table: str, column: str) -> str:
    """Return ``<physical_table>.<column>`` for SQLAlchemy ``ForeignKey``."""
    col = column.strip()
    if not col:
        raise ValueError("column must not be empty")
    return f"{physical_table_name(logical_table)}.{col}"
