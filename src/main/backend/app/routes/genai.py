from __future__ import annotations

from datetime import date, datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..deps import get_db, require_user, current_space as current_space_dep
from ..ai.llm import call_chat_completion, GenAIConfigError
from ..ai.prompt_loader import render_prompt
from ..models import (
    Project,
    Phase,
    Solution,
    Subcomponent,
    SOWDocument,
    ChecklistItem,
    AIRequest,
)
from ..utils.enums import (
    ProjectStatus,
    SolutionStatus,
    SubcomponentStatus,
    RagStatus,
    ConfidenceLevel,
)
from ..schemas import (
    GenAIRequest,
    GenAIResponse,
    GenAIApproveRequest,
    GenAIIntentRequest,
    GenAIIntentResponse,
    GenAIMessage,
    GenAISearchRequest,
    GenAISearchResponse,
    GenAISearchResult,
)
from ..services.spaces import SpaceContext

router = APIRouter()

_AI_REQUEST_OUTPUT_MAX = 255


def _in_space(model, space_id: str):
    return model.space_id == space_id


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
    summary = f"{req or 'request'} approved for {target}"

    if req == "autofill":
        fields = _parse_fields(output or "")
        keys = [str(k) for k in list(fields.keys())[:8]]
        summary = f"autofill approved for {target}"
        if keys:
            summary += f"; fields: {', '.join(keys)}"
    elif req == "subcomponents":
        items = _parse_subcomponents(output or "")
        summary = f"subcomponents approved for {target}; count: {len(items)}"
    elif req == "checklist":
        items = _parse_checklist(output or "")
        summary = f"checklist approved for {target}; month: {month_key or 'current'}; items: {len(items)}"
    elif req in {"sow", "charter_create", "plan_create", "decision_log_create"}:
        text = str(output or "")
        summary = f"{req} approved for {target}; content_len: {len(text)}"

    tools = _sanitize_audit_tools(audit_tools)
    if tools:
        summary += f"; tools: {', '.join(tools[:8])}"
    return _compact_ai_request_output(summary) or summary


def _project_context(project: Project) -> Dict[str, Any]:
    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "description": project.description,
        "success_criteria": project.success_criteria,
        "strategic_objective": project.strategic_objective,
        "priority": project.priority,
    }


def _solution_context(solution: Solution) -> Dict[str, Any]:
    return {
        "solution_id": solution.solution_id,
        "solution_name": solution.solution_name,
        "version": solution.version,
        "status": solution.status.value if hasattr(solution.status, "value") else solution.status,
        "rag_status": solution.rag_status.value if hasattr(solution.rag_status, "value") else solution.rag_status,
        "priority": solution.priority,
        "due_date": solution.due_date.isoformat() if solution.due_date else None,
        "current_phase": solution.current_phase,
        "description": solution.description,
        "success_criteria": solution.success_criteria,
        "problem_statement": solution.problem_statement,
        "blockers": solution.blockers,
        "risks": solution.risks,
    }


def _subcomponent_context(sub: Subcomponent) -> Dict[str, Any]:
    return {
        "subcomponent_id": sub.subcomponent_id,
        "subcomponent_name": sub.subcomponent_name,
        "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
        "priority": sub.priority,
        "due_date": sub.due_date.isoformat() if sub.due_date else None,
        "blocked": sub.blocked,
        "blocker_note": sub.blocker_note,
        "done_criteria": sub.done_criteria,
        "estimate_hours": sub.estimate_hours,
    }


