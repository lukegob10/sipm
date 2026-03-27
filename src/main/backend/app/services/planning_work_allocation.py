from datetime import date, datetime, timezone
import os
import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Project, Solution, SpaceMembership, Subcomponent, Team, User
from ..utils.enums import ProjectStatus, SolutionStatus
from .spaces import SpaceContext

WORK_ALLOCATION_DOMAIN = os.getenv("DOMAIN_NAME", "local.invalid")
WORK_ALLOCATION_PROJECT_PREFIX = "Work Allocation Board"
WORK_ALLOCATION_SOLUTION_NAME = "Backlog"
WORK_ALLOCATION_SOLUTION_VERSION = "1.0.0"
WORK_ALLOCATION_DEFAULT_ASSIGNEE = "Unassigned"


def active_space_user_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(User)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(User.is_active == True)
    )


def _work_allocation_project_name(space_ctx: SpaceContext) -> str:
    token = (space_ctx.space_id or "default").strip()[:8] or "default"
    return f"{WORK_ALLOCATION_PROJECT_PREFIX} [{token}]"


def _project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
    )


def board_solution(session: Session, space_ctx: SpaceContext) -> Solution:
    project_name = _work_allocation_project_name(space_ctx)
    now = datetime.now(timezone.utc)
    changed = False

    project = (
        session.query(Project)
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.project_name == project_name)
        .first()
    )
    if not project:
        project = Project(
            space_id=space_ctx.space_id,
            project_name=project_name,
            status=ProjectStatus.not_started,
            sponsor="Planning Board",
            priority=3,
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.flush()
        changed = True
    elif project.deleted_at is not None:
        project.deleted_at = None
        project.updated_at = now
        session.add(project)
        session.flush()
        changed = True

    solution = (
        session.query(Solution)
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.project_id == project.project_id)
        .filter(Solution.solution_name == WORK_ALLOCATION_SOLUTION_NAME)
        .filter(Solution.version == WORK_ALLOCATION_SOLUTION_VERSION)
        .first()
    )
    if not solution:
        solution = Solution(
            space_id=space_ctx.space_id,
            project_id=project.project_id,
            solution_name=WORK_ALLOCATION_SOLUTION_NAME,
            version=WORK_ALLOCATION_SOLUTION_VERSION,
            status=SolutionStatus.not_started,
            priority=3,
            owner="Planning Board",
            assignee=WORK_ALLOCATION_DEFAULT_ASSIGNEE,
            created_at=now,
            updated_at=now,
        )
        session.add(solution)
        session.flush()
        changed = True
    elif solution.deleted_at is not None:
        solution.deleted_at = None
        solution.updated_at = now
        session.add(solution)
        session.flush()
        changed = True

    if changed:
        session.commit()
        session.refresh(solution)
    return solution


def planning_task_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Subcomponent)
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(Subcomponent.space_id == space_ctx.space_id)
    )


def task_fte_months(subcomponent: Subcomponent, *, hours_per_fte_month: float) -> float:
    hours = int(subcomponent.capacity_hours or subcomponent.estimate_hours or 0)
    if hours <= 0:
        return 0.25
    return round(max(float(hours), 0.0) / hours_per_fte_month, 3)


def month_from_token(month_token: str) -> date:
    token = str(month_token or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must use YYYY-MM")
    return date.fromisoformat(f"{token}-01")


def month_token(value: Optional[date]) -> str:
    if value is None:
        today = datetime.now(timezone.utc).date()
        return f"{today.year:04d}-{today.month:02d}"
    return f"{value.year:04d}-{value.month:02d}"


def active_person_by_soeid(session: Session, soeid: str, space_ctx: SpaceContext) -> User:
    norm = str(soeid or "").strip().lower()
    if not norm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    user = active_space_user_query(session, space_ctx).filter(func.lower(User.soeid) == norm).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return user


def team_name_to_id_map(session: Session, space_ctx: SpaceContext) -> dict[str, str]:
    rows = (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
        .all()
    )
    return {str(row.name or "").strip().lower(): row.team_id for row in rows if row.name}


def team_display_name(session: Session, team_id: Optional[str], space_ctx: SpaceContext) -> Optional[str]:
    if not team_id:
        return None
    team = (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
        .filter(Team.team_id == team_id)
        .first()
    )
    return team.name if team else None


def _normalize_soeid_base(name: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())
    return raw[:14] or "person"


def next_available_soeid(session: Session, name: str) -> str:
    base = _normalize_soeid_base(name)
    candidate = base
    counter = 1
    while session.query(User).filter(func.lower(User.soeid) == candidate).first():
        counter += 1
        candidate = f"{base[:10]}{counter:02d}"
    return candidate


def ensure_membership(session: Session, user_id: str, space_id: str) -> None:
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == user_id)
        .first()
    )
    if not membership:
        membership = SpaceMembership(
            space_id=space_id,
            user_id=user_id,
            role="member",
            status="active",
        )
        session.add(membership)
        return
    membership.deleted_at = None
    membership.status = "active"
    if not (membership.role or "").strip():
        membership.role = "member"
    session.add(membership)


__all__ = [
    "WORK_ALLOCATION_DEFAULT_ASSIGNEE",
    "WORK_ALLOCATION_DOMAIN",
    "active_person_by_soeid",
    "active_space_user_query",
    "board_solution",
    "ensure_membership",
    "month_from_token",
    "month_token",
    "next_available_soeid",
    "planning_task_query",
    "task_fte_months",
    "team_display_name",
    "team_name_to_id_map",
]
