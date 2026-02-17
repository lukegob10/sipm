from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_db, require_user, current_space as current_space_dep
from ..ai.orchestrator import run_agentic_chat
from ..ai.tools import (
    read_context,
    read_context_complete,
    read_project_detail,
    read_solution_detail,
    read_subcomponent_detail,
    read_artifacts_detail,
    read_sow_document,
    list_projects,
    list_solutions_for_project,
    explain_app_usage,
    list_project_cards,
    list_solution_cards,
    list_task_cards,
    get_project_card,
    get_solution_card,
    get_task_card,
    get_scope_digest,
    get_entity_fields,
    get_entity_deltas,
    read_entity_index,
    read_entity_deltas,
    validate_draft,
    apply_draft,
    verify_write,
)
from ..models import (
    AIRequest,
    AISession,
    ProjectCharter,
    ProjectPlan,
    ProjectDecisionLog,
    ExternalDocument,
)
from ..routes.genai import _parse_fields, _parse_checklist, _parse_subcomponents, _coerce_date
from ..models import Project, Solution, Subcomponent, ChecklistItem, SOWDocument
from ..schemas import AIChatRequest, AIChatResponse, GenAIApproveRequest
from ..services.spaces import SpaceContext

router = APIRouter()


_INT_FIELDS = {"priority", "capacity_hours", "estimate_hours"}
_FLOAT_FIELDS = {"rag_confidence"}
_BOOL_FIELDS = {"blocked"}
_AUTO_SAVE_REQUESTS = {
    "autofill",
    "sow",
    "checklist",
    "subcomponents",
    "project_create",
    "solution_create",
    "subcomponent_create",
    "charter_create",
    "plan_create",
    "decision_log_create",
}
_AUTO_SAVE_BLOCKERS = {
    "draft",
    "preview",
    "suggest",
    "proposal",
    "propose",
    "option",
    "options",
    "idea",
    "outline",
    "example",
    "sample",
}
_AUTO_SAVE_VERBS = {
    "create",
    "make",
    "add",
    "update",
    "change",
    "edit",
    "set",
    "assign",
    "save",
    "finalize",
    "submit",
    "go ahead",
    "let's",
    "lets",
    "do it",
}

_AI_REQUEST_OUTPUT_MAX = 255


def _missing_fields_section_detail(request_type: str, required: Optional[list[str]] = None) -> str:
    required_text = f" Required fields: {', '.join(required)}." if required else ""
    return (
        f"Invalid AI output: missing fields for {request_type}."
        f"{required_text} Expected JSON with a fields object or an updates array."
    )


def _coerce_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in {"true", "yes", "1"}:
        return True
    if raw in {"false", "no", "0"}:
        return False
    return None


def _parse_int_or_default(value: object, default: int) -> int:
    if value is None or value == "":
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _sanitize_upload_filename(filename: Optional[str]) -> str:
    raw = str(filename or "").strip()
    if not raw:
        return "document"
    # Keep only the last path segment to avoid path traversal via user-supplied names.
    name = raw.replace("\\", "/").split("/")[-1]
    if not name:
        return "document"
    # Replace characters that are risky across filesystems.
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    safe = safe.lstrip(".")
    if not safe:
        safe = "document"
    return safe[:128]


def _extract_json_content(output: Optional[str]) -> Optional[str]:
    if not output:
        return output
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                return content
    except Exception:
        pass
    return output


def _parse_csv_param(values: Optional[str]) -> Optional[list[str]]:
    if values is None:
        return None
    entries = [entry.strip() for entry in str(values).split(",") if entry and entry.strip()]
    return entries or None


def _compact_ai_request_output(output: Optional[str]) -> Optional[str]:
    if output is None:
        return None
    text = str(output)
    if len(text) <= _AI_REQUEST_OUTPUT_MAX:
        return text
    suffix = f"... [truncated {len(text)} chars]"
    keep = max(0, _AI_REQUEST_OUTPUT_MAX - len(suffix))
    return text[:keep] + suffix


