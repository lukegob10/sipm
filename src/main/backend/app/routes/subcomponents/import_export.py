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
from ...models import Project, Solution, Subcomponent, User
from ...services.audit_log import log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_status, normalize_str, parse_date, parse_datetime, parse_priority, read_csv, read_text_value
from ...utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus
from .._mutations import commit_session
from ..projects.common import _resolve_project_sponsor
from ..solutions.common import _resolve_solution_owner
from .common import (
    _apply_subcomponent_completion_state,
    _project_query,
    _publish_subcomponent_import,
    _resolve_subcomponent_assignee,
    _run_enable_all_phases,
    _solution_query,
    _subcomponent_query,
    normalize_github_repo_url,
)

router = APIRouter()


@router.post("/subcomponents/import")
def import_subcomponents(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    dry_run: bool = False,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {
            "created": 0,
            "updated": 0,
            "projects_created": 0,
            "solutions_created": 0,
            "errors": errors,
            "total_rows": 0,
            "dry_run": dry_run,
        }
    created = updated = projects_created = solutions_created = 0
    seen = set()
    dry_project_keys = set()
    dry_solution_keys = set()
    projects_by_name = {p.project_name.lower(): p for p in _project_query(session, space_ctx).all()}
    solutions_by_key = {
        (s.project_id, s.solution_name.lower(), s.version.lower()): s
        for s in _solution_query(session, space_ctx).all()
    }

    for idx, row in enumerate(rows, start=2):
        project_name = normalize_str(row.get("project_name"))
        solution_name = normalize_str(row.get("solution_name"))
        sub_name = normalize_str(row.get("subcomponent_name"))
        version_raw = normalize_str(row.get("version")) or "0.1.0"
        solution_owner_val = normalize_str(row.get("solution_owner")) or normalize_str(row.get("owner"))
        assignee_input = normalize_str(row.get("assignee"))
        assignee_user_soeid = normalize_str(row.get("assignee_user_soeid")) or None
        blocker_note = normalize_str(row.get("blocker_note")) or None
        done_criteria = normalize_str(row.get("done_criteria")) or None
        try:
            github_repo_url = normalize_github_repo_url(row.get("github_repo_url"))
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue
        blocked_raw = normalize_str(row.get("blocked"))
        blocked_val = blocked_raw.lower() in {"true", "1", "yes", "y"} if blocked_raw else False
        if not project_name or not solution_name or not sub_name:
            errors.append(
                f"Row {idx}: project_name, solution_name, and subcomponent_name are required"
            )
            continue
        key = (project_name.lower(), solution_name.lower(), version_raw.lower(), sub_name.lower())
        if key in seen:
            errors.append(
                f"Row {idx}: duplicate subcomponent '{sub_name}' for solution '{solution_name}' in project '{project_name}' (strict-first policy)"
            )
            continue
        seen.add(key)

        try:
            status_enum = normalize_status(
                row.get("status") or SubcomponentStatus.to_do.value, SubcomponentStatus
            )
            priority_val = parse_priority(row.get("priority"), default=3)
            due_val = parse_date(row.get("due_date"))
            completed_at_val = parse_datetime(row.get("completed_at"))
            estimate_hours = int(row.get("estimate_hours")) if normalize_str(row.get("estimate_hours")) else None
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue

        project = projects_by_name.get(project_name.lower())
        if dry_run:
            project_key = project_name.lower()
            if not project and project_key not in dry_project_keys:
                dry_project_keys.add(project_key)
                projects_created += 1
            solution = None
            if project:
                solution = solutions_by_key.get((project.project_id, solution_name.lower(), version_raw.lower()))
            solution_key = (project_key, solution_name.lower(), version_raw.lower())
            if not solution and solution_key not in dry_solution_keys:
                dry_solution_keys.add(solution_key)
                solutions_created += 1
            if project and solution:
                existing = (
                    _subcomponent_query(session, space_ctx)
                    .filter(Subcomponent.solution_id == solution.solution_id)
                    .filter(Subcomponent.subcomponent_name == sub_name)
                    .first()
                )
                if existing:
                    updated += 1
                else:
                    created += 1
            else:
                created += 1
            continue
        project_created_this_row = False
        if not project:
            sponsor_val, sponsor_user_soeid = _resolve_project_sponsor(
                solution_owner_val,
                None,
                current_user,
            )
            project = Project(
                space_id=space_ctx.space_id,
                project_name=project_name,
                status=ProjectStatus.not_started,
                description=None,
                sponsor=sponsor_val,
                sponsor_user_soeid=sponsor_user_soeid,
            )
            session.add(project)
            session.flush()
            project_created_this_row = True
            log_changes(
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
                    "sponsor": (None, project.sponsor),
                    "sponsor_user_soeid": (None, project.sponsor_user_soeid),
                },
                request_id=None,
            )

        solution_key = (project.project_id, solution_name.lower(), version_raw.lower())
        solution = solutions_by_key.get(solution_key)
        solution_created_this_row = False
        if not solution:
            try:
                solution_owner, solution_owner_user_soeid = _resolve_solution_owner(
                    solution_owner_val,
                    None,
                    current_user,
                )
                solution = Solution(
                    space_id=space_ctx.space_id,
                    project_id=project.project_id,
                    solution_name=solution_name,
                    version=version_raw,
                    status=SolutionStatus.not_started,
                    priority=3,
                    due_date=None,
                    current_phase=None,
                    description=None,
                    owner=solution_owner,
                    owner_user_soeid=solution_owner_user_soeid,
                    assignee="",
                    approver=None,
                    key_stakeholder=None,
                    blockers=None,
                    risks=None,
                    completed_at=None,
                )
                session.add(solution)
                session.flush()
                log_changes(
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
                        "priority": (None, solution.priority),
                        "due_date": (None, solution.due_date),
                        "current_phase": (None, solution.current_phase),
                        "description": (None, solution.description),
                        "owner": (None, solution.owner),
                        "owner_user_soeid": (None, solution.owner_user_soeid),
                        "assignee": (None, solution.assignee),
                        "approver": (None, solution.approver),
                        "key_stakeholder": (None, solution.key_stakeholder),
                        "blockers": (None, solution.blockers),
                        "risks": (None, solution.risks),
                        "completed_at": (None, solution.completed_at),
                    },
                    request_id=None,
                )
                _run_enable_all_phases(session, solution.solution_id)
                solution_created_this_row = True
            except Exception as exc:
                session.rollback()
                errors.append(f"Row {idx}: {exc}")
                continue

        try:
            existing = (
                _subcomponent_query(session, space_ctx)
                .filter(Subcomponent.solution_id == solution.solution_id)
                .filter(Subcomponent.subcomponent_name == sub_name)
                .first()
            )
            now = datetime.now(timezone.utc)
            if existing:
                if assignee_input:
                    resolved_assignee, resolved_assignee_user_soeid = _resolve_subcomponent_assignee(
                        assignee_input,
                        assignee_user_soeid,
                        current_user,
                    )
                else:
                    resolved_assignee = existing.assignee
                    resolved_assignee_user_soeid = existing.assignee_user_soeid
                before = {
                    "status": existing.status,
                    "priority": existing.priority,
                    "due_date": existing.due_date,
                    "assignee": existing.assignee,
                    "assignee_user_soeid": existing.assignee_user_soeid,
                    "github_repo_url": existing.github_repo_url,
                    "estimate_hours": existing.estimate_hours,
                    "blocked": existing.blocked,
                    "blocker_note": existing.blocker_note,
                    "done_criteria": existing.done_criteria,
                    "completed_at": existing.completed_at,
                }
                existing.status = status_enum
                existing.priority = priority_val
                existing.due_date = due_val
                existing.assignee = resolved_assignee
                existing.assignee_user_soeid = resolved_assignee_user_soeid
                existing.github_repo_url = github_repo_url
                existing.estimate_hours = estimate_hours
                existing.blocked = blocked_val
                existing.blocker_note = blocker_note
                existing.done_criteria = done_criteria
                existing.updated_at = now
                if not existing.space_id:
                    existing.space_id = space_ctx.space_id
                _apply_subcomponent_completion_state(
                    existing,
                    next_status=status_enum,
                    now=now,
                )
                if status_enum == SubcomponentStatus.complete and completed_at_val is not None:
                    existing.completed_at = completed_at_val
                session.add(existing)
                log_changes(
                    session,
                    entity_type="subcomponent",
                    entity_id=existing.subcomponent_id,
                    user_id=current_user.user_id,
                    action="update",
                    space_id=space_ctx.space_id,
                    changes={
                        "status": (before["status"], existing.status),
                        "priority": (before["priority"], existing.priority),
                        "due_date": (before["due_date"], existing.due_date),
                        "assignee": (before["assignee"], existing.assignee),
                        "assignee_user_soeid": (before["assignee_user_soeid"], existing.assignee_user_soeid),
                        "github_repo_url": (before["github_repo_url"], existing.github_repo_url),
                        "estimate_hours": (before["estimate_hours"], existing.estimate_hours),
                        "blocked": (before["blocked"], existing.blocked),
                        "blocker_note": (before["blocker_note"], existing.blocker_note),
                        "done_criteria": (before["done_criteria"], existing.done_criteria),
                        "completed_at": (before["completed_at"], existing.completed_at),
                    },
                    request_id=None,
                )
                commit_session(session)
                updated += 1
            else:
                resolved_assignee, resolved_assignee_user_soeid = _resolve_subcomponent_assignee(
                    assignee_input,
                    assignee_user_soeid,
                    current_user,
                )
                completed_at = completed_at_val if status_enum == SubcomponentStatus.complete and completed_at_val is not None else (
                    now if status_enum == SubcomponentStatus.complete else None
                )
                subcomponent = Subcomponent(
                    space_id=space_ctx.space_id,
                    project_id=project.project_id,
                    solution_id=solution.solution_id,
                    subcomponent_name=sub_name,
                    status=status_enum,
                    priority=priority_val,
                    due_date=due_val,
                    assignee=resolved_assignee,
                    assignee_user_soeid=resolved_assignee_user_soeid,
                    github_repo_url=github_repo_url,
                    estimate_hours=estimate_hours,
                    blocked=blocked_val,
                    blocker_note=blocker_note,
                    done_criteria=done_criteria,
                    completed_at=completed_at,
                )
                session.add(subcomponent)
                session.flush()
                log_changes(
                    session,
                    entity_type="subcomponent",
                    entity_id=subcomponent.subcomponent_id,
                    user_id=current_user.user_id,
                    action="create",
                    space_id=space_ctx.space_id,
                    changes={
                        "subcomponent_name": (None, subcomponent.subcomponent_name),
                        "status": (None, subcomponent.status),
                        "priority": (None, subcomponent.priority),
                        "due_date": (None, subcomponent.due_date),
                        "assignee": (None, subcomponent.assignee),
                        "assignee_user_soeid": (None, subcomponent.assignee_user_soeid),
                        "github_repo_url": (None, subcomponent.github_repo_url),
                        "estimate_hours": (None, subcomponent.estimate_hours),
                        "blocked": (None, subcomponent.blocked),
                        "blocker_note": (None, subcomponent.blocker_note),
                        "done_criteria": (None, subcomponent.done_criteria),
                        "completed_at": (None, subcomponent.completed_at),
                    },
                    request_id=None,
                )
                commit_session(session)
                created += 1
            if project_created_this_row:
                projects_by_name[project_name.lower()] = project
                projects_created += 1
            if solution_created_this_row:
                solutions_by_key[solution_key] = solution
                solutions_created += 1
        except ValueError as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")
        except Exception as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")

    if not dry_run:
        _publish_subcomponent_import(
            space_ctx.space_id,
            projects_created=projects_created,
            solutions_created=solutions_created,
        )
    return {
        "created": created,
        "updated": updated,
        "projects_created": projects_created,
        "solutions_created": solutions_created,
        "errors": errors,
        "total_rows": len(rows),
        "dry_run": dry_run,
    }


