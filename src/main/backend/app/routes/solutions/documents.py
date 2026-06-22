from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_non_agent_write, require_space_role
from ...models import SolutionDocument, User
from ...schemas import SolutionDocumentRead
from ...services.audit_log import safe_log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_str
from ...services.mutations import commit_session
from .common import _get_solution_or_404, _publish_solution_mutation

router = APIRouter()

MAX_SOLUTION_DOCUMENT_BYTES = 25 * 1024 * 1024


def _document_payload(document: SolutionDocument) -> dict:
    return SolutionDocumentRead.model_validate(document).model_dump(mode="json")


def _binary_value(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if hasattr(value, "read"):
        data = value.read()
        return data if isinstance(data, bytes) else bytes(data)
    return bytes(value or b"")


def _content_disposition(filename: str) -> str:
    fallback = "".join(ch if ch.isascii() and ch not in {'"', "\\", "\r", "\n"} else "_" for ch in filename).strip()
    fallback = fallback or "document"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _get_document_or_404(
    session: Session,
    *,
    solution_id: str,
    document_id: str,
    space_ctx: SpaceContext,
) -> SolutionDocument:
    _get_solution_or_404(session, solution_id, space_ctx)
    document = (
        session.query(SolutionDocument)
        .filter(SolutionDocument.document_id == document_id)
        .filter(SolutionDocument.solution_id == solution_id)
        .filter(SolutionDocument.space_id == space_ctx.space_id)
        .filter(SolutionDocument.deleted_at.is_(None))
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/solutions/{solution_id}/documents", response_model=list[SolutionDocumentRead])
def list_solution_documents(
    solution_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    _get_solution_or_404(session, solution_id, space_ctx)
    rows = (
        session.query(SolutionDocument)
        .filter(SolutionDocument.solution_id == solution_id)
        .filter(SolutionDocument.space_id == space_ctx.space_id)
        .filter(SolutionDocument.deleted_at.is_(None))
        .order_by(SolutionDocument.created_at.desc(), SolutionDocument.filename.asc())
        .all()
    )
    return [_document_payload(row) for row in rows]


@router.post(
    "/solutions/{solution_id}/documents",
    response_model=SolutionDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_solution_document(
    solution_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    _get_solution_or_404(session, solution_id, space_ctx)
    filename = normalize_str(file.filename) or "document"
    content = await file.read()
    size_bytes = len(content)
    if size_bytes > MAX_SOLUTION_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Document exceeds the 25 MB limit",
        )
    now = datetime.now(timezone.utc)
    document = SolutionDocument(
        space_id=space_ctx.space_id,
        solution_id=solution_id,
        filename=filename,
        content_type=normalize_str(file.content_type) or "application/octet-stream",
        size_bytes=size_bytes,
        content=content,
        uploaded_by_user_id=current_user.user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(document)
    session.flush()
    safe_log_changes(
        session,
        entity_type="solution_document",
        entity_id=document.document_id,
        user_id=current_user.user_id,
        action="create",
        space_id=space_ctx.space_id,
        changes={
            "solution_id": (None, document.solution_id),
            "filename": (None, document.filename),
            "content_type": (None, document.content_type),
            "size_bytes": (None, document.size_bytes),
        },
    )
    commit_session(session)
    session.refresh(document)
    _publish_solution_mutation(space_ctx.space_id)
    return _document_payload(document)


@router.get("/solutions/{solution_id}/documents/{document_id}/download")
def download_solution_document(
    solution_id: str,
    document_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    document = _get_document_or_404(
        session,
        solution_id=solution_id,
        document_id=document_id,
        space_ctx=space_ctx,
    )
    headers = {"Content-Disposition": _content_disposition(document.filename)}
    return StreamingResponse(
        BytesIO(_binary_value(document.content)),
        media_type=document.content_type or "application/octet-stream",
        headers=headers,
    )


@router.delete("/solutions/{solution_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_solution_document(
    solution_id: str,
    document_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    document = _get_document_or_404(
        session,
        solution_id=solution_id,
        document_id=document_id,
        space_ctx=space_ctx,
    )
    now = datetime.now(timezone.utc)
    document.deleted_at = now
    document.updated_at = now
    session.add(document)
    safe_log_changes(
        session,
        entity_type="solution_document",
        entity_id=document.document_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    commit_session(session)
    _publish_solution_mutation(space_ctx.space_id)
    return None
