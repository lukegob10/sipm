from __future__ import annotations

from datetime import datetime, timezone, date
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import current_user as current_user_dep
from ..deps import get_db, current_space as current_space_dep
from ..ai.llm import call_chat_completion, GenAIConfigError
from ..ai.prompt_loader import render_prompt
from ..services.realtime import schedule_broadcast
from ..utils.enums import RagStatus, SolutionStatus, SubcomponentStatus
from ..models import (
    ChecklistItem,
    Project,
    ProjectCharter,
    ProjectPlan,
    Solution,
    Subcomponent,
    SOWDocument,
    User,
)
from ..schemas import (
    WorkbenchChecklistGenerateRequest,
    WorkbenchChecklistGenerateResponse,
    WorkbenchChecklistReadResponse,
    WorkbenchChecklistSaveRequest,
    WorkbenchDocListResponse,
    WorkbenchDocRevisionResponse,
    WorkbenchDocRevisionSummary,
    WorkbenchDocSaveRequest,
    WorkbenchRefineRequest,
    WorkbenchRefineResponse,
    WorkbenchTemplateResponse,
    WorkbenchValidateRequest,
    WorkbenchValidateResponse,
    WorkbenchValidationError,
    StructureStudioCommitRequest,
    StructureStudioCommitResponse,
    StructureStudioContextResponse,
    StructureStudioCreatedSolution,
    StructureStudioCreatedSubcomponent,
    StructureStudioDraftItem,
    StructureStudioDraftPayload,
    StructureStudioEvidence,
    StructureStudioGenerateRequest,
    StructureStudioGenerateResponse,
    StructureStudioRefineRequest,
    StructureStudioRefineResponse,
    StructureStudioRefineOperation,
    StructureStudioSourceDoc,
    StructureStudioSources,
    StructureStudioSufficiency,
)
from ..services.spaces import SpaceContext


router = APIRouter()


def _in_space(model, space_id: str):
    return model.space_id == space_id


_DOC_TYPES = {"charter", "plan", "sow", "checklist"}


def _find_templates_dir() -> Path:
    explicit = os.getenv("SIPM_TEMPLATES_DIR")
    if explicit:
        path = Path(explicit)
        if path.exists() and path.is_dir():
            return path

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "templates"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return here.parent / "templates"


def _load_workbench_template(doc_type: str) -> Tuple[str, Dict[str, Any]]:
    doc_type = (doc_type or "").strip().lower()
    if doc_type not in _DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doc_type")

    base = _find_templates_dir() / "workbench"
    config_path = base / f"{doc_type}.config.json"
    if not config_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template config not found")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template_path = base / f"{doc_type}.md"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    return template, config


def _strip_fenced_block(output: str) -> str:
    """Return contents inside the first ```...``` fenced block, or original output.

    This is deterministic and avoids regex so JSON parsing remains resilient.
    """
    if not output:
        return ""
    text = output.strip()
    if not text.startswith("```"):
        return text
    first_nl = text.find("\n")
    if first_nl == -1:
        return text
    closing = text.find("```", first_nl + 1)
    if closing == -1:
        return text[first_nl + 1 :].strip()
    return text[first_nl + 1 : closing].strip()


def _project_context(project: Project) -> Dict[str, Any]:
    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "description": project.description,
        "success_criteria": project.success_criteria,
        "strategic_objective": project.strategic_objective,
        "priority": project.priority,
        "sponsor": project.sponsor,
        "sponsor_user_soeid": project.sponsor_user_soeid,
    }


def _solution_context(solution: Solution) -> Dict[str, Any]:
    return {
        "solution_id": solution.solution_id,
        "project_id": solution.project_id,
        "solution_name": solution.solution_name,
        "version": solution.version,
        "status": solution.status.value if hasattr(solution.status, "value") else solution.status,
        "rag_status": solution.rag_status.value if hasattr(solution.rag_status, "value") else solution.rag_status,
        "priority": solution.priority,
        "due_date": solution.due_date.isoformat() if solution.due_date else None,
        "current_phase": solution.current_phase,
        "description": solution.description,
        "success_criteria": solution.success_criteria,
        "owner": solution.owner,
        "owner_user_soeid": solution.owner_user_soeid,
        "assignee": solution.assignee,
        "assignee_user_soeid": solution.assignee_user_soeid,
    }


def _subcomponent_context(sub: Subcomponent) -> Dict[str, Any]:
    return {
        "subcomponent_id": sub.subcomponent_id,
        "project_id": sub.project_id,
        "solution_id": sub.solution_id,
        "subcomponent_name": sub.subcomponent_name,
        "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
        "priority": sub.priority,
        "due_date": sub.due_date.isoformat() if sub.due_date else None,
        "blocked": sub.blocked,
        "assignee": sub.assignee,
        "assignee_user_soeid": sub.assignee_user_soeid,
    }


