from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Program, Project, Solution, Task
from ..schemas.agent import (
    AgentProgramRead,
    AgentProjectRead,
    AgentSolutionRead,
    AgentTaskRead,
)
from .programs import program_query
from .spaces import SpaceContext
from .work_items import (
    project_payload,
    project_query,
    solution_payload,
    solution_query,
    task_payload,
    task_query,
)


def _not_found(entity: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{entity.title()} not found",
        headers={"X-Error-Code": f"{entity.upper()}_NOT_FOUND"},
    )


def _with_visible_program(query, space_ctx: SpaceContext):
    return (
        query.join(Program, Program.program_id == Project.program_id)
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.deleted_at.is_(None))
    )


def get_agent_program(
    session: Session, program_id: str, space_ctx: SpaceContext
) -> AgentProgramRead:
    row = (
        program_query(session, space_ctx)
        .filter(Program.program_id == program_id)
        .first()
    )
    if row is None:
        raise _not_found("program")
    return AgentProgramRead.model_validate(row)


def get_agent_project(
    session: Session, project_id: str, space_ctx: SpaceContext
) -> AgentProjectRead:
    row = (
        _with_visible_program(project_query(session, space_ctx), space_ctx)
        .add_columns(Program.program_name)
        .filter(Project.project_id == project_id)
        .first()
    )
    if row is None:
        raise _not_found("project")
    project, program_name = row
    return AgentProjectRead.model_validate(
        project_payload(project, program_name=program_name)
    )


def get_agent_solution(
    session: Session, solution_id: str, space_ctx: SpaceContext
) -> AgentSolutionRead:
    row = (
        _with_visible_program(solution_query(session, space_ctx), space_ctx)
        .filter(Solution.solution_id == solution_id)
        .first()
    )
    if row is None:
        raise _not_found("solution")
    return AgentSolutionRead.model_validate(solution_payload(row))


def get_agent_task(
    session: Session, task_id: str, space_ctx: SpaceContext
) -> AgentTaskRead:
    row = (
        _with_visible_program(task_query(session, space_ctx), space_ctx)
        .add_columns(Solution.github_repo_url)
        .filter(Task.project_id == Project.project_id)
        .filter(Task.task_id == task_id)
        .first()
    )
    if row is None:
        raise _not_found("task")
    task, repo_url = row
    return AgentTaskRead.model_validate(task_payload(task, solution_repo_url=repo_url))
