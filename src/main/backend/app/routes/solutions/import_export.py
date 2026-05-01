from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_space_role
from ...models import Phase, Project, Solution, User
from ...services.audit_log import safe_log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_status, normalize_str, parse_date, parse_priority, read_csv
from ...utils.enums import ConfidenceLevel, ProjectStatus, RagStatus, SolutionStatus
from .._mutations import commit_session
from ..projects.common import _resolve_project_sponsor
from .common import (
    _apply_solution_completion_state,
    _exclude_work_allocation_board_solutions,
    _parse_rag_status,
    _publish_solution_import,
    _resolve_solution_assignee,
    _resolve_solution_owner,
    _run_enable_all_phases,
    _solution_query,
    _validate_current_phase,
    normalize_github_repo_url,
    read_text_value,
)

router = APIRouter()


@router.post("/solutions/import")
def import_solutions(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"created": 0, "updated": 0, "projects_created": 0, "errors": errors, "total_rows": 0}
    created = updated = projects_created = 0
    invalidate_subcomponents = False
    seen = set()
    projects_by_name = {
        p.project_name.lower(): p
        for p in (
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.space_id == space_ctx.space_id)
            .all()
        )
    }

    for idx, row in enumerate(rows, start=2):
        project_name = normalize_str(row.get("project_name"))
        solution_name = normalize_str(row.get("solution_name"))
        version_raw = normalize_str(row.get("version")) or "0.1.0"
        owner_input = normalize_str(row.get("owner"))
        assignee_input = normalize_str(row.get("assignee"))
        owner_user_soeid = normalize_str(row.get("owner_user_soeid")) or None
        assignee_user_soeid = normalize_str(row.get("assignee_user_soeid")) or None
        approver = normalize_str(row.get("approver")) or None
        approver_user_soeid = normalize_str(row.get("approver_user_soeid")) or None
        key_stakeholder = normalize_str(row.get("key_stakeholder"))
        if not project_name or not solution_name:
            errors.append(f"Row {idx}: project_name and solution_name are required")
            continue
        key = (project_name.lower(), solution_name.lower(), version_raw.lower())
        if key in seen:
            errors.append(
                f"Row {idx}: duplicate solution '{solution_name}' version '{version_raw}' for project '{project_name}' in CSV (strict-first policy)"
            )
            continue
        seen.add(key)
        try:
            status_enum = normalize_status(
                row.get("status") or SolutionStatus.not_started.value, SolutionStatus
            )
            priority_val = parse_priority(row.get("priority"), default=3)
            due_date_val = parse_date(row.get("due_date"))
            planned_start_date = parse_date(row.get("planned_start_date"))
            rag_status_raw = _parse_rag_status(row.get("rag_status"))
            rag_confidence = (
                float(row.get("rag_confidence")) if normalize_str(row.get("rag_confidence")) else None
            )
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue

        description = normalize_str(row.get("description")) or None
        success_criteria = normalize_str(row.get("success_criteria")) or None
        problem_statement = normalize_str(row.get("problem_statement")) or None
        try:
            github_repo_url = normalize_github_repo_url(row.get("github_repo_url"))
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue
        rag_reason_val = normalize_str(row.get("rag_reason")) or None
        current_phase = normalize_str(row.get("current_phase")) or None
        if current_phase:
            phase_exists = session.query(Phase).filter(Phase.phase_id == current_phase).first()
            if not phase_exists:
                errors.append(f"Row {idx}: current_phase '{current_phase}' does not exist")
                continue
        blockers = normalize_str(row.get("blockers")) or None
        risks = normalize_str(row.get("risks")) or None

        rag_status_val = rag_status_raw or RagStatus.green
        impact_confidence = None
        impact_conf_raw = normalize_str(row.get("impact_confidence"))
        if impact_conf_raw:
            for candidate in ConfidenceLevel:
                if candidate.value.lower() == impact_conf_raw.lower():
                    impact_confidence = candidate
                    break
            if impact_confidence is None:
                errors.append(f"Row {idx}: invalid impact_confidence '{impact_conf_raw}'")
                continue

        project = projects_by_name.get(project_name.lower())
        project_created_this_row = False
        if not project:
            project_sponsor, project_sponsor_user_soeid = _resolve_project_sponsor(
                owner_input,
                owner_user_soeid,
                current_user,
            )
            project = Project(
                space_id=space_ctx.space_id,
                project_name=project_name,
                status=ProjectStatus.not_started,
                description=None,
                sponsor=project_sponsor,
                sponsor_user_soeid=project_sponsor_user_soeid,
            )
            session.add(project)
            session.flush()
            project_created_this_row = True
            safe_log_changes(
                session,
                entity_type="project",
                entity_id=project.project_id,
                user_id=current_user.user_id,
                action="create",
                space_id=space_ctx.space_id,
                changes={
                    "project_name": (None, project.project_name),
                    "status": (None, project.status),
                    "description": (None, project.description),
                    "success_criteria": (None, project.success_criteria),
                    "sponsor": (None, project.sponsor),
                    "sponsor_user_soeid": (None, project.sponsor_user_soeid),
                },
                request_id=None,
            )

        existing = (
            _solution_query(session, space_ctx)
            .filter(Solution.project_id == project.project_id)
            .filter(Solution.solution_name == solution_name)
            .filter(Solution.version == version_raw)
            .first()
        )
        try:
            if existing:
                if owner_input:
                    resolved_owner, resolved_owner_user_soeid = _resolve_solution_owner(
                        owner_input,
                        owner_user_soeid,
                        current_user,
                    )
                else:
                    resolved_owner = existing.owner
                    resolved_owner_user_soeid = existing.owner_user_soeid
                if assignee_input:
                    resolved_assignee, resolved_assignee_user_soeid = _resolve_solution_assignee(
                        assignee_input,
                        assignee_user_soeid,
                        owner=resolved_owner,
                        owner_user_soeid=resolved_owner_user_soeid,
                        current_user=current_user,
                    )
                else:
                    resolved_assignee = existing.assignee
                    resolved_assignee_user_soeid = existing.assignee_user_soeid
                if current_phase:
                    _validate_current_phase(session, existing.solution_id, current_phase)

                before = {
                    "status": existing.status,
                    "rag_status": existing.rag_status,
                    "rag_reason": existing.rag_reason,
                    "priority": existing.priority,
                    "due_date": existing.due_date,
                    "planned_start_date": existing.planned_start_date,
                    "current_phase": existing.current_phase,
                    "description": existing.description,
                    "success_criteria": existing.success_criteria,
                    "problem_statement": existing.problem_statement,
                    "github_repo_url": existing.github_repo_url,
                    "impact_confidence": existing.impact_confidence,
                    "owner": existing.owner,
                    "owner_user_soeid": existing.owner_user_soeid,
                    "assignee": existing.assignee,
                    "assignee_user_soeid": existing.assignee_user_soeid,
                    "approver": existing.approver,
                    "approver_user_soeid": existing.approver_user_soeid,
                    "key_stakeholder": existing.key_stakeholder,
                    "blockers": existing.blockers,
                    "risks": existing.risks,
                    "rag_confidence": existing.rag_confidence,
                    "completed_at": existing.completed_at,
                }
                now = datetime.now(timezone.utc)
                existing.status = status_enum
                existing.rag_status = rag_status_val
                existing.rag_reason = rag_reason_val
                existing.priority = priority_val
                existing.due_date = due_date_val
                existing.planned_start_date = planned_start_date
                existing.current_phase = current_phase
                existing.description = description
                existing.success_criteria = success_criteria
                existing.problem_statement = problem_statement
                existing.github_repo_url = github_repo_url
                existing.impact_confidence = impact_confidence
                existing.owner = resolved_owner
                existing.owner_user_soeid = resolved_owner_user_soeid
                existing.assignee = resolved_assignee or ""
                existing.assignee_user_soeid = resolved_assignee_user_soeid
                existing.approver = approver
                existing.approver_user_soeid = approver_user_soeid
                existing.key_stakeholder = key_stakeholder or None
                existing.blockers = blockers
                existing.risks = risks
                existing.rag_confidence = rag_confidence
                if not existing.space_id:
                    existing.space_id = space_ctx.space_id
                _apply_solution_completion_state(
                    session,
                    existing,
                    next_status=status_enum,
                    now=now,
                )
                existing.updated_at = now
                session.add(existing)
                safe_log_changes(
                    session,
                    entity_type="solution",
                    entity_id=existing.solution_id,
                    user_id=current_user.user_id,
                    action="update",
                    space_id=space_ctx.space_id,
                    changes={
                        "status": (before["status"], existing.status),
                        "rag_status": (before["rag_status"], existing.rag_status),
                        "rag_reason": (before["rag_reason"], existing.rag_reason),
                        "priority": (before["priority"], existing.priority),
                        "due_date": (before["due_date"], existing.due_date),
                        "planned_start_date": (before["planned_start_date"], existing.planned_start_date),
                        "current_phase": (before["current_phase"], existing.current_phase),
                        "description": (before["description"], existing.description),
                        "success_criteria": (before["success_criteria"], existing.success_criteria),
                        "problem_statement": (before["problem_statement"], existing.problem_statement),
                        "github_repo_url": (before["github_repo_url"], existing.github_repo_url),
                        "impact_confidence": (before["impact_confidence"], existing.impact_confidence),
                        "owner": (before["owner"], existing.owner),
                        "owner_user_soeid": (before["owner_user_soeid"], existing.owner_user_soeid),
                        "assignee": (before["assignee"], existing.assignee),
                        "assignee_user_soeid": (before["assignee_user_soeid"], existing.assignee_user_soeid),
                        "approver": (before["approver"], existing.approver),
                        "approver_user_soeid": (before["approver_user_soeid"], existing.approver_user_soeid),
                        "key_stakeholder": (before["key_stakeholder"], existing.key_stakeholder),
                        "blockers": (before["blockers"], existing.blockers),
                        "risks": (before["risks"], existing.risks),
                        "rag_confidence": (before["rag_confidence"], existing.rag_confidence),
                        "completed_at": (before["completed_at"], existing.completed_at),
                    },
                    request_id=None,
                )
                if before["github_repo_url"] != existing.github_repo_url:
                    invalidate_subcomponents = True
                updated += 1
                commit_session(session)
            else:
                resolved_owner, resolved_owner_user_soeid = _resolve_solution_owner(
                    owner_input,
                    owner_user_soeid,
                    current_user,
                )
                resolved_assignee, resolved_assignee_user_soeid = _resolve_solution_assignee(
                    assignee_input,
                    assignee_user_soeid,
                    owner=resolved_owner,
                    owner_user_soeid=resolved_owner_user_soeid,
                    current_user=current_user,
                )
                now = datetime.now(timezone.utc)
                completed_at = now if status_enum == SolutionStatus.complete else None
                solution = Solution(
                    space_id=space_ctx.space_id,
                    project_id=project.project_id,
                    solution_name=solution_name,
                    version=version_raw,
                    status=status_enum,
                    rag_status=rag_status_val,
                    rag_reason=rag_reason_val,
                    rag_confidence=rag_confidence,
                    priority=priority_val,
                    due_date=due_date_val,
                    planned_start_date=planned_start_date,
                    current_phase=current_phase,
                    description=description,
                    success_criteria=success_criteria,
                    problem_statement=problem_statement,
                    github_repo_url=github_repo_url,
                    impact_confidence=impact_confidence,
                    owner=resolved_owner,
                    owner_user_soeid=resolved_owner_user_soeid,
                    assignee=resolved_assignee or "",
                    assignee_user_soeid=resolved_assignee_user_soeid,
                    approver=approver,
                    approver_user_soeid=approver_user_soeid,
                    key_stakeholder=key_stakeholder or None,
                    blockers=blockers,
                    risks=risks,
                    completed_at=completed_at,
                )
                session.add(solution)
                session.flush()
                safe_log_changes(
                    session,
                    entity_type="solution",
                    entity_id=solution.solution_id,
                    user_id=current_user.user_id,
                    action="create",
                    space_id=space_ctx.space_id,
                    changes={
                        "solution_name": (None, solution.solution_name),
                        "version": (None, solution.version),
                        "status": (None, solution.status),
                        "rag_status": (None, solution.rag_status),
                        "rag_reason": (None, solution.rag_reason),
                        "rag_confidence": (None, solution.rag_confidence),
                        "priority": (None, solution.priority),
                        "due_date": (None, solution.due_date),
                        "planned_start_date": (None, solution.planned_start_date),
                        "current_phase": (None, solution.current_phase),
                        "description": (None, solution.description),
                        "success_criteria": (None, solution.success_criteria),
                        "problem_statement": (None, solution.problem_statement),
                        "github_repo_url": (None, solution.github_repo_url),
                        "impact_confidence": (None, solution.impact_confidence),
                        "owner": (None, solution.owner),
                        "owner_user_soeid": (None, solution.owner_user_soeid),
                        "assignee": (None, solution.assignee),
                        "assignee_user_soeid": (None, solution.assignee_user_soeid),
                        "approver": (None, solution.approver),
                        "approver_user_soeid": (None, solution.approver_user_soeid),
                        "key_stakeholder": (None, solution.key_stakeholder),
                        "blockers": (None, solution.blockers),
                        "risks": (None, solution.risks),
                        "completed_at": (None, solution.completed_at),
                    },
                    request_id=None,
                )
                _run_enable_all_phases(session, solution.solution_id)
                commit_session(session)
                created += 1
            if project_created_this_row:
                projects_by_name[project_name.lower()] = project
                projects_created += 1
        except Exception as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")
    _publish_solution_import(
        space_ctx.space_id,
        projects_created=projects_created,
        invalidate_subcomponents=invalidate_subcomponents,
    )
    return {
        "created": created,
        "updated": updated,
        "projects_created": projects_created,
        "errors": errors,
        "total_rows": len(rows),
    }