def _get_min_project_context(session: Session, project_id: str, space_id: str) -> Dict[str, Any]:
    project = (
        session.query(Project)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(_in_space(Project, space_id))
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    solutions = (
        session.query(Solution)
        .filter(Solution.project_id == project.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(_in_space(Solution, space_id))
        .all()
    )
    subcomponents = (
        session.query(Subcomponent)
        .filter(Subcomponent.project_id == project.project_id)
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(_in_space(Subcomponent, space_id))
        .all()
    )
    return {
        "project": _project_context(project),
        "solutions": [_solution_context(s) for s in solutions],
        "subcomponents": [_subcomponent_context(sc) for sc in subcomponents],
    }


def _doc_model(doc_type: str):
    if doc_type == "charter":
        return ProjectCharter, "charter_id"
    if doc_type == "plan":
        return ProjectPlan, "plan_id"
    if doc_type == "sow":
        return SOWDocument, "sow_id"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doc_type")


def _to_revision_response(doc_type: str, row: Any) -> WorkbenchDocRevisionResponse:
    model, id_field = _doc_model(doc_type)
    revision_id = getattr(row, id_field)
    base = {
        "doc_type": doc_type,
        "revision_id": revision_id,
        "project_id": row.project_id,
        "title": getattr(row, "title", None),
        "content": row.content,
        "state": getattr(row, "state", "draft") or "draft",
        "created_at": row.created_at,
        "created_by_user_id": row.created_by_user_id,
    }
    if doc_type == "sow":
        base.update(
            {
                "approval_state": getattr(row, "approval_state", None),
                "approval_note": getattr(row, "approval_note", None),
            }
        )
    return WorkbenchDocRevisionResponse(**base)


def _to_revision_summary(doc_type: str, row: Any) -> WorkbenchDocRevisionSummary:
    _, id_field = _doc_model(doc_type)
    base = {
        "revision_id": getattr(row, id_field),
        "title": getattr(row, "title", None),
        "state": getattr(row, "state", "draft") or "draft",
        "created_at": row.created_at,
        "created_by_user_id": row.created_by_user_id,
    }
    if doc_type == "sow":
        base["approval_state"] = getattr(row, "approval_state", None)
    return WorkbenchDocRevisionSummary(**base)


def _extract_iso_dates(text: str) -> List[str]:
    """Find YYYY-MM-DD tokens without regex (best-effort)."""
    if not text:
        return []
    results: List[str] = []
    n = len(text)
    i = 0
    while i + 10 <= n:
        chunk = text[i : i + 10]
        if (
            chunk[4:5] == "-"
            and chunk[7:8] == "-"
            and chunk[:4].isdigit()
            and chunk[5:7].isdigit()
            and chunk[8:10].isdigit()
        ):
            results.append(chunk)
            i += 10
            continue
        i += 1
    # de-dupe while preserving order
    seen = set()
    unique = []
    for d in results:
        if d in seen:
            continue
        seen.add(d)
        unique.append(d)
    return unique


def _validate_content(doc_type: str, content: str, config: Dict[str, Any], state: str) -> List[WorkbenchValidationError]:
    errors: List[WorkbenchValidationError] = []
    state_norm = (state or "draft").strip().lower()
    heading_level = int(config.get("heading_level") or 2)
    required_sections = config.get("required_sections") or []
    placeholders = config.get("placeholders") or []

    prefix = "#" * heading_level + " "
    lines = (content or "").splitlines()
    headings = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            headings.add(stripped[len(prefix) :].strip())

    for section in required_sections:
        if section not in headings:
            errors.append(
                WorkbenchValidationError(
                    code="missing_section",
                    message=f"Missing required section: {section}",
                    section=section,
                )
            )

    if state_norm == "final":
        for token in placeholders:
            if token and token in (content or ""):
                errors.append(
                    WorkbenchValidationError(
                        code="placeholder_remaining",
                        message=f"Placeholder remains in final document: {token}",
                    )
                )
                break

    for token in _extract_iso_dates(content or ""):
        try:
            date.fromisoformat(token)
        except Exception:
            errors.append(
                WorkbenchValidationError(
                    code="invalid_date",
                    message=f"Invalid ISO date: {token}",
                )
            )
            break

    return errors


def _normalize_assist_level(level: Optional[str]) -> Literal["light", "medium", "heavy"]:
    raw = str(level or "").strip().lower()
    if raw in {"medium", "heavy"}:
        return raw
    return "light"


def _assist_policy_payload(level: Literal["light", "medium", "heavy"]) -> Dict[str, Any]:
    if level == "heavy":
        return {
            "level": "heavy",
            "intent": "Act as an analyst. Build a complete, coherent draft across required sections.",
            "missing_info_behavior": (
                "Synthesize grounded content from project context and existing draft, label assumptions explicitly, "
                "and ask questions only for true blockers."
            ),
            "aggressiveness": "high",
        }
    if level == "medium":
        return {
            "level": "medium",
            "intent": "Improve structure and fill obvious gaps in required sections.",
            "missing_info_behavior": (
                "Prefer grounded drafting with explicit assumptions. Ask concise follow-up questions for unresolved blockers."
            ),
            "aggressiveness": "moderate",
        }
    return {
        "level": "light",
        "intent": "Conservative edit and polish pass.",
        "missing_info_behavior": "Do not infer beyond direct context; ask questions when information is missing.",
        "aggressiveness": "low",
    }


def _workbench_gap_report(doc_type: str, content: str, config: Dict[str, Any]) -> Dict[str, Any]:
    errors = _validate_content(doc_type, content or "", config, state="draft")
    missing_required_sections: list[str] = []
    validation_messages: list[str] = []
    for err in errors:
        validation_messages.append(str(err.message or "").strip())
        if err.code == "missing_section" and err.section:
            missing_required_sections.append(str(err.section).strip())

    placeholders = []
    for token in config.get("placeholders") or []:
        marker = str(token or "").strip()
        if marker and marker in (content or ""):
            placeholders.append(marker)

    seen_sections: set[str] = set()
    ordered_sections: list[str] = []
    for section in missing_required_sections:
        key = section.lower()
        if key in seen_sections:
            continue
        seen_sections.add(key)
        ordered_sections.append(section)

    return {
        "missing_required_sections": ordered_sections,
        "placeholder_tokens_present": placeholders,
        "validation_messages": [msg for msg in validation_messages if msg],
        "has_gaps": bool(ordered_sections or placeholders),
    }


def _normalize_refine_output(data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, List[str], List[str]]:
    patches = data.get("patches")
    if not isinstance(patches, list):
        patches = []

    # Ensure we always return at least one patch when the model provides a revised content blob.
    if not patches and isinstance(data.get("content"), str) and data.get("content").strip():
        patches = [{"op": "replace_document", "content": data.get("content")}]

    normalized: List[Dict[str, Any]] = []
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        op = str(patch.get("op") or "").strip()
        content = patch.get("content")
        if not op:
            continue
        normalized.append({"op": op, "content": content})

    summary = str(data.get("summary") or "")
    questions = data.get("questions")
    if not isinstance(questions, list):
        questions = []
    warnings = data.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    return (
        normalized,
        summary,
        [str(q).strip() for q in questions if str(q).strip()],
        [str(w).strip() for w in warnings if str(w).strip()],
    )


def _extract_replace_patch_content(patches: List[Dict[str, Any]]) -> Optional[str]:
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        if str(patch.get("op") or "").strip() != "replace_document":
            continue
        content = patch.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return None


@router.get("/templates/{doc_type}", response_model=WorkbenchTemplateResponse)
def workbench_template(doc_type: str) -> WorkbenchTemplateResponse:
    template, config = _load_workbench_template(doc_type)
    return WorkbenchTemplateResponse(doc_type=doc_type, template=template, config=config)


@router.get("/docs/{doc_type}/latest", response_model=None)
def workbench_latest_doc(
    doc_type: str,
    project_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    model, _ = _doc_model(doc_type)
    row = (
        session.query(model)
        .filter(model.project_id == project_id)
        .filter(model.deleted_at.is_(None))
        .filter(_in_space(model, space_ctx.space_id))
        .order_by(model.created_at.desc())
        .first()
    )
    if not row:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return _to_revision_response(doc_type, row)


@router.get("/docs/{doc_type}/revisions", response_model=WorkbenchDocListResponse)
def workbench_list_revisions(
    doc_type: str,
    project_id: str,
    limit: int = 50,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocListResponse:
    model, _ = _doc_model(doc_type)
    rows = (
        session.query(model)
        .filter(model.project_id == project_id)
        .filter(model.deleted_at.is_(None))
        .filter(_in_space(model, space_ctx.space_id))
        .order_by(model.created_at.desc())
        .limit(limit)
        .all()
    )
    return WorkbenchDocListResponse(
        doc_type=doc_type,
        project_id=project_id,
        revisions=[_to_revision_summary(doc_type, row) for row in rows],
    )


@router.get("/docs/{doc_type}/revisions/{revision_id}", response_model=WorkbenchDocRevisionResponse)
def workbench_get_revision(
    doc_type: str,
    revision_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocRevisionResponse:
    model, id_field = _doc_model(doc_type)
    row = (
        session.query(model)
        .filter(getattr(model, id_field) == revision_id)
        .filter(model.deleted_at.is_(None))
        .filter(_in_space(model, space_ctx.space_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    return _to_revision_response(doc_type, row)


@router.delete("/docs/{doc_type}/revisions/{revision_id}")
def workbench_delete_revision(
    doc_type: str,
    revision_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> dict:
    model, id_field = _doc_model(doc_type)
    row = (
        session.query(model)
        .filter(getattr(model, id_field) == revision_id)
        .filter(model.deleted_at.is_(None))
        .filter(_in_space(model, space_ctx.space_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    # Soft-delete for auditability. UI can restore by saving a new revision based on an older one.
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    session.commit()
    return {"deleted": True, "revision_id": revision_id, "doc_type": doc_type}


@router.post("/docs/{doc_type}/save", response_model=WorkbenchDocRevisionResponse)
def workbench_save_revision(
    doc_type: str,
    payload: WorkbenchDocSaveRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocRevisionResponse:
    _get_project_or_404(session, payload.project_id, space_ctx.space_id)
    model, _ = _doc_model(doc_type)
    if doc_type == "charter":
        row = ProjectCharter(
            space_id=space_ctx.space_id,
            project_id=payload.project_id,
            title=payload.title,
            content=payload.content,
            state="draft",
            created_by_user_id=current_user.user_id,
        )
    elif doc_type == "plan":
        row = ProjectPlan(
            space_id=space_ctx.space_id,
            project_id=payload.project_id,
            title=payload.title,
            content=payload.content,
            state="draft",
            created_by_user_id=current_user.user_id,
        )
    elif doc_type == "sow":
        row = SOWDocument(
            space_id=space_ctx.space_id,
            project_id=payload.project_id,
            title=payload.title,
            content=payload.content,
            state="draft",
            approval_state="draft",
            created_by_user_id=current_user.user_id,
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doc_type")

    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_revision_response(doc_type, row)


class WorkbenchFinalizeRequest(BaseModel):
    revision_id: str


@router.post("/docs/{doc_type}/finalize", response_model=WorkbenchDocRevisionResponse)
def workbench_finalize_revision(
    doc_type: str,
    payload: WorkbenchFinalizeRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocRevisionResponse:
    model, id_field = _doc_model(doc_type)
    row = (
        session.query(model)
        .filter(getattr(model, id_field) == payload.revision_id)
        .filter(model.deleted_at.is_(None))
        .filter(_in_space(model, space_ctx.space_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    template, config = _load_workbench_template(doc_type)
    _ = template  # reserved for future template_version enforcement

    if doc_type == "sow":
        approval_state = (getattr(row, "approval_state", "") or "").strip().lower()
        if approval_state != "approved":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="approval_required")

    errors = _validate_content(doc_type, row.content, config, state="final")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "errors": [e.model_dump() for e in errors]},
        )

    row.state = "final"
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_revision_response(doc_type, row)


class _ApprovalRequest(BaseModel):
    revision_id: str
    note: Optional[str] = None


@router.post("/docs/sow/request-approval", response_model=WorkbenchDocRevisionResponse)
def sow_request_approval(
    payload: _ApprovalRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocRevisionResponse:
    row = (
        session.query(SOWDocument)
        .filter(SOWDocument.sow_id == payload.revision_id)
        .filter(SOWDocument.deleted_at.is_(None))
        .filter(_in_space(SOWDocument, space_ctx.space_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    row.approval_state = "in_review"
    row.approval_requested_at = datetime.now(timezone.utc)
    row.approval_requested_by_user_id = current_user.user_id
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_revision_response("sow", row)


@router.post("/docs/sow/approve", response_model=WorkbenchDocRevisionResponse)
def sow_approve(
    payload: _ApprovalRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocRevisionResponse:
    row = (
        session.query(SOWDocument)
        .filter(SOWDocument.sow_id == payload.revision_id)
        .filter(SOWDocument.deleted_at.is_(None))
        .filter(_in_space(SOWDocument, space_ctx.space_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    row.approval_state = "approved"
    row.approval_decided_at = datetime.now(timezone.utc)
    row.approval_decided_by_user_id = current_user.user_id
    row.approval_note = payload.note
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_revision_response("sow", row)


@router.post("/docs/sow/reject", response_model=WorkbenchDocRevisionResponse)
def sow_reject(
    payload: _ApprovalRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchDocRevisionResponse:
    row = (
        session.query(SOWDocument)
        .filter(SOWDocument.sow_id == payload.revision_id)
        .filter(SOWDocument.deleted_at.is_(None))
        .filter(_in_space(SOWDocument, space_ctx.space_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    row.approval_state = "rejected"
    row.approval_decided_at = datetime.now(timezone.utc)
    row.approval_decided_by_user_id = current_user.user_id
    row.approval_note = payload.note
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_revision_response("sow", row)


@router.post("/validate", response_model=WorkbenchValidateResponse)
def workbench_validate(payload: WorkbenchValidateRequest) -> WorkbenchValidateResponse:
    _, config = _load_workbench_template(payload.doc_type)
    errors = _validate_content(payload.doc_type, payload.content, config, payload.state)
    return WorkbenchValidateResponse(ok=not errors, errors=errors)


@router.post("/refine", response_model=WorkbenchRefineResponse)
def workbench_refine(
    payload: WorkbenchRefineRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchRefineResponse:
    template, config = _load_workbench_template(payload.doc_type)
    project_context = _get_min_project_context(session, payload.project_id, space_ctx.space_id)
    assist_level = _normalize_assist_level(payload.assist_level)
    assist_policy = _assist_policy_payload(assist_level)
    input_gap_report = _workbench_gap_report(payload.doc_type, payload.content or "", config)

    now = datetime.now(timezone.utc)
    date_line = f"Today's date and time: {now.isoformat()}\nToday's date: {now.date().isoformat()}\n"
    user_line = (
        f"Current user display_name: {current_user.display_name}\n"
        f"Current user soeid (user identifier): {current_user.soeid}\n\n"
    )
    system_prompt = render_prompt("genai/system.md", task_name="workbench_refine_document")

    def _build_refine_prompt(content: str, gap_report: Dict[str, Any], refinement_focus: str) -> str:
        return (
            date_line
            + user_line
            + render_prompt(
                "workbench/refine_document.md",
                doc_type=payload.doc_type,
                assist_level=assist_level,
                assist_policy_json=json.dumps(assist_policy, indent=2),
                template_config_json=json.dumps(config, indent=2),
                template_markdown=template,
                project_context_json=json.dumps(project_context, indent=2),
                current_content=content or "",
                draft_gap_report_json=json.dumps(gap_report, indent=2),
                refinement_focus=(refinement_focus or "Standard refinement pass."),
            )
        )

    def _run_refine_llm(content: str, gap_report: Dict[str, Any], refinement_focus: str) -> Tuple[List[Dict[str, Any]], str, List[str], List[str]]:
        prompt = _build_refine_prompt(content, gap_report, refinement_focus)
        raw = call_chat_completion(system_prompt, prompt)
        cleaned = _strip_fenced_block(raw)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Invalid AI output")
        return _normalize_refine_output(data)

    try:
        normalized, summary, questions, warnings = _run_refine_llm(
            payload.content or "",
            input_gap_report,
            "Primary refinement pass.",
        )
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AI output") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AI output") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM call failed") from exc

    # For medium/heavy, retry once in explicit gap-fill mode when required sections remain missing.
    if assist_level in {"medium", "heavy"}:
        first_content = _extract_replace_patch_content(normalized)
        if first_content:
            first_gap_report = _workbench_gap_report(payload.doc_type, first_content, config)
            first_missing = first_gap_report.get("missing_required_sections") or []
            if isinstance(first_missing, list) and first_missing:
                try:
                    retry_patches, retry_summary, retry_questions, retry_warnings = _run_refine_llm(
                        first_content,
                        first_gap_report,
                        (
                            "Gap-fill pass: fill all missing required sections using grounded, analyst-style synthesis. "
                            "Use explicit assumptions where details are uncertain; ask only blocker questions."
                        ),
                    )
                    retry_content = _extract_replace_patch_content(retry_patches)
                    if retry_content:
                        retry_gap_report = _workbench_gap_report(payload.doc_type, retry_content, config)
                        retry_missing = retry_gap_report.get("missing_required_sections") or []
                        if isinstance(retry_missing, list) and len(retry_missing) <= len(first_missing):
                            normalized = retry_patches
                            summary = retry_summary or summary
                            questions = retry_questions
                            warnings = warnings + retry_warnings
                            if len(retry_missing) < len(first_missing):
                                warnings.append("Applied an additional gap-fill pass to cover missing required sections.")
                except Exception:
                    warnings.append("Gap-fill retry was unavailable; returning primary refinement output.")

    return WorkbenchRefineResponse(
        patches=normalized,
        summary=summary,
        questions=[str(q).strip() for q in questions if str(q).strip()],
        warnings=[str(w).strip() for w in warnings if str(w).strip()],
    )


@router.get("/checklist", response_model=WorkbenchChecklistReadResponse)
def workbench_get_checklist(
    project_id: str,
    month_key: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchChecklistReadResponse:
    _get_project_or_404(session, project_id, space_ctx.space_id)
    rows = (
        session.query(ChecklistItem)
        .filter(ChecklistItem.project_id == project_id)
        .filter(ChecklistItem.month_key == month_key)
        .filter(ChecklistItem.deleted_at.is_(None))
        .filter(_in_space(ChecklistItem, space_ctx.space_id))
        .order_by(ChecklistItem.created_at.asc())
        .all()
    )
    return WorkbenchChecklistReadResponse(
        project_id=project_id,
        month_key=month_key,
        items=[
            {
                "checklist_id": row.checklist_id,
                "title": row.title,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    )


@router.post("/checklist/save")
def workbench_save_checklist(
    payload: WorkbenchChecklistSaveRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> dict:
    _get_project_or_404(session, payload.project_id, space_ctx.space_id)
    now = datetime.now(timezone.utc)
    # Soft-delete prior items for this month to preserve history.
    prior = (
        session.query(ChecklistItem)
        .filter(ChecklistItem.project_id == payload.project_id)
        .filter(ChecklistItem.month_key == payload.month_key)
        .filter(ChecklistItem.deleted_at.is_(None))
        .filter(_in_space(ChecklistItem, space_ctx.space_id))
        .all()
    )
    for row in prior:
        row.deleted_at = now
        session.add(row)

    created = 0
    for title in payload.items or []:
        t = str(title or "").strip()
        if not t:
            continue
        session.add(
            ChecklistItem(
                space_id=space_ctx.space_id,
                project_id=payload.project_id,
                month_key=payload.month_key,
                title=t,
                status="open",
                created_by_user_id=current_user.user_id,
            )
        )
        created += 1

    session.commit()
    return {"saved": created}


@router.post("/checklist/generate", response_model=WorkbenchChecklistGenerateResponse)
def workbench_generate_checklist(
    payload: WorkbenchChecklistGenerateRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> WorkbenchChecklistGenerateResponse:
    project_context = _get_min_project_context(session, payload.project_id, space_ctx.space_id)
    # v1: deltas are optional; we send an empty object unless we implement cursoring.
    deltas: Dict[str, Any] = {}
    _, checklist_config = _load_workbench_template("checklist")
    controls = checklist_config.get("controls")
    if not isinstance(controls, list):
        controls = []

    now = datetime.now(timezone.utc)
    date_line = f"Today's date and time: {now.isoformat()}\nToday's date: {now.date().isoformat()}\n"
    user_line = (
        f"Current user display_name: {current_user.display_name}\n"
        f"Current user soeid (user identifier): {current_user.soeid}\n\n"
    )
    user_prompt = (
        date_line
        + user_line
        + render_prompt(
            "workbench/generate_checklist.md",
            month_key=payload.month_key,
            project_context_json=json.dumps(project_context, indent=2),
            deltas_json=json.dumps(deltas, indent=2),
            controls_json=json.dumps(controls, indent=2),
        )
    )
    system_prompt = render_prompt("genai/system.md", task_name="workbench_generate_checklist")

    try:
        raw = call_chat_completion(system_prompt, user_prompt)
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM call failed") from exc

    cleaned = _strip_fenced_block(raw)
    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AI output") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AI output")

    items = data.get("checklist")
    if not isinstance(items, list):
        items = []
    summary = str(data.get("summary") or "")
    questions = data.get("questions")
    if not isinstance(questions, list):
        questions = []
    warnings = data.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    markdown = data.get("markdown")
    if not isinstance(markdown, str):
        markdown = ""

    # Backward/forward compatibility: some prompts return a governance attestation schema
    # with `controls` + `exec_summary` instead of a `checklist` array.
    if not items and isinstance(data.get("controls"), list):
        converted: list[str] = []
        for raw_control in data.get("controls") or []:
            if not isinstance(raw_control, dict):
                continue
            cid = str(raw_control.get("id") or "").strip()
            desc = str(raw_control.get("description") or "").strip()
            att = str(raw_control.get("attestation") or "").strip().upper()
            if not (cid or desc or att):
                continue
            label = cid if cid else "CONTROL"
            if desc and att:
                converted.append(f"I attest that [{label}] {desc} => {att}.")
            elif desc:
                converted.append(f"I attest that [{label}] {desc}.")
            elif att:
                converted.append(f"I attest that [{label}] attestation is {att}.")
        items = converted
        if not summary:
            exec_summary = str(data.get("exec_summary") or "").strip()
            delta_summary = str(data.get("delta_summary") or "").strip()
            summary = "\n\n".join([s for s in (exec_summary, delta_summary) if s])

    if not summary:
        exec_summary = str(data.get("exec_summary") or "").strip()
        delta_summary = str(data.get("delta_summary") or "").strip()
        summary = "\n\n".join([s for s in (exec_summary, delta_summary) if s])

    if not markdown.strip():
        # Always return an executive-ready markdown document. If the model did not provide one,
        # synthesize it deterministically from whatever structure we received.
        proj = project_context.get("project") if isinstance(project_context, dict) else None
        proj_name = ""
        sponsor = ""
        if isinstance(proj, dict):
            proj_name = str(proj.get("project_name") or proj.get("project") or proj.get("name") or "").strip()
            sponsor = str(proj.get("sponsor") or "").strip()
        month_key = payload.month_key
        phase = str(data.get("project", {}).get("phase") if isinstance(data.get("project"), dict) else data.get("phase") or "").strip()
        owner = str(data.get("project", {}).get("owner") if isinstance(data.get("project"), dict) else "").strip()
        if not owner:
            owner = sponsor
        if not phase:
            phase = "UNKNOWN"
        if not proj_name:
            proj_name = "UNKNOWN"
        if not owner:
            owner = "UNKNOWN"

        # Prefer rendering a control table when possible.
        controls_rows = data.get("controls") if isinstance(data, dict) else None
        controls_table = ""
        if isinstance(controls_rows, list) and controls_rows:
            lines = ["| Control ID | Category | Attestation | Notes |", "|---|---|---|---|"]
            for c in controls_rows:
                if not isinstance(c, dict):
                    continue
                cid = str(c.get("id") or "").strip() or "UNKNOWN"
                cat = str(c.get("category") or "").strip() or ""
                att = str(c.get("attestation") or "").strip() or "UNKNOWN"
                notes = str(c.get("notes") or "").strip()
                lines.append(
                    f"| {cid} | {cat} | {att} | {notes.replace(chr(10), ' ').replace(chr(13), '').strip()} |"
                )
            controls_table = "\n".join(lines)
        else:
            # Fall back to the attestations list.
            lines = ["| Attestation |", "|---|"]
            for it in items:
                text = str(it or "").strip().replace("\n", " ").replace("\r", "")
                if not text:
                    continue
                lines.append(f"| {text} |")
            controls_table = "\n".join(lines)

        def _bullet_section(title: str, items_list: list[str]) -> str:
            cleaned = [str(x).strip() for x in items_list if str(x).strip()]
            if not cleaned:
                return f"## {title}\n\n- None\n"
            return "## " + title + "\n\n" + "\n".join([f"- {x}" for x in cleaned]) + "\n"

        exceptions = data.get("exceptions")
        if not isinstance(exceptions, list):
            exceptions = []
        risks = data.get("risks")
        if not isinstance(risks, list):
            risks = []

        markdown = "\n".join(
            [
                "# Monthly SOW Governance Attestation",
                "",
                f"**Project:** {proj_name}",
                f"**Month:** {month_key}",
                f"**Phase:** {phase}",
                f"**Owner:** {owner}",
                "",
                "## Executive Summary",
                "",
                (str(data.get("exec_summary") or summary or "").strip() or "UNKNOWN"),
                "",
                "## Phase Status",
                "",
                f"- Current phase: {phase}",
                "",
                "## Governance Attestation",
                "",
                controls_table or "",
                "",
                "## Change & Delta Review",
                "",
                (str(data.get("delta_summary") or "").strip() or "No material changes were recorded this period."),
                "",
                _bullet_section("Risk & Issue Governance", [str(x) for x in risks]),
                _bullet_section("Open Questions", [str(x) for x in questions]),
                _bullet_section("Warnings", [str(x) for x in warnings]),
                _bullet_section("Exceptions", [str(x) for x in exceptions]),
                "## Overall Attestation Statement",
                "",
                "I attest that the above statements are accurate to the best of my knowledge based on the available project context and recorded deltas.",
                "",
                "Signed: ____________________________",
                "",
            ]
        ).strip() + "\n"

    return WorkbenchChecklistGenerateResponse(
        checklist=[str(i).strip() for i in items if str(i).strip()],
        summary=summary,
        questions=[str(q).strip() for q in questions if str(q).strip()],
        warnings=[str(w).strip() for w in warnings if str(w).strip()],
        markdown=markdown,
    )


# ------------------------------
# Structure Studio
# ------------------------------


def _to_structure_source(doc_type: str, row: Any) -> Optional[StructureStudioSourceDoc]:
    if not row:
        return None
    revision_id = row.charter_id if doc_type == "charter" else row.plan_id
    return StructureStudioSourceDoc(
        doc_type=doc_type,
        revision_id=revision_id,
        title=getattr(row, "title", None),
        state=getattr(row, "state", "draft"),
        created_at=getattr(row, "created_at", None),
        content=getattr(row, "content", "") or "",
    )


def _latest_charter(session: Session, project_id: str, space_id: str) -> Optional[ProjectCharter]:
    return (
        session.query(ProjectCharter)
        .filter(ProjectCharter.project_id == project_id)
        .filter(ProjectCharter.deleted_at.is_(None))
        .filter(_in_space(ProjectCharter, space_id))
        .order_by(ProjectCharter.created_at.desc())
        .first()
    )


def _latest_plan(session: Session, project_id: str, space_id: str) -> Optional[ProjectPlan]:
    return (
        session.query(ProjectPlan)
        .filter(ProjectPlan.project_id == project_id)
        .filter(ProjectPlan.deleted_at.is_(None))
        .filter(_in_space(ProjectPlan, space_id))
        .order_by(ProjectPlan.created_at.desc())
        .first()
    )


def _get_project_or_404(session: Session, project_id: str, space_id: str) -> Project:
    project = (
        session.query(Project)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(_in_space(Project, space_id))
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _contains_objective_signal(text: str) -> bool:
    raw = str(text or "").lower()
    if not raw:
        return False
    tokens = ("objective", "goal", "success", "outcome", "purpose", "scope")
    return any(token in raw for token in tokens)


def _structure_sufficiency(
    project: Project,
    charter_row: Optional[ProjectCharter],
    plan_row: Optional[ProjectPlan],
) -> StructureStudioSufficiency:
    missing: list[str] = []
    charter_text = (charter_row.content if charter_row else "") or ""
    plan_text = (plan_row.content if plan_row else "") or ""

    objective_detected = bool(
        (project.strategic_objective or "").strip()
        or (project.success_criteria or "").strip()
        or (project.description or "").strip()
        or _contains_objective_signal(charter_text)
        or _contains_objective_signal(plan_text)
    )

    if not charter_text.strip():
        missing.append("Charter content is missing.")
    if not plan_text.strip():
        missing.append("Plan content is missing.")

    status_value = "sufficient"
    summary = "Inputs are sufficient for draft generation."
    if missing:
        status_value = "insufficient"
        summary = "Required source inputs are missing."
    else:
        thin_inputs: list[str] = []
        if len(charter_text.strip()) < 180:
            thin_inputs.append("Charter appears too brief for reliable structure derivation.")
        if len(plan_text.strip()) < 180:
            thin_inputs.append("Plan appears too brief for reliable structure derivation.")
        if thin_inputs:
            status_value = "partial"
            missing.extend(thin_inputs)
            summary = "Inputs are partially sufficient; draft quality may be limited."

    return StructureStudioSufficiency(
        status=status_value,
        missing=missing,
        objective_detected=objective_detected,
        summary=summary,
    )


def _safe_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            values.append(text)
    return values


def _normalize_structure_item(raw: Any, kind: str) -> Optional[StructureStudioDraftItem]:
    if kind not in {"solution", "subcomponent"}:
        return None

    if isinstance(raw, str):
        name = raw.strip()
        if not name:
            return None
        return StructureStudioDraftItem(
            draft_id=str(uuid4()),
            kind=kind,
            name=name,
            status="draft",
            confidence="low",
        )

    if not isinstance(raw, dict):
        return None

    name = str(
        raw.get("name")
        or raw.get("solution_name")
        or raw.get("subcomponent_name")
        or ""
    ).strip()
    if not name:
        return None

    evidence: list[StructureStudioEvidence] = []
    for ev in raw.get("evidence") or []:
        if isinstance(ev, dict):
            doc_type = str(ev.get("doc_type") or "").strip().lower() or "charter"
            evidence.append(
                StructureStudioEvidence(
                    doc_type=doc_type,
                    revision_id=str(ev.get("revision_id") or "").strip() or None,
                    line_start=int(ev.get("line_start")) if isinstance(ev.get("line_start"), int) else None,
                    line_end=int(ev.get("line_end")) if isinstance(ev.get("line_end"), int) else None,
                    excerpt=str(ev.get("excerpt") or "").strip() or None,
                )
            )

    return StructureStudioDraftItem(
        draft_id=str(raw.get("draft_id") or uuid4()),
        kind=kind,
        name=name,
        description=str(raw.get("description") or "").strip() or None,
        parent_solution_draft_id=str(raw.get("parent_solution_draft_id") or "").strip() or None,
        status="draft",
        user_edited_fields=_safe_string_list(raw.get("user_edited_fields")),
        assumptions=_safe_string_list(raw.get("assumptions")),
        evidence=evidence,
        confidence=str(raw.get("confidence") or "").strip() or None,
    )


def _extract_heading_candidates(text: str) -> list[str]:
    headings: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        if not title:
            continue
        if len(title) > 90:
            continue
        headings.append(title)
    seen: set[str] = set()
    deduped: list[str] = []
    for title in headings:
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(title)
    return deduped


def _objective_seed(project: Project, charter_text: str, plan_text: str) -> str:
    for candidate in [project.strategic_objective, project.success_criteria, project.description]:
        text = str(candidate or "").strip()
        if text:
            return text
    for heading in _extract_heading_candidates(charter_text) + _extract_heading_candidates(plan_text):
        if heading:
            return heading
    return project.project_name or "Core Delivery"


def _normalize_decomposition_level(level: Optional[str]) -> Literal["simple", "detailed"]:
    return "detailed" if str(level or "").strip().lower() == "detailed" else "simple"


def _complexity_score(project: Project, charter_text: str, plan_text: str) -> int:
    joined = " ".join(
        [
            str(project.description or ""),
            str(project.success_criteria or ""),
            str(project.strategic_objective or ""),
            str(charter_text or ""),
            str(plan_text or ""),
        ]
    ).lower()
    word_count = len([token for token in joined.split() if token.strip()])
    heading_count = len(_extract_heading_candidates(charter_text)) + len(_extract_heading_candidates(plan_text))
    signal_tokens = (
        "dependency",
        "dependencies",
        "integration",
        "migration",
        "security",
        "compliance",
        "regulatory",
        "governance",
        "controls",
        "workflow",
        "data",
        "architecture",
        "operating model",
        "cross-functional",
        "multi-team",
        "change management",
    )
    signal_hits = sum(1 for token in signal_tokens if token in joined)

    score = 0
    if word_count >= 1800:
        score += 3
    elif word_count >= 900:
        score += 2
    elif word_count >= 350:
        score += 1

    if heading_count >= 16:
        score += 2
    elif heading_count >= 8:
        score += 1

    if signal_hits >= 10:
        score += 2
    elif signal_hits >= 5:
        score += 1

    return max(0, min(score, 6))


def _decomposition_guidance(
    project: Project,
    charter_text: str,
    plan_text: str,
    decomposition_level: Optional[str],
) -> Dict[str, Any]:
    level = _normalize_decomposition_level(decomposition_level)
    score = _complexity_score(project, charter_text, plan_text)

    if level == "detailed":
        solutions_max = 2 + min(score, 4)  # 2..6
        subcomponents_per_solution_max = 2 + min(3, score // 2 + (1 if score >= 5 else 0))  # 2..5
    else:
        solutions_max = 1 + (1 if score >= 2 else 0) + (1 if score >= 5 else 0)  # 1..3
        subcomponents_per_solution_max = 1 + (1 if score >= 3 else 0) + (1 if score >= 6 else 0)  # 1..3

    solutions_max = max(1, solutions_max)
    subcomponents_per_solution_max = max(1, subcomponents_per_solution_max)
    subcomponents_total_max = max(
        subcomponents_per_solution_max,
        solutions_max * subcomponents_per_solution_max,
    )
    if level == "detailed":
        summary = (
            "Detailed mode: perform analyst-style decomposition and surface major workstreams and supporting "
            "subcomponents while keeping the structure bounded."
        )
    else:
        summary = (
            "Simple mode: keep decomposition concise and focused on highest-value structure from available evidence."
        )
    return {
        "decomposition_level": level,
        "complexity_score": score,
        "summary": summary,
        "solutions_max": solutions_max,
        "subcomponents_per_solution_max": subcomponents_per_solution_max,
        "subcomponents_total_max": subcomponents_total_max,
    }


def _extract_plan_work_packages(text: str) -> list[str]:
    candidates: list[str] = []
    skip = {
        "overview",
        "problem statement",
        "success criteria",
        "in scope",
        "out of scope",
        "timeline",
        "risks",
        "assumptions",
    }
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        item = ""
        if stripped.startswith(("-", "*")):
            item = stripped.lstrip("-* ").strip()
        elif stripped.startswith("###") or stripped.startswith("##"):
            item = stripped.lstrip("#").strip()
        if not item:
            continue
        if len(item) < 4 or len(item) > 110:
            continue
        if item.lower() in skip:
            continue
        candidates.append(item)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _heuristic_structure_draft(
    project: Project,
    charter_text: str,
    plan_text: str,
    minimal: bool = False,
    decomposition_level: Literal["simple", "detailed"] = "simple",
    decomposition_guidance: Optional[Dict[str, Any]] = None,
) -> tuple[StructureStudioDraftPayload, list[str], list[str], bool]:
    assumptions: list[str] = []
    warnings: list[str] = []
    used_minimal = minimal

    guidance = decomposition_guidance or _decomposition_guidance(
        project,
        charter_text,
        plan_text,
        decomposition_level,
    )
    max_solutions = int(guidance.get("solutions_max") or 3)
    max_subcomponents_per_solution = int(guidance.get("subcomponents_per_solution_max") or 2)
    max_subcomponents_total = int(guidance.get("subcomponents_total_max") or (max_solutions * max_subcomponents_per_solution))
    headings = _extract_heading_candidates(plan_text)
    skip = {
        "overview",
        "problem statement",
        "success criteria",
        "in scope",
        "out of scope",
        "timeline",
        "risks",
        "assumptions",
    }
    candidate_names = [h for h in headings if h.lower() not in skip][:max_solutions]
    if minimal or not candidate_names:
        seed = _objective_seed(project, charter_text, plan_text)
        short_seed = seed.split(".")[0].strip()[:72] or f"{project.project_name} Core Delivery"
        candidate_names = [short_seed]
        used_minimal = True
        assumptions.append("Minimal draft generated because source detail is limited.")

    solutions: list[StructureStudioDraftItem] = []
    subcomponents: list[StructureStudioDraftItem] = []

    generic_packages = [
        "Requirements & Analysis",
        "Design",
        "Implementation",
        "Validation & Readiness",
        "Operational Handover",
    ]
    extracted_packages = _extract_plan_work_packages(plan_text)
    package_cursor = 0
    total_subcomponents = 0

    for idx, name in enumerate(candidate_names):
        sol_draft_id = str(uuid4())
        solution_name = str(name or "").strip()[:120]
        if not solution_name:
            continue
        solutions.append(
            StructureStudioDraftItem(
                draft_id=sol_draft_id,
                kind="solution",
                name=solution_name,
                description=f"Derived from Charter/Plan for {project.project_name}.",
                status="draft",
                assumptions=[],
                evidence=[],
                confidence="low" if used_minimal else "medium",
            )
        )
        if total_subcomponents >= max_subcomponents_total:
            continue
        packages_per_solution = max(1, min(max_subcomponents_per_solution, len(extracted_packages) // max(1, len(candidate_names))))
        if _normalize_decomposition_level(decomposition_level) == "detailed" and not used_minimal:
            packages_per_solution = max(2, packages_per_solution)
        packages_per_solution = min(packages_per_solution, max_subcomponents_per_solution)

        for package_index in range(packages_per_solution):
            if total_subcomponents >= max_subcomponents_total:
                break
            package_name = ""
            if package_cursor < len(extracted_packages):
                package_name = extracted_packages[package_cursor]
                package_cursor += 1
            else:
                package_name = generic_packages[min(package_index, len(generic_packages) - 1)]
            normalized_package = package_name.strip() or "Core Implementation"
            subcomponents.append(
                StructureStudioDraftItem(
                    draft_id=str(uuid4()),
                    kind="subcomponent",
                    name=f"{solution_name} - {normalized_package}",
                    description=f"Derived work package from source outline for {solution_name}.",
                    parent_solution_draft_id=sol_draft_id,
                    status="draft",
                    assumptions=[],
                    evidence=[],
                    confidence="low" if used_minimal else ("medium" if idx == 0 else "low"),
                )
            )
            total_subcomponents += 1

    if not solutions:
        warnings.append("No draft items could be derived from current inputs.")
    return StructureStudioDraftPayload(solutions=solutions, subcomponents=subcomponents), assumptions, warnings, used_minimal


def _draft_lookup(draft: StructureStudioDraftPayload) -> Dict[str, StructureStudioDraftItem]:
    items = {}
    for item in draft.solutions + draft.subcomponents:
        items[item.draft_id] = item
    return items


def _normalize_generate_output(
    data: Dict[str, Any],
    default_parent_solution: Optional[str] = None,
    max_solutions: Optional[int] = None,
    max_subcomponents_per_solution: Optional[int] = None,
    max_subcomponents_total: Optional[int] = None,
) -> StructureStudioDraftPayload:
    raw_solutions = data.get("solutions") if isinstance(data, dict) else []
    raw_subs = data.get("subcomponents") if isinstance(data, dict) else []

    solutions: list[StructureStudioDraftItem] = []
    seen_solutions: set[str] = set()
    for raw in raw_solutions if isinstance(raw_solutions, list) else []:
        item = _normalize_structure_item(raw, "solution")
        if not item:
            continue
        key = item.name.strip().lower()
        if key in seen_solutions:
            continue
        seen_solutions.add(key)
        solutions.append(item)
    if isinstance(max_solutions, int) and max_solutions > 0:
        solutions = solutions[:max_solutions]

    solution_name_to_id = {s.name.strip().lower(): s.draft_id for s in solutions if s.name.strip()}
    fallback_solution_id = solutions[0].draft_id if solutions else default_parent_solution
    valid_solution_ids = {s.draft_id for s in solutions}

    subcomponents: list[StructureStudioDraftItem] = []
    seen_subs: set[tuple[str, str]] = set()
    per_solution_counts: dict[str, int] = {}
    for raw in raw_subs if isinstance(raw_subs, list) else []:
        item = _normalize_structure_item(raw, "subcomponent")
        if not item:
            continue
        if isinstance(raw, dict) and not item.parent_solution_draft_id:
            parent_name = str(raw.get("parent_solution_name") or raw.get("solution_name") or "").strip().lower()
            if parent_name and parent_name in solution_name_to_id:
                item.parent_solution_draft_id = solution_name_to_id[parent_name]
        if item.parent_solution_draft_id and item.parent_solution_draft_id not in valid_solution_ids:
            item.parent_solution_draft_id = fallback_solution_id
        if not item.parent_solution_draft_id:
            item.parent_solution_draft_id = fallback_solution_id
        if not item.parent_solution_draft_id:
            continue
        if isinstance(max_subcomponents_total, int) and max_subcomponents_total > 0 and len(subcomponents) >= max_subcomponents_total:
            break
        count_for_solution = per_solution_counts.get(item.parent_solution_draft_id, 0)
        if (
            isinstance(max_subcomponents_per_solution, int)
            and max_subcomponents_per_solution > 0
            and count_for_solution >= max_subcomponents_per_solution
        ):
            continue
        key = (item.parent_solution_draft_id, item.name.strip().lower())
        if key in seen_subs:
            continue
        seen_subs.add(key)
        subcomponents.append(item)
        per_solution_counts[item.parent_solution_draft_id] = count_for_solution + 1

    return StructureStudioDraftPayload(solutions=solutions, subcomponents=subcomponents)


def _instruction_allows_override(instruction: str) -> bool:
    raw = str(instruction or "").lower()
    return any(token in raw for token in ("override", "overwrite", "replace", "ignore lock"))


def _normalize_refine_operations(data: Dict[str, Any]) -> list[StructureStudioRefineOperation]:
    operations_raw = data.get("operations") if isinstance(data, dict) else []
    operations: list[StructureStudioRefineOperation] = []
    if not isinstance(operations_raw, list):
        return operations
    for raw in operations_raw:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "").strip()
        if not op:
            continue
        items: list[StructureStudioDraftItem] = []
        if isinstance(raw.get("items"), list):
            for item in raw.get("items") or []:
                normalized_kind = str(item.get("kind") or "subcomponent") if isinstance(item, dict) else "subcomponent"
                normalized = _normalize_structure_item(item, normalized_kind if normalized_kind in {"solution", "subcomponent"} else "subcomponent")
                if normalized:
                    items.append(normalized)
        operations.append(
            StructureStudioRefineOperation(
                op=op,
                item_id=str(raw.get("item_id") or "").strip() or None,
                target_id=str(raw.get("target_id") or "").strip() or None,
                kind=str(raw.get("kind") or "").strip() or None,
                fields=raw.get("fields") if isinstance(raw.get("fields"), dict) else {},
                items=items,
                reason=str(raw.get("reason") or "").strip(),
            )
        )
    return operations


def _heuristic_refine_operations(payload: StructureStudioRefineRequest) -> list[StructureStudioRefineOperation]:
    draft_items = _draft_lookup(payload.draft)
    target_id = payload.target_ids[0] if payload.target_ids else None
    target_item = draft_items.get(target_id or "") if target_id else None
    message = (payload.instruction or "").strip().lower()
    if not target_item:
        return []

    if "split" in message and target_item.kind == "solution":
        left = StructureStudioDraftItem(
            draft_id=str(uuid4()),
            kind="solution",
            name=f"{target_item.name} - Part A",
            description=target_item.description,
            status="draft",
            confidence=target_item.confidence or "low",
        )
        right = StructureStudioDraftItem(
            draft_id=str(uuid4()),
            kind="solution",
            name=f"{target_item.name} - Part B",
            description=target_item.description,
            status="draft",
            confidence=target_item.confidence or "low",
        )
        return [StructureStudioRefineOperation(op="split_solution", target_id=target_item.draft_id, items=[left, right], reason="Heuristic split applied.")]

    if "remove reporting" in message:
        current_desc = target_item.description or ""
        updated = current_desc.replace("reporting", "").replace("Reporting", "").strip()
        return [
            StructureStudioRefineOperation(
                op="update_item_fields",
                item_id=target_item.draft_id,
                fields={"description": updated or "Reporting scope removed per instruction."},
                reason="Heuristic targeted removal applied.",
            )
        ]

    if "more technical" in message:
        current_desc = target_item.description or ""
        updated = f"{current_desc}\nTechnical focus: include interfaces, integration patterns, and non-functional constraints.".strip()
        return [
            StructureStudioRefineOperation(
                op="update_item_fields",
                item_id=target_item.draft_id,
                fields={"description": updated},
                reason="Heuristic technical adjustment applied.",
            )
        ]

    if "less technical" in message:
        current_desc = target_item.description or ""
        updated = f"{current_desc}\nBusiness framing: use plain language and avoid implementation-level details.".strip()
        return [
            StructureStudioRefineOperation(
                op="update_item_fields",
                item_id=target_item.draft_id,
                fields={"description": updated},
                reason="Heuristic simplification applied.",
            )
        ]

    return []


def _target_items_context(
    draft: StructureStudioDraftPayload,
    target_ids: list[str],
) -> list[Dict[str, Any]]:
    if not target_ids:
        return []
    lookup = _draft_lookup(draft)
    context_rows: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw_id in target_ids:
        target_id = str(raw_id or "").strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        item = lookup.get(target_id)
        if not item:
            continue
        context_rows.append(
            {
                "draft_id": item.draft_id,
                "kind": item.kind,
                "name": item.name,
                "description": item.description,
                "parent_solution_draft_id": item.parent_solution_draft_id,
            }
        )
    return context_rows


def _bind_refine_operations_to_target_context(
    operations: list[StructureStudioRefineOperation],
    draft: StructureStudioDraftPayload,
    target_ids: list[str],
) -> list[StructureStudioRefineOperation]:
    allowed = [str(item_id or "").strip() for item_id in target_ids if str(item_id or "").strip()]
    if len(allowed) != 1:
        return operations

    lookup = _draft_lookup(draft)
    target_id = allowed[0]
    target_item = lookup.get(target_id)
    if not target_item:
        return operations

    fallback_parent_solution_id = (
        target_item.draft_id
        if target_item.kind == "solution"
        else (target_item.parent_solution_draft_id or "")
    )

    for op in operations:
        if op.op == "update_item_fields" and not (op.item_id or op.target_id):
            op.item_id = target_id
            continue
        if op.op == "discard_item" and not (op.item_id or op.target_id):
            op.item_id = target_id
            continue
        if op.op == "split_solution" and not (op.target_id or op.item_id):
            op.target_id = target_id
            continue
        if op.op == "add_subcomponent":
            if not (op.target_id or op.item_id):
                op.target_id = target_id
            if fallback_parent_solution_id:
                for item in op.items:
                    if not item.parent_solution_draft_id:
                        item.parent_solution_draft_id = fallback_parent_solution_id
    return operations


def _filter_refine_operations(
    operations: list[StructureStudioRefineOperation],
    target_ids: list[str],
    allow_full_regeneration: bool,
) -> list[StructureStudioRefineOperation]:
    if allow_full_regeneration:
        return operations
    allowed = {str(item_id).strip() for item_id in target_ids if str(item_id).strip()}
    if not allowed:
        return operations

    filtered: list[StructureStudioRefineOperation] = []
    for op in operations:
        touched: set[str] = set()
        if op.item_id:
            touched.add(op.item_id)
        if op.target_id:
            touched.add(op.target_id)
        if op.items:
            for item in op.items:
                if item.draft_id:
                    touched.add(item.draft_id)
                if item.parent_solution_draft_id:
                    touched.add(item.parent_solution_draft_id)
        if not touched.intersection(allowed):
            continue
        filtered.append(op)
    return filtered


def _apply_locked_fields(
    operations: list[StructureStudioRefineOperation],
    locked_fields_by_item: Dict[str, list[str]],
    allow_override: bool,
) -> tuple[list[StructureStudioRefineOperation], list[str]]:
    if allow_override:
        return operations, []

    warnings: list[str] = []
    normalized: list[StructureStudioRefineOperation] = []
    for op in operations:
        if op.op != "update_item_fields":
            normalized.append(op)
            continue
        item_id = op.item_id or op.target_id or ""
        locked = set(locked_fields_by_item.get(item_id, []))
        if not locked:
            normalized.append(op)
            continue
        kept = {key: val for key, val in op.fields.items() if key not in locked}
        removed = sorted([key for key in op.fields.keys() if key in locked])
        if removed:
            warnings.append(f"Protected user-edited fields were preserved for {item_id}: {', '.join(removed)}")
        if kept:
            op.fields = kept
            normalized.append(op)
    return normalized, warnings


def _enforce_refine_operation_limits(
    operations: list[StructureStudioRefineOperation],
    draft: StructureStudioDraftPayload,
    guidance: Dict[str, Any],
) -> tuple[list[StructureStudioRefineOperation], list[str]]:
    warnings: list[str] = []
    max_solutions = int(guidance.get("solutions_max") or 3)
    max_sub_per_solution = int(guidance.get("subcomponents_per_solution_max") or 2)
    max_sub_total = int(guidance.get("subcomponents_total_max") or (max_solutions * max_sub_per_solution))

    current_solution_ids = {item.draft_id for item in draft.solutions}
    sub_counts: dict[str, int] = {}
    for item in draft.subcomponents:
        parent = item.parent_solution_draft_id or ""
        if parent:
            sub_counts[parent] = sub_counts.get(parent, 0) + 1
    current_sub_total = len(draft.subcomponents)

    bounded: list[StructureStudioRefineOperation] = []
    for op in operations:
        if op.op == "split_solution" and op.items:
            allowed_additional = max(max_solutions - len(current_solution_ids), 0)
            max_items = max(1, allowed_additional + 1)
            if len(op.items) > max_items:
                op.items = op.items[:max_items]
                warnings.append(
                    f"Split operation was bounded to {max_items} solution(s) to keep decomposition manageable."
                )
            for item in op.items:
                current_solution_ids.add(item.draft_id)
            bounded.append(op)
            continue

        if op.op == "add_subcomponent" and op.items:
            kept: list[StructureStudioDraftItem] = []
            for item in op.items:
                if current_sub_total >= max_sub_total:
                    break
                parent_id = item.parent_solution_draft_id or ""
                if parent_id and sub_counts.get(parent_id, 0) >= max_sub_per_solution:
                    continue
                kept.append(item)
                current_sub_total += 1
                if parent_id:
                    sub_counts[parent_id] = sub_counts.get(parent_id, 0) + 1
            if len(kept) < len(op.items):
                warnings.append(
                    "Some generated subcomponents were skipped to keep decomposition within configured bounds."
                )
            if kept:
                op.items = kept
                bounded.append(op)
            continue

        bounded.append(op)

    return bounded, warnings


@router.get("/structure-studio/context", response_model=StructureStudioContextResponse)
def structure_studio_context(
    project_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> StructureStudioContextResponse:
    project = _get_project_or_404(session, project_id, space_ctx.space_id)
    charter = _latest_charter(session, project.project_id, space_ctx.space_id)
    plan = _latest_plan(session, project.project_id, space_ctx.space_id)
    sufficiency = _structure_sufficiency(project, charter, plan)
    return StructureStudioContextResponse(
        project_id=project.project_id,
        sufficiency=sufficiency,
        sources=StructureStudioSources(
            charter=_to_structure_source("charter", charter),
            plan=_to_structure_source("plan", plan),
        ),
    )


@router.post("/structure-studio/generate", response_model=StructureStudioGenerateResponse)
def structure_studio_generate(
    payload: StructureStudioGenerateRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> StructureStudioGenerateResponse:
    project = _get_project_or_404(session, payload.project_id, space_ctx.space_id)
    charter = _latest_charter(session, project.project_id, space_ctx.space_id)
    plan = _latest_plan(session, project.project_id, space_ctx.space_id)
    sufficiency = _structure_sufficiency(project, charter, plan)

    charter_text = (charter.content if charter else "") or ""
    plan_text = (plan.content if plan else "") or ""
    decomposition_level = _normalize_decomposition_level(payload.decomposition_level)
    decomposition_guidance = _decomposition_guidance(
        project,
        charter_text,
        plan_text,
        decomposition_level,
    )

    if sufficiency.status == "insufficient" and not payload.allow_minimal_on_insufficient:
        return StructureStudioGenerateResponse(
            project_id=project.project_id,
            sufficiency=sufficiency,
            draft=StructureStudioDraftPayload(solutions=[], subcomponents=[]),
            assumptions=[],
            warnings=["Generation blocked until required inputs are provided."],
            minimal_draft=False,
        )

    project_context = _get_min_project_context(session, project.project_id, space_ctx.space_id)
    existing_solution_names = sorted(
        {str(item.get("solution_name") or "").strip() for item in project_context.get("solutions", []) if str(item.get("solution_name") or "").strip()}
    )
    existing_subcomponent_names = sorted(
        {str(item.get("subcomponent_name") or "").strip() for item in project_context.get("subcomponents", []) if str(item.get("subcomponent_name") or "").strip()}
    )

    warnings: list[str] = []
    assumptions: list[str] = []
    draft_payload: Optional[StructureStudioDraftPayload] = None
    minimal_draft = False
    charter_source = _to_structure_source("charter", charter)
    plan_source = _to_structure_source("plan", plan)

    now = datetime.now(timezone.utc)
    date_line = f"Today's date and time: {now.isoformat()}\nToday's date: {now.date().isoformat()}\n"
    user_line = (
        f"Current user display_name: {current_user.display_name}\n"
        f"Current user soeid (user identifier): {current_user.soeid}\n\n"
    )
    user_prompt = (
        date_line
        + user_line
        + render_prompt(
            "workbench/structure_studio_generate.md",
            project_context_json=json.dumps(project_context, indent=2),
            charter_source_json=json.dumps((charter_source.model_dump(mode="json") if charter_source else {}), indent=2),
            plan_source_json=json.dumps((plan_source.model_dump(mode="json") if plan_source else {}), indent=2),
            sufficiency_json=json.dumps(sufficiency.model_dump(), indent=2),
            decomposition_level_json=json.dumps(decomposition_level),
            decomposition_guidance_json=json.dumps(decomposition_guidance, indent=2),
            existing_solution_names_json=json.dumps(existing_solution_names, indent=2),
            existing_subcomponent_names_json=json.dumps(existing_subcomponent_names, indent=2),
        )
    )
    system_prompt = render_prompt("genai/system.md", task_name="workbench_structure_studio_generate")

    try:
        raw = call_chat_completion(system_prompt, user_prompt)
        cleaned = _strip_fenced_block(raw)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Invalid AI output")
        raw_solution_count = len(data.get("solutions")) if isinstance(data.get("solutions"), list) else 0
        raw_subcomponent_count = len(data.get("subcomponents")) if isinstance(data.get("subcomponents"), list) else 0
        draft_payload = _normalize_generate_output(
            data,
            max_solutions=int(decomposition_guidance.get("solutions_max") or 0),
            max_subcomponents_per_solution=int(decomposition_guidance.get("subcomponents_per_solution_max") or 0),
            max_subcomponents_total=int(decomposition_guidance.get("subcomponents_total_max") or 0),
        )
        assumptions = _safe_string_list(data.get("assumptions"))
        warnings.extend(_safe_string_list(data.get("warnings")))
        minimal_draft = bool(data.get("minimal_draft"))
        if raw_solution_count > len(draft_payload.solutions):
            warnings.append(
                f"Generated solutions were bounded to {len(draft_payload.solutions)} based on project complexity and decomposition level."
            )
        if raw_subcomponent_count > len(draft_payload.subcomponents):
            warnings.append(
                f"Generated subcomponents were bounded to {len(draft_payload.subcomponents)} to avoid over-fragmentation."
            )
    except Exception:
        draft_payload = None
        warnings.append("AI generation was unavailable; returned deterministic fallback draft.")

    if not draft_payload or not draft_payload.solutions:
        draft_payload, fallback_assumptions, fallback_warnings, used_minimal = _heuristic_structure_draft(
            project,
            charter_text,
            plan_text,
            minimal=(sufficiency.status != "sufficient"),
            decomposition_level=decomposition_level,
            decomposition_guidance=decomposition_guidance,
        )
        assumptions.extend(fallback_assumptions)
        warnings.extend(fallback_warnings)
        minimal_draft = minimal_draft or used_minimal

    return StructureStudioGenerateResponse(
        project_id=project.project_id,
        sufficiency=sufficiency,
        draft=draft_payload,
        assumptions=assumptions,
        warnings=warnings,
        minimal_draft=minimal_draft,
    )


@router.post("/structure-studio/refine", response_model=StructureStudioRefineResponse)
def structure_studio_refine(
    payload: StructureStudioRefineRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> StructureStudioRefineResponse:
    project = _get_project_or_404(session, payload.project_id, space_ctx.space_id)
    charter = _latest_charter(session, payload.project_id, space_ctx.space_id)
    plan = _latest_plan(session, payload.project_id, space_ctx.space_id)
    charter_text = (charter.content if charter else "") or ""
    plan_text = (plan.content if plan else "") or ""
    decomposition_level = _normalize_decomposition_level(payload.decomposition_level)
    decomposition_guidance = _decomposition_guidance(
        project,
        charter_text,
        plan_text,
        decomposition_level,
    )
    operations: list[StructureStudioRefineOperation] = []
    warnings: list[str] = []
    assumptions: list[str] = []
    used_heuristic_fallback = False

    now = datetime.now(timezone.utc)
    date_line = f"Today's date and time: {now.isoformat()}\nToday's date: {now.date().isoformat()}\n"
    user_line = (
        f"Current user display_name: {current_user.display_name}\n"
        f"Current user soeid (user identifier): {current_user.soeid}\n\n"
    )
    user_prompt = (
        date_line
        + user_line
        + render_prompt(
            "workbench/structure_studio_refine.md",
            instruction=payload.instruction,
            draft_json=json.dumps(payload.draft.model_dump(), indent=2),
            target_ids_json=json.dumps(payload.target_ids or [], indent=2),
            target_items_json=json.dumps(_target_items_context(payload.draft, payload.target_ids), indent=2),
            allow_full_regeneration_json=json.dumps(bool(payload.allow_full_regeneration)),
            locked_fields_json=json.dumps(payload.locked_fields_by_item or {}, indent=2),
            decomposition_level_json=json.dumps(decomposition_level),
            decomposition_guidance_json=json.dumps(decomposition_guidance, indent=2),
        )
    )
    system_prompt = render_prompt("genai/system.md", task_name="workbench_structure_studio_refine")

    try:
        raw = call_chat_completion(system_prompt, user_prompt)
        cleaned = _strip_fenced_block(raw)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Invalid AI output")
        operations = _normalize_refine_operations(data)
        warnings.extend(_safe_string_list(data.get("warnings")))
        assumptions.extend(_safe_string_list(data.get("assumptions")))
    except Exception:
        operations = []
        warnings.append("AI refinement was unavailable; attempted deterministic fallback.")

    if not operations:
        operations = _heuristic_refine_operations(payload)
        used_heuristic_fallback = bool(operations)

    operations = _bind_refine_operations_to_target_context(
        operations,
        draft=payload.draft,
        target_ids=payload.target_ids,
    )
    operations = _filter_refine_operations(
        operations,
        target_ids=payload.target_ids,
        allow_full_regeneration=payload.allow_full_regeneration,
    )
    operations, lock_warnings = _apply_locked_fields(
        operations,
        payload.locked_fields_by_item or {},
        allow_override=_instruction_allows_override(payload.instruction),
    )
    warnings.extend(lock_warnings)
    operations, bound_warnings = _enforce_refine_operation_limits(
        operations,
        payload.draft,
        decomposition_guidance,
    )
    warnings.extend(bound_warnings)

    if not operations and not used_heuristic_fallback:
        retry_ops = _heuristic_refine_operations(payload)
        if retry_ops:
            retry_ops = _bind_refine_operations_to_target_context(
                retry_ops,
                draft=payload.draft,
                target_ids=payload.target_ids,
            )
            retry_ops = _filter_refine_operations(
                retry_ops,
                target_ids=payload.target_ids,
                allow_full_regeneration=payload.allow_full_regeneration,
            )
            retry_ops, retry_lock_warnings = _apply_locked_fields(
                retry_ops,
                payload.locked_fields_by_item or {},
                allow_override=_instruction_allows_override(payload.instruction),
            )
            retry_ops, retry_bound_warnings = _enforce_refine_operation_limits(
                retry_ops,
                payload.draft,
                decomposition_guidance,
            )
            warnings.extend(retry_lock_warnings)
            warnings.extend(retry_bound_warnings)
            if retry_ops:
                operations = retry_ops
                warnings.append("Applied deterministic targeted fallback refinement for the selected item.")

    if not operations:
        warnings.append("No targeted edits were generated from the instruction.")

    return StructureStudioRefineResponse(operations=operations, warnings=warnings, assumptions=assumptions)


@router.post("/structure-studio/commit", response_model=StructureStudioCommitResponse)
def structure_studio_commit(
    payload: StructureStudioCommitRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> StructureStudioCommitResponse:
    project = _get_project_or_404(session, payload.project_id, space_ctx.space_id)
    now = datetime.now(timezone.utc)

    draft_solutions = {item.draft_id: item for item in payload.draft.solutions}
    draft_subcomponents = {item.draft_id: item for item in payload.draft.subcomponents}
    accepted_solution_ids = [item_id for item_id in payload.accepted.solution_ids if item_id in draft_solutions]
    accepted_subcomponent_ids = [item_id for item_id in payload.accepted.subcomponent_ids if item_id in draft_subcomponents]

    validation_errors: list[str] = []
    accepted_solution_set = set(accepted_solution_ids)
    for sub_id in accepted_subcomponent_ids:
        parent_id = draft_subcomponents[sub_id].parent_solution_draft_id
        if not parent_id:
            validation_errors.append(f"Subcomponent {sub_id} is missing parent_solution_draft_id.")
            continue
        if parent_id not in accepted_solution_set:
            validation_errors.append(
                f"Subcomponent {sub_id} cannot be committed because parent solution {parent_id} is not accepted."
            )

    if validation_errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": validation_errors})

    created_solutions: list[StructureStudioCreatedSolution] = []
    created_subcomponents: list[StructureStudioCreatedSubcomponent] = []
    draft_solution_to_persisted: dict[str, str] = {}
    warnings: list[str] = []

    # Validate duplicate names in payload before writing.
    seen_solution_names: set[str] = set()
    for draft_id in accepted_solution_ids:
        draft_item = draft_solutions[draft_id]
        name_key = draft_item.name.strip().lower()
        if not name_key:
            validation_errors.append(f"Solution {draft_id} has no name.")
            continue
        if name_key in seen_solution_names:
            validation_errors.append(f"Duplicate accepted solution name: {draft_item.name}")
            continue
        seen_solution_names.add(name_key)

    if validation_errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": validation_errors})

    try:
        for draft_id in accepted_solution_ids:
            item = draft_solutions[draft_id]
            existing_solution = (
                session.query(Solution)
                .filter(Solution.project_id == project.project_id)
                .filter(Solution.solution_name == item.name.strip())
                .filter(Solution.version == "0.1.0")
                .filter(Solution.deleted_at.is_(None))
                .filter(_in_space(Solution, space_ctx.space_id))
                .first()
            )
            if existing_solution:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"errors": [f"Solution '{item.name.strip()}' already exists in this project."]},
                )
            solution = Solution(
                space_id=space_ctx.space_id,
                project_id=project.project_id,
                solution_name=item.name.strip(),
                version="0.1.0",
                status=SolutionStatus.not_started,
                rag_status=RagStatus.green,
                description=item.description,
                owner=current_user.display_name or current_user.soeid or "",
                owner_user_soeid=current_user.soeid,
                assignee=current_user.display_name or current_user.soeid or "",
                assignee_user_soeid=current_user.soeid,
                priority=3,
                created_at=now,
                updated_at=now,
                capacity_hours=0,
            )
            session.add(solution)
            session.flush()
            draft_solution_to_persisted[draft_id] = solution.solution_id
            created_solutions.append(
                StructureStudioCreatedSolution(
                    draft_id=draft_id,
                    solution_id=solution.solution_id,
                    solution_name=solution.solution_name,
                )
            )

        for draft_id in accepted_subcomponent_ids:
            item = draft_subcomponents[draft_id]
            parent_draft_id = item.parent_solution_draft_id or ""
            parent_solution_id = draft_solution_to_persisted.get(parent_draft_id)
            if not parent_solution_id:
                continue
            existing_sub = (
                session.query(Subcomponent)
                .filter(Subcomponent.solution_id == parent_solution_id)
                .filter(Subcomponent.subcomponent_name == item.name.strip())
                .filter(Subcomponent.deleted_at.is_(None))
                .filter(_in_space(Subcomponent, space_ctx.space_id))
                .first()
            )
            if existing_sub:
                warnings.append(
                    f"Subcomponent '{item.name.strip()}' already exists for its solution and was skipped."
                )
                continue
            sub = Subcomponent(
                space_id=space_ctx.space_id,
                project_id=project.project_id,
                solution_id=parent_solution_id,
                subcomponent_name=item.name.strip(),
                status=SubcomponentStatus.to_do,
                priority=3,
                assignee=current_user.display_name or current_user.soeid or "",
                assignee_user_soeid=current_user.soeid,
                done_criteria=item.description,
                created_at=now,
                updated_at=now,
                blocked=False,
                capacity_hours=0,
            )
            session.add(sub)
            session.flush()
            created_subcomponents.append(
                StructureStudioCreatedSubcomponent(
                    draft_id=draft_id,
                    subcomponent_id=sub.subcomponent_id,
                    subcomponent_name=sub.subcomponent_name,
                    solution_id=sub.solution_id,
                )
            )
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Commit failed due to a data conflict.") from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to commit selected items.") from exc

    schedule_broadcast("solutions")
    schedule_broadcast("subcomponents")
    total_draft_items = len(payload.draft.solutions) + len(payload.draft.subcomponents)
    kept_items = len(created_solutions) + len(created_subcomponents)
    discarded_count = max(total_draft_items - kept_items, 0)
    return StructureStudioCommitResponse(
        project_id=project.project_id,
        created_solutions=created_solutions,
        created_subcomponents=created_subcomponents,
        discarded_count=discarded_count,
        warnings=warnings,
    )