def _get_context(session: Session, payload: GenAIRequest, space_id: str) -> Dict[str, Any]:
    phases = session.query(Phase).order_by(Phase.sequence).all()
    phase_list = [
        {"phase_id": phase.phase_id, "phase_name": phase.phase_name, "phase_group": phase.phase_group}
        for phase in phases
    ]
    entity_type = payload.entity_type
    entity_id = payload.entity_id
    if not entity_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_id is required")

    if entity_type == "project":
        project = (
            session.query(Project)
            .filter(Project.project_id == entity_id)
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
            "phases": phase_list,
            "project": _project_context(project),
            "solutions": [_solution_context(s) for s in solutions],
            "subcomponents": [_subcomponent_context(sc) for sc in subcomponents],
        }

    if entity_type == "solution":
        solution = (
            session.query(Solution)
            .filter(Solution.solution_id == entity_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(_in_space(Solution, space_id))
            .first()
        )
        if not solution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        project = (
            session.query(Project)
            .filter(Project.project_id == solution.project_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_id))
            .first()
        )
        subcomponents = (
            session.query(Subcomponent)
            .filter(Subcomponent.solution_id == solution.solution_id)
            .filter(Subcomponent.deleted_at.is_(None))
            .filter(_in_space(Subcomponent, space_id))
            .all()
        )
        return {
            "phases": phase_list,
            "project": _project_context(project) if project else None,
            "solution": _solution_context(solution),
            "subcomponents": [_subcomponent_context(sc) for sc in subcomponents],
        }

    if entity_type == "subcomponent":
        sub = (
            session.query(Subcomponent)
            .filter(Subcomponent.subcomponent_id == entity_id)
            .filter(Subcomponent.deleted_at.is_(None))
            .filter(_in_space(Subcomponent, space_id))
            .first()
        )
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcomponent not found")
        solution = (
            session.query(Solution)
            .filter(Solution.solution_id == sub.solution_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(_in_space(Solution, space_id))
            .first()
        )
        project = (
            session.query(Project)
            .filter(Project.project_id == sub.project_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_id))
            .first()
        )
        return {
            "phases": phase_list,
            "project": _project_context(project) if project else None,
            "solution": _solution_context(solution) if solution else None,
            "subcomponent": _subcomponent_context(sub),
        }

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entity_type")


def _system_prompt(task_name: str) -> str:
    return render_prompt("genai/system.md", task_name=task_name)


def _intent_system_prompt() -> str:
    return render_prompt("agent/intent.md")


def _intent_user_prompt(
    message: str,
    entity_type: str | None,
    entity_id: str | None,
    history: List[GenAIMessage],
    current_date: str | None,
) -> str:
    context = {"entity_type": entity_type, "entity_id": entity_id}
    history_block = _format_history(history)
    now = datetime.now(timezone.utc).isoformat()
    date_line = f"Today's date and time: {now}\n"
    date_hint = f"Today's date: {current_date}\n" if current_date else ""
    return f"{date_line}{date_hint}Message: {message}\nContext: {context}\n{history_block}"


def _fallback_intent(message: str) -> str:
    msg = (message or "").lower()
    if "update" in msg or "edit" in msg or "change" in msg:
        return "autofill"
    if "create project" in msg or "new project" in msg:
        return "project_create"
    if "create solution" in msg or "new solution" in msg:
        return "solution_create"
    if "sow" in msg:
        return "sow"
    if "checklist" in msg:
        return "checklist"
    if "subcomponent" in msg or "tasks" in msg:
        return "subcomponents"
    if "autofill" in msg or "fill" in msg:
        return "autofill"
    if "search" in msg or "find" in msg:
        return "search"
    return "none"


def _parse_intent_response(text: str) -> Dict[str, str]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            intent = str(data.get("intent", "")).strip()
            reply = str(data.get("reply", "")).strip()
            if intent:
                return {"intent": intent, "reply": reply}
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                intent = str(data.get("intent", "")).strip()
                reply = str(data.get("reply", "")).strip()
                if intent:
                    return {"intent": intent, "reply": reply}
        except Exception:
            pass
    return {"intent": "", "reply": ""}


def _normalize_intent(intent: str) -> str:
    allowed = {
        "autofill",
        "update",
        "sow",
        "checklist",
        "subcomponents",
        "project_create",
        "solution_create",
        "search",
        "none",
    }
    intent = (intent or "").strip().lower()
    if intent == "update":
        return "autofill"
    return intent if intent in allowed else ""