@router.get("/solutions/export")
def export_solutions(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    solutions = _exclude_work_allocation_board_solutions(
        _solution_query(session, space_ctx),
        session,
        space_ctx,
    ).all()
    project_map = {
        p.project_id: p.project_name
        for p in (
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.space_id == space_ctx.space_id)
        )
    }
    buffer = StringIO()
    fieldnames = [
        "project_name",
        "solution_name",
        "version",
        "status",
        "rag_status",
        "rag_reason",
        "rag_confidence",
        "priority",
        "due_date",
        "planned_start_date",
        "current_phase",
        "description",
        "problem_statement",
        "success_criteria",
        "github_repo_url",
        "impact_confidence",
        "owner",
        "owner_user_soeid",
        "assignee",
        "assignee_user_soeid",
        "approver",
        "approver_user_soeid",
        "key_stakeholder",
        "blockers",
        "risks",
        "completed_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for solution in solutions:
        writer.writerow(
            {
                "project_name": project_map.get(solution.project_id, ""),
                "solution_name": solution.solution_name,
                "version": solution.version,
                "status": solution.status.value if hasattr(solution.status, "value") else solution.status,
                "rag_status": solution.rag_status.value if hasattr(solution.rag_status, "value") else solution.rag_status,
                "rag_reason": solution.rag_reason or "",
                "rag_confidence": solution.rag_confidence if solution.rag_confidence is not None else "",
                "priority": solution.priority,
                "due_date": solution.due_date.isoformat() if solution.due_date else "",
                "planned_start_date": solution.planned_start_date.isoformat() if solution.planned_start_date else "",
                "current_phase": solution.current_phase or "",
                "description": read_text_value(solution.description) or "",
                "problem_statement": read_text_value(solution.problem_statement) or "",
                "success_criteria": read_text_value(solution.success_criteria) or "",
                "github_repo_url": solution.github_repo_url or "",
                "impact_confidence": solution.impact_confidence.value if hasattr(solution.impact_confidence, "value") else (solution.impact_confidence or ""),
                "owner": solution.owner or "",
                "owner_user_soeid": solution.owner_user_soeid or "",
                "assignee": solution.assignee or "",
                "assignee_user_soeid": solution.assignee_user_soeid or "",
                "approver": solution.approver or "",
                "approver_user_soeid": solution.approver_user_soeid or "",
                "key_stakeholder": solution.key_stakeholder or "",
                "blockers": solution.blockers or "",
                "risks": solution.risks or "",
                "completed_at": solution.completed_at.isoformat() if solution.completed_at else "",
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename=\"solutions.csv\"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)
