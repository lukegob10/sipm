from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Program, Project, Solution, Subcomponent
from ..schemas.agent import (
    AgentProjectNode,
    AgentSolutionNode,
    AgentSubcomponentNode,
    AgentWorkGraphRead,
)
from ..services.spaces import SpaceContext
from ..utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus


def _enum_value(value: object) -> str:
    return str(value.value if hasattr(value, "value") else value)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def build_work_graph(
    session: Session,
    space_ctx: SpaceContext,
    *,
    project_id: str | None = None,
    solution_id: str | None = None,
    status: str | None = None,
    owner_user_soeid: str | None = None,
    assignee_user_soeid: str | None = None,
    updated_since: datetime | None = None,
    limit: int = 50,
) -> AgentWorkGraphRead:
    updated_since_value = _utc_naive(updated_since) if updated_since else None
    query = (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )
    if project_id:
        query = query.filter(Project.project_id == project_id)
    if solution_id:
        query = query.join(Solution, Solution.project_id == Project.project_id).filter(
            Solution.solution_id == solution_id,
            Solution.deleted_at.is_(None),
            Solution.space_id == space_ctx.space_id,
        )
    if status:
        status_filters = []
        for enum_type, column in (
            (ProjectStatus, Project.status),
            (SolutionStatus, Solution.status),
            (SubcomponentStatus, Subcomponent.status),
        ):
            try:
                status_filters.append(column == enum_type(status))
            except ValueError:
                pass
        if not status_filters:
            return AgentWorkGraphRead(space_id=space_ctx.space_id, records=[])
        query = (
            query.outerjoin(Solution, Solution.project_id == Project.project_id)
            .outerjoin(Subcomponent, Subcomponent.project_id == Project.project_id)
            .filter(or_(*status_filters))
        )
    if owner_user_soeid:
        query = query.join(Solution, Solution.project_id == Project.project_id).filter(
            Solution.deleted_at.is_(None),
            Solution.space_id == space_ctx.space_id,
            Solution.owner_user_soeid == owner_user_soeid,
        )
    if assignee_user_soeid:
        query = query.join(
            Subcomponent, Subcomponent.project_id == Project.project_id
        ).filter(
            Subcomponent.deleted_at.is_(None),
            Subcomponent.space_id == space_ctx.space_id,
            Subcomponent.assignee_user_soeid == assignee_user_soeid,
        )
    if updated_since_value:
        query = query.outerjoin(
            Solution, Solution.project_id == Project.project_id
        ).outerjoin(
            Subcomponent, Subcomponent.project_id == Project.project_id
        ).filter(
            or_(
                Project.updated_at >= updated_since_value,
                Solution.updated_at >= updated_since_value,
                Subcomponent.updated_at >= updated_since_value,
            )
        )

    projects = (
        query.distinct()
        .order_by(Project.updated_at.desc(), Project.project_name.asc())
        .limit(limit)
        .all()
    )
    project_ids = [project.project_id for project in projects]
    if not project_ids:
        return AgentWorkGraphRead(space_id=space_ctx.space_id, records=[])

    solutions = (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.project_id.in_(project_ids))
        .order_by(Solution.solution_name.asc(), Solution.version.asc())
        .all()
    )
    solution_ids = [solution.solution_id for solution in solutions]
    subcomponents = []
    if solution_ids:
        subcomponents = (
            session.query(Subcomponent)
            .filter(Subcomponent.deleted_at.is_(None))
            .filter(Subcomponent.space_id == space_ctx.space_id)
            .filter(Subcomponent.solution_id.in_(solution_ids))
            .order_by(Subcomponent.subcomponent_name.asc())
            .all()
        )

    subcomponents_by_solution: dict[str, list[AgentSubcomponentNode]] = {}
    for subcomponent in subcomponents:
        subcomponents_by_solution.setdefault(subcomponent.solution_id, []).append(
            AgentSubcomponentNode(
                subcomponent_id=subcomponent.subcomponent_id,
                project_id=subcomponent.project_id,
                solution_id=subcomponent.solution_id,
                subcomponent_name=subcomponent.subcomponent_name,
                status=_enum_value(subcomponent.status),
                priority=subcomponent.priority,
                assignee=subcomponent.assignee,
                assignee_user_soeid=subcomponent.assignee_user_soeid,
                updated_at=subcomponent.updated_at,
            )
        )

    solutions_by_project: dict[str, list[AgentSolutionNode]] = {}
    for solution in solutions:
        solutions_by_project.setdefault(solution.project_id, []).append(
            AgentSolutionNode(
                solution_id=solution.solution_id,
                project_id=solution.project_id,
                solution_name=solution.solution_name,
                version=solution.version,
                status=_enum_value(solution.status),
                rag_status=_enum_value(solution.rag_status),
                priority=solution.priority,
                owner=solution.owner,
                owner_user_soeid=solution.owner_user_soeid,
                assignee=solution.assignee,
                assignee_user_soeid=solution.assignee_user_soeid,
                updated_at=solution.updated_at,
                subcomponents=subcomponents_by_solution.get(solution.solution_id, []),
            )
        )

    program_names = {
        row.program_id: row.program_name
        for row in (
            session.query(Program)
            .filter(Program.deleted_at.is_(None))
            .filter(Program.space_id == space_ctx.space_id)
            .filter(Program.program_id.in_([project.program_id for project in projects]))
            .all()
        )
    }

    records = [
        AgentProjectNode(
            project_id=project.project_id,
            program_id=project.program_id,
            program_name=program_names.get(project.program_id),
            project_name=project.project_name,
            status=_enum_value(project.status),
            priority=project.priority,
            sponsor=project.sponsor,
            sponsor_user_soeid=project.sponsor_user_soeid,
            updated_at=project.updated_at,
            solutions=solutions_by_project.get(project.project_id, []),
        )
        for project in projects
    ]
    return AgentWorkGraphRead(space_id=space_ctx.space_id, records=records)
