#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_DIR = REPO_ROOT / "src" / "main"
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SIPM_COORDINATION_BACKEND", "memory")
os.environ.setdefault("SIPM_DISABLE_STARTUP", "true")
os.environ.setdefault("SIPM_KEEPALIVE_TASK", "false")
os.environ.setdefault("SIPM_BCRYPT_ROUNDS", "4")

from backend.app.auth.auth import hash_password  # noqa: E402
from backend.app.models import (  # noqa: E402
    Base,
    Program,
    Project,
    Solution,
    Space,
    SpaceMembership,
    Task,
    User,
    UserPreference,
    UserTaskState,
)
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus, TaskStatus  # noqa: E402
import backend.app.db.db as db_module  # noqa: E402
from backend.main import app  # noqa: E402


DEMO_SOEID = "developer"
DEMO_PASSWORD = "Developer123!"


def configure_sqlite_runtime(temp_dir: Path):
    db_path = temp_dir / "developer-mode-demo.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine


def seed_demo() -> None:
    today = date.today()
    with db_module.SessionLocal() as session:
        user = User(
            user_id="demo-developer",
            soeid=DEMO_SOEID,
            email="developer@example.com",
            display_name="Alex Developer",
            password_hash=hash_password(DEMO_PASSWORD),
            role="user",
            is_active=True,
            team_tag="Platform Engineering",
        )
        teammate = User(
            user_id="demo-teammate",
            soeid="product",
            email="product@example.com",
            display_name="Morgan Product",
            password_hash=hash_password(DEMO_PASSWORD),
            role="user",
            is_active=True,
            team_tag="Product",
        )
        space = Space(
            space_id="developer-mode-demo",
            name="Developer Mode Demo",
            slug="developer-mode-demo",
            owner_user_id=user.user_id,
        )
        memberships = [
            SpaceMembership(space_id=space.space_id, user_id=user.user_id, role="space_admin", status="active"),
            SpaceMembership(space_id=space.space_id, user_id=teammate.user_id, role="member", status="active"),
        ]
        preference = UserPreference(
            user_id=user.user_id,
            developer_mode_enabled=True,
            theme="dark",
        )
        program = Program(
            program_id="program-developer-experience",
            space_id=space.space_id,
            program_name="Developer Experience",
            description="Make SIPM useful in the daily developer workflow.",
        )
        project = Project(
            project_id="project-developer-mode",
            space_id=space.space_id,
            program_id=program.program_id,
            project_name="SIPM Developer Mode",
            status=ProjectStatus.active,
            description="An opt-in execution lens over canonical SIPM Tasks.",
            sponsor="Morgan Product",
            sponsor_user_soeid=teammate.soeid,
            owner=user.display_name,
            owner_user_soeid=user.soeid,
            priority=1,
        )
        solution = Solution(
            solution_id="solution-my-work",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_name="My Work experience",
            version="0.1.0",
            status=SolutionStatus.active,
            rag_status=RagStatus.green,
            priority=1,
            due_date=today + timedelta(days=18),
            description="Personal execution view backed by shared Tasks.",
            success_criteria="Developers can focus work without creating a second task system.",
            github_repo_url="https://github.com/example/sipm",
            owner=user.display_name,
            owner_user_soeid=user.soeid,
            assignee=user.display_name,
            assignee_user_soeid=user.soeid,
        )
        repository_solution = Solution(
            solution_id="solution-payments-platform",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_name="Payments platform modernization",
            version="1.4.0",
            status=SolutionStatus.active,
            rag_status=RagStatus.amber,
            priority=2,
            due_date=today + timedelta(days=45),
            description="Modernize settlement services while preserving developer tooling standards.",
            success_criteria="Repository ownership and delivery context are visible in one workspace index.",
            github_repo_url="https://github.com/example/bank-core",
            owner=teammate.display_name,
            owner_user_soeid=teammate.soeid,
            assignee=teammate.display_name,
            assignee_user_soeid=teammate.soeid,
        )
        tasks = [
            Task(
                task_id="task-api-contract",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Resolve completion-report API contract",
                description="Agree on where implementation summaries and artifact links belong before extending the agent skill.",
                done_criteria="The shared completion result has an explicit owner, schema, and permission model.",
                status=TaskStatus.in_progress,
                priority=1,
                due_date=today + timedelta(days=1),
                assignee=user.display_name,
                assignee_user_soeid=user.soeid,
                blocked=True,
                blocker_note="Waiting for product decision on comments versus a completion summary field.",
                estimate_hours=3,
            ),
            Task(
                task_id="task-queue-ordering",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Add private queue ordering",
                description="Persist each developer's queue order separately from shared Task status.",
                done_criteria="Queue changes stay private and never appear as shared Task activity.",
                status=TaskStatus.in_progress,
                priority=1,
                due_date=today + timedelta(days=4),
                assignee=user.display_name,
                assignee_user_soeid=user.soeid,
                estimate_hours=6,
            ),
            Task(
                task_id="task-keyboard-flow",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Add keyboard-first queue navigation",
                description="Support fast selection and status updates without replacing the existing Tasks workbench.",
                done_criteria="Arrow keys move selection and actions preserve focus.",
                status=TaskStatus.to_do,
                priority=2,
                due_date=today + timedelta(days=8),
                assignee=user.display_name,
                assignee_user_soeid=user.soeid,
                estimate_hours=5,
            ),
            Task(
                task_id="task-agent-checkout",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Design agent checkout work package",
                description="Export a canonical Task snapshot into a local folder without turning SIPM into an execution host.",
                done_criteria="The package contains TASK.md and sync metadata, but never credentials.",
                status=TaskStatus.to_do,
                priority=2,
                due_date=today + timedelta(days=12),
                assignee=user.display_name,
                assignee_user_soeid=user.soeid,
                github_repo_url="https://github.com/example/sipm-agent-skill",
                estimate_hours=5,
            ),
            Task(
                task_id="task-mobile-layout",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Polish compact-screen task detail",
                description="Review after the desktop interaction model has stabilized.",
                done_criteria="The queue and detail pane remain usable below 760px.",
                status=TaskStatus.on_hold,
                priority=3,
                due_date=today + timedelta(days=20),
                assignee=user.display_name,
                assignee_user_soeid=user.soeid,
            ),
            Task(
                task_id="task-completed-demo",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Document compatibility boundaries",
                description="Keep Deliverables, Tasks, routes, and existing user defaults intact.",
                done_criteria="Compatibility requirements are reviewed.",
                status=TaskStatus.complete,
                priority=1,
                assignee=user.display_name,
                assignee_user_soeid=user.soeid,
            ),
            Task(
                task_id="task-teammate",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=solution.solution_id,
                task_name="Prepare pilot feedback questions",
                status=TaskStatus.to_do,
                priority=2,
                assignee=teammate.display_name,
                assignee_user_soeid=teammate.soeid,
            ),
            Task(
                task_id="task-bank-settlement",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=repository_solution.solution_id,
                task_name="Refactor settlement boundaries",
                description="Separate settlement orchestration from bank-specific adapters.",
                status=TaskStatus.in_progress,
                priority=1,
                assignee=teammate.display_name,
                assignee_user_soeid=teammate.soeid,
            ),
            Task(
                task_id="task-bank-dev-tooling",
                space_id=space.space_id,
                project_id=project.project_id,
                solution_id=repository_solution.solution_id,
                task_name="Reuse SIPM repository conventions",
                description="Apply the shared developer workflow conventions to the payments project.",
                status=TaskStatus.to_do,
                priority=2,
                assignee=teammate.display_name,
                assignee_user_soeid=teammate.soeid,
                github_repo_url="https://github.com/example/sipm",
            ),
        ]
        queue_states = [
            UserTaskState(
                user_id=user.user_id,
                space_id=space.space_id,
                task_id="task-queue-ordering",
                sort_rank=100,
            ),
            UserTaskState(
                user_id=user.user_id,
                space_id=space.space_id,
                task_id="task-keyboard-flow",
                sort_rank=200,
            ),
            UserTaskState(
                user_id=user.user_id,
                space_id=space.space_id,
                task_id="task-agent-checkout",
                sort_rank=300,
            ),
            UserTaskState(
                user_id=user.user_id,
                space_id=space.space_id,
                task_id="task-mobile-layout",
                sort_rank=400,
            ),
        ]
        session.add_all([user, teammate, space, *memberships, preference, program, project, solution, repository_solution, *tasks, *queue_states])
        session.commit()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sipm-developer-mode-demo-") as temp_dir:
        engine = configure_sqlite_runtime(Path(temp_dir))
        seed_demo()
        port = int(os.getenv("SIPM_DEVELOPER_MODE_DEMO_PORT", "8011"))
        print(f"Developer Mode demo: http://127.0.0.1:{port}/project-manager/")
        print(f"Sign in with SOEID '{DEMO_SOEID}' and password '{DEMO_PASSWORD}'.")
        try:
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        finally:
            engine.dispose()
            db_module.engine = None
            db_module.SessionLocal = None


if __name__ == "__main__":
    main()
