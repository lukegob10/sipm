from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
from collections import defaultdict
from datetime import datetime, date, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    AIRequest,
    AIToolCall,
    AIQueryMetric,
    AISession,
    Project,
    ProjectCardDigest,
    Solution,
    SolutionCardDigest,
    Subcomponent,
    TaskCardDigest,
    Phase,
    ProjectCharter,
    ProjectPlan,
    ProjectDecisionLog,
    ExternalDocument,
    SOWDocument,
    ChecklistItem,
    SolutionPhase,
)
from .contracts import get_contract, load_contracts, contract_hints
from ..utils.enums import (
    ProjectStatus,
    SolutionStatus,
    SubcomponentStatus,
    RagStatus,
    ConfidenceLevel,
)


def _enum_values(enum_cls) -> List[str]:
    return [str(item.value) for item in enum_cls]


def _iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _project_context(project: Project) -> Dict[str, Any]:
    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "description": project.description,
        "success_criteria": project.success_criteria,
        "sponsor": project.sponsor,
        "sponsor_user_soeid": project.sponsor_user_soeid,
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
        "rag_reason": solution.rag_reason,
        "priority": solution.priority,
        "due_date": solution.due_date.isoformat() if solution.due_date else None,
        "current_phase": solution.current_phase,
        "description": solution.description,
        "success_criteria": solution.success_criteria,
        "problem_statement": solution.problem_statement,
        "blockers": solution.blockers,
        "risks": solution.risks,
        "owner": solution.owner,
        "assignee": solution.assignee,
        "approver": solution.approver,
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
        "assignee": sub.assignee,
    }


def _project_detail(project: Project) -> Dict[str, Any]:
    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "description": project.description,
        "success_criteria": project.success_criteria,
        "sponsor": project.sponsor,
        "sponsor_user_soeid": project.sponsor_user_soeid,
        "strategic_objective": project.strategic_objective,
        "priority": project.priority,
        "created_at": _iso_date(project.created_at),
        "updated_at": _iso_date(project.updated_at),
        "deleted_at": _iso_date(project.deleted_at),
    }


def _solution_detail(solution: Solution) -> Dict[str, Any]:
    return {
        "solution_id": solution.solution_id,
        "project_id": solution.project_id,
        "solution_name": solution.solution_name,
        "version": solution.version,
        "status": solution.status.value if hasattr(solution.status, "value") else solution.status,
        "rag_status": solution.rag_status.value if hasattr(solution.rag_status, "value") else solution.rag_status,
        "rag_reason": solution.rag_reason,
        "priority": solution.priority,
        "due_date": _iso_date(solution.due_date),
        "current_phase": solution.current_phase,
        "description": solution.description,
        "success_criteria": solution.success_criteria,
        "problem_statement": solution.problem_statement,
        "owner": solution.owner,
        "owner_user_soeid": solution.owner_user_soeid,
        "assignee": solution.assignee,
        "assignee_user_soeid": solution.assignee_user_soeid,
        "approver": solution.approver,
        "approver_user_soeid": solution.approver_user_soeid,
        "key_stakeholder": solution.key_stakeholder,
        "blockers": solution.blockers,
        "risks": solution.risks,
        "impact_confidence": solution.impact_confidence.value if hasattr(solution.impact_confidence, "value") else solution.impact_confidence,
        "planned_start_date": _iso_date(solution.planned_start_date),
        "rag_confidence": solution.rag_confidence,
        "completed_at": _iso_date(solution.completed_at),
        "capacity_hours": solution.capacity_hours,
        "created_at": _iso_date(solution.created_at),
        "updated_at": _iso_date(solution.updated_at),
        "deleted_at": _iso_date(solution.deleted_at),
    }


def _subcomponent_detail(sub: Subcomponent) -> Dict[str, Any]:
    return {
        "subcomponent_id": sub.subcomponent_id,
        "project_id": sub.project_id,
        "solution_id": sub.solution_id,
        "subcomponent_name": sub.subcomponent_name,
        "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
        "priority": sub.priority,
        "due_date": _iso_date(sub.due_date),
        "completed_at": _iso_date(sub.completed_at),
        "assignee_user_soeid": sub.assignee_user_soeid,
        "assignee": sub.assignee,
        "estimate_hours": sub.estimate_hours,
        "blocked": sub.blocked,
        "blocker_note": sub.blocker_note,
        "done_criteria": sub.done_criteria,
        "capacity_hours": sub.capacity_hours,
        "created_at": _iso_date(sub.created_at),
        "updated_at": _iso_date(sub.updated_at),
        "deleted_at": _iso_date(sub.deleted_at),
    }


def _dropdown_values() -> Dict[str, List[str]]:
    return {
        "project.status": _enum_values(ProjectStatus),
        "solution.status": _enum_values(SolutionStatus),
        "solution.rag_status": _enum_values(RagStatus),
        "solution.impact_confidence": _enum_values(ConfidenceLevel),
        "subcomponent.status": _enum_values(SubcomponentStatus),
    }


def _schema_context() -> Dict[str, Any]:
    contracts = load_contracts()
    if not contracts:
        return {}

    def _dictionary(contract: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        fields = contract.get("fields", {}) or {}
        required = set(contract.get("required", []) or [])
        return {
            field: {
                "required": field in required,
                "description": str(meta.get("description") or ""),
            }
            for field, meta in fields.items()
        }

    return {key: _dictionary(contract) for key, contract in contracts.items()}


def _truncate_text(text: Optional[str], limit: int = 4000) -> Optional[str]:
    if not text:
        return text
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


_APP_GUIDE_ENV = "SIPM_APP_GUIDE_PATH"
_APP_GUIDE_FILE_CANDIDATES = (
    "assistant-user-guide.md",
    "ai-assistant-user-guide.md",
    "app-user-guide.md",
)
_APP_GUIDE_FALLBACK = """
## App Overview
Jira-lite has three primary navigation groups:
- Build: Deliverables, Planning, Kanban, Calendar, Dashboard
- AI & Docs: Workbench, Structure Studio, AI Assistant
- Admin: Team Capacity, Spaces, Access

Use Build for delivery execution, AI & Docs for drafting and decomposition, and Admin for people, spaces, and access controls.

## Quick Start
1. Choose your active space from the top bar Space switcher.
2. Open Deliverables and create a project.
3. Add one or more solutions under the project.
4. Add subcomponents for solution execution tasks.
5. Use Planning to allocate monthly FTE.
6. Use Kanban and Calendar to track flow and due dates.
7. Use Dashboard for portfolio summaries.

## Roles And Access
- member: everyday project execution
- space_admin: manage members and operational setup within a space
- global_admin: platform-wide access including global admin assignment and space lifecycle control

Global admin is managed from Admin > Access.
""".strip()


def _guide_tokens(text: str) -> List[str]:
    if not text:
        return []
    return [token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) >= 3]


def _find_app_guide_path() -> Optional[Path]:
    explicit = str(os.getenv(_APP_GUIDE_ENV, "")).strip()
    if explicit:
        candidate = Path(explicit)
        if candidate.exists() and candidate.is_file():
            return candidate
    here = Path(__file__).resolve()
    for parent in here.parents:
        docs_dir = parent / "docs"
        if not docs_dir.exists():
            continue
        for filename in _APP_GUIDE_FILE_CANDIDATES:
            candidate = docs_dir / filename
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def _parse_app_guide_sections(markdown: str) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    current_title = "Overview"
    current_lines: List[str] = []
    order = 0
    saw_heading = False

    for raw_line in str(markdown or "").splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            # Skip the single top heading; section headings are read from "##".
            continue
        if line.startswith("## "):
            if saw_heading and any(chunk.strip() for chunk in current_lines):
                sections.append(
                    {
                        "title": current_title.strip(),
                        "content": "\n".join(current_lines).strip(),
                        "order": order,
                    }
                )
                order += 1
            current_title = line[3:].strip() or "Overview"
            current_lines = []
            saw_heading = True
            continue
        current_lines.append(line)

    if any(chunk.strip() for chunk in current_lines):
        sections.append(
            {
                "title": current_title.strip(),
                "content": "\n".join(current_lines).strip(),
                "order": order,
            }
        )

    if sections:
        return sections
    if str(markdown or "").strip():
        return [{"title": "Overview", "content": str(markdown).strip(), "order": 0}]
    return []


@lru_cache(maxsize=1)
def _load_app_guide_payload() -> Dict[str, Any]:
    source_path = _find_app_guide_path()
    if source_path:
        raw_markdown = source_path.read_text(encoding="utf-8")
        source = str(source_path)
    else:
        raw_markdown = _APP_GUIDE_FALLBACK
        source = "embedded_fallback"
    sections = _parse_app_guide_sections(raw_markdown)
    return {
        "source": source,
        "raw_markdown": raw_markdown,
        "sections": sections,
    }


def _score_guide_section(section: Dict[str, Any], phrase: str, tokens: List[str]) -> int:
    title = str(section.get("title") or "").lower()
    content = str(section.get("content") or "").lower()
    score = 0
    if phrase:
        if phrase in title:
            score += 30
        if phrase in content:
            score += 12
    for token in tokens:
        if token in title:
            score += 6
            continue
        if token in content:
            score += 2
    return score


def explain_app_usage(
    question: Optional[str] = None,
    topic: Optional[str] = None,
    max_sections: int = 4,
) -> Dict[str, Any]:
    payload = _load_app_guide_payload()
    sections = list(payload.get("sections") or [])
    if not sections:
        return {
            "mode": "usage_rag_context",
            "query": {
                "question": question or "",
                "topic": topic or "",
                "text": " ".join(part for part in [str(topic or "").strip(), str(question or "").strip()] if part).strip(),
            },
            "retrieval": {
                "strategy": "keyword_overlap_v2",
                "selected_count": 0,
                "total_sections": 0,
            },
            "sections": [],
            "guide_context": "No in-product usage guide is configured yet.",
            "source": payload.get("source") or "unknown",
            "assistant_instruction": (
                "Answer only the user's issue. Keep the response concise and on-topic. "
                "Be explicit about menu/view names and provide a short step-by-step procedure. "
                "Avoid unrelated commentary."
            ),
        }

    merged_query = " ".join(part for part in [str(topic or "").strip(), str(question or "").strip()] if part).strip()
    query_phrase = merged_query.lower()
    query_tokens = _guide_tokens(merged_query)

    try:
        limit = int(max_sections)
    except Exception:
        limit = 4
    limit = max(1, min(limit, 8))

    ranked: List[Dict[str, Any]] = []
    for section in sections:
        ranked.append(
            {
                "section": section,
                "score": _score_guide_section(section, query_phrase, query_tokens),
            }
        )
    ranked.sort(key=lambda item: (int(item.get("score") or 0), -int(item["section"].get("order") or 0)), reverse=True)

    selected = [item for item in ranked if int(item.get("score") or 0) > 0][:limit]
    if not selected:
        selected = ranked[:limit]

    selected_sections: List[Dict[str, Any]] = []
    guide_context_parts: List[str] = []
    for item in selected:
        section = item.get("section") or {}
        title = str(section.get("title") or "Guide").strip()
        content = _truncate_text(str(section.get("content") or "").strip(), limit=12000) or ""
        score = int(item.get("score") or 0)
        selected_sections.append(
            {
                "title": title,
                "content": content,
                "score": score,
                "order": int(section.get("order") or 0),
            }
        )
        if content:
            guide_context_parts.append(f"## {title}\n{content}")

    return {
        "mode": "usage_rag_context",
        "query": {
            "question": question or "",
            "topic": topic or "",
            "text": merged_query,
        },
        "retrieval": {
            "strategy": "keyword_overlap_v2",
            "selected_count": len(selected_sections),
            "total_sections": len(sections),
        },
        "sections": selected_sections,
        "guide_context": "\n\n".join(guide_context_parts).strip(),
        "source": payload.get("source") or "unknown",
        "assistant_instruction": (
            "Use the guide context to answer only the user's how-to question. "
            "Keep the response concise and focused on resolution. "
            "Include concrete menu/view names and actionable steps. "
            "Do not add unrelated commentary."
        ),
    }


_ENUM_MAP = {
    "ProjectStatus": ProjectStatus,
    "SolutionStatus": SolutionStatus,
    "SubcomponentStatus": SubcomponentStatus,
    "RagStatus": RagStatus,
    "ConfidenceLevel": ConfidenceLevel,
}


def _enum_values_by_name(name: Optional[str]) -> List[str]:
    if not name:
        return []
    enum_cls = _ENUM_MAP.get(name)
    if not enum_cls:
        return []
    return _enum_values(enum_cls)


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _space_scoped(query, model, space_id: Optional[str]):
    if not space_id:
        return query
    column = getattr(model, "space_id", None)
    if column is None:
        return query
    return query.filter(column == space_id)


def _space_equals(model, space_id: Optional[str]):
    if not space_id:
        return True
    column = getattr(model, "space_id", None)
    if column is None:
        return True
    return column == space_id