def _sanitize_audit_tools(tools: Optional[list[Any]]) -> list[str]:
    if not isinstance(tools, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tools:
        name = str(raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned


def _extract_result_tools_for_audit(result: Dict[str, Any]) -> list[str]:
    tool_names: list[str] = []
    traces: list[Dict[str, Any]] = []

    debug = result.get("debug")
    if isinstance(debug, dict) and isinstance(debug.get("trace"), list):
        traces.extend(entry for entry in debug.get("trace") or [] if isinstance(entry, dict))
    if isinstance(result.get("trace"), list):
        traces.extend(entry for entry in result.get("trace") or [] if isinstance(entry, dict))

    for entry in traces:
        if entry.get("type") != "tool":
            continue
        name = str(entry.get("tool") or "").strip()
        if name:
            tool_names.append(name)
    return _sanitize_audit_tools(tool_names)


def _build_ai_request_audit_summary(
    request_type: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    output: Optional[str],
    month_key: Optional[str] = None,
    audit_tools: Optional[list[Any]] = None,
) -> str:
    req = str(request_type or "").strip().lower()
    target = f"{entity_type or 'entity'}:{entity_id or 'n/a'}"
    summary = f"{req or 'request'} saved"

    if req == "autofill":
        updates = _parse_autofill_updates(output, entity_type, entity_id)
        if updates:
            counts: Dict[str, int] = {}
            field_names: list[str] = []
            field_seen: set[str] = set()
            for update in updates:
                kind = str(update.get("entity_type") or "unknown")
                counts[kind] = int(counts.get(kind) or 0) + 1
                fields = update.get("fields") or {}
                if isinstance(fields, dict):
                    for key in fields.keys():
                        name = str(key or "").strip()
                        if not name or name in field_seen:
                            continue
                        field_seen.add(name)
                        field_names.append(name)
            counts_text = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            fields_text = ", ".join(field_names[:6])
            summary = f"autofill applied {len(updates)} update(s) [{counts_text}]"
            if fields_text:
                summary += f"; fields: {fields_text}"
        else:
            summary = f"autofill requested for {target}"
    elif req in {"project_create", "solution_create", "subcomponent_create"}:
        fields = _parse_fields(output or "")
        keys = [str(k) for k in list(fields.keys())[:6]]
        summary = f"{req} for {target}"
        if keys:
            summary += f"; fields: {', '.join(keys)}"
    elif req == "subcomponents":
        items = _parse_subcomponents(output or "")
        summary = f"subcomponents approved for {target}; count: {len(items)}"
    elif req == "checklist":
        items = _parse_checklist(output or "")
        summary = f"checklist approved for {target}; month: {month_key or 'current'}; items: {len(items)}"
    elif req in {"sow", "charter_create", "plan_create", "decision_log_create"}:
        content = _extract_json_content(output) or ""
        summary = f"{req} approved for {target}; content_len: {len(content)}"
    else:
        summary = f"{req or 'request'} approved for {target}"

    tools = _sanitize_audit_tools(audit_tools)
    if tools:
        summary += f"; tools: {', '.join(tools[:8])}"
    return _compact_ai_request_output(summary) or summary


def _strip_fenced_block(output: Optional[str]) -> str:
    text = str(output or "").strip()
    if not text.startswith("```"):
        return text
    start = text.find("```")
    end = text.find("```", start + 3)
    if end == -1:
        return text
    inner = text[start + 3 : end].lstrip()
    first_newline = inner.find("\n")
    if first_newline != -1:
        first_line = inner[:first_newline].strip().lower()
        if first_line == "json":
            inner = inner[first_newline + 1 :]
    return inner.strip()


def _coerce_autofill_update_item(
    item: Any,
    default_entity_type: Optional[str],
    default_entity_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    inferred_entity_type = item.get("entity_type")
    if not inferred_entity_type:
        if item.get("solution_id"):
            inferred_entity_type = "solution"
        elif item.get("subcomponent_id") or item.get("task_id"):
            inferred_entity_type = "subcomponent"
        elif item.get("project_id"):
            inferred_entity_type = "project"
    entity_type = str(inferred_entity_type or default_entity_type or "").strip().lower()
    if entity_type not in {"project", "solution", "subcomponent"}:
        return None

    entity_id = item.get("entity_id")
    if not entity_id:
        if entity_type == "project":
            entity_id = item.get("project_id")
        elif entity_type == "solution":
            entity_id = item.get("solution_id")
        else:
            entity_id = item.get("subcomponent_id") or item.get("task_id")
    if not entity_id and entity_type == (default_entity_type or "").strip().lower():
        entity_id = default_entity_id
    if not entity_id:
        return None

    fields = item.get("fields")
    if not isinstance(fields, dict):
        reserved = {
            "entity_type",
            "entity_id",
            "project_id",
            "solution_id",
            "subcomponent_id",
            "task_id",
            "fields",
        }
        fields = {k: v for k, v in item.items() if k not in reserved}
    if not isinstance(fields, dict) or not fields:
        return None
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id).strip(),
        "fields": fields,
    }


def _parse_autofill_updates(
    output: Optional[str],
    default_entity_type: Optional[str],
    default_entity_id: Optional[str],
) -> List[Dict[str, Any]]:
    parsed_updates: List[Dict[str, Any]] = []
    if output:
        candidate = _strip_fenced_block(output)
        data = None
        try:
            data = json.loads(candidate)
        except Exception:
            data = None

        if isinstance(data, dict):
            if isinstance(data.get("updates"), list):
                for raw in data.get("updates") or []:
                    coerced = _coerce_autofill_update_item(raw, default_entity_type, default_entity_id)
                    if coerced:
                        parsed_updates.append(coerced)
            else:
                coerced = _coerce_autofill_update_item(data, default_entity_type, default_entity_id)
                if coerced:
                    parsed_updates.append(coerced)
        elif isinstance(data, list):
            for raw in data:
                coerced = _coerce_autofill_update_item(raw, default_entity_type, default_entity_id)
                if coerced:
                    parsed_updates.append(coerced)

    if parsed_updates:
        return parsed_updates

    single_fields = _parse_fields(output or "")
    if not single_fields:
        return []
    fallback_type = str(default_entity_type or "").strip().lower()
    fallback_id = str(default_entity_id or "").strip()
    if fallback_type not in {"project", "solution", "subcomponent"} or not fallback_id:
        return []
    return [{"entity_type": fallback_type, "entity_id": fallback_id, "fields": single_fields}]


def _infer_request_type_from_output(
    output: Optional[str],
    entity_type: Optional[str],
    entity_id: Optional[str],
) -> Optional[str]:
    if not output:
        return None
    if _parse_autofill_updates(output, entity_type, entity_id):
        return "autofill"
    if _parse_subcomponents(output):
        return "subcomponents"
    if _parse_checklist(output):
        return "checklist"
    return None


def _auto_save_entity_type(request_type: str | None, fallback: Optional[str]) -> Optional[str]:
    if request_type == "project_create":
        return "project"
    if request_type == "solution_create":
        return "solution"
    if request_type == "subcomponent_create":
        return "subcomponent"
    return fallback


def _should_auto_save(message: str, request_type: Optional[str], output: Optional[str]) -> bool:
    if not request_type or request_type not in _AUTO_SAVE_REQUESTS:
        return False
    if not output:
        return False
    text = (message or "").lower()
    if any(blocker in text for blocker in _AUTO_SAVE_BLOCKERS):
        return False
    return any(verb in text for verb in _AUTO_SAVE_VERBS)


def _in_space(model, space_id: str):
    return model.space_id == space_id


def _load_session(
    session: Session,
    session_id: Optional[str],
    user_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> Optional[AISession]:
    if not session_id:
        return None
    query = session.query(AISession).filter(AISession.session_id == session_id)
    if space_id:
        query = query.filter(_in_space(AISession, space_id))
    if user_id:
        query = query.filter(AISession.user_id == user_id)
    return query.first()


def _save_session(session: Session, session_obj: AISession, history) -> AISession:
    serializable = []
    for msg in history:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = str(msg.get("content") or "")
            if content.startswith("DEBUG SUMMARY") or content.startswith("DEBUG TRACE"):
                continue
            serializable.append({"role": role, "content": content})
        else:
            role = getattr(msg, "role", "user")
            content = str(getattr(msg, "content", "") or "")
            if content.startswith("DEBUG SUMMARY") or content.startswith("DEBUG TRACE"):
                continue
            serializable.append({"role": role, "content": content})
    # Keep stored history bounded; client controls what gets sent back to the model.
    if len(serializable) > 40:
        serializable = serializable[-40:]
    session_obj.messages = json.dumps(serializable)
    session_obj.last_active_at = datetime.now(timezone.utc)
    session.add(session_obj)
    session.flush()
    return session_obj


@router.post("/chat", response_model=AIChatResponse)
def ai_chat(
    payload: AIChatRequest,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    session_obj = _load_session(
        session,
        payload.session_id,
        user_id=current_user.user_id,
        space_id=space_ctx.space_id,
    )
    if not session_obj:
        session_obj = AISession(
            session_id=str(uuid4()),
            space_id=space_ctx.space_id,
            project_id=payload.project_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            user_id=current_user.user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(session_obj)
        session.flush()
    history = payload.history or []
    if session_obj and session_obj.messages:
        try:
            stored = json.loads(session_obj.messages)
            # Prefer explicit client-provided history; only fall back to stored history when none is provided.
            if isinstance(stored, list) and not history:
                history = stored
        except Exception:
            pass

    if not payload.project_id and session_obj.project_id:
        payload.project_id = session_obj.project_id
    if not payload.entity_type and session_obj.entity_type:
        payload.entity_type = session_obj.entity_type
    if not payload.entity_id and session_obj.entity_id:
        payload.entity_id = session_obj.entity_id

    if not payload.project_id:
        # fall back to dropdown-selected entity context
        if not payload.project_id and payload.entity_type == "project" and payload.entity_id:
            project = (
                session.query(Project)
                .filter(Project.project_id == payload.entity_id)
                .filter(Project.deleted_at.is_(None))
                .filter(_in_space(Project, space_ctx.space_id))
                .first()
            )
            if project:
                payload.project_id = project.project_id
        if not payload.project_id and payload.entity_type == "solution" and payload.entity_id:
            solution = (
                session.query(Solution)
                .filter(Solution.solution_id == payload.entity_id)
                .filter(Solution.deleted_at.is_(None))
                .filter(_in_space(Solution, space_ctx.space_id))
                .first()
            )
            if solution:
                payload.project_id = solution.project_id
        if not payload.project_id and payload.entity_type == "subcomponent" and payload.entity_id:
            sub = (
                session.query(Subcomponent)
                .filter(Subcomponent.subcomponent_id == payload.entity_id)
                .filter(Subcomponent.deleted_at.is_(None))
                .filter(_in_space(Subcomponent, space_ctx.space_id))
                .first()
            )
            if sub:
                payload.project_id = sub.project_id

    result = run_agentic_chat(
        session,
        {
            "session_id": session_obj.session_id,
            "message": payload.message,
            "entity_type": payload.entity_type,
            "entity_id": payload.entity_id,
            "project_id": payload.project_id,
            "current_date": payload.current_date,
            "space_id": space_ctx.space_id,
            "history": history,
            "current_user": {
                "display_name": current_user.display_name,
                "soeid": current_user.soeid,
                "user_id": current_user.user_id,
            },
        },
    )

    resolved_entity_type = result.get("entity_type") or payload.entity_type
    resolved_entity_id = result.get("entity_id") or payload.entity_id

    output = result.get("output")
    if isinstance(output, dict):
        output = json.dumps(output)
    if not output and result.get("request_type"):
        output = result.get("reply", "")
    result_request_type = str(result.get("request_type") or "").strip().lower() or None
    if not result_request_type and output:
        inferred_request_type = _infer_request_type_from_output(output, resolved_entity_type, resolved_entity_id)
        if inferred_request_type:
            result_request_type = inferred_request_type
            result["request_type"] = inferred_request_type

    auto_saved = False
    if _should_auto_save(payload.message, result_request_type, output):
        audit_tools = _extract_result_tools_for_audit(result)
        approve_payload = GenAIApproveRequest(
            request_type=result_request_type,
            entity_type=_auto_save_entity_type(result_request_type, resolved_entity_type),
            entity_id=resolved_entity_id,
            output=output or "",
            month_key=None,
            audit_tools=audit_tools,
        )
        try:
            saved = ai_approve(approve_payload, session, current_user, space_ctx)
        except HTTPException as exc:
            result["reply"] = f"Auto-save failed: {exc.detail}"
            result["requires_approval"] = True
        else:
            auto_saved = True
            result["reply"] = saved.reply or "Saved."
            result["requires_approval"] = False
            result["request_type"] = saved.request_type or result_request_type
            result_request_type = saved.request_type or result_request_type
            output = saved.output or output
            if saved.entity_id:
                payload.entity_id = saved.entity_id
            if saved.entity_type:
                payload.entity_type = saved.entity_type
            resolved_entity_id = payload.entity_id
            resolved_entity_type = payload.entity_type

    history = history + [
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": result.get("reply", "")},
    ]
    session_obj.project_id = resolved_entity_id if resolved_entity_type == "project" else payload.project_id
    session_obj.entity_type = resolved_entity_type
    session_obj.entity_id = resolved_entity_id
    if not session_obj.space_id:
        session_obj.space_id = space_ctx.space_id
    _save_session(session, session_obj, history)
    session.commit()
    requires_approval = bool(result.get("requires_approval"))
    if (not auto_saved) and result_request_type in {
        "autofill",
        "sow",
        "checklist",
        "subcomponents",
        "project_create",
        "solution_create",
        "subcomponent_create",
        "charter_create",
        "plan_create",
        "decision_log_create",
    } and not requires_approval:
        requires_approval = True
    next_action = result.get("next_action")
    if auto_saved:
        next_action = "done"
    elif requires_approval:
        next_action = "approve_or_discard"
    elif not next_action:
        next_action = "answer_question" if (result.get("reply", "").strip().endswith("?")) else "done"
    return AIChatResponse(
        reply=result.get("reply", ""),
        requires_approval=requires_approval,
        request_type=result_request_type,
        entity_type=resolved_entity_type,
        entity_id=resolved_entity_id,
        output=output,
        session_id=session_obj.session_id,
        next_action=next_action,
        debug=result.get("debug"),
    )


@router.post("/approve", response_model=AIChatResponse)
def ai_approve(
    payload: GenAIApproveRequest,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    now = datetime.now(timezone.utc)
    autofill_update_count = 0
    req_type = (payload.request_type or "").strip().lower()
    request_type_map = {
        "create_project": "project_create",
        "project": "project_create",
        "create_solution": "solution_create",
        "solution": "solution_create",
        "create_subcomponent": "subcomponent_create",
        "subcomponent": "subcomponent_create",
        "draft_solution": "solution_create",
        "create_solution_draft": "solution_create",
        "update": "autofill",
        "charter": "charter_create",
        "plan": "plan_create",
        "decision_log": "decision_log_create",
    }
    normalized_request_type = request_type_map.get(req_type, req_type)
    if not normalized_request_type:
        inferred = _infer_request_type_from_output(payload.output, payload.entity_type, payload.entity_id)
        if inferred:
            normalized_request_type = inferred
    audit_summary = _build_ai_request_audit_summary(
        normalized_request_type,
        payload.entity_type,
        payload.entity_id,
        payload.output,
        month_key=payload.month_key,
        audit_tools=payload.audit_tools,
    )
    ai_request = AIRequest(
        space_id=space_ctx.space_id,
        request_type=normalized_request_type,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        instruction=None,
        prompt=None,
        output=audit_summary,
        approved=True,
        approved_by_user_id=current_user.user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(ai_request)

    if normalized_request_type == "autofill":
        updates_to_apply = _parse_autofill_updates(payload.output, payload.entity_type, payload.entity_id)
        if not updates_to_apply:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_missing_fields_section_detail("autofill"),
            )
        applied_count = 0
        first_entity_type = None
        first_entity_id = None
        for update in updates_to_apply:
            entity_type = update.get("entity_type")
            entity_id = update.get("entity_id")
            fields = update.get("fields") or {}
            if entity_type == "project":
                entity = (
                    session.query(Project)
                    .filter(Project.project_id == entity_id)
                    .filter(Project.deleted_at.is_(None))
                    .filter(_in_space(Project, space_ctx.space_id))
                    .first()
                )
            elif entity_type == "solution":
                entity = (
                    session.query(Solution)
                    .filter(Solution.solution_id == entity_id)
                    .filter(Solution.deleted_at.is_(None))
                    .filter(_in_space(Solution, space_ctx.space_id))
                    .first()
                )
            elif entity_type == "subcomponent":
                entity = (
                    session.query(Subcomponent)
                    .filter(Subcomponent.subcomponent_id == entity_id)
                    .filter(Subcomponent.deleted_at.is_(None))
                    .filter(_in_space(Subcomponent, space_ctx.space_id))
                    .first()
                )
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported entity_type: {entity_type}")
            if not entity:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Entity not found: {entity_type}:{entity_id}")
            if first_entity_type is None:
                first_entity_type = entity_type
                first_entity_id = entity_id
            for key, value in fields.items():
                if not hasattr(entity, key):
                    continue
                if value is None or value == "":
                    continue
                if key in {"due_date", "planned_start_date"}:
                    parsed = _coerce_date(value)
                    if parsed is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid date for {key}: {value}",
                        )
                    setattr(entity, key, parsed)
                elif key in _BOOL_FIELDS:
                    parsed = _coerce_bool(value)
                    if parsed is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid boolean for {key}: {value}",
                        )
                    setattr(entity, key, parsed)
                elif key in _INT_FIELDS:
                    try:
                        parsed = int(value)
                    except Exception as exc:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid integer for {key}: {value}",
                        ) from exc
                    setattr(entity, key, parsed)
                elif key in _FLOAT_FIELDS:
                    try:
                        parsed = float(value)
                    except Exception as exc:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid number for {key}: {value}",
                        ) from exc
                    setattr(entity, key, parsed)
                else:
                    setattr(entity, key, value)
            entity.updated_at = now
            session.add(entity)
            applied_count += 1
        autofill_update_count = applied_count
        if first_entity_type:
            ai_request.entity_type = first_entity_type
        if first_entity_id:
            ai_request.entity_id = first_entity_id

    elif normalized_request_type == "sow":
        content = _extract_json_content(payload.output)
        sow = SOWDocument(
            space_id=space_ctx.space_id,
            project_id=payload.entity_id if payload.entity_type == "project" else None,
            solution_id=payload.entity_id if payload.entity_type == "solution" else None,
            content=content,
            created_by_user_id=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        if not sow.project_id and payload.entity_type == "solution":
            solution = (
                session.query(Solution)
                .filter(Solution.solution_id == payload.entity_id)
                .filter(Solution.deleted_at.is_(None))
                .filter(_in_space(Solution, space_ctx.space_id))
                .first()
            )
            if solution:
                sow.project_id = solution.project_id
        if not sow.project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project context required for SOW")
        session.add(sow)

    elif normalized_request_type == "checklist":
        items = _parse_checklist(payload.output)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid AI output: missing # Checklist section",
            )
        month_key = payload.month_key or datetime.now(timezone.utc).strftime("%Y-%m")
        project_exists = (
            session.query(Project)
            .filter(Project.project_id == payload.entity_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        for item in items:
            entry = ChecklistItem(
                space_id=space_ctx.space_id,
                project_id=payload.entity_id,
                month_key=month_key,
                title=item,
                status="open",
                created_by_user_id=current_user.user_id,
                created_at=now,
                updated_at=now,
            )
            session.add(entry)

    elif normalized_request_type == "subcomponents":
        items = _parse_subcomponents(payload.output)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid AI output: missing # Subcomponents section",
            )
        if payload.entity_type != "solution":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subcomponents require solution context")
        solution = (
            session.query(Solution)
            .filter(Solution.solution_id == payload.entity_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(_in_space(Solution, space_ctx.space_id))
            .first()
        )
        if not solution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        for item in items:
            name = item.get("name")
            if not name:
                continue
            priority = _parse_int_or_default(item.get("priority", "3"), 3)
            assignee = item.get("assignee", "")
            sub = Subcomponent(
                space_id=space_ctx.space_id,
                project_id=solution.project_id,
                solution_id=solution.solution_id,
                subcomponent_name=name,
                status="to_do",
                priority=priority,
                assignee=assignee or "",
                created_at=now,
                updated_at=now,
            )
            session.add(sub)

    elif normalized_request_type == "charter_create":
        if not payload.entity_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")
        project_exists = (
            session.query(Project)
            .filter(Project.project_id == payload.entity_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        content = _extract_json_content(payload.output)
        charter = ProjectCharter(
            space_id=space_ctx.space_id,
            project_id=payload.entity_id,
            title=None,
            content=content,
            created_by_user_id=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(charter)

    elif normalized_request_type == "plan_create":
        if not payload.entity_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")
        project_exists = (
            session.query(Project)
            .filter(Project.project_id == payload.entity_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        content = _extract_json_content(payload.output)
        plan = ProjectPlan(
            space_id=space_ctx.space_id,
            project_id=payload.entity_id,
            title=None,
            content=content,
            created_by_user_id=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(plan)

    elif normalized_request_type == "decision_log_create":
        if not payload.entity_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")
        project_exists = (
            session.query(Project)
            .filter(Project.project_id == payload.entity_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        content = _extract_json_content(payload.output)
        decision = ProjectDecisionLog(
            space_id=space_ctx.space_id,
            project_id=payload.entity_id,
            title=None,
            decision=content,
            rationale=None,
            impact=None,
            created_by_user_id=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(decision)

    elif normalized_request_type == "project_create":
        fields = _parse_fields(payload.output or "")
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_missing_fields_section_detail("project_create", ["project_name"]),
            )
        name = fields.get("project_name") or fields.get("name")
        if not name:
            return AIChatResponse(
                reply="I still need a project name to save this. What should it be called?",
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                output=payload.output,
            )
        existing = (
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .filter(func.lower(Project.project_name) == name.strip().lower())
            .first()
        )
        if existing:
            return AIChatResponse(
                reply=f"A project named '{existing.project_name}' already exists. Use a different name or tell me to update the existing project.",
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type=payload.entity_type,
                entity_id=existing.project_id,
                output=payload.output,
            )
        status_val = fields.get("status") or "not_started"
        sponsor = fields.get("sponsor") or current_user.display_name or "Sponsor"
        sponsor_user_soeid = str(fields.get("sponsor_user_soeid") or "").strip() or None
        if sponsor_user_soeid is None and current_user.soeid:
            sponsor_clean = str(sponsor or "").strip()
            if sponsor_clean and sponsor_clean in {current_user.display_name, current_user.soeid}:
                sponsor_user_soeid = current_user.soeid
        priority = _parse_int_or_default(fields.get("priority"), 3)
        project = Project(
            space_id=space_ctx.space_id,
            project_name=name,
            status=status_val,
            sponsor=sponsor,
            sponsor_user_soeid=sponsor_user_soeid,
            priority=priority,
            description=fields.get("description"),
            success_criteria=fields.get("success_criteria"),
            strategic_objective=fields.get("strategic_objective"),
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.flush()
        ai_request.entity_type = "project"
        ai_request.entity_id = project.project_id

    elif normalized_request_type == "solution_create":
        fields = _parse_fields(payload.output or "")
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_missing_fields_section_detail("solution_create", ["solution_name"]),
            )
        if not payload.entity_id:
            return AIChatResponse(
                reply="Which project should this solution belong to?",
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                output=payload.output,
            )
        project = (
            session.query(Project)
            .filter(Project.project_id == payload.entity_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        name = fields.get("solution_name") or fields.get("name")
        if not name:
            return AIChatResponse(
                reply="I still need a solution name to save this. What should it be called?",
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                output=payload.output,
            )
        existing = (
            session.query(Solution)
            .filter(Solution.project_id == payload.entity_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(_in_space(Solution, space_ctx.space_id))
            .filter(func.lower(Solution.solution_name) == name.strip().lower())
            .first()
        )
        if existing:
            return AIChatResponse(
                reply=(
                    f"A solution named '{existing.solution_name}' already exists in this project. "
                    "Use a different name or tell me to update the existing solution."
                ),
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type="solution",
                entity_id=existing.solution_id,
                output=payload.output,
            )
        version = fields.get("version") or "0.1.0"
        status_val = fields.get("status") or "not_started"
        owner = fields.get("owner") or current_user.display_name or current_user.soeid or ""
        assignee = fields.get("assignee") or owner
        priority = _parse_int_or_default(fields.get("priority"), 3)
        rag_status = fields.get("rag_status") or "green"
        capacity_hours = _parse_int_or_default(fields.get("capacity_hours"), 0)
        due_date = None
        if fields.get("due_date"):
            due_date = _coerce_date(str(fields.get("due_date")))
            if due_date is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid date for due_date: {fields.get('due_date')}",
                )
        solution = Solution(
            space_id=space_ctx.space_id,
            project_id=payload.entity_id,
            solution_name=name,
            version=version,
            status=status_val,
            owner=owner,
            priority=priority,
            description=fields.get("description"),
            success_criteria=fields.get("success_criteria"),
            risks=fields.get("risks"),
            blockers=fields.get("blockers"),
            assignee=assignee,
            rag_status=rag_status,
            rag_reason=fields.get("rag_reason"),
            capacity_hours=capacity_hours,
            due_date=due_date,
            current_phase=fields.get("current_phase"),
            impact_confidence=fields.get("impact_confidence"),
            owner_user_soeid=fields.get("owner_user_soeid"),
            assignee_user_soeid=fields.get("assignee_user_soeid"),
            approver=fields.get("approver"),
            approver_user_soeid=fields.get("approver_user_soeid"),
            created_at=now,
            updated_at=now,
        )
        session.add(solution)
        session.flush()
        ai_request.entity_type = "solution"
        ai_request.entity_id = solution.solution_id

    elif normalized_request_type == "subcomponent_create":
        fields = _parse_fields(payload.output or "")
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_missing_fields_section_detail("subcomponent_create", ["subcomponent_name"]),
            )
        if not payload.entity_id:
            return AIChatResponse(
                reply="Which solution should this subcomponent belong to?",
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                output=payload.output,
            )
        solution = (
            session.query(Solution)
            .filter(Solution.solution_id == payload.entity_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(_in_space(Solution, space_ctx.space_id))
            .first()
        )
        if not solution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")

        name = fields.get("subcomponent_name") or fields.get("name")
        if not name:
            return AIChatResponse(
                reply="I still need a subcomponent name to save this. What should it be called?",
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                output=payload.output,
            )
        existing = (
            session.query(Subcomponent)
            .filter(Subcomponent.solution_id == solution.solution_id)
            .filter(Subcomponent.deleted_at.is_(None))
            .filter(_in_space(Subcomponent, space_ctx.space_id))
            .filter(func.lower(Subcomponent.subcomponent_name) == name.strip().lower())
            .first()
        )
        if existing:
            return AIChatResponse(
                reply=(
                    f"A subcomponent named '{existing.subcomponent_name}' already exists in this solution. "
                    "Use a different name or tell me to update the existing subcomponent."
                ),
                requires_approval=False,
                request_type=normalized_request_type,
                entity_type="subcomponent",
                entity_id=existing.subcomponent_id,
                output=payload.output,
            )

        status_val = fields.get("status") or "to_do"
        priority = _parse_int_or_default(fields.get("priority"), 3)
        assignee = fields.get("assignee") or current_user.display_name or current_user.soeid or ""
        assignee_user_soeid = fields.get("assignee_user_soeid")
        blocked = False
        if fields.get("blocked") is not None:
            coerced = _coerce_bool(fields.get("blocked"))
            if coerced is not None:
                blocked = coerced
        due_date = None
        if fields.get("due_date"):
            due_date = _coerce_date(str(fields.get("due_date")))
            if due_date is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid date for due_date: {fields.get('due_date')}",
                )
        estimate_hours = None
        if fields.get("estimate_hours") is not None:
            try:
                estimate_hours = int(fields.get("estimate_hours"))
            except Exception:
                estimate_hours = None
        capacity_hours = _parse_int_or_default(fields.get("capacity_hours"), 0)

        sub = Subcomponent(
            space_id=space_ctx.space_id,
            project_id=solution.project_id,
            solution_id=solution.solution_id,
            subcomponent_name=name,
            status=status_val,
            priority=priority,
            due_date=due_date,
            assignee=assignee or "",
            assignee_user_soeid=str(assignee_user_soeid).strip() if assignee_user_soeid else None,
            estimate_hours=estimate_hours,
            blocked=blocked,
            blocker_note=fields.get("blocker_note"),
            done_criteria=fields.get("done_criteria"),
            capacity_hours=capacity_hours,
            created_at=now,
            updated_at=now,
        )
        session.add(sub)
        session.flush()
        ai_request.entity_type = "subcomponent"
        ai_request.entity_id = sub.subcomponent_id

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported request_type")

    session.commit()
    # For create flows, return the created entity id/type so the client can keep context.
    entity_type_out = ai_request.entity_type or payload.entity_type
    entity_id_out = ai_request.entity_id or payload.entity_id
    reply_text = "Saved."
    if normalized_request_type == "autofill":
        if autofill_update_count > 1:
            reply_text = f"Saved. Updated {autofill_update_count} items."
    return AIChatResponse(
        reply=reply_text,
        requires_approval=False,
        request_type=normalized_request_type,
        entity_type=entity_type_out,
        entity_id=entity_id_out,
        output=payload.output,
        next_action="done",
    )


@router.post("/documents/upload")
def upload_document(
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    if project_id:
        project_exists = (
            session.query(Project)
            .filter(Project.project_id == project_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if solution_id:
        solution_exists = (
            session.query(Solution)
            .filter(Solution.solution_id == solution_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(_in_space(Solution, space_ctx.space_id))
            .first()
        )
        if not solution_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        if project_id and solution_exists.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solution does not belong to project")

    storage_root = os.getenv("SIPM_DOC_STORAGE", "data/external_docs")
    os.makedirs(storage_root, exist_ok=True)
    safe_name = _sanitize_upload_filename(file.filename)
    doc_id = str(uuid4())
    storage_path = os.path.join(storage_root, f"{doc_id}_{safe_name}")
    with open(storage_path, "wb") as f:
        f.write(file.file.read())

    doc = ExternalDocument(
        document_id=doc_id,
        space_id=space_ctx.space_id,
        project_id=project_id,
        solution_id=solution_id,
        filename=safe_name,
        content_type=file.content_type,
        storage_path=storage_path,
        uploaded_by_user_id=current_user.user_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    session.commit()

    return {"document_id": doc.document_id, "filename": doc.filename}


@router.post("/tools/read_context")
def read_context_tool(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    project_id: Optional[str] = None,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_context(session, entity_type, entity_id, project_id, space_id=space_ctx.space_id)


@router.post("/tools/read_context_complete")
def read_context_complete_tool(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    project_id: Optional[str] = None,
    history_limit: int = 200,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_context_complete(
        session,
        entity_type,
        entity_id,
        project_id,
        history_limit=history_limit,
        space_id=space_ctx.space_id,
    )


@router.post("/tools/read_project_detail")
def read_project_detail_tool(
    project_id: str,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_project_detail(session, project_id, space_id=space_ctx.space_id)


@router.post("/tools/read_solution_detail")
def read_solution_detail_tool(
    solution_id: str,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_solution_detail(session, solution_id, space_id=space_ctx.space_id)


@router.post("/tools/read_subcomponent_detail")
def read_subcomponent_detail_tool(
    subcomponent_id: str,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_subcomponent_detail(session, subcomponent_id, space_id=space_ctx.space_id)


@router.post("/tools/read_artifacts_detail")
def read_artifacts_detail_tool(
    project_id: str,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_artifacts_detail(session, project_id, space_id=space_ctx.space_id)


@router.post("/tools/read_sow_document")
def read_sow_document_tool(
    sow_id: str,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_sow_document(session, sow_id, space_id=space_ctx.space_id)


@router.post("/tools/list_projects")
def list_projects_tool(
    limit: int = 200,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return list_projects(session, limit=limit, space_id=space_ctx.space_id)


@router.post("/tools/list_solutions_for_project")
def list_solutions_for_project_tool(
    project_id: str,
    limit: int = 200,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return list_solutions_for_project(session, project_id, limit=limit, space_id=space_ctx.space_id)


@router.post("/tools/explain_app_usage")
def explain_app_usage_tool(
    question: Optional[str] = None,
    topic: Optional[str] = None,
    max_sections: int = 4,
    current_user=Depends(require_user),
    _space_ctx: SpaceContext = Depends(current_space_dep),
):
    del current_user
    return explain_app_usage(question=question, topic=topic, max_sections=max_sections)


@router.post("/tools/get_scope_digest")
def get_scope_digest_tool(
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 5,
    question: Optional[str] = None,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return get_scope_digest(
        session,
        project_id=project_id,
        solution_id=solution_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        question=question,
        space_id=space_ctx.space_id,
    )


@router.post("/tools/list_project_cards")
def list_project_cards_tool(
    limit: int = 50,
    cursor: Optional[str] = None,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    query: Optional[str] = None,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "packed",
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return list_project_cards(
        session,
        limit=limit,
        cursor=cursor,
        project_id=project_id,
        status=_parse_csv_param(status),
        query=query,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
        response_format=response_format,
        space_id=space_ctx.space_id,
    )


@router.post("/tools/list_solution_cards")
def list_solution_cards_tool(
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    status: Optional[str] = None,
    rag_status: Optional[str] = None,
    query: Optional[str] = None,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "packed",
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return list_solution_cards(
        session,
        project_id=project_id,
        solution_id=solution_id,
        limit=limit,
        cursor=cursor,
        status=_parse_csv_param(status),
        rag_status=_parse_csv_param(rag_status),
        query=query,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
        response_format=response_format,
        space_id=space_ctx.space_id,
    )


@router.post("/tools/list_task_cards")
def list_task_cards_tool(
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    status: Optional[str] = None,
    blocked: Optional[bool] = None,
    query: Optional[str] = None,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "packed",
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return list_task_cards(
        session,
        project_id=project_id,
        solution_id=solution_id,
        limit=limit,
        cursor=cursor,
        status=_parse_csv_param(status),
        blocked=blocked,
        query=query,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
        response_format=response_format,
        space_id=space_ctx.space_id,
    )


@router.post("/tools/get_project_card")
def get_project_card_tool(
    project_id: str,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "objects",
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return get_project_card(
        session,
        project_id=project_id,
        space_id=space_ctx.space_id,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
        response_format=response_format,
    )


@router.post("/tools/get_solution_card")
def get_solution_card_tool(
    solution_id: str,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "objects",
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return get_solution_card(
        session,
        solution_id=solution_id,
        space_id=space_ctx.space_id,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
        response_format=response_format,
    )


@router.post("/tools/get_task_card")
def get_task_card_tool(
    task_id: str,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "objects",
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return get_task_card(
        session,
        task_id=task_id,
        space_id=space_ctx.space_id,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
        response_format=response_format,
    )


@router.post("/tools/get_entity_fields")
def get_entity_fields_tool(
    entity_type: str,
    entity_id: str,
    fields: Optional[str] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return get_entity_fields(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        space_id=space_ctx.space_id,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
    )


@router.post("/tools/get_entity_deltas")
def get_entity_deltas_tool(
    since_cursor: Optional[str] = None,
    entity_types: Optional[str] = None,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = 200,
    fields: Optional[str] = None,
    field_pack: Optional[str] = "minimal",
    question: Optional[str] = None,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return get_entity_deltas(
        session,
        since_cursor=since_cursor,
        entity_types=_parse_csv_param(entity_types),
        project_id=project_id,
        solution_id=solution_id,
        limit=limit,
        space_id=space_ctx.space_id,
        fields=_parse_csv_param(fields),
        field_pack=field_pack,
        question=question,
    )


@router.post("/tools/read_entity_index")
def read_entity_index_tool(
    entity_type: str,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = 200,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_entity_index(
        session,
        entity_type,
        project_id=project_id,
        solution_id=solution_id,
        limit=limit,
        space_id=space_ctx.space_id,
    )


@router.post("/tools/read_entity_deltas")
def read_entity_deltas_tool(
    entity_type: str,
    since: Optional[str] = None,
    limit: int = 200,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return read_entity_deltas(session, entity_type, since=since, limit=limit, space_id=space_ctx.space_id)


@router.post("/tools/validate_draft")
def validate_draft_tool(
    entity_type: str,
    action: str,
    fields: Dict[str, Any],
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return validate_draft(session, entity_type, fields, action=action, space_id=space_ctx.space_id)


@router.post("/tools/apply_draft")
def apply_draft_tool(
    entity_type: str,
    action: str,
    fields: Dict[str, Any],
    entity_id: Optional[str] = None,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return apply_draft(session, entity_type, action, fields, entity_id=entity_id, space_id=space_ctx.space_id)


@router.post("/tools/verify_write")
def verify_write_tool(
    entity_type: str,
    entity_id: str,
    expected_fields: Dict[str, Any],
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    return verify_write(session, entity_type, entity_id, expected_fields, space_id=space_ctx.space_id)
