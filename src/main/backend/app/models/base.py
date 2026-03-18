from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, MetaData
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.sqltypes import String as SQLAlchemyString


class Base(DeclarativeBase):
    metadata = MetaData()


@compiles(SQLAlchemyString, "oracle")
def _compile_oracle_string_with_default_length(type_, compiler, **kw):
    # Oracle table DDL requires VARCHAR2 length; default to 255 when unspecified.
    if type_.length is None:
        return "VARCHAR2(255 CHAR)"
    return compiler.visit_VARCHAR(type_, **kw)


def _utcnow_naive() -> datetime:
    # Keep DB values UTC while preserving naive DateTime column behavior.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        onupdate=_utcnow_naive,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )


__all__ = ["Base", "SoftDeleteMixin", "TimestampMixin", "_utcnow_naive"]
