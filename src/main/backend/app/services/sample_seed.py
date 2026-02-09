import os
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus
from ..models import Project, Solution, Subcomponent
from .spaces import get_or_create_default_space


def seed_sample_data(session: Session) -> None:
    """
    Idempotent sample seed for local/dev use.
    Controlled by env var SAMPLE_SEED=true.
    """
    if os.getenv("SAMPLE_SEED", "").lower() != "true":
        return

    now = datetime.now(timezone.utc)
    default_space = get_or_create_default_space(session)
    default_space_id = default_space.space_id
    project = (
        session.query(Project)
        .filter(Project.project_name == "Sample Project")
        .filter(Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        project = Project(
            space_id=default_space_id,
            project_name="Sample Project",
            status=ProjectStatus.active,
            description="Demo project for Jira-lite",
            sponsor="Sample Sponsor",
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.commit()
        session.refresh(project)
    elif not project.space_id:
        project.space_id = default_space_id
        project.updated_at = now
        session.add(project)
        session.commit()
        session.refresh(project)

    solution = (
        session.query(Solution)
        .filter(Solution.project_id == project.project_id)
        .filter(Solution.solution_name == "Demo Solution")
        .filter(Solution.version == "0.1.0")
        .filter(Solution.deleted_at.is_(None))
        .first()
    )
    if not solution:
        solution = Solution(
            space_id=default_space_id,
            project_id=project.project_id,
            solution_name="Demo Solution",
            version="0.1.0",
            status=SolutionStatus.active,
            priority=2,
            due_date=date.today(),
            current_phase="poc",
            description="Demo solution for seeding",
            owner="Sample Owner",
            assignee="Sample Assignee",
            created_at=now,
            updated_at=now,
        )
        session.add(solution)
        session.commit()
        session.refresh(solution)
    elif not solution.space_id:
        solution.space_id = default_space_id
        solution.updated_at = now
        session.add(solution)
        session.commit()
        session.refresh(solution)

    # Subcomponents seed
    existing = (
        session.query(Subcomponent)
        .filter(Subcomponent.solution_id == solution.solution_id)
        .filter(Subcomponent.deleted_at.is_(None))
        .all()
    )
    if existing:
        updated = False
        for row in existing:
            if not row.space_id:
                row.space_id = default_space_id
                row.updated_at = now
                session.add(row)
                updated = True
        if updated:
            session.commit()
        return

    subs = [
        Subcomponent(
            space_id=default_space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            subcomponent_name="Define RBAC roles",
            status=SubcomponentStatus.in_progress,
            priority=1,
            due_date=date.today(),
            assignee="Engineer A",
            created_at=now,
            updated_at=now,
        ),
        Subcomponent(
            space_id=default_space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            subcomponent_name="Set up audit logging",
            status=SubcomponentStatus.to_do,
            priority=2,
            due_date=None,
            assignee="Engineer B",
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(subs)
    session.commit()