def _user_prompt(task_name: str, context: Dict[str, Any], instruction: str | None) -> str:
    history_block = ""
    if isinstance(context.get("_history"), list):
        history_block = _format_history(context.get("_history", []))
    now = datetime.now(timezone.utc).isoformat()
    date_line = f"Today's date and time: {now}\n"
    if context.get("_current_date"):
        date_line += f"Today's date: {context.get('_current_date')}\n"
    current_user = context.get("_current_user") or {}
    user_name = str(current_user.get("display_name") or "").strip()
    user_soeid = str(current_user.get("soeid") or "").strip()
    user_block = ""
    if user_name and user_soeid:
        user_block = (
            f"Current user display_name: {user_name}\n"
            f"Current user soeid (user identifier): {user_soeid}\n"
        )
    elif user_name:
        user_block = f"Current user display_name: {user_name}\n"
    elif user_soeid:
        user_block = f"Current user soeid (user identifier): {user_soeid}\n"
    dropdown_block = _dropdown_text(context)
    return (
        f"Task: {task_name}.\n"
        "Use only the context below and respond in strict JSON.\n"
        "Only include fields you are confident about; omit unknowns.\n"
        "Use ISO dates (YYYY-MM-DD) for any date fields.\n"
        "Return JSON with optional keys:\n"
        "- summary: string\n"
        "- fields: object of field_name -> value\n"
        "- checklist: array of strings\n"
        "- subcomponents: array of {name, priority, assignee}\n"
        "- content: string (for drafts like SOW/plan/charter/decision log)\n"
        "- question: string (only if missing required info)\n"
        f"Instruction: {instruction or 'N/A'}\n\n"
        f"{date_line}"
        f"{user_block}"
        f"{dropdown_block}"
        f"Context JSON:\n{context}\n\n"
        f"{history_block}"
    )


def _project_prompt(instruction: str | None) -> str:
    return render_prompt(
        "agent/tasks/project_create.md",
        status_values=", ".join(_enum_values(ProjectStatus)),
        instruction=instruction or "N/A",
    )


def _solution_prompt(instruction: str | None) -> str:
    return render_prompt(
        "agent/tasks/solution_create.md",
        status_values=", ".join(_enum_values(SolutionStatus)),
        rag_status_values=", ".join(_enum_values(RagStatus)),
        impact_confidence_values=", ".join(_enum_values(ConfidenceLevel)),
        instruction=instruction or "N/A",
    )


def _subcomponent_prompt(instruction: str | None) -> str:
    return render_prompt(
        "agent/tasks/subcomponent_create.md",
        status_values=", ".join(_enum_values(SubcomponentStatus)),
        instruction=instruction or "N/A",
    )


def _format_history(history: List[GenAIMessage]) -> str:
    if not history:
        return ""
    lines = ["Conversation so far:"]
    for msg in history[-12:]:
        role = msg.role or "user"
        content = msg.content or ""
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def _parse_section_lines(output: str, header: str) -> List[str]:
    lines = output.splitlines()
    in_section = False
    result: List[str] = []
    for line in lines:
        if line.strip().startswith("# "):
            in_section = line.strip().lower() == f"# {header}".lower()
            continue
        if in_section and line.strip():
            result.append(line.strip())
    return result


def _strip_fenced_block(output: str) -> str:
    """Extract the contents of the first ```...``` fenced block if present.

    This avoids brittle regex parsing and makes JSON parsing resilient when the model wraps output in markdown fences.
    """
    if not output:
        return output
    text = str(output)
    start = text.find("```")
    if start == -1:
        return output
    end = text.find("```", start + 3)
    if end == -1:
        return output
    inner = text[start + 3 : end]
    inner = inner.lstrip()
    # Handle ```json\n...\n``` (language tag on the first line).
    first_newline = inner.find("\n")
    if first_newline != -1:
        first_line = inner[:first_newline].strip().lower()
        if first_line == "json":
            inner = inner[first_newline + 1 :]
    return inner.strip()


def _parse_fields(output: str) -> Dict[str, str]:
    if not output:
        return {}
    output = _strip_fenced_block(output)
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            if isinstance(data.get("fields"), dict):
                return data.get("fields") or {}
            if any(isinstance(v, (str, int, float, bool)) or v is None for v in data.values()):
                return {
                    k: v
                    for k, v in data.items()
                    if k not in {"summary", "content", "checklist", "subcomponents", "question", "questions"}
                }
    except Exception:
        pass
    fields: Dict[str, str] = {}
    for line in _parse_section_lines(output, "Fields"):
        line = line.lstrip("- ").strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def _coerce_date(value: str) -> date | None:
    if not value:
        return None
    cleaned = value.strip().strip('"').strip()
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError:
            return None