def validate_draft(
    session: Session,
    entity_type: str,
    fields: Dict[str, Any],
    action: str = "create",
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    contract = get_contract(entity_type)
    errors = {
        "missing_required": [],
        "invalid_enum": [],
        "fk_missing": [],
        "other_errors": [],
    }
    if not contract:
        errors["other_errors"].append("missing_contract")
        return {"valid": False, "errors": errors}

    required = contract.get("required", []) if action == "create" else []
    for key in required:
        if fields.get(key) in (None, ""):
            errors["missing_required"].append(key)

    constraints = contract.get("constraints", {}) or {}
    for field, rules in constraints.items():
        if field not in fields:
            continue
        value = fields.get(field)
        if value in (None, ""):
            continue
        enum_name = rules.get("enum")
        if enum_name:
            allowed = _enum_values_by_name(enum_name)
            if str(value) not in allowed:
                errors["invalid_enum"].append(field)

    if entity_type == "solution":
        project_id = fields.get("project_id")
        if project_id:
            exists = (
                _space_scoped(session.query(Project), Project, space_id)
                .filter(Project.project_id == project_id)
                .filter(Project.deleted_at.is_(None))
                .first()
            )
            if not exists:
                errors["fk_missing"].append("project_id")
    if entity_type == "subcomponent":
        project_id = fields.get("project_id")
        solution_id = fields.get("solution_id")
        if project_id:
            exists = (
                _space_scoped(session.query(Project), Project, space_id)
                .filter(Project.project_id == project_id)
                .filter(Project.deleted_at.is_(None))
                .first()
            )
            if not exists:
                errors["fk_missing"].append("project_id")
        if solution_id:
            solution = (
                _space_scoped(session.query(Solution), Solution, space_id)
                .filter(Solution.solution_id == solution_id)
                .filter(Solution.deleted_at.is_(None))
                .first()
            )
            if not solution:
                errors["fk_missing"].append("solution_id")
            elif project_id and solution.project_id != project_id:
                errors["other_errors"].append("solution_project_mismatch")

    valid = not any(errors.values())
    return {"valid": valid, "errors": errors}


def apply_draft(
    session: Session,
    entity_type: str,
    action: str,
    fields: Dict[str, Any],
    entity_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    if action not in {"create", "update"}:
        return {"error": "Invalid action; must be create or update."}
    if not isinstance(fields, dict):
        return {"error": "Invalid fields payload"}

    validation = validate_draft(session, entity_type, fields, action=action, space_id=space_id)
    if not validation.get("valid"):
        return {"error": "Draft failed validation.", "validation": validation}

    entity = None
    if action == "update":
        if entity_type == "project":
            entity = _space_scoped(session.query(Project), Project, space_id).filter(Project.project_id == entity_id).first()
        elif entity_type == "solution":
            entity = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.solution_id == entity_id).first()
        elif entity_type == "subcomponent":
            entity = _space_scoped(session.query(Subcomponent), Subcomponent, space_id).filter(Subcomponent.subcomponent_id == entity_id).first()
        if not entity:
            return {"error": "Entity not found"}

    contract = get_contract(entity_type) or {}
    constraints = contract.get("constraints", {}) or {}
    contract_fields = contract.get("fields", {}) or {}
    allowed_fields = {str(key) for key in contract_fields.keys() if key}
    read_only_fields = {
        str(key) for key, meta in contract_fields.items() if isinstance(meta, dict) and bool(meta.get("read_only"))
    }

    def _apply_common(model, payload: Dict[str, Any]) -> None:
        for key, value in payload.items():
            if allowed_fields and key not in allowed_fields:
                continue
            if key in read_only_fields:
                continue
            if not hasattr(model, key):
                continue
            if value is None or value == "":
                continue
            enum_name = constraints.get(key, {}).get("enum")
            if enum_name:
                enum_cls = _ENUM_MAP.get(enum_name)
                if enum_cls:
                    try:
                        if isinstance(value, enum_cls):
                            setattr(model, key, value)
                        else:
                            setattr(model, key, enum_cls(str(value)))
                    except Exception:
                        continue
                    continue
            if key in {"due_date", "planned_start_date"}:
                parsed = _parse_date(value)
                if parsed is None:
                    continue
                setattr(model, key, parsed)
            elif key in {"completed_at"}:
                parsed = _parse_datetime(value)
                if parsed is None:
                    continue
                setattr(model, key, parsed)
            elif key in {"priority", "capacity_hours", "estimate_hours"}:
                try:
                    setattr(model, key, int(value))
                except Exception:
                    continue
            elif key in {"rag_confidence"}:
                try:
                    setattr(model, key, float(value))
                except Exception:
                    continue
            elif key in {"blocked"}:
                if isinstance(value, bool):
                    setattr(model, key, value)
                else:
                    val = str(value).strip().lower()
                    if val in {"true", "yes", "1"}:
                        setattr(model, key, True)
                    elif val in {"false", "no", "0"}:
                        setattr(model, key, False)
            else:
                setattr(model, key, value)

    if action == "create":
        if entity_type == "project":
            entity = Project(
                space_id=space_id,
                project_name=fields.get("project_name"),
                sponsor=fields.get("sponsor", ""),
            )
        elif entity_type == "solution":
            entity = Solution(
                space_id=space_id,
                project_id=fields.get("project_id"),
                solution_name=fields.get("solution_name"),
                version=fields.get("version") or "0.1.0",
            )
        elif entity_type == "subcomponent":
            entity = Subcomponent(
                space_id=space_id,
                project_id=fields.get("project_id"),
                solution_id=fields.get("solution_id"),
                subcomponent_name=fields.get("subcomponent_name"),
            )
        else:
            return {"error": "Unsupported entity_type"}
        _apply_common(entity, fields)
        session.add(entity)
    else:
        _apply_common(entity, fields)

    entity.updated_at = datetime.now(timezone.utc)
    session.add(entity)
    session.commit()

    if entity_type == "project":
        return {"entity": _project_detail(entity)}
    if entity_type == "solution":
        return {"entity": _solution_detail(entity)}
    return {"entity": _subcomponent_detail(entity)}


def verify_write(
    session: Session,
    entity_type: str,
    entity_id: str,
    expected_fields: Dict[str, Any],
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    if entity_type == "project":
        current = read_project_detail(session, entity_id, space_id=space_id)
    elif entity_type == "solution":
        current = read_solution_detail(session, entity_id, space_id=space_id)
    else:
        current = read_subcomponent_detail(session, entity_id, space_id=space_id)
    detail = current.get(entity_type) if isinstance(current, dict) else None
    if not isinstance(detail, dict):
        detail = current
    diff: Dict[str, Any] = {}
    for key, expected in expected_fields.items():
        actual = detail.get(key) if isinstance(detail, dict) else None
        if actual != expected:
            diff[key] = {"expected": expected, "actual": actual}
    return {"verified": len(diff) == 0, "diff": diff, "current": detail}


def read_entity_index(
    session: Session,
    entity_type: str,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = 200,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    max_rows = max(1, int(limit))
    if entity_type == "project":
        rows = (
            _space_scoped(session.query(Project), Project, space_id)
            .filter(Project.deleted_at.is_(None))
            .order_by(Project.project_name.asc())
            .limit(max_rows)
            .all()
        )
        return {
            "projects": [
                {
                    "project_id": row.project_id,
                    "project_name": row.project_name,
                    "status": row.status.value if hasattr(row.status, "value") else row.status,
                }
                for row in rows
            ]
        }
    if entity_type == "solution":
        query = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.deleted_at.is_(None))
        if project_id:
            query = query.filter(Solution.project_id == project_id)
        rows = query.order_by(Solution.solution_name.asc()).limit(max_rows).all()
        return {
            "solutions": [
                {
                    "solution_id": row.solution_id,
                    "solution_name": row.solution_name,
                    "status": row.status.value if hasattr(row.status, "value") else row.status,
                    "project_id": row.project_id,
                }
                for row in rows
            ]
        }
    if entity_type == "subcomponent":
        query = _space_scoped(session.query(Subcomponent), Subcomponent, space_id).filter(Subcomponent.deleted_at.is_(None))
        if solution_id:
            query = query.filter(Subcomponent.solution_id == solution_id)
        if project_id:
            query = query.filter(Subcomponent.project_id == project_id)
        rows = query.order_by(Subcomponent.subcomponent_name.asc()).limit(max_rows).all()
        return {
            "subcomponents": [
                {
                    "subcomponent_id": row.subcomponent_id,
                    "subcomponent_name": row.subcomponent_name,
                    "status": row.status.value if hasattr(row.status, "value") else row.status,
                    "solution_id": row.solution_id,
                    "project_id": row.project_id,
                }
                for row in rows
            ]
        }
    return {"error": "Invalid entity_type"}


def read_entity_deltas(
    session: Session,
    entity_type: str,
    since: Optional[str] = None,
    limit: int = 200,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not since:
        return {"deltas": []}
    try:
        since_dt = datetime.fromisoformat(str(since))
    except Exception:
        return {"error": "Invalid since timestamp"}

    max_rows = max(1, int(limit))
    if entity_type == "project":
        rows = (
            _space_scoped(session.query(Project), Project, space_id)
            .filter(Project.updated_at > since_dt)
            .filter(Project.deleted_at.is_(None))
            .order_by(Project.updated_at.desc())
            .limit(max_rows)
            .all()
        )
        return {"deltas": [_project_detail(row) for row in rows]}
    if entity_type == "solution":
        rows = (
            _space_scoped(session.query(Solution), Solution, space_id)
            .filter(Solution.updated_at > since_dt)
            .filter(Solution.deleted_at.is_(None))
            .order_by(Solution.updated_at.desc())
            .limit(max_rows)
            .all()
        )
        return {"deltas": [_solution_detail(row) for row in rows]}
    if entity_type == "subcomponent":
        rows = (
            _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
            .filter(Subcomponent.updated_at > since_dt)
            .filter(Subcomponent.deleted_at.is_(None))
            .order_by(Subcomponent.updated_at.desc())
            .limit(max_rows)
            .all()
        )
        return {"deltas": [_subcomponent_detail(row) for row in rows]}
    return {"error": "Invalid entity_type"}


def _sow_context(doc: SOWDocument) -> Dict[str, Any]:
    return {
        "sow_id": doc.sow_id,
        "project_id": doc.project_id,
        "solution_id": doc.solution_id,
        "content": _truncate_text(doc.content),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def _sow_detail(doc: SOWDocument) -> Dict[str, Any]:
    return {
        "sow_id": doc.sow_id,
        "project_id": doc.project_id,
        "solution_id": doc.solution_id,
        "content": doc.content,
        "created_at": _iso_date(doc.created_at),
        "updated_at": _iso_date(doc.updated_at),
        "deleted_at": _iso_date(doc.deleted_at),
        "created_by_user_id": doc.created_by_user_id,
    }


def _charter_detail(entry: ProjectCharter) -> Dict[str, Any]:
    return {
        "charter_id": entry.charter_id,
        "project_id": entry.project_id,
        "title": entry.title,
        "content": entry.content,
        "created_by_user_id": entry.created_by_user_id,
        "created_at": _iso_date(entry.created_at),
        "updated_at": _iso_date(entry.updated_at),
        "deleted_at": _iso_date(entry.deleted_at),
    }


def _plan_detail(entry: ProjectPlan) -> Dict[str, Any]:
    return {
        "plan_id": entry.plan_id,
        "project_id": entry.project_id,
        "title": entry.title,
        "content": entry.content,
        "created_by_user_id": entry.created_by_user_id,
        "created_at": _iso_date(entry.created_at),
        "updated_at": _iso_date(entry.updated_at),
        "deleted_at": _iso_date(entry.deleted_at),
    }


def _decision_detail(entry: ProjectDecisionLog) -> Dict[str, Any]:
    return {
        "decision_id": entry.decision_id,
        "project_id": entry.project_id,
        "title": entry.title,
        "decision": entry.decision,
        "rationale": entry.rationale,
        "impact": entry.impact,
        "created_by_user_id": entry.created_by_user_id,
        "created_at": _iso_date(entry.created_at),
        "updated_at": _iso_date(entry.updated_at),
        "deleted_at": _iso_date(entry.deleted_at),
    }


def _checklist_detail(entry: ChecklistItem) -> Dict[str, Any]:
    return {
        "checklist_id": entry.checklist_id,
        "project_id": entry.project_id,
        "month_key": entry.month_key,
        "title": entry.title,
        "status": entry.status,
        "created_by_user_id": entry.created_by_user_id,
        "created_at": _iso_date(entry.created_at),
        "updated_at": _iso_date(entry.updated_at),
        "deleted_at": _iso_date(entry.deleted_at),
    }


def read_context(
    session: Session,
    entity_type: Optional[str],
    entity_id: Optional[str],
    project_id: Optional[str],
    history_limit: int = 50,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "dropdowns": _dropdown_values(),
        "schema": _schema_context(),
        "contracts": contract_hints(),
    }

    project: Optional[Project] = None
    if project_id:
        project = _space_scoped(session.query(Project), Project, space_id).filter(Project.project_id == project_id).first()
    if entity_type == "project" and entity_id:
        project = _space_scoped(session.query(Project), Project, space_id).filter(Project.project_id == entity_id).first()

    if entity_type == "solution" and entity_id:
        solution = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.solution_id == entity_id).first()
        if solution:
            project = _space_scoped(session.query(Project), Project, space_id).filter(Project.project_id == solution.project_id).first()
            context["solution"] = _solution_context(solution)
            subcomponents = (
                _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
                .filter(Subcomponent.solution_id == solution.solution_id)
                .filter(Subcomponent.deleted_at.is_(None))
                .all()
            )
            context["subcomponents"] = [_subcomponent_context(sc) for sc in subcomponents]
    elif entity_type == "subcomponent" and entity_id:
        sub = _space_scoped(session.query(Subcomponent), Subcomponent, space_id).filter(Subcomponent.subcomponent_id == entity_id).first()
        if sub:
            project = _space_scoped(session.query(Project), Project, space_id).filter(Project.project_id == sub.project_id).first()
            solution = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.solution_id == sub.solution_id).first()
            context["subcomponent"] = _subcomponent_context(sub)
            if solution:
                context["solution"] = _solution_context(solution)
    if project:
        context["project"] = _project_context(project)
        solutions = (
            _space_scoped(session.query(Solution), Solution, space_id)
            .filter(Solution.project_id == project.project_id)
            .filter(Solution.deleted_at.is_(None))
            .all()
        )
        subcomponents = (
            _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
            .filter(Subcomponent.project_id == project.project_id)
            .filter(Subcomponent.deleted_at.is_(None))
            .all()
        )
        context.setdefault("solutions", [_solution_context(s) for s in solutions])
        context.setdefault("subcomponents", [_subcomponent_context(sc) for sc in subcomponents])

        latest_charter = (
            _space_scoped(session.query(ProjectCharter), ProjectCharter, space_id)
            .filter(ProjectCharter.project_id == project.project_id)
            .filter(ProjectCharter.deleted_at.is_(None))
            .order_by(ProjectCharter.created_at.desc())
            .first()
        )
        latest_plan = (
            _space_scoped(session.query(ProjectPlan), ProjectPlan, space_id)
            .filter(ProjectPlan.project_id == project.project_id)
            .filter(ProjectPlan.deleted_at.is_(None))
            .order_by(ProjectPlan.created_at.desc())
            .first()
        )
        latest_decision = (
            _space_scoped(session.query(ProjectDecisionLog), ProjectDecisionLog, space_id)
            .filter(ProjectDecisionLog.project_id == project.project_id)
            .filter(ProjectDecisionLog.deleted_at.is_(None))
            .order_by(ProjectDecisionLog.created_at.desc())
            .first()
        )
        if latest_charter:
            context["project_charter"] = {
                "title": latest_charter.title,
                "content": latest_charter.content,
                "created_at": latest_charter.created_at.isoformat() if latest_charter.created_at else None,
            }
        if latest_plan:
            context["project_plan"] = {
                "title": latest_plan.title,
                "content": latest_plan.content,
                "created_at": latest_plan.created_at.isoformat() if latest_plan.created_at else None,
            }
        if latest_decision:
            context["project_decision_log"] = {
                "title": latest_decision.title,
                "decision": latest_decision.decision,
                "rationale": latest_decision.rationale,
                "impact": latest_decision.impact,
                "created_at": latest_decision.created_at.isoformat() if latest_decision.created_at else None,
            }

        project_sows = (
            _space_scoped(session.query(SOWDocument), SOWDocument, space_id)
            .filter(SOWDocument.project_id == project.project_id)
            .filter(SOWDocument.deleted_at.is_(None))
            .order_by(SOWDocument.created_at.desc())
            .limit(3)
            .all()
        )
        if project_sows:
            context["sow_documents"] = [_sow_context(doc) for doc in project_sows]
            context["latest_sow"] = context["sow_documents"][0]

    if context.get("solution"):
        solution_id = context["solution"].get("solution_id")
        if solution_id:
            solution_sows = (
                _space_scoped(session.query(SOWDocument), SOWDocument, space_id)
                .filter(SOWDocument.solution_id == solution_id)
                .filter(SOWDocument.deleted_at.is_(None))
                .order_by(SOWDocument.created_at.desc())
                .limit(3)
                .all()
            )
            if solution_sows:
                context["solution_sow_documents"] = [_sow_context(doc) for doc in solution_sows]

    return context


def read_project_detail(session: Session, project_id: str, space_id: Optional[str] = None) -> Dict[str, Any]:
    project = (
        _space_scoped(session.query(Project), Project, space_id)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        return {"error": "Project not found"}

    solutions = (
        _space_scoped(session.query(Solution), Solution, space_id)
        .filter(Solution.project_id == project.project_id)
        .filter(Solution.deleted_at.is_(None))
        .all()
    )
    subcomponents = (
        _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
        .filter(Subcomponent.project_id == project.project_id)
        .filter(Subcomponent.deleted_at.is_(None))
        .all()
    )
    charters = (
        _space_scoped(session.query(ProjectCharter), ProjectCharter, space_id)
        .filter(ProjectCharter.project_id == project.project_id)
        .filter(ProjectCharter.deleted_at.is_(None))
        .order_by(ProjectCharter.created_at.desc())
        .all()
    )
    plans = (
        _space_scoped(session.query(ProjectPlan), ProjectPlan, space_id)
        .filter(ProjectPlan.project_id == project.project_id)
        .filter(ProjectPlan.deleted_at.is_(None))
        .order_by(ProjectPlan.created_at.desc())
        .all()
    )
    decisions = (
        _space_scoped(session.query(ProjectDecisionLog), ProjectDecisionLog, space_id)
        .filter(ProjectDecisionLog.project_id == project.project_id)
        .filter(ProjectDecisionLog.deleted_at.is_(None))
        .order_by(ProjectDecisionLog.created_at.desc())
        .all()
    )
    sows = (
        _space_scoped(session.query(SOWDocument), SOWDocument, space_id)
        .filter(SOWDocument.project_id == project.project_id)
        .filter(SOWDocument.deleted_at.is_(None))
        .order_by(SOWDocument.created_at.desc())
        .all()
    )
    checklists = (
        _space_scoped(session.query(ChecklistItem), ChecklistItem, space_id)
        .filter(ChecklistItem.project_id == project.project_id)
        .filter(ChecklistItem.deleted_at.is_(None))
        .order_by(ChecklistItem.created_at.desc())
        .all()
    )

    return {
        "project_detail": _project_detail(project),
        "solutions_detail": [_solution_detail(s) for s in solutions],
        "subcomponents_detail": [_subcomponent_detail(sc) for sc in subcomponents],
        "project_charters": [_charter_detail(c) for c in charters],
        "project_plans": [_plan_detail(p) for p in plans],
        "project_decision_logs": [_decision_detail(d) for d in decisions],
        "sow_documents": [_sow_detail(s) for s in sows],
        "checklists": [_checklist_detail(c) for c in checklists],
    }


def read_solution_detail(session: Session, solution_id: str, space_id: Optional[str] = None) -> Dict[str, Any]:
    solution = (
        _space_scoped(session.query(Solution), Solution, space_id)
        .filter(Solution.solution_id == solution_id)
        .filter(Solution.deleted_at.is_(None))
        .first()
    )
    if not solution:
        return {"error": "Solution not found"}

    project = (
        _space_scoped(session.query(Project), Project, space_id)
        .filter(Project.project_id == solution.project_id)
        .filter(Project.deleted_at.is_(None))
        .first()
    )
    subcomponents = (
        _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
        .filter(Subcomponent.solution_id == solution.solution_id)
        .filter(Subcomponent.deleted_at.is_(None))
        .all()
    )
    sows = (
        _space_scoped(session.query(SOWDocument), SOWDocument, space_id)
        .filter(SOWDocument.solution_id == solution.solution_id)
        .filter(SOWDocument.deleted_at.is_(None))
        .order_by(SOWDocument.created_at.desc())
        .all()
    )
    solution_phases = (
        session.query(SolutionPhase)
        .filter(SolutionPhase.solution_id == solution.solution_id)
        .all()
    )

    return {
        "solution_detail": _solution_detail(solution),
        "project_detail": _project_detail(project) if project else None,
        "subcomponents_detail": [_subcomponent_detail(sc) for sc in subcomponents],
        "solution_sow_documents": [_sow_detail(s) for s in sows],
        "solution_phases": [
            {
                "solution_phase_id": sp.solution_phase_id,
                "solution_id": sp.solution_id,
                "phase_id": sp.phase_id,
                "is_enabled": sp.is_enabled,
                "sequence_override": sp.sequence_override,
                "created_at": _iso_date(sp.created_at),
                "updated_at": _iso_date(sp.updated_at),
            }
            for sp in solution_phases
        ],
    }


def read_subcomponent_detail(session: Session, subcomponent_id: str, space_id: Optional[str] = None) -> Dict[str, Any]:
    sub = (
        _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
        .filter(Subcomponent.subcomponent_id == subcomponent_id)
        .filter(Subcomponent.deleted_at.is_(None))
        .first()
    )
    if not sub:
        return {"error": "Subcomponent not found"}
    solution = (
        _space_scoped(session.query(Solution), Solution, space_id)
        .filter(Solution.solution_id == sub.solution_id)
        .filter(Solution.deleted_at.is_(None))
        .first()
    )
    project = (
        _space_scoped(session.query(Project), Project, space_id)
        .filter(Project.project_id == sub.project_id)
        .filter(Project.deleted_at.is_(None))
        .first()
    )
    return {
        "subcomponent_detail": _subcomponent_detail(sub),
        "solution_detail": _solution_detail(solution) if solution else None,
        "project_detail": _project_detail(project) if project else None,
    }


def read_sow_document(session: Session, sow_id: str, space_id: Optional[str] = None) -> Dict[str, Any]:
    doc = (
        _space_scoped(session.query(SOWDocument), SOWDocument, space_id)
        .filter(SOWDocument.sow_id == sow_id)
        .filter(SOWDocument.deleted_at.is_(None))
        .first()
    )
    if not doc:
        return {"error": "SOW document not found"}
    return _sow_detail(doc)


def read_artifacts_detail(session: Session, project_id: str, space_id: Optional[str] = None) -> Dict[str, Any]:
    charters = (
        _space_scoped(session.query(ProjectCharter), ProjectCharter, space_id)
        .filter(ProjectCharter.project_id == project_id)
        .filter(ProjectCharter.deleted_at.is_(None))
        .order_by(ProjectCharter.created_at.desc())
        .all()
    )
    plans = (
        _space_scoped(session.query(ProjectPlan), ProjectPlan, space_id)
        .filter(ProjectPlan.project_id == project_id)
        .filter(ProjectPlan.deleted_at.is_(None))
        .order_by(ProjectPlan.created_at.desc())
        .all()
    )
    decisions = (
        _space_scoped(session.query(ProjectDecisionLog), ProjectDecisionLog, space_id)
        .filter(ProjectDecisionLog.project_id == project_id)
        .filter(ProjectDecisionLog.deleted_at.is_(None))
        .order_by(ProjectDecisionLog.created_at.desc())
        .all()
    )
    return {
        "project_charters": [_charter_detail(c) for c in charters],
        "project_plans": [_plan_detail(p) for p in plans],
        "project_decision_logs": [_decision_detail(d) for d in decisions],
    }


def read_context_complete(
    session: Session,
    entity_type: Optional[str],
    entity_id: Optional[str],
    project_id: Optional[str],
    history_limit: int = 200,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    phases = session.query(Phase).order_by(Phase.sequence).all()
    phase_list = [
        {"phase_id": phase.phase_id, "phase_name": phase.phase_name, "phase_group": phase.phase_group}
        for phase in phases
    ]
    context: Dict[str, Any] = {
        "context_mode": "complete",
        "phases": phase_list,
        "dropdowns": _dropdown_values(),
        "schema": _schema_context(),
        "contracts": contract_hints(),
    }

    if entity_type == "project" and entity_id:
        project_id = entity_id
    if entity_type == "solution" and entity_id:
        detail = read_solution_detail(session, entity_id, space_id=space_id)
        if detail.get("error"):
            context.setdefault("errors", []).append(detail.get("error"))
        else:
            context.update(detail)
            project_id = detail.get("solution_detail", {}).get("project_id")
    if entity_type == "subcomponent" and entity_id:
        detail = read_subcomponent_detail(session, entity_id, space_id=space_id)
        if detail.get("error"):
            context.setdefault("errors", []).append(detail.get("error"))
        else:
            context.update(detail)
            project_id = detail.get("subcomponent_detail", {}).get("project_id")

    if project_id:
        project_detail = read_project_detail(session, project_id, space_id=space_id)
        if project_detail.get("error"):
            context.setdefault("errors", []).append(project_detail.get("error"))
        else:
            context.update(project_detail)

    return context


def read_external_doc(session: Session, document_id: str, space_id: Optional[str] = None) -> Dict[str, Any]:
    doc = _space_scoped(session.query(ExternalDocument), ExternalDocument, space_id).filter(
        ExternalDocument.document_id == document_id
    ).first()
    if not doc:
        return {"error": "Document not found"}
    try:
        with open(doc.storage_path, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1", errors="ignore")
    except Exception as exc:
        return {"error": f"Failed to read document: {exc}"}
    return {
        "document_id": doc.document_id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "content": text,
    }


_SEARCH_ENTITY_NOISE_TOKENS = {
    "a",
    "an",
    "the",
    "for",
    "to",
    "in",
    "on",
    "of",
    "please",
    "use",
    "using",
    "show",
    "find",
    "open",
    "select",
    "choose",
    "pick",
    "switch",
    "set",
    "me",
    "my",
    "project",
    "projects",
    "solution",
    "solutions",
    "subcomponent",
    "subcomponents",
    "task",
    "tasks",
}


def _search_tokens(query: str) -> List[str]:
    raw = re.sub(r"[^A-Za-z0-9]+", " ", (query or "").lower()).strip()
    if not raw:
        return []
    return [token for token in raw.split() if token and token not in _SEARCH_ENTITY_NOISE_TOKENS]


def _apply_token_filters(base_query, column, tokens: List[str]):
    filtered = base_query
    for token in tokens:
        filtered = filtered.filter(func.lower(column).like(f"%{token}%"))
    return filtered


def search_entities(
    session: Session,
    query: str,
    entity_types: Optional[List[str]] = None,
    limit: int = 5,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    return_mode: str = "ids",
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    response_format: str = "packed",
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    clean = (query or "").strip()
    if not clean:
        return {"results": []}
    normalized = re.sub(r"\b(projects?|solutions?|subcomponents?|tasks?)\b", "", clean, flags=re.IGNORECASE).strip()
    if normalized:
        clean = normalized
    tokens = _search_tokens(clean)
    max_results = _safe_int(limit, default=5, minimum=1, maximum=200)
    if max_results <= 0:
        return {"results": []}
    raw_types = entity_types
    if isinstance(raw_types, str):
        raw_types = [raw_types]
    types = {_normalize_entity_type(t) for t in (raw_types or []) if t}
    if not types:
        types = {"project", "solution", "subcomponent"}
    per_type_limit = max(1, max_results // max(len(types), 1))
    pattern = f"%{clean.lower()}%"
    results: List[Dict[str, Any]] = []

    if "project" in types:
        base_query = (
            _space_scoped(session.query(Project), Project, space_id)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.project_id == project_id if project_id else True)
            .order_by(Project.project_name.asc())
        )
        token_rows = (
            _apply_token_filters(base_query, Project.project_name, tokens).limit(per_type_limit).all() if tokens else []
        )
        rows = token_rows
        if not rows:
            rows = base_query.filter(func.lower(Project.project_name).like(pattern)).limit(per_type_limit).all()
        for project in rows:
            results.append(
                {
                    "entity_type": "project",
                    "entity_id": project.project_id,
                    "label": project.project_name,
                    "project_id": project.project_id,
                }
            )

    if "solution" in types:
        base_query = (
            _space_scoped(session.query(Solution), Solution, space_id)
            .filter(Solution.deleted_at.is_(None))
            .filter(Solution.project_id == project_id if project_id else True)
            .filter(Solution.solution_id == solution_id if solution_id else True)
            .order_by(Solution.solution_name.asc())
        )
        token_rows = (
            _apply_token_filters(base_query, Solution.solution_name, tokens).limit(per_type_limit).all()
            if tokens
            else []
        )
        rows = token_rows
        if not rows:
            rows = base_query.filter(func.lower(Solution.solution_name).like(pattern)).limit(per_type_limit).all()
        for solution in rows:
            results.append(
                {
                    "entity_type": "solution",
                    "entity_id": solution.solution_id,
                    "label": solution.solution_name,
                    "project_id": solution.project_id,
                }
            )

    if "subcomponent" in types:
        base_query = (
            _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
            .filter(Subcomponent.deleted_at.is_(None))
            .filter(Subcomponent.project_id == project_id if project_id else True)
            .filter(Subcomponent.solution_id == solution_id if solution_id else True)
            .order_by(Subcomponent.subcomponent_name.asc())
        )
        token_rows = (
            _apply_token_filters(base_query, Subcomponent.subcomponent_name, tokens).limit(per_type_limit).all()
            if tokens
            else []
        )
        rows = token_rows
        if not rows:
            rows = (
                base_query.filter(func.lower(Subcomponent.subcomponent_name).like(pattern)).limit(per_type_limit).all()
            )
        for sub in rows:
            results.append(
                {
                    "entity_type": "subcomponent",
                    "entity_id": sub.subcomponent_id,
                    "label": sub.subcomponent_name,
                    "project_id": sub.project_id,
                    "solution_id": sub.solution_id,
                }
            )

    results = results[:max_results]
    mode = (return_mode or "ids").strip().lower()
    if mode in {"ids", "index"}:
        return {"mode": "ids", "results": results}

    if mode in {"cards", "card"}:
        enriched: List[Dict[str, Any]] = []
        for row in results:
            etype = row.get("entity_type")
            entity_id = row.get("entity_id")
            if etype == "project":
                card_resp = get_project_card(
                    session,
                    entity_id,
                    space_id=space_id,
                    fields=fields,
                    field_pack=field_pack,
                    question=clean,
                    response_format="objects" if response_format != "packed" else "packed",
                )
            elif etype == "solution":
                card_resp = get_solution_card(
                    session,
                    entity_id,
                    space_id=space_id,
                    fields=fields,
                    field_pack=field_pack,
                    question=clean,
                    response_format="objects" if response_format != "packed" else "packed",
                )
            else:
                card_resp = get_task_card(
                    session,
                    entity_id,
                    space_id=space_id,
                    fields=fields,
                    field_pack=field_pack,
                    question=clean,
                    response_format="objects" if response_format != "packed" else "packed",
                )
            enriched.append({**row, "card": card_resp.get("card")})
        return {"mode": "cards", "results": enriched}

    if mode in {"fields", "detail_fields"}:
        enriched = []
        for row in results:
            etype = row.get("entity_type")
            entity_id = row.get("entity_id")
            detail = get_entity_fields(
                session,
                etype,
                entity_id,
                space_id=space_id,
                fields=fields,
                field_pack=field_pack,
                question=clean,
            )
            enriched.append({**row, "data": detail.get("data"), "fields": detail.get("fields")})
        return {"mode": "fields", "results": enriched}

    return {"mode": "ids", "results": results}


def list_projects(session: Session, limit: int = 200, space_id: Optional[str] = None) -> Dict[str, Any]:
    max_rows = max(1, int(limit))
    rows = (
        _space_scoped(session.query(Project), Project, space_id)
        .filter(Project.deleted_at.is_(None))
        .order_by(Project.project_name.asc())
        .limit(max_rows)
        .all()
    )
    return {
        "projects": [
            {
                "project_id": row.project_id,
                "project_name": row.project_name,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
            }
            for row in rows
        ]
    }


def list_solutions_for_project(
    session: Session,
    project_id: str,
    limit: int = 200,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    max_rows = max(1, int(limit))
    rows = (
        _space_scoped(session.query(Solution), Solution, space_id)
        .filter(Solution.project_id == project_id)
        .filter(Solution.deleted_at.is_(None))
        .order_by(Solution.solution_name.asc())
        .limit(max_rows)
        .all()
    )
    return {
        "solutions": [
            {
                "solution_id": row.solution_id,
                "solution_name": row.solution_name,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
                "project_id": row.project_id,
            }
            for row in rows
        ]
    }


_CARD_LIMIT_DEFAULT = 50
_CARD_LIMIT_MAX = 200
_MAX_FIELD_COUNT = 24
_CARD_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_CARD_CACHE_LOCK = threading.Lock()

_PROJECT_STATUS_CODES = {
    "not_started": 0,
    "active": 1,
    "on_hold": 2,
    "complete": 3,
    "abandoned": 4,
}
_SOLUTION_STATUS_CODES = dict(_PROJECT_STATUS_CODES)
_TASK_STATUS_CODES = {
    "to_do": 0,
    "in_progress": 1,
    "on_hold": 2,
    "complete": 3,
    "abandoned": 4,
}
_RAG_STATUS_CODES = {"green": 0, "yellow": 1, "red": 2}

_PROJECT_CARD_FIELD_PACKS: Dict[str, List[str]] = {
    "minimal": ["project_id", "project_name", "status", "last_updated"],
    "default": [
        "project_id",
        "project_name",
        "status",
        "priority",
        "sponsor",
        "open_solution_count",
        "open_task_count",
        "last_updated",
        "short_summary",
    ],
    "risk": ["project_id", "project_name", "status", "top_risks", "open_task_count", "last_updated"],
    "ownership": ["project_id", "project_name", "status", "sponsor", "priority", "last_updated"],
    "schedule": [
        "project_id",
        "project_name",
        "status",
        "open_solution_count",
        "open_task_count",
        "last_updated",
    ],
}
_SOLUTION_CARD_FIELD_PACKS: Dict[str, List[str]] = {
    "minimal": ["solution_id", "solution_name", "status", "last_updated"],
    "default": [
        "solution_id",
        "project_id",
        "solution_name",
        "status",
        "rag_status",
        "priority",
        "current_phase",
        "due_date",
        "owner",
        "open_task_count",
        "blocked_task_count",
        "last_updated",
        "short_summary",
    ],
    "risk": [
        "solution_id",
        "project_id",
        "solution_name",
        "status",
        "rag_status",
        "blocked_task_count",
        "top_risks",
        "last_updated",
    ],
    "ownership": ["solution_id", "project_id", "solution_name", "status", "owner", "assignee", "last_updated"],
    "schedule": [
        "solution_id",
        "project_id",
        "solution_name",
        "status",
        "current_phase",
        "due_date",
        "open_task_count",
        "last_updated",
    ],
}
_TASK_CARD_FIELD_PACKS: Dict[str, List[str]] = {
    "minimal": ["subcomponent_id", "subcomponent_name", "status", "last_updated"],
    "default": [
        "subcomponent_id",
        "project_id",
        "solution_id",
        "subcomponent_name",
        "status",
        "priority",
        "assignee",
        "due_date",
        "blocked",
        "estimate_hours",
        "last_updated",
        "short_summary",
    ],
    "risk": [
        "subcomponent_id",
        "solution_id",
        "subcomponent_name",
        "status",
        "blocked",
        "blocker_note",
        "last_updated",
    ],
    "ownership": ["subcomponent_id", "solution_id", "subcomponent_name", "status", "assignee", "last_updated"],
    "schedule": [
        "subcomponent_id",
        "solution_id",
        "subcomponent_name",
        "status",
        "due_date",
        "estimate_hours",
        "last_updated",
    ],
}

_PROJECT_CARD_ALIASES = {
    "project_id": "pid",
    "project_name": "nm",
    "status": "st",
    "priority": "pri",
    "sponsor": "own",
    "open_solution_count": "osc",
    "open_task_count": "otc",
    "top_risks": "rsk",
    "last_updated": "upd",
    "short_summary": "sum",
}
_SOLUTION_CARD_ALIASES = {
    "solution_id": "sid",
    "project_id": "pid",
    "solution_name": "nm",
    "status": "st",
    "rag_status": "rag",
    "priority": "pri",
    "current_phase": "ph",
    "due_date": "due",
    "owner": "own",
    "assignee": "asg",
    "open_task_count": "otc",
    "blocked_task_count": "btc",
    "top_risks": "rsk",
    "last_updated": "upd",
    "short_summary": "sum",
}
_TASK_CARD_ALIASES = {
    "subcomponent_id": "tid",
    "project_id": "pid",
    "solution_id": "sid",
    "subcomponent_name": "nm",
    "status": "st",
    "priority": "pri",
    "assignee": "asg",
    "due_date": "due",
    "blocked": "blk",
    "blocker_note": "blk_note",
    "estimate_hours": "est",
    "last_updated": "upd",
    "short_summary": "sum",
}

_ENTITY_FIELD_ALLOWLIST: Dict[str, set[str]] = {
    "project": set(
        [
            "project_id",
            "project_name",
            "status",
            "description",
            "success_criteria",
            "sponsor",
            "sponsor_user_soeid",
            "strategic_objective",
            "priority",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
    ),
    "solution": set(
        [
            "solution_id",
            "project_id",
            "solution_name",
            "version",
            "status",
            "rag_status",
            "rag_reason",
            "priority",
            "due_date",
            "current_phase",
            "description",
            "success_criteria",
            "problem_statement",
            "owner",
            "owner_user_soeid",
            "assignee",
            "assignee_user_soeid",
            "approver",
            "approver_user_soeid",
            "key_stakeholder",
            "blockers",
            "risks",
            "impact_confidence",
            "planned_start_date",
            "rag_confidence",
            "completed_at",
            "capacity_hours",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
    ),
    "subcomponent": set(
        [
            "subcomponent_id",
            "project_id",
            "solution_id",
            "subcomponent_name",
            "status",
            "priority",
            "due_date",
            "completed_at",
            "assignee_user_soeid",
            "assignee",
            "estimate_hours",
            "blocked",
            "blocker_note",
            "done_criteria",
            "capacity_hours",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
    ),
}
_DETAIL_FIELD_PACKS: Dict[str, Dict[str, List[str]]] = {
    "project": {
        "minimal": ["project_id", "project_name", "status", "priority", "updated_at"],
        "default": [
            "project_id",
            "project_name",
            "status",
            "priority",
            "sponsor",
            "description",
            "success_criteria",
            "updated_at",
        ],
        "risk": ["project_id", "project_name", "status", "description", "updated_at"],
        "schedule": ["project_id", "project_name", "status", "priority", "updated_at"],
        "ownership": ["project_id", "project_name", "status", "sponsor", "sponsor_user_soeid", "updated_at"],
    },
    "solution": {
        "minimal": ["solution_id", "solution_name", "status", "updated_at"],
        "default": [
            "solution_id",
            "project_id",
            "solution_name",
            "status",
            "rag_status",
            "priority",
            "due_date",
            "current_phase",
            "owner",
            "assignee",
            "blockers",
            "risks",
            "updated_at",
        ],
        "risk": ["solution_id", "solution_name", "status", "rag_status", "blockers", "risks", "updated_at"],
        "schedule": ["solution_id", "solution_name", "status", "due_date", "current_phase", "updated_at"],
        "ownership": ["solution_id", "solution_name", "status", "owner", "assignee", "updated_at"],
    },
    "subcomponent": {
        "minimal": ["subcomponent_id", "subcomponent_name", "status", "updated_at"],
        "default": [
            "subcomponent_id",
            "project_id",
            "solution_id",
            "subcomponent_name",
            "status",
            "priority",
            "due_date",
            "assignee",
            "blocked",
            "blocker_note",
            "estimate_hours",
            "updated_at",
        ],
        "risk": ["subcomponent_id", "subcomponent_name", "status", "blocked", "blocker_note", "updated_at"],
        "schedule": ["subcomponent_id", "subcomponent_name", "status", "due_date", "estimate_hours", "updated_at"],
        "ownership": ["subcomponent_id", "subcomponent_name", "status", "assignee", "updated_at"],
    },
}


def _safe_int(value: Any, default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
    try:
        num = int(value)
    except Exception:
        num = int(default)
    num = max(minimum, num)
    if maximum is not None:
        num = min(maximum, num)
    return num


def _status_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _normalize_entity_type(entity_type: Optional[str]) -> str:
    raw = (entity_type or "").strip().lower()
    if raw in {"task", "tasks"}:
        return "subcomponent"
    if raw in {"subcomponents"}:
        return "subcomponent"
    if raw in {"projects"}:
        return "project"
    if raw in {"solutions"}:
        return "solution"
    return raw


def _card_cache_ttl_seconds() -> int:
    return _safe_int(os.getenv("AI_TOOL_CACHE_TTL_SECONDS", "0"), default=0, minimum=0, maximum=3600)


def _cache_key(
    tool_name: str,
    payload: Dict[str, Any],
    etag: Optional[str],
) -> str:
    raw = json.dumps(
        {
            "tool": tool_name,
            "etag": etag or "",
            "payload": payload,
        },
        sort_keys=True,
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    ttl = _card_cache_ttl_seconds()
    if ttl <= 0:
        return None
    now_ts = datetime.now(timezone.utc).timestamp()
    with _CARD_CACHE_LOCK:
        entry = _CARD_CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at <= now_ts:
            _CARD_CACHE.pop(key, None)
            return None
        cached = copy.deepcopy(value)
        if isinstance(cached, dict):
            cached["cache_hit"] = True
        return cached


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    ttl = _card_cache_ttl_seconds()
    if ttl <= 0:
        return
    expires_at = datetime.now(timezone.utc).timestamp() + ttl
    with _CARD_CACHE_LOCK:
        if len(_CARD_CACHE) >= 2000:
            # Opportunistically prune oldest few keys by expiry timestamp.
            for dead_key, _ in sorted(_CARD_CACHE.items(), key=lambda kv: kv[1][0])[:200]:
                _CARD_CACHE.pop(dead_key, None)
        _CARD_CACHE[key] = (expires_at, copy.deepcopy(value))


def _short_text(value: Optional[str], limit: int = 160) -> str:
    if not value:
        return ""
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _risk_list(value: Optional[str], max_items: int = 2) -> List[str]:
    if not value:
        return []
    chunks = []
    for segment in re.split(r"[;\n]+", str(value)):
        cleaned = _short_text(segment.strip(), limit=120)
        if cleaned:
            chunks.append(cleaned)
        if len(chunks) >= max_items:
            break
    return chunks


def _decode_offset_cursor(cursor: Optional[str]) -> int:
    if not cursor:
        return 0
    return _safe_int(cursor, default=0, minimum=0, maximum=1_000_000)


def _encode_offset_cursor(offset: int) -> Optional[str]:
    if offset <= 0:
        return "0"
    return str(offset)


def _parse_csv_values(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [entry.strip() for entry in values.split(",") if entry and entry.strip()]
    if isinstance(values, (list, tuple, set)):
        return [str(entry).strip() for entry in values if str(entry).strip()]
    return []


def _infer_pack_from_question(question: Optional[str]) -> str:
    text = (question or "").strip().lower()
    if not text:
        return "default"
    if any(token in text for token in ["risk", "blocker", "issue", "red", "yellow"]):
        return "risk"
    if any(token in text for token in ["owner", "assignee", "sponsor", "who owns", "owned by"]):
        return "ownership"
    if any(token in text for token in ["due", "deadline", "schedule", "timeline", "phase", "when"]):
        return "schedule"
    if any(token in text for token in ["list", "show all", "index", "catalog", "what exists"]):
        return "minimal"
    return "default"


def _field_pack_map(entity_type: str) -> tuple[Dict[str, List[str]], Dict[str, str], Dict[str, Dict[str, int]]]:
    if entity_type == "project":
        return (
            _PROJECT_CARD_FIELD_PACKS,
            _PROJECT_CARD_ALIASES,
            {"status": _PROJECT_STATUS_CODES},
        )
    if entity_type == "solution":
        return (
            _SOLUTION_CARD_FIELD_PACKS,
            _SOLUTION_CARD_ALIASES,
            {"status": _SOLUTION_STATUS_CODES, "rag_status": _RAG_STATUS_CODES},
        )
    return (
        _TASK_CARD_FIELD_PACKS,
        _TASK_CARD_ALIASES,
        {"status": _TASK_STATUS_CODES},
    )


def _resolve_card_fields(
    entity_type: str,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
) -> tuple[List[str], str]:
    packs, _, _ = _field_pack_map(entity_type)
    requested = _parse_csv_values(fields)
    allowed_fields = set()
    for pack_values in packs.values():
        allowed_fields.update(pack_values)
    if requested:
        selected = [field for field in requested if field in allowed_fields][:_MAX_FIELD_COUNT]
        if selected:
            return selected, "custom"
    inferred = (field_pack or "").strip().lower() or _infer_pack_from_question(question)
    if inferred not in packs:
        inferred = "default"
    selected = list(packs.get(inferred) or packs["default"])[:_MAX_FIELD_COUNT]
    return selected, inferred


def _resolve_detail_fields(
    entity_type: str,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
) -> tuple[List[str], str]:
    packs = _DETAIL_FIELD_PACKS.get(entity_type) or _DETAIL_FIELD_PACKS["project"]
    allowed_fields = _ENTITY_FIELD_ALLOWLIST.get(entity_type) or set()
    requested = _parse_csv_values(fields)
    if requested:
        selected = [field for field in requested if field in allowed_fields][:_MAX_FIELD_COUNT]
        if selected:
            return selected, "custom"
    inferred = (field_pack or "").strip().lower() or _infer_pack_from_question(question)
    if inferred not in packs:
        inferred = "default"
    selected = [field for field in packs.get(inferred, packs["default"]) if field in allowed_fields][:_MAX_FIELD_COUNT]
    return selected, inferred


def _select_fields(row: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    return {field: row.get(field) for field in fields}


def _format_rows(
    entity_type: str,
    rows: List[Dict[str, Any]],
    fields: List[str],
    response_format: str = "packed",
) -> Any:
    normalized_format = (response_format or "packed").strip().lower()
    if normalized_format in {"object", "objects", "dict"}:
        return [_select_fields(row, fields) for row in rows]

    _, aliases, enum_fields = _field_pack_map(entity_type)
    alias_to_field = {}
    cols = []
    for field in fields:
        alias = aliases.get(field, field)
        cols.append(alias)
        alias_to_field[alias] = field

    packed_rows: List[List[Any]] = []
    decode_enums: Dict[str, Dict[str, str]] = {}
    for field in fields:
        enum_map = enum_fields.get(field)
        if not enum_map:
            continue
        alias = aliases.get(field, field)
        decode_enums[alias] = {str(code): label for label, code in enum_map.items()}

    for row in rows:
        packed_row: List[Any] = []
        for field in fields:
            value = row.get(field)
            enum_map = enum_fields.get(field)
            if enum_map and value is not None:
                key = str(value)
                if key in enum_map:
                    value = enum_map[key]
            packed_row.append(value)
        packed_rows.append(packed_row)

    payload: Dict[str, Any] = {
        "schema": f"{entity_type}_card.v1",
        "encoding": "packed_rows_v1",
        "cols": cols,
        "abbr": alias_to_field,
        "rows": packed_rows,
    }
    if decode_enums:
        payload["enums"] = decode_enums
    return payload


def _max_updated_iso(
    session: Session,
    model,
    filters: Optional[List[Any]] = None,
) -> str:
    query = session.query(func.max(model.updated_at))
    for predicate in (filters or []):
        query = query.filter(predicate)
    value = query.scalar()
    return _iso_date(value) or ""


def _project_scope_etag(session: Session, project_id: Optional[str] = None, space_id: Optional[str] = None) -> str:
    filters_project = [Project.deleted_at.is_(None)]
    filters_solution = [Solution.deleted_at.is_(None)]
    filters_task = [Subcomponent.deleted_at.is_(None)]
    if space_id:
        filters_project.append(_space_equals(Project, space_id))
        filters_solution.append(_space_equals(Solution, space_id))
        filters_task.append(_space_equals(Subcomponent, space_id))
    if project_id:
        filters_project.append(Project.project_id == project_id)
        filters_solution.append(Solution.project_id == project_id)
        filters_task.append(Subcomponent.project_id == project_id)
    parts = [
        _max_updated_iso(session, Project, filters_project),
        _max_updated_iso(session, Solution, filters_solution),
        _max_updated_iso(session, Subcomponent, filters_task),
    ]
    return "|".join(parts)


def _solution_scope_etag(
    session: Session,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> str:
    filters_solution = [Solution.deleted_at.is_(None)]
    filters_task = [Subcomponent.deleted_at.is_(None)]
    if space_id:
        filters_solution.append(_space_equals(Solution, space_id))
        filters_task.append(_space_equals(Subcomponent, space_id))
    if project_id:
        filters_solution.append(Solution.project_id == project_id)
        filters_task.append(Subcomponent.project_id == project_id)
    if solution_id:
        filters_solution.append(Solution.solution_id == solution_id)
        filters_task.append(Subcomponent.solution_id == solution_id)
    parts = [
        _max_updated_iso(session, Solution, filters_solution),
        _max_updated_iso(session, Subcomponent, filters_task),
    ]
    return "|".join(parts)


def _task_scope_etag(
    session: Session,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> str:
    filters_task = [Subcomponent.deleted_at.is_(None)]
    if space_id:
        filters_task.append(_space_equals(Subcomponent, space_id))
    if project_id:
        filters_task.append(Subcomponent.project_id == project_id)
    if solution_id:
        filters_task.append(Subcomponent.solution_id == solution_id)
    return _max_updated_iso(session, Subcomponent, filters_task)


def _open_solution_counts_by_project(
    session: Session,
    project_ids: List[str],
    space_id: Optional[str] = None,
) -> Dict[str, int]:
    if not project_ids:
        return {}
    rows = (
        _space_scoped(session.query(Solution.project_id, func.count(Solution.solution_id)), Solution, space_id)
        .filter(Solution.project_id.in_(project_ids))
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.status != SolutionStatus.complete)
        .group_by(Solution.project_id)
        .all()
    )
    return {project_id: int(count or 0) for project_id, count in rows}


def _open_task_counts_by_project(
    session: Session,
    project_ids: List[str],
    space_id: Optional[str] = None,
) -> Dict[str, int]:
    if not project_ids:
        return {}
    rows = (
        _space_scoped(
            session.query(Subcomponent.project_id, func.count(Subcomponent.subcomponent_id)),
            Subcomponent,
            space_id,
        )
        .filter(Subcomponent.project_id.in_(project_ids))
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(Subcomponent.status != SubcomponentStatus.complete)
        .group_by(Subcomponent.project_id)
        .all()
    )
    return {project_id: int(count or 0) for project_id, count in rows}


def _project_risk_hints(
    session: Session,
    project_ids: List[str],
    per_project: int = 2,
    space_id: Optional[str] = None,
) -> Dict[str, List[str]]:
    if not project_ids:
        return {}
    rows = (
        _space_scoped(session.query(Solution.project_id, Solution.risks, Solution.updated_at), Solution, space_id)
        .filter(Solution.project_id.in_(project_ids))
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.risks.isnot(None))
        .order_by(Solution.updated_at.desc())
        .all()
    )
    hints: Dict[str, List[str]] = defaultdict(list)
    for project_id, risks, _updated_at in rows:
        entries = _risk_list(risks, max_items=2)
        if not entries:
            continue
        for entry in entries:
            if entry not in hints[project_id]:
                hints[project_id].append(entry)
            if len(hints[project_id]) >= per_project:
                break
    return dict(hints)


def _open_task_counts_by_solution(
    session: Session,
    solution_ids: List[str],
    space_id: Optional[str] = None,
) -> Dict[str, int]:
    if not solution_ids:
        return {}
    rows = (
        _space_scoped(
            session.query(Subcomponent.solution_id, func.count(Subcomponent.subcomponent_id)),
            Subcomponent,
            space_id,
        )
        .filter(Subcomponent.solution_id.in_(solution_ids))
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(Subcomponent.status != SubcomponentStatus.complete)
        .group_by(Subcomponent.solution_id)
        .all()
    )
    return {solution_id: int(count or 0) for solution_id, count in rows}


def _blocked_task_counts_by_solution(
    session: Session,
    solution_ids: List[str],
    space_id: Optional[str] = None,
) -> Dict[str, int]:
    if not solution_ids:
        return {}
    rows = (
        _space_scoped(
            session.query(Subcomponent.solution_id, func.count(Subcomponent.subcomponent_id)),
            Subcomponent,
            space_id,
        )
        .filter(Subcomponent.solution_id.in_(solution_ids))
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(Subcomponent.blocked.is_(True))
        .filter(Subcomponent.status != SubcomponentStatus.complete)
        .group_by(Subcomponent.solution_id)
        .all()
    )
    return {solution_id: int(count or 0) for solution_id, count in rows}


def _project_card(
    project: Project,
    open_solution_count: int = 0,
    open_task_count: int = 0,
    top_risks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    summary = project.description or project.success_criteria or project.strategic_objective
    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": _status_text(project.status),
        "priority": project.priority,
        "sponsor": project.sponsor,
        "open_solution_count": int(open_solution_count or 0),
        "open_task_count": int(open_task_count or 0),
        "top_risks": top_risks or [],
        "last_updated": _iso_date(project.updated_at),
        "short_summary": _short_text(summary, limit=180),
    }


def _solution_card(
    solution: Solution,
    open_task_count: int = 0,
    blocked_task_count: int = 0,
) -> Dict[str, Any]:
    summary = solution.description or solution.success_criteria or solution.problem_statement
    return {
        "solution_id": solution.solution_id,
        "project_id": solution.project_id,
        "solution_name": solution.solution_name,
        "status": _status_text(solution.status),
        "rag_status": _status_text(solution.rag_status),
        "priority": solution.priority,
        "current_phase": solution.current_phase,
        "due_date": _iso_date(solution.due_date),
        "owner": solution.owner,
        "assignee": solution.assignee,
        "open_task_count": int(open_task_count or 0),
        "blocked_task_count": int(blocked_task_count or 0),
        "top_risks": _risk_list(solution.risks, max_items=2),
        "last_updated": _iso_date(solution.updated_at),
        "short_summary": _short_text(summary, limit=180),
    }


def _task_card(sub: Subcomponent) -> Dict[str, Any]:
    summary = sub.blocker_note or sub.done_criteria
    return {
        "subcomponent_id": sub.subcomponent_id,
        "project_id": sub.project_id,
        "solution_id": sub.solution_id,
        "subcomponent_name": sub.subcomponent_name,
        "status": _status_text(sub.status),
        "priority": sub.priority,
        "assignee": sub.assignee,
        "due_date": _iso_date(sub.due_date),
        "blocked": bool(sub.blocked),
        "blocker_note": _short_text(sub.blocker_note, limit=160),
        "estimate_hours": sub.estimate_hours,
        "last_updated": _iso_date(sub.updated_at),
        "short_summary": _short_text(summary, limit=180),
    }


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _is_digest_fresh(source_updated_at: Optional[datetime], digest_source_updated_at: Optional[datetime]) -> bool:
    source = _naive_utc(source_updated_at)
    digest = _naive_utc(digest_source_updated_at)
    if source is None:
        return digest is not None
    if digest is None:
        return False
    return digest >= source


def _digest_writes_enabled() -> bool:
    raw = str(os.getenv("AI_DIGEST_WRITE_ENABLED", "true")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _load_json_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [str(entry) for entry in parsed if str(entry).strip()]
    return []


def _project_card_from_digest(digest: ProjectCardDigest) -> Dict[str, Any]:
    return {
        "project_id": digest.project_id,
        "project_name": digest.project_name,
        "status": digest.status,
        "priority": digest.priority,
        "sponsor": digest.sponsor,
        "open_solution_count": int(digest.open_solution_count or 0),
        "open_task_count": int(digest.open_task_count or 0),
        "top_risks": _load_json_list(digest.top_risks_json),
        "last_updated": _iso_date(digest.source_updated_at or digest.updated_at),
        "short_summary": digest.short_summary or "",
    }


def _solution_card_from_digest(digest: SolutionCardDigest) -> Dict[str, Any]:
    return {
        "solution_id": digest.solution_id,
        "project_id": digest.project_id,
        "solution_name": digest.solution_name,
        "status": digest.status,
        "rag_status": digest.rag_status,
        "priority": digest.priority,
        "current_phase": digest.current_phase,
        "due_date": _iso_date(digest.due_date),
        "owner": digest.owner,
        "assignee": digest.assignee,
        "open_task_count": int(digest.open_task_count or 0),
        "blocked_task_count": int(digest.blocked_task_count or 0),
        "top_risks": _load_json_list(digest.top_risks_json),
        "last_updated": _iso_date(digest.source_updated_at or digest.updated_at),
        "short_summary": digest.short_summary or "",
    }


def _task_card_from_digest(digest: TaskCardDigest) -> Dict[str, Any]:
    return {
        "subcomponent_id": digest.subcomponent_id,
        "project_id": digest.project_id,
        "solution_id": digest.solution_id,
        "subcomponent_name": digest.subcomponent_name,
        "status": digest.status,
        "priority": digest.priority,
        "assignee": digest.assignee,
        "due_date": _iso_date(digest.due_date),
        "blocked": bool(digest.blocked),
        "blocker_note": digest.blocker_note,
        "estimate_hours": digest.estimate_hours,
        "last_updated": _iso_date(digest.source_updated_at or digest.updated_at),
        "short_summary": digest.short_summary or "",
    }


def _sync_project_card_digests(
    session: Session,
    projects: List[Project],
    open_solution_counts: Dict[str, int],
    open_task_counts: Dict[str, int],
    risk_hints: Dict[str, List[str]],
    space_id: Optional[str] = None,
) -> None:
    if not projects or not _digest_writes_enabled():
        return
    project_ids = [row.project_id for row in projects]
    digest_query = session.query(ProjectCardDigest).filter(ProjectCardDigest.project_id.in_(project_ids))
    if space_id:
        digest_query = digest_query.filter(ProjectCardDigest.space_id == space_id)
    existing = {row.project_id: row for row in digest_query.all()}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for project in projects:
        card = _project_card(
            project,
            open_solution_count=open_solution_counts.get(project.project_id, 0),
            open_task_count=open_task_counts.get(project.project_id, 0),
            top_risks=risk_hints.get(project.project_id, []),
        )
        digest = existing.get(project.project_id)
        if digest and _is_digest_fresh(project.updated_at, digest.source_updated_at):
            continue
        if not digest:
            digest = ProjectCardDigest(project_id=project.project_id)
        digest.space_id = space_id or getattr(project, "space_id", None)
        digest.tenant_id = None
        digest.project_name = card.get("project_name") or ""
        digest.status = card.get("status")
        digest.priority = card.get("priority")
        digest.sponsor = card.get("sponsor")
        digest.open_solution_count = int(card.get("open_solution_count") or 0)
        digest.open_task_count = int(card.get("open_task_count") or 0)
        digest.top_risks_json = json.dumps(card.get("top_risks") or [], ensure_ascii=True)
        digest.short_summary = card.get("short_summary")
        digest.source_updated_at = _naive_utc(project.updated_at or project.created_at)
        digest.refreshed_at = now
        digest.updated_at = now
        session.add(digest)


def _sync_solution_card_digests(
    session: Session,
    solutions: List[Solution],
    open_task_counts: Dict[str, int],
    blocked_task_counts: Dict[str, int],
    space_id: Optional[str] = None,
) -> None:
    if not solutions or not _digest_writes_enabled():
        return
    solution_ids = [row.solution_id for row in solutions]
    digest_query = session.query(SolutionCardDigest).filter(SolutionCardDigest.solution_id.in_(solution_ids))
    if space_id:
        digest_query = digest_query.filter(SolutionCardDigest.space_id == space_id)
    existing = {row.solution_id: row for row in digest_query.all()}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for solution in solutions:
        card = _solution_card(
            solution,
            open_task_count=open_task_counts.get(solution.solution_id, 0),
            blocked_task_count=blocked_task_counts.get(solution.solution_id, 0),
        )
        digest = existing.get(solution.solution_id)
        if digest and _is_digest_fresh(solution.updated_at, digest.source_updated_at):
            continue
        if not digest:
            digest = SolutionCardDigest(solution_id=solution.solution_id, project_id=solution.project_id)
        digest.space_id = space_id or getattr(solution, "space_id", None)
        digest.tenant_id = None
        digest.project_id = solution.project_id
        digest.solution_name = card.get("solution_name") or ""
        digest.status = card.get("status")
        digest.rag_status = card.get("rag_status")
        digest.priority = card.get("priority")
        digest.current_phase = card.get("current_phase")
        digest.due_date = solution.due_date
        digest.owner = card.get("owner")
        digest.assignee = card.get("assignee")
        digest.open_task_count = int(card.get("open_task_count") or 0)
        digest.blocked_task_count = int(card.get("blocked_task_count") or 0)
        digest.top_risks_json = json.dumps(card.get("top_risks") or [], ensure_ascii=True)
        digest.short_summary = card.get("short_summary")
        digest.source_updated_at = _naive_utc(solution.updated_at or solution.created_at)
        digest.refreshed_at = now
        digest.updated_at = now
        session.add(digest)


def _sync_task_card_digests(
    session: Session,
    tasks: List[Subcomponent],
    space_id: Optional[str] = None,
) -> None:
    if not tasks or not _digest_writes_enabled():
        return
    task_ids = [row.subcomponent_id for row in tasks]
    digest_query = session.query(TaskCardDigest).filter(TaskCardDigest.subcomponent_id.in_(task_ids))
    if space_id:
        digest_query = digest_query.filter(TaskCardDigest.space_id == space_id)
    existing = {row.subcomponent_id: row for row in digest_query.all()}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for task in tasks:
        card = _task_card(task)
        digest = existing.get(task.subcomponent_id)
        if digest and _is_digest_fresh(task.updated_at, digest.source_updated_at):
            continue
        if not digest:
            digest = TaskCardDigest(
                subcomponent_id=task.subcomponent_id,
                project_id=task.project_id,
                solution_id=task.solution_id,
            )
        digest.space_id = space_id or getattr(task, "space_id", None)
        digest.tenant_id = None
        digest.project_id = task.project_id
        digest.solution_id = task.solution_id
        digest.subcomponent_name = card.get("subcomponent_name") or ""
        digest.status = card.get("status")
        digest.priority = card.get("priority")
        digest.assignee = card.get("assignee")
        digest.due_date = task.due_date
        digest.blocked = bool(card.get("blocked"))
        digest.blocker_note = card.get("blocker_note")
        digest.estimate_hours = card.get("estimate_hours")
        digest.short_summary = card.get("short_summary")
        digest.source_updated_at = _naive_utc(task.updated_at or task.created_at)
        digest.refreshed_at = now
        digest.updated_at = now
        session.add(digest)


def list_project_cards(
    session: Session,
    limit: int = _CARD_LIMIT_DEFAULT,
    cursor: Optional[str] = None,
    project_id: Optional[str] = None,
    status: Optional[List[str]] = None,
    query: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "packed",
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    max_rows = _safe_int(limit, default=_CARD_LIMIT_DEFAULT, minimum=1, maximum=_CARD_LIMIT_MAX)
    offset = _decode_offset_cursor(cursor)
    statuses = {entry for entry in _parse_csv_values(status)}
    search_text = (query or "").strip().lower()
    selected_fields, resolved_pack = _resolve_card_fields("project", fields=fields, field_pack=field_pack, question=question)

    cache_payload = {
        "limit": max_rows,
        "offset": offset,
        "space_id": space_id,
        "project_id": project_id,
        "status": sorted(statuses),
        "query": search_text,
        "fields": selected_fields,
        "format": response_format,
    }
    etag = _project_scope_etag(session, project_id=project_id, space_id=space_id)
    cache_key = _cache_key("list_project_cards", cache_payload, etag)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    query_obj = _space_scoped(session.query(Project), Project, space_id).filter(Project.deleted_at.is_(None))
    if project_id:
        query_obj = query_obj.filter(Project.project_id == project_id)
    if statuses:
        query_obj = query_obj.filter(Project.status.in_(list(statuses)))
    if search_text:
        pattern = f"%{search_text}%"
        query_obj = query_obj.filter(
            func.lower(Project.project_name).like(pattern)
            | func.lower(func.coalesce(Project.description, "")).like(pattern)
        )

    rows = (
        query_obj.order_by(Project.updated_at.desc(), Project.project_id.asc())
        .offset(offset)
        .limit(max_rows + 1)
        .all()
    )
    has_more = len(rows) > max_rows
    rows = rows[:max_rows]
    next_cursor = _encode_offset_cursor(offset + len(rows)) if has_more else None

    project_ids = [row.project_id for row in rows]
    open_solution_counts = _open_solution_counts_by_project(session, project_ids, space_id=space_id)
    open_task_counts = _open_task_counts_by_project(session, project_ids, space_id=space_id)
    risk_hints = _project_risk_hints(session, project_ids, space_id=space_id)
    cards_by_id = {
        row.project_id: _project_card(
            row,
            open_solution_count=open_solution_counts.get(row.project_id, 0),
            open_task_count=open_task_counts.get(row.project_id, 0),
            top_risks=risk_hints.get(row.project_id, []),
        )
        for row in rows
    }
    _sync_project_card_digests(
        session,
        rows,
        open_solution_counts=open_solution_counts,
        open_task_counts=open_task_counts,
        risk_hints=risk_hints,
        space_id=space_id,
    )
    if _digest_writes_enabled():
        session.flush()
    digest_query = session.query(ProjectCardDigest).filter(ProjectCardDigest.project_id.in_(project_ids))
    if space_id:
        digest_query = digest_query.filter(ProjectCardDigest.space_id == space_id)
    digest_rows = {row.project_id: row for row in digest_query.all()}
    cards = [
        _project_card_from_digest(digest_rows[row.project_id])
        if row.project_id in digest_rows
        else cards_by_id[row.project_id]
        for row in rows
    ]
    formatted = _format_rows("project", cards, selected_fields, response_format=response_format)
    output = {
        "entity_type": "project",
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "cards": formatted,
        "count": len(cards),
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
        "cache_hit": False,
        "materialized": True,
    }
    _cache_set(cache_key, output)
    return output


def list_solution_cards(
    session: Session,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = _CARD_LIMIT_DEFAULT,
    cursor: Optional[str] = None,
    status: Optional[List[str]] = None,
    rag_status: Optional[List[str]] = None,
    query: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "packed",
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    max_rows = _safe_int(limit, default=_CARD_LIMIT_DEFAULT, minimum=1, maximum=_CARD_LIMIT_MAX)
    offset = _decode_offset_cursor(cursor)
    statuses = {entry for entry in _parse_csv_values(status)}
    rag_statuses = {entry for entry in _parse_csv_values(rag_status)}
    search_text = (query or "").strip().lower()
    selected_fields, resolved_pack = _resolve_card_fields("solution", fields=fields, field_pack=field_pack, question=question)

    cache_payload = {
        "space_id": space_id,
        "project_id": project_id,
        "solution_id": solution_id,
        "limit": max_rows,
        "offset": offset,
        "status": sorted(statuses),
        "rag_status": sorted(rag_statuses),
        "query": search_text,
        "fields": selected_fields,
        "format": response_format,
    }
    etag = _solution_scope_etag(session, project_id=project_id, solution_id=solution_id, space_id=space_id)
    cache_key = _cache_key("list_solution_cards", cache_payload, etag)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    query_obj = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.deleted_at.is_(None))
    if project_id:
        query_obj = query_obj.filter(Solution.project_id == project_id)
    if solution_id:
        query_obj = query_obj.filter(Solution.solution_id == solution_id)
    if statuses:
        query_obj = query_obj.filter(Solution.status.in_(list(statuses)))
    if rag_statuses:
        query_obj = query_obj.filter(Solution.rag_status.in_(list(rag_statuses)))
    if search_text:
        pattern = f"%{search_text}%"
        query_obj = query_obj.filter(
            func.lower(Solution.solution_name).like(pattern)
            | func.lower(func.coalesce(Solution.description, "")).like(pattern)
        )

    rows = (
        query_obj.order_by(Solution.updated_at.desc(), Solution.solution_id.asc())
        .offset(offset)
        .limit(max_rows + 1)
        .all()
    )
    has_more = len(rows) > max_rows
    rows = rows[:max_rows]
    next_cursor = _encode_offset_cursor(offset + len(rows)) if has_more else None

    solution_ids = [row.solution_id for row in rows]
    open_task_counts = _open_task_counts_by_solution(session, solution_ids, space_id=space_id)
    blocked_task_counts = _blocked_task_counts_by_solution(session, solution_ids, space_id=space_id)
    cards_by_id = {
        row.solution_id: _solution_card(
            row,
            open_task_count=open_task_counts.get(row.solution_id, 0),
            blocked_task_count=blocked_task_counts.get(row.solution_id, 0),
        )
        for row in rows
    }
    _sync_solution_card_digests(
        session,
        rows,
        open_task_counts=open_task_counts,
        blocked_task_counts=blocked_task_counts,
        space_id=space_id,
    )
    if _digest_writes_enabled():
        session.flush()
    digest_query = session.query(SolutionCardDigest).filter(SolutionCardDigest.solution_id.in_(solution_ids))
    if space_id:
        digest_query = digest_query.filter(SolutionCardDigest.space_id == space_id)
    digest_rows = {row.solution_id: row for row in digest_query.all()}
    cards = [
        _solution_card_from_digest(digest_rows[row.solution_id])
        if row.solution_id in digest_rows
        else cards_by_id[row.solution_id]
        for row in rows
    ]
    formatted = _format_rows("solution", cards, selected_fields, response_format=response_format)
    output = {
        "entity_type": "solution",
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "cards": formatted,
        "count": len(cards),
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
        "cache_hit": False,
        "materialized": True,
    }
    _cache_set(cache_key, output)
    return output


def list_task_cards(
    session: Session,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = _CARD_LIMIT_DEFAULT,
    cursor: Optional[str] = None,
    status: Optional[List[str]] = None,
    blocked: Optional[bool] = None,
    query: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "packed",
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    max_rows = _safe_int(limit, default=_CARD_LIMIT_DEFAULT, minimum=1, maximum=_CARD_LIMIT_MAX)
    offset = _decode_offset_cursor(cursor)
    statuses = {entry for entry in _parse_csv_values(status)}
    search_text = (query or "").strip().lower()
    selected_fields, resolved_pack = _resolve_card_fields("subcomponent", fields=fields, field_pack=field_pack, question=question)

    cache_payload = {
        "space_id": space_id,
        "project_id": project_id,
        "solution_id": solution_id,
        "limit": max_rows,
        "offset": offset,
        "status": sorted(statuses),
        "blocked": blocked,
        "query": search_text,
        "fields": selected_fields,
        "format": response_format,
    }
    etag = _task_scope_etag(session, project_id=project_id, solution_id=solution_id, space_id=space_id)
    cache_key = _cache_key("list_task_cards", cache_payload, etag)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    query_obj = _space_scoped(session.query(Subcomponent), Subcomponent, space_id).filter(Subcomponent.deleted_at.is_(None))
    if project_id:
        query_obj = query_obj.filter(Subcomponent.project_id == project_id)
    if solution_id:
        query_obj = query_obj.filter(Subcomponent.solution_id == solution_id)
    if statuses:
        query_obj = query_obj.filter(Subcomponent.status.in_(list(statuses)))
    if blocked is not None:
        query_obj = query_obj.filter(Subcomponent.blocked.is_(bool(blocked)))
    if search_text:
        pattern = f"%{search_text}%"
        query_obj = query_obj.filter(
            func.lower(Subcomponent.subcomponent_name).like(pattern)
            | func.lower(func.coalesce(Subcomponent.blocker_note, "")).like(pattern)
            | func.lower(func.coalesce(Subcomponent.done_criteria, "")).like(pattern)
        )

    rows = (
        query_obj.order_by(Subcomponent.updated_at.desc(), Subcomponent.subcomponent_id.asc())
        .offset(offset)
        .limit(max_rows + 1)
        .all()
    )
    has_more = len(rows) > max_rows
    rows = rows[:max_rows]
    next_cursor = _encode_offset_cursor(offset + len(rows)) if has_more else None

    task_ids = [row.subcomponent_id for row in rows]
    cards_by_id = {row.subcomponent_id: _task_card(row) for row in rows}
    _sync_task_card_digests(session, rows, space_id=space_id)
    if _digest_writes_enabled():
        session.flush()
    digest_query = session.query(TaskCardDigest).filter(TaskCardDigest.subcomponent_id.in_(task_ids))
    if space_id:
        digest_query = digest_query.filter(TaskCardDigest.space_id == space_id)
    digest_rows = {row.subcomponent_id: row for row in digest_query.all()}
    cards = [
        _task_card_from_digest(digest_rows[row.subcomponent_id])
        if row.subcomponent_id in digest_rows
        else cards_by_id[row.subcomponent_id]
        for row in rows
    ]
    formatted = _format_rows("subcomponent", cards, selected_fields, response_format=response_format)
    output = {
        "entity_type": "subcomponent",
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "cards": formatted,
        "count": len(cards),
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
        "cache_hit": False,
        "materialized": True,
    }
    _cache_set(cache_key, output)
    return output


def get_project_card(
    session: Session,
    project_id: str,
    space_id: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "objects",
) -> Dict[str, Any]:
    project = (
        _space_scoped(session.query(Project), Project, space_id)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        return {"error": "Project not found"}
    digest_query = session.query(ProjectCardDigest).filter(ProjectCardDigest.project_id == project_id)
    if space_id:
        digest_query = digest_query.filter(ProjectCardDigest.space_id == space_id)
    digest = digest_query.first()
    if not digest or not _is_digest_fresh(project.updated_at, digest.source_updated_at):
        open_solution_count = _open_solution_counts_by_project(session, [project_id], space_id=space_id).get(project_id, 0)
        open_task_count = _open_task_counts_by_project(session, [project_id], space_id=space_id).get(project_id, 0)
        risk_hints = _project_risk_hints(session, [project_id], space_id=space_id).get(project_id, [])
        _sync_project_card_digests(
            session,
            [project],
            open_solution_counts={project_id: open_solution_count},
            open_task_counts={project_id: open_task_count},
            risk_hints={project_id: risk_hints},
            space_id=space_id,
        )
        if _digest_writes_enabled():
            session.flush()
        digest_query = session.query(ProjectCardDigest).filter(ProjectCardDigest.project_id == project_id)
        if space_id:
            digest_query = digest_query.filter(ProjectCardDigest.space_id == space_id)
        digest = digest_query.first()
    card = _project_card_from_digest(digest) if digest else _project_card(project)
    selected_fields, resolved_pack = _resolve_card_fields("project", fields=fields, field_pack=field_pack, question=question)
    if (response_format or "").strip().lower() in {"packed", "table"}:
        formatted = _format_rows("project", [card], selected_fields, response_format=response_format)
    else:
        formatted = _select_fields(card, selected_fields)
    return {
        "entity_type": "project",
        "entity_id": project_id,
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "card": formatted,
        "drilldown": False,
    }


def get_solution_card(
    session: Session,
    solution_id: str,
    space_id: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "objects",
) -> Dict[str, Any]:
    solution = (
        _space_scoped(session.query(Solution), Solution, space_id)
        .filter(Solution.solution_id == solution_id)
        .filter(Solution.deleted_at.is_(None))
        .first()
    )
    if not solution:
        return {"error": "Solution not found"}
    digest_query = session.query(SolutionCardDigest).filter(SolutionCardDigest.solution_id == solution_id)
    if space_id:
        digest_query = digest_query.filter(SolutionCardDigest.space_id == space_id)
    digest = digest_query.first()
    if not digest or not _is_digest_fresh(solution.updated_at, digest.source_updated_at):
        open_task_count = _open_task_counts_by_solution(session, [solution_id], space_id=space_id).get(solution_id, 0)
        blocked_task_count = _blocked_task_counts_by_solution(session, [solution_id], space_id=space_id).get(solution_id, 0)
        _sync_solution_card_digests(
            session,
            [solution],
            open_task_counts={solution_id: open_task_count},
            blocked_task_counts={solution_id: blocked_task_count},
            space_id=space_id,
        )
        if _digest_writes_enabled():
            session.flush()
        digest_query = session.query(SolutionCardDigest).filter(SolutionCardDigest.solution_id == solution_id)
        if space_id:
            digest_query = digest_query.filter(SolutionCardDigest.space_id == space_id)
        digest = digest_query.first()
    card = _solution_card_from_digest(digest) if digest else _solution_card(solution)
    selected_fields, resolved_pack = _resolve_card_fields("solution", fields=fields, field_pack=field_pack, question=question)
    if (response_format or "").strip().lower() in {"packed", "table"}:
        formatted = _format_rows("solution", [card], selected_fields, response_format=response_format)
    else:
        formatted = _select_fields(card, selected_fields)
    return {
        "entity_type": "solution",
        "entity_id": solution_id,
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "card": formatted,
        "drilldown": False,
    }


def get_task_card(
    session: Session,
    task_id: str,
    space_id: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
    response_format: str = "objects",
) -> Dict[str, Any]:
    task = (
        _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
        .filter(Subcomponent.subcomponent_id == task_id)
        .filter(Subcomponent.deleted_at.is_(None))
        .first()
    )
    if not task:
        return {"error": "Task not found"}
    digest_query = session.query(TaskCardDigest).filter(TaskCardDigest.subcomponent_id == task_id)
    if space_id:
        digest_query = digest_query.filter(TaskCardDigest.space_id == space_id)
    digest = digest_query.first()
    if not digest or not _is_digest_fresh(task.updated_at, digest.source_updated_at):
        _sync_task_card_digests(session, [task], space_id=space_id)
        if _digest_writes_enabled():
            session.flush()
        digest_query = session.query(TaskCardDigest).filter(TaskCardDigest.subcomponent_id == task_id)
        if space_id:
            digest_query = digest_query.filter(TaskCardDigest.space_id == space_id)
        digest = digest_query.first()
    card = _task_card_from_digest(digest) if digest else _task_card(task)
    selected_fields, resolved_pack = _resolve_card_fields("subcomponent", fields=fields, field_pack=field_pack, question=question)
    if (response_format or "").strip().lower() in {"packed", "table"}:
        formatted = _format_rows("subcomponent", [card], selected_fields, response_format=response_format)
    else:
        formatted = _select_fields(card, selected_fields)
    return {
        "entity_type": "subcomponent",
        "entity_id": task_id,
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "card": formatted,
        "drilldown": False,
    }


def get_scope_digest(
    session: Session,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 5,
    question: Optional[str] = None,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_type = _normalize_entity_type(entity_type)
    if normalized_type == "project" and entity_id and not project_id:
        project_id = entity_id
    if normalized_type == "solution" and entity_id and not solution_id:
        solution_id = entity_id
    if normalized_type == "subcomponent" and entity_id and not solution_id:
        sub = (
            _space_scoped(session.query(Subcomponent), Subcomponent, space_id)
            .filter(Subcomponent.subcomponent_id == entity_id)
            .filter(Subcomponent.deleted_at.is_(None))
            .first()
        )
        if sub:
            solution_id = sub.solution_id
            project_id = sub.project_id
    if solution_id and not project_id:
        solution = (
            _space_scoped(session.query(Solution), Solution, space_id)
            .filter(Solution.solution_id == solution_id)
            .filter(Solution.deleted_at.is_(None))
            .first()
        )
        if solution:
            project_id = solution.project_id

    max_rows = _safe_int(limit, default=5, minimum=1, maximum=20)
    project_query = _space_scoped(session.query(Project), Project, space_id).filter(Project.deleted_at.is_(None))
    solution_query = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.deleted_at.is_(None))
    task_query = _space_scoped(session.query(Subcomponent), Subcomponent, space_id).filter(Subcomponent.deleted_at.is_(None))
    if project_id:
        project_query = project_query.filter(Project.project_id == project_id)
        solution_query = solution_query.filter(Solution.project_id == project_id)
        task_query = task_query.filter(Subcomponent.project_id == project_id)
    if solution_id:
        solution_query = solution_query.filter(Solution.solution_id == solution_id)
        task_query = task_query.filter(Subcomponent.solution_id == solution_id)

    project_count = int(project_query.count())
    solution_count = int(solution_query.count())
    task_count = int(task_query.count())
    blocked_task_count = int(task_query.filter(Subcomponent.blocked.is_(True)).count())
    open_task_count = int(task_query.filter(Subcomponent.status != SubcomponentStatus.complete).count())

    updated_candidates = [
        _max_updated_iso(session, Project, [Project.deleted_at.is_(None)] + ([Project.project_id == project_id] if project_id else [])),
        _max_updated_iso(
            session,
            Solution,
            [Solution.deleted_at.is_(None)]
            + ([_space_equals(Solution, space_id)] if space_id else [])
            + ([Solution.project_id == project_id] if project_id else [])
            + ([Solution.solution_id == solution_id] if solution_id else []),
        ),
        _max_updated_iso(
            session,
            Subcomponent,
            [Subcomponent.deleted_at.is_(None)]
            + ([_space_equals(Subcomponent, space_id)] if space_id else [])
            + ([Subcomponent.project_id == project_id] if project_id else [])
            + ([Subcomponent.solution_id == solution_id] if solution_id else []),
        ),
    ]
    if space_id:
        updated_candidates[0] = _max_updated_iso(
            session,
            Project,
            [Project.deleted_at.is_(None), _space_equals(Project, space_id)]
            + ([Project.project_id == project_id] if project_id else []),
        )
    updated_at = ""
    for candidate in updated_candidates:
        if candidate and candidate > updated_at:
            updated_at = candidate

    projects = list_project_cards(
        session,
        project_id=project_id,
        limit=max_rows,
        space_id=space_id,
        field_pack="minimal" if not question else _infer_pack_from_question(question),
        response_format="objects",
    ).get("cards", [])
    solutions = list_solution_cards(
        session,
        project_id=project_id,
        solution_id=solution_id,
        limit=max_rows,
        space_id=space_id,
        field_pack="minimal" if not question else _infer_pack_from_question(question),
        response_format="objects",
    ).get("cards", [])
    tasks = list_task_cards(
        session,
        project_id=project_id,
        solution_id=solution_id,
        limit=max_rows,
        space_id=space_id,
        field_pack="minimal" if not question else _infer_pack_from_question(question),
        response_format="objects",
    ).get("cards", [])

    return {
        "scope": {
            "entity_type": normalized_type or None,
            "entity_id": entity_id,
            "project_id": project_id,
            "solution_id": solution_id,
        },
        "summary": {
            "project_count": project_count,
            "solution_count": solution_count,
            "task_count": task_count,
            "open_task_count": open_task_count,
            "blocked_task_count": blocked_task_count,
            "last_updated": updated_at,
        },
        "top_projects": projects[:max_rows],
        "top_solutions": solutions[:max_rows],
        "top_tasks": tasks[:max_rows],
        "cursor": updated_at,
        "drilldown": False,
    }


def get_entity_fields(
    session: Session,
    entity_type: str,
    entity_id: str,
    space_id: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = None,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_type = _normalize_entity_type(entity_type)
    if normalized_type not in {"project", "solution", "subcomponent"}:
        return {"error": "Invalid entity_type"}
    if not entity_id:
        return {"error": "entity_id is required"}

    if normalized_type == "project":
        detail = read_project_detail(session, entity_id, space_id=space_id)
        entity = detail.get("project_detail") if isinstance(detail, dict) else None
        if not entity:
            return {"error": "Project not found"}
    elif normalized_type == "solution":
        detail = read_solution_detail(session, entity_id, space_id=space_id)
        entity = detail.get("solution_detail") if isinstance(detail, dict) else None
        if not entity:
            return {"error": "Solution not found"}
    else:
        detail = read_subcomponent_detail(session, entity_id, space_id=space_id)
        entity = detail.get("subcomponent_detail") if isinstance(detail, dict) else None
        if not entity:
            return {"error": "Task not found"}

    selected_fields, resolved_pack = _resolve_detail_fields(
        normalized_type,
        fields=fields,
        field_pack=field_pack,
        question=question,
    )
    selected = {field: entity.get(field) for field in selected_fields}
    return {
        "entity_type": normalized_type,
        "entity_id": entity_id,
        "field_pack": resolved_pack,
        "fields": selected_fields,
        "data": selected,
        "drilldown": True,
    }


def _parse_delta_cursor(since_cursor: Optional[str]) -> Optional[datetime]:
    if not since_cursor:
        return None
    raw = str(since_cursor).strip()
    if not raw:
        return None
    # Supports both raw ISO and {"ts":"<iso>"} payloads.
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
            raw = str(payload.get("ts") or payload.get("cursor") or "").strip()
        except Exception:
            return None
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _delta_cursor(updated_at: Optional[datetime], fallback: Optional[str]) -> str:
    if updated_at:
        if updated_at.tzinfo:
            updated_at = updated_at.astimezone(timezone.utc).replace(tzinfo=None)
        return updated_at.isoformat()
    return str(fallback or datetime.now(timezone.utc).replace(tzinfo=None).isoformat())


def get_entity_deltas(
    session: Session,
    since_cursor: Optional[str],
    entity_types: Optional[List[str]] = None,
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    limit: int = 200,
    space_id: Optional[str] = None,
    fields: Optional[List[str]] = None,
    field_pack: Optional[str] = "minimal",
    question: Optional[str] = None,
) -> Dict[str, Any]:
    since_dt = _parse_delta_cursor(since_cursor)
    if since_dt is None:
        now_cursor = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        return {"items": [], "next_cursor": now_cursor, "has_more": False, "drilldown": False}

    max_rows = _safe_int(limit, default=100, minimum=1, maximum=500)
    requested_types = _parse_csv_values(entity_types) if entity_types is not None else ["project", "solution", "subcomponent"]
    normalized_types = {_normalize_entity_type(entry) for entry in requested_types}
    normalized_types = {entry for entry in normalized_types if entry in {"project", "solution", "subcomponent"}}
    if not normalized_types:
        normalized_types = {"project", "solution", "subcomponent"}

    if solution_id and not project_id:
        solution = (
            _space_scoped(session.query(Solution), Solution, space_id)
            .filter(Solution.solution_id == solution_id)
            .filter(Solution.deleted_at.is_(None))
            .first()
        )
        if solution:
            project_id = solution.project_id

    events: List[tuple[datetime, str, str, Any]] = []
    if "project" in normalized_types:
        query_obj = _space_scoped(session.query(Project), Project, space_id).filter(Project.updated_at > since_dt)
        if project_id:
            query_obj = query_obj.filter(Project.project_id == project_id)
        rows = query_obj.order_by(Project.updated_at.asc(), Project.project_id.asc()).limit(max_rows + 1).all()
        for row in rows:
            events.append((row.updated_at or row.created_at or since_dt, "project", row.project_id, row))

    if "solution" in normalized_types:
        query_obj = _space_scoped(session.query(Solution), Solution, space_id).filter(Solution.updated_at > since_dt)
        if project_id:
            query_obj = query_obj.filter(Solution.project_id == project_id)
        if solution_id:
            query_obj = query_obj.filter(Solution.solution_id == solution_id)
        rows = query_obj.order_by(Solution.updated_at.asc(), Solution.solution_id.asc()).limit(max_rows + 1).all()
        for row in rows:
            events.append((row.updated_at or row.created_at or since_dt, "solution", row.solution_id, row))

    if "subcomponent" in normalized_types:
        query_obj = _space_scoped(session.query(Subcomponent), Subcomponent, space_id).filter(Subcomponent.updated_at > since_dt)
        if project_id:
            query_obj = query_obj.filter(Subcomponent.project_id == project_id)
        if solution_id:
            query_obj = query_obj.filter(Subcomponent.solution_id == solution_id)
        rows = query_obj.order_by(Subcomponent.updated_at.asc(), Subcomponent.subcomponent_id.asc()).limit(max_rows + 1).all()
        for row in rows:
            events.append((row.updated_at or row.created_at or since_dt, "subcomponent", row.subcomponent_id, row))

    events.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
    has_more = len(events) > max_rows
    events = events[:max_rows]

    items: List[Dict[str, Any]] = []
    max_updated: Optional[datetime] = None
    for updated_at, etype, entity_id_value, row in events:
        if max_updated is None or updated_at > max_updated:
            max_updated = updated_at
        deleted = bool(getattr(row, "deleted_at", None))
        item: Dict[str, Any] = {
            "entity_type": etype,
            "entity_id": entity_id_value,
            "op": "delete" if deleted else "upsert",
            "last_updated": _iso_date(updated_at),
        }
        if not deleted:
            if etype == "project":
                card = _project_card(row)
            elif etype == "solution":
                card = _solution_card(row)
            else:
                card = _task_card(row)
            selected_fields, _resolved_pack = _resolve_card_fields(
                etype,
                fields=fields,
                field_pack=field_pack,
                question=question,
            )
            item["card"] = _select_fields(card, selected_fields)
        items.append(item)

    return {
        "items": items,
        "count": len(items),
        "has_more": has_more,
        "next_cursor": _delta_cursor(max_updated, since_cursor),
        "drilldown": False,
    }




def _approx_tokens(value: Optional[str]) -> int:
    if not value:
        return 0
    # Lightweight heuristic to avoid tokenizer dependency in tool path.
    return max(1, int(len(value) / 4))


def log_tool_call(
    session: Session,
    tool_name: str,
    payload: Dict[str, Any],
    output: Optional[Dict[str, Any]] = None,
    ai_request_id: Optional[str] = None,
    space_id: Optional[str] = None,
    status: str = "ok",
    elapsed_ms: Optional[int] = None,
    telemetry: Optional[Dict[str, Any]] = None,
) -> None:
    payload_json = json.dumps(payload) if payload is not None else None
    output_json = json.dumps(output) if output is not None else None
    payload_bytes = len(payload_json.encode("utf-8")) if payload_json else 0
    output_bytes = len(output_json.encode("utf-8")) if output_json else 0
    telem = telemetry or {}
    entry = AIToolCall(
        space_id=space_id,
        ai_request_id=ai_request_id,
        tool_name=tool_name,
        payload=payload_json,
        output=output_json,
        status=status,
        elapsed_ms=elapsed_ms,
        payload_bytes=payload_bytes,
        output_bytes=output_bytes,
        payload_tokens=_approx_tokens(payload_json),
        output_tokens=_approx_tokens(output_json),
        cache_hit=telem.get("cache_hit"),
        drilldown=telem.get("drilldown"),
        context_bytes=telem.get("context_bytes"),
    )
    session.add(entry)


def log_query_metric(
    session: Session,
    *,
    session_id: Optional[str],
    space_id: Optional[str],
    user_id: Optional[str],
    project_id: Optional[str],
    entity_type: Optional[str],
    entity_id: Optional[str],
    tool_calls_count: int,
    context_calls_count: int,
    bytes_returned: int,
    approx_tokens_returned: int,
    bytes_sent: int,
    approx_tokens_sent: int,
    cache_hit_rate: Optional[float],
    drilldown_rate: Optional[float],
    answer_quality_score: Optional[float] = None,
    notes: Optional[str] = None,
) -> None:
    row = AIQueryMetric(
        space_id=space_id,
        session_id=session_id,
        user_id=user_id,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        tool_calls_count=int(tool_calls_count or 0),
        context_calls_count=int(context_calls_count or 0),
        bytes_returned=int(bytes_returned or 0),
        approx_tokens_returned=int(approx_tokens_returned or 0),
        bytes_sent=int(bytes_sent or 0),
        approx_tokens_sent=int(approx_tokens_sent or 0),
        cache_hit_rate=cache_hit_rate,
        drilldown_rate=drilldown_rate,
        answer_quality_score=answer_quality_score,
        notes=notes,
    )
    session.add(row)


def get_tool_catalog() -> List[Dict[str, Any]]:
    return [
        {
            "name": "read_context",
            "description": "Load project tree, phases, dropdowns, and change log context.",
            "args": ["entity_type", "entity_id", "project_id"],
        },
        {
            "name": "get_scope_digest",
            "description": "Tier-A compact scope digest with counts and top cards for projects/solutions/tasks.",
            "args": ["project_id", "solution_id", "entity_type", "entity_id", "limit", "question"],
        },
        {
            "name": "list_project_cards",
            "description": "Tier-A project cards with pagination/cursor, field packs, and compact packed output.",
            "args": [
                "limit",
                "cursor",
                "project_id",
                "status",
                "query",
                "field_pack",
                "fields",
                "question",
                "response_format",
            ],
        },
        {
            "name": "list_solution_cards",
            "description": "Tier-A solution cards with filtering, cursor pagination, and packed output.",
            "args": [
                "project_id",
                "solution_id",
                "limit",
                "cursor",
                "status",
                "rag_status",
                "query",
                "field_pack",
                "fields",
                "question",
                "response_format",
            ],
        },
        {
            "name": "list_task_cards",
            "description": "Tier-A task (subcomponent) cards with filtering, cursor pagination, and packed output.",
            "args": [
                "project_id",
                "solution_id",
                "limit",
                "cursor",
                "status",
                "blocked",
                "query",
                "field_pack",
                "fields",
                "question",
                "response_format",
            ],
        },
        {
            "name": "get_project_card",
            "description": "Fetch one project card by id with minimal fields; use before full drill-down.",
            "args": ["project_id", "field_pack", "fields", "question", "response_format"],
        },
        {
            "name": "get_solution_card",
            "description": "Fetch one solution card by id with minimal fields; use before full drill-down.",
            "args": ["solution_id", "field_pack", "fields", "question", "response_format"],
        },
        {
            "name": "get_task_card",
            "description": "Fetch one task/subcomponent card by id with minimal fields.",
            "args": ["task_id", "field_pack", "fields", "question", "response_format"],
        },
        {
            "name": "get_entity_fields",
            "description": "Tier-B drill-down: fetch only requested canonical fields for one entity.",
            "args": ["entity_type", "entity_id", "fields", "field_pack", "question"],
        },
        {
            "name": "get_entity_deltas",
            "description": "Delta sync: fetch changed entities since cursor with next_cursor for incremental refresh.",
            "args": ["since_cursor", "entity_types", "project_id", "solution_id", "limit", "fields", "field_pack", "question"],
        },
        {
            "name": "read_project_detail",
            "description": "Load full project detail, including solutions, subcomponents, artifacts, SOWs, and checklists.",
            "args": ["project_id"],
        },
        {
            "name": "read_solution_detail",
            "description": "Load full solution detail, including subcomponents and solution phases.",
            "args": ["solution_id"],
        },
        {
            "name": "read_subcomponent_detail",
            "description": "Load full subcomponent detail with parent solution and project.",
            "args": ["subcomponent_id"],
        },
        {
            "name": "read_artifacts_detail",
            "description": "Load all project charters, plans, and decision logs (full content).",
            "args": ["project_id"],
        },
        {
            "name": "read_sow_document",
            "description": "Load a full SOW document by sow_id.",
            "args": ["sow_id"],
        },
        {
            "name": "list_projects",
            "description": "List all projects (id + name + status).",
            "args": ["limit"],
        },
        {
            "name": "list_solutions_for_project",
            "description": "List all solutions for a given project.",
            "args": ["project_id", "limit"],
        },
        {
            "name": "read_entity_index",
            "description": "Load a compact index of entities by type to prevent duplicates.",
            "args": ["entity_type", "project_id", "solution_id", "limit"],
        },
        {
            "name": "read_entity_deltas",
            "description": "Load entities updated since a cursor/timestamp.",
            "args": ["entity_type", "since", "limit"],
        },
        {
            "name": "validate_draft",
            "description": "Deterministically validate a draft against contracts.",
            "args": ["entity_type", "action", "fields"],
        },
        {
            "name": "read_external_doc",
            "description": "Read an uploaded external document by document_id.",
            "args": ["document_id"],
        },
        {
            "name": "explain_app_usage",
            "description": "Provide detailed how-to guidance for screens, workflows, roles, spaces, and troubleshooting.",
            "args": ["question", "topic", "max_sections"],
        },
        {
            "name": "search_entities",
            "description": "Find entities by name; can return ids only, cards, or selected fields.",
            "args": [
                "query",
                "entity_types",
                "limit",
                "project_id",
                "solution_id",
                "return_mode",
                "field_pack",
                "fields",
                "response_format",
            ],
        },
        {
            "name": "draft_charter",
            "description": "Draft a project charter (return JSON with content).",
            "args": ["project_id", "instruction"],
        },
        {
            "name": "draft_plan",
            "description": "Draft a project plan (return JSON with content).",
            "args": ["project_id", "instruction"],
        },
        {
            "name": "draft_decision_log",
            "description": "Draft a project decision log entry (return JSON with content).",
            "args": ["project_id", "instruction"],
        },
        {
            "name": "draft_update",
            "description": "Draft updates for project/solution/subcomponent fields.",
            "args": ["entity_type", "entity_id", "instruction"],
        },
        {
            "name": "draft_create_solution",
            "description": "Draft a new solution for a project (return JSON with fields).",
            "args": ["project_id", "instruction"],
        },
        {
            "name": "draft_create_project",
            "description": "Draft a new project (return JSON with fields).",
            "args": ["instruction"],
        },
        {
            "name": "draft_create_subcomponent",
            "description": "Draft a new subcomponent for a solution (return JSON with fields).",
            "args": ["solution_id", "instruction"],
        },
        {
            "name": "draft_subcomponents",
            "description": "Draft subcomponents for a solution (return JSON).",
            "args": ["solution_id", "instruction"],
        },
        {
            "name": "draft_sow",
            "description": "Draft a SOW for a project or solution (return JSON with content).",
            "args": ["entity_type", "entity_id", "instruction"],
        },
        {
            "name": "draft_checklist",
            "description": "Draft a monthly checklist for a project.",
            "args": ["project_id", "instruction"],
        },
    ]
