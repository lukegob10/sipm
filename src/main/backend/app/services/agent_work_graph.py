from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models import Program, Project, Solution, Task
from ..schemas.agent import (
    AgentProgramNode,
    AgentProjectNode,
    AgentSolutionNode,
    AgentTaskNode,
    AgentWorkGraphRead,
)
from ..services.spaces import SpaceContext
from ..services.agent_pagination import decode_cursor, encode_cursor
from ..services.work_items import project_payload, solution_payload, task_payload
from ..utils.enums import ProjectStatus, SolutionStatus, TaskStatus


def _enum_value(value: object) -> str:
    return str(value.value if hasattr(value, "value") else value)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


GRAPH_CURSOR_SCOPE = "agent_work_graph_v2"


def _program_nodes(
    session: Session, space_ctx: SpaceContext, *, projection: str
) -> list[AgentProgramNode]:
    programs = (
        session.query(Program)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .order_by(Program.program_name.asc())
        .all()
    )
    return [
        AgentProgramNode(
            program_id=program.program_id,
            program_name=program.program_name,
            description=program.description,
            created_at=program.created_at if projection == "full" else None,
            updated_at=program.updated_at,
        )
        for program in programs
    ]


def build_work_graph(
    session: Session,
    space_ctx: SpaceContext,
    *,
    project_id: str | None = None,
    solution_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
    owner_user_soeid: str | None = None,
    assignee_user_soeid: str | None = None,
    updated_since: datetime | None = None,
    projection: str = "summary",
    cursor: str | None = None,
    limit: int = 50,
) -> AgentWorkGraphRead:
    programs = _program_nodes(session, space_ctx, projection=projection)
    updated_since_value = _utc_naive(updated_since) if updated_since else None
    query = (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )
    if project_id:
        query = query.filter(Project.project_id == project_id)
    active_solutions = session.query(Solution.project_id).filter(
        Solution.deleted_at.is_(None), Solution.space_id == space_ctx.space_id
    )
    active_tasks = session.query(Task.project_id).filter(
        Task.deleted_at.is_(None), Task.space_id == space_ctx.space_id
    )
    if solution_id:
        query = query.filter(
            Project.project_id.in_(
                active_solutions.filter(Solution.solution_id == solution_id)
            )
        )
    if task_id:
        query = query.filter(
            Project.project_id.in_(active_tasks.filter(Task.task_id == task_id))
        )
    if status:
        status_filters = []
        for enum_type, column in (
            (ProjectStatus, Project.status),
            (SolutionStatus, Solution.status),
            (TaskStatus, Task.status),
        ):
            try:
                if column is Project.status:
                    status_filters.append(column == enum_type(status))
                elif column is Solution.status:
                    status_filters.append(
                        Project.project_id.in_(
                            active_solutions.filter(column == enum_type(status))
                        )
                    )
                else:
                    status_filters.append(
                        Project.project_id.in_(
                            active_tasks.filter(column == enum_type(status))
                        )
                    )
            except ValueError:
                pass
        if not status_filters:
            return AgentWorkGraphRead(
                space_id=space_ctx.space_id,
                projection=projection,
                programs=programs,
                records=[],
            )
        query = query.filter(or_(*status_filters))
    if owner_user_soeid:
        query = query.filter(
            Project.project_id.in_(
                active_solutions.filter(Solution.owner_user_soeid == owner_user_soeid)
            )
        )
    if assignee_user_soeid:
        query = query.filter(
            Project.project_id.in_(
                active_tasks.filter(Task.assignee_user_soeid == assignee_user_soeid)
            )
        )
    if updated_since_value:
        query = query.filter(
            or_(
                Project.updated_at >= updated_since_value,
                Project.project_id.in_(
                    active_solutions.filter(Solution.updated_at >= updated_since_value)
                ),
                Project.project_id.in_(
                    active_tasks.filter(Task.updated_at >= updated_since_value)
                ),
            )
        )

    cursor_filters = {
        "space_id": space_ctx.space_id,
        "project_id": project_id,
        "solution_id": solution_id,
        "task_id": task_id,
        "status": status,
        "owner_user_soeid": owner_user_soeid,
        "assignee_user_soeid": assignee_user_soeid,
        "updated_since": updated_since_value,
        "projection": projection,
    }
    if cursor:
        cursor_at, cursor_id = decode_cursor(
            cursor, scope=GRAPH_CURSOR_SCOPE, filters=cursor_filters
        )
        cursor_at = _utc_naive(cursor_at)
        query = query.filter(
            or_(
                Project.updated_at < cursor_at,
                and_(Project.updated_at == cursor_at, Project.project_id < cursor_id),
            )
        )

    projects = (
        query.order_by(Project.updated_at.desc(), Project.project_id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(projects) > limit
    projects = projects[:limit]
    next_cursor = None
    if has_more and projects:
        next_cursor = encode_cursor(
            scope=GRAPH_CURSOR_SCOPE,
            filters=cursor_filters,
            ordered_at=projects[-1].updated_at,
            ordered_id=projects[-1].project_id,
        )
    project_ids = [project.project_id for project in projects]
    if not project_ids:
        return AgentWorkGraphRead(
            space_id=space_ctx.space_id,
            projection=projection,
            programs=programs,
            records=[],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    solutions = (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.project_id.in_(project_ids))
        .order_by(Solution.solution_name.asc(), Solution.version.asc())
        .all()
    )
    solution_ids = [solution.solution_id for solution in solutions]
    tasks = []
    if solution_ids:
        tasks = (
            session.query(Task)
            .filter(Task.deleted_at.is_(None))
            .filter(Task.space_id == space_ctx.space_id)
            .filter(Task.solution_id.in_(solution_ids))
            .order_by(Task.task_name.asc())
            .all()
        )

    tasks_by_solution: dict[str, list[AgentTaskNode]] = {}
    solution_repo_urls = {
        solution.solution_id: solution.github_repo_url for solution in solutions
    }
    for task in tasks:
        if projection == "full":
            tasks_by_solution.setdefault(task.solution_id, []).append(
                AgentTaskNode(
                    **task_payload(
                        task,
                        solution_repo_url=solution_repo_urls.get(task.solution_id),
                    )
                )
            )
            continue
        tasks_by_solution.setdefault(task.solution_id, []).append(
            AgentTaskNode(
                task_id=task.task_id,
                project_id=task.project_id,
                solution_id=task.solution_id,
                task_name=task.task_name,
                status=_enum_value(task.status),
                priority=task.priority,
                assignee=task.assignee,
                assignee_user_soeid=task.assignee_user_soeid,
                updated_at=task.updated_at,
            )
        )

    solutions_by_project: dict[str, list[AgentSolutionNode]] = {}
    for solution in solutions:
        if projection == "full":
            solutions_by_project.setdefault(solution.project_id, []).append(
                AgentSolutionNode(
                    **solution_payload(solution),
                    tasks=tasks_by_solution.get(solution.solution_id, []),
                )
            )
            continue
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
                tasks=tasks_by_solution.get(solution.solution_id, []),
            )
        )

    program_names = {
        row.program_id: row.program_name
        for row in (
            session.query(Program)
            .filter(Program.deleted_at.is_(None))
            .filter(Program.space_id == space_ctx.space_id)
            .filter(
                Program.program_id.in_([project.program_id for project in projects])
            )
            .all()
        )
    }

    records = []
    for project in projects:
        if projection == "full":
            records.append(
                AgentProjectNode(
                    **project_payload(
                        project, program_name=program_names.get(project.program_id)
                    ),
                    solutions=solutions_by_project.get(project.project_id, []),
                )
            )
            continue
        records.append(
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
        )
    return AgentWorkGraphRead(
        space_id=space_ctx.space_id,
        projection=projection,
        programs=programs,
        records=records,
        next_cursor=next_cursor,
        has_more=has_more,
    )
