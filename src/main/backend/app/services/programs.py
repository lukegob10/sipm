from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Program
from .spaces import SpaceContext

DEFAULT_PROGRAM_NAME = "Default Program"


def program_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Program)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
    )


def get_program_or_404(session: Session, program_id: str, space_ctx: SpaceContext) -> Program:
    program = (
        program_query(session, space_ctx)
        .filter(Program.program_id == program_id)
        .first()
    )
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


def ensure_program_exists(session: Session, program_id: str, space_ctx: SpaceContext) -> Program:
    return get_program_or_404(session, program_id, space_ctx)


def ensure_default_program(session: Session, space_ctx: SpaceContext) -> Program:
    program = (
        session.query(Program)
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.program_name == DEFAULT_PROGRAM_NAME)
        .first()
    )
    now = datetime.now(timezone.utc)
    if program and program.deleted_at is None:
        return program
    if program:
        program.deleted_at = None
        program.updated_at = now
        session.add(program)
        session.flush()
        return program
    program = Program(
        space_id=space_ctx.space_id,
        program_name=DEFAULT_PROGRAM_NAME,
        description="Default umbrella program for existing projects.",
        created_at=now,
        updated_at=now,
    )
    session.add(program)
    session.flush()
    return program