@router.get("/subcomponents/export")
def export_subcomponents(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    subcomponents = _subcomponent_query(session, space_ctx).order_by(Subcomponent.created_at.asc()).all()
    project_map = {project.project_id: project.project_name for project in _project_query(session, space_ctx)}
    solution_map = {
        solution.solution_id: (solution.solution_name, solution.version)
        for solution in _solution_query(session, space_ctx)
    }
    buffer = StringIO()
    fieldnames = [
        "project_name",
        "solution_name",
        "version",
        "subcomponent_name",
        "status",
        "priority",
        "due_date",
        "assignee",
        "assignee_user_soeid",
        "github_repo_url",
        "estimate_hours",
        "blocked",
        "blocker_note",
        "done_criteria",
        "completed_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for subcomponent in subcomponents:
        solution_name, solution_version = solution_map.get(subcomponent.solution_id, ("", ""))
        writer.writerow(
            {
                "project_name": project_map.get(subcomponent.project_id, ""),
                "solution_name": solution_name,
                "version": solution_version,
                "subcomponent_name": subcomponent.subcomponent_name,
                "status": subcomponent.status.value if hasattr(subcomponent.status, "value") else subcomponent.status,
                "priority": subcomponent.priority,
                "due_date": subcomponent.due_date.isoformat() if subcomponent.due_date else "",
                "assignee": subcomponent.assignee or "",
                "assignee_user_soeid": subcomponent.assignee_user_soeid or "",
                "github_repo_url": subcomponent.github_repo_url or "",
                "estimate_hours": subcomponent.estimate_hours if subcomponent.estimate_hours is not None else "",
                "blocked": subcomponent.blocked,
                "blocker_note": read_text_value(subcomponent.blocker_note) or "",
                "done_criteria": read_text_value(subcomponent.done_criteria) or "",
                "completed_at": subcomponent.completed_at.isoformat() if subcomponent.completed_at else "",
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename=\"subcomponents.csv\"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)