def _enum_values(enum_cls) -> List[str]:
    return [str(item.value) for item in enum_cls]


def _dropdown_text(context: Dict[str, Any]) -> str:
    sections: List[str] = []
    if context.get("phases"):
        phase_names = [p.get("phase_name") for p in context.get("phases", []) if p.get("phase_name")]
        if phase_names:
            sections.append(f"- current_phase: {', '.join(phase_names)}")
    if context.get("project"):
        sections.append(f"- status: {', '.join(_enum_values(ProjectStatus))}")
    if context.get("solution"):
        sections.append(f"- status: {', '.join(_enum_values(SolutionStatus))}")
        sections.append(f"- rag_status: {', '.join(_enum_values(RagStatus))}")
        sections.append(f"- impact_confidence: {', '.join(_enum_values(ConfidenceLevel))}")
    if context.get("subcomponent"):
        sections.append(f"- status: {', '.join(_enum_values(SubcomponentStatus))}")
    if not sections:
        return ""
    return "Dropdown values:\n" + "\n".join(sections) + "\n"


def _parse_checklist(output: str) -> List[str]:
    if not output:
        return []
    output = _strip_fenced_block(output)
    try:
        data = json.loads(output)
        if isinstance(data, dict) and isinstance(data.get("checklist"), list):
            return [str(item).strip() for item in data.get("checklist") if str(item).strip()]
    except Exception:
        pass
    items: List[str] = []
    for line in _parse_section_lines(output, "Checklist"):
        clean = line.lstrip("- ").strip()
        if clean.startswith("["):
            parts = clean.split("]", 1)
            if len(parts) > 1:
                clean = parts[1].strip()
        if clean:
            items.append(clean)
    return items


def _parse_subcomponents(output: str) -> List[Dict[str, str]]:
    if not output:
        return []
    output = _strip_fenced_block(output)
    try:
        data = json.loads(output)
        if isinstance(data, dict) and isinstance(data.get("subcomponents"), list):
            out: List[Dict[str, str]] = []
            for item in data.get("subcomponents"):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                out.append(
                    {
                        "name": name,
                        "priority": str(item.get("priority", "3")),
                        "assignee": str(item.get("assignee", "")),
                    }
                )
            return out
    except Exception:
        pass
    results: List[Dict[str, str]] = []
    for line in _parse_section_lines(output, "Subcomponents"):
        clean = line.lstrip("- ").strip()
        parts = [p.strip() for p in clean.split("|")]
        entry: Dict[str, str] = {}
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                entry[key.strip()] = value.strip().strip('"')
        if entry.get("name"):
            results.append(entry)
    return results


@router.post("/intent", response_model=GenAIIntentResponse)
def genai_intent(payload: GenAIIntentRequest) -> GenAIIntentResponse:
    system_prompt = _intent_system_prompt()
    history = payload.history or []
    user_prompt = _intent_user_prompt(payload.message, payload.entity_type, payload.entity_id, history, payload.current_date)
    try:
        raw = call_chat_completion(system_prompt, user_prompt)
    except GenAIConfigError:
        intent = _fallback_intent(payload.message)
        reply = ""
        if intent == "none":
            reply = (
                "I can help with autofill, SOWs, monthly checklists, project/solution creation, or subcomponents. "
                "Tell me what you want to do."
            )
        return GenAIIntentResponse(intent=intent, reply=reply)
    parsed = _parse_intent_response(raw)
    intent = _normalize_intent(parsed.get("intent") or "")
    if not intent:
        intent = _fallback_intent(payload.message)
    reply = parsed.get("reply") or ""
    return GenAIIntentResponse(intent=intent, reply=reply)


@router.post("/autofill", response_model=GenAIResponse)
def genai_autofill(
    payload: GenAIRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAIResponse:
    context = _get_context(session, payload, space_ctx.space_id)
    if payload.history:
        context["_history"] = payload.history
    if payload.current_date:
        context["_current_date"] = payload.current_date
    try:
        output = call_chat_completion(_system_prompt("autofill"), _user_prompt("autofill", context, payload.instruction))
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return GenAIResponse(output=output)


@router.post("/sow", response_model=GenAIResponse)
def genai_sow(
    payload: GenAIRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAIResponse:
    context = _get_context(session, payload, space_ctx.space_id)
    if payload.history:
        context["_history"] = payload.history
    if payload.current_date:
        context["_current_date"] = payload.current_date
    try:
        output = call_chat_completion(_system_prompt("sow"), _user_prompt("sow", context, payload.instruction))
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return GenAIResponse(output=output)


@router.post("/checklist", response_model=GenAIResponse)
def genai_checklist(
    payload: GenAIRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAIResponse:
    context = _get_context(session, payload, space_ctx.space_id)
    if payload.history:
        context["_history"] = payload.history
    if payload.current_date:
        context["_current_date"] = payload.current_date
    try:
        output = call_chat_completion(
            _system_prompt("monthly_checklist"),
            _user_prompt("monthly_checklist", context, payload.instruction),
        )
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return GenAIResponse(output=output)


@router.post("/subcomponents", response_model=GenAIResponse)
def genai_subcomponents(
    payload: GenAIRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAIResponse:
    context = _get_context(session, payload, space_ctx.space_id)
    if payload.history:
        context["_history"] = payload.history
    if payload.current_date:
        context["_current_date"] = payload.current_date
    try:
        output = call_chat_completion(
            _system_prompt("subcomponents"),
            _user_prompt("subcomponents", context, payload.instruction),
        )
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return GenAIResponse(output=output)


@router.post("/project-create", response_model=GenAIResponse)
def genai_project_create(payload: GenAIRequest) -> GenAIResponse:
    try:
        output = call_chat_completion(_system_prompt("project_create"), _project_prompt(payload.instruction))
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return GenAIResponse(output=output)


@router.post("/solution-create", response_model=GenAIResponse)
def genai_solution_create(
    payload: GenAIRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAIResponse:
    if not payload.entity_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")
    context = _get_context(
        session,
        GenAIRequest(entity_type="project", entity_id=payload.entity_id, instruction=None),
        space_ctx.space_id,
    )
    try:
        output = call_chat_completion(
            _system_prompt("solution_create"),
            _user_prompt("solution_create", context, payload.instruction) + "\n" + _solution_prompt(payload.instruction),
        )
    except GenAIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return GenAIResponse(output=output)

@router.post("/approve", response_model=GenAIResponse)
def genai_approve(
    payload: GenAIApproveRequest,
    session: Session = Depends(get_db),
    current_user=Depends(require_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAIResponse:
    now = datetime.now(timezone.utc)
    audit_summary = _build_ai_request_audit_summary(
        payload.request_type,
        payload.entity_type,
        payload.entity_id,
        payload.output,
        month_key=payload.month_key,
        audit_tools=payload.audit_tools,
    )
    ai_request = AIRequest(
        space_id=space_ctx.space_id,
        request_type=payload.request_type,
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

    if payload.request_type == "autofill":
        fields = _parse_fields(payload.output)
        if payload.entity_type == "project":
            entity = (
                session.query(Project)
                .filter(Project.project_id == payload.entity_id)
                .filter(Project.deleted_at.is_(None))
                .filter(_in_space(Project, space_ctx.space_id))
                .first()
            )
        elif payload.entity_type == "solution":
            entity = (
                session.query(Solution)
                .filter(Solution.solution_id == payload.entity_id)
                .filter(Solution.deleted_at.is_(None))
                .filter(_in_space(Solution, space_ctx.space_id))
                .first()
            )
        else:
            entity = (
                session.query(Subcomponent)
                .filter(Subcomponent.subcomponent_id == payload.entity_id)
                .filter(Subcomponent.deleted_at.is_(None))
                .filter(_in_space(Subcomponent, space_ctx.space_id))
                .first()
            )
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
        for key, value in fields.items():
            if hasattr(entity, key) and value:
                if key in {"due_date", "planned_start_date"}:
                    parsed = _coerce_date(value)
                    if parsed is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid date for {key}: {value}",
                        )
                    setattr(entity, key, parsed)
                else:
                    setattr(entity, key, value)
        entity.updated_at = now
        session.add(entity)

    elif payload.request_type == "sow":
        sow = SOWDocument(
            space_id=space_ctx.space_id,
            project_id=payload.entity_id if payload.entity_type == "project" else None,
            solution_id=payload.entity_id if payload.entity_type == "solution" else None,
            content=payload.output,
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

    elif payload.request_type == "checklist":
        items = _parse_checklist(payload.output)
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

    elif payload.request_type == "subcomponents":
        items = _parse_subcomponents(payload.output)
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
            priority = int(item.get("priority", "3") or 3)
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
    elif payload.request_type == "project_create":
        fields = _parse_fields(payload.output)
        name = fields.get("project_name") or fields.get("name")
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_name is required")
        status_val = fields.get("status") or "not_started"
        sponsor = fields.get("sponsor") or current_user.display_name or "Sponsor"
        priority = int(fields.get("priority") or 3)
        project = Project(
            space_id=space_ctx.space_id,
            project_name=name,
            status=status_val,
            sponsor=sponsor,
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
    elif payload.request_type == "solution_create":
        fields = _parse_fields(payload.output)
        if not payload.entity_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")
        name = fields.get("solution_name") or fields.get("name")
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="solution_name is required")
        version = fields.get("version") or "0.1.0"
        status_val = fields.get("status") or "not_started"
        owner = fields.get("owner") or current_user.display_name or ""
        priority = int(fields.get("priority") or 3)
        project = (
            session.query(Project)
            .filter(Project.project_id == payload.entity_id)
            .filter(Project.deleted_at.is_(None))
            .filter(_in_space(Project, space_ctx.space_id))
            .first()
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
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
            blockers=fields.get("blockers"),
            risks=fields.get("risks"),
            created_at=now,
            updated_at=now,
        )
        session.add(solution)
        session.flush()
        ai_request.entity_type = "solution"
        ai_request.entity_id = solution.solution_id
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported request_type")

    session.commit()
    return GenAIResponse(output=payload.output)


@router.post("/search", response_model=GenAISearchResponse)
def genai_search(
    payload: GenAISearchRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
) -> GenAISearchResponse:
    query = (payload.query or "").strip()
    if not query:
        return GenAISearchResponse(results=[])

    # Use genai to expand keywords (optional). If client isn't available, fall back to raw query.
    try:
        expanded = call_chat_completion(
            _system_prompt("search"),
            f"Return 5 keywords for search. Query: {query}",
        )
    except GenAIConfigError:
        expanded = query

    terms = [query]
    if expanded:
        terms.extend([t.strip() for t in expanded.split() if t.strip()])

    like_terms = [f"%{t}%" for t in terms[:5]]
    results: List[GenAISearchResult] = []

    term = like_terms[0]
    proj_matches = (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(_in_space(Project, space_ctx.space_id))
        .filter(or_(Project.project_name.ilike(term), Project.description.ilike(term)))
        .limit(payload.limit)
        .all()
    )
    for p in proj_matches:
        results.append(GenAISearchResult(entity_type="project", entity_id=p.project_id, label=p.project_name))

    sol_matches = (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(_in_space(Solution, space_ctx.space_id))
        .filter(or_(Solution.solution_name.ilike(term), Solution.description.ilike(term)))
        .limit(payload.limit)
        .all()
    )
    for s in sol_matches:
        results.append(GenAISearchResult(entity_type="solution", entity_id=s.solution_id, label=s.solution_name))

    sub_matches = (
        session.query(Subcomponent)
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(_in_space(Subcomponent, space_ctx.space_id))
        .filter(Subcomponent.subcomponent_name.ilike(term))
        .limit(payload.limit)
        .all()
    )
    for sc in sub_matches:
        results.append(GenAISearchResult(entity_type="subcomponent", entity_id=sc.subcomponent_id, label=sc.subcomponent_name))

    return GenAISearchResponse(results=results[: payload.limit])
