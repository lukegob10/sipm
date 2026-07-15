#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_DIR = REPO_ROOT / "src" / "main"
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SIPM_COORDINATION_BACKEND", "memory")
os.environ.setdefault("SIPM_DISABLE_STARTUP", "true")
os.environ.setdefault("SIPM_DISABLE_THREADPOOL", "true")

from backend.app import deps as deps_module  # noqa: E402
from backend.app.models import (  # noqa: E402
    ApiToken,
    Base,
    Program,
    Project,
    Solution,
    Space,
    SpaceMembership,
    Task,
    User,
)
from backend.app.services.api_tokens import (  # noqa: E402
    TOKEN_PREFIX,
    hash_api_token,
)
from backend.app.utils.enums import (  # noqa: E402
    ProjectStatus,
    RagStatus,
    SolutionStatus,
    TaskStatus,
)
from backend.main import app  # noqa: E402


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _seed_data(
    session_factory,
    *,
    project_count: int,
    solutions_per_project: int,
    tasks_per_solution: int,
) -> tuple[str, str, str, str]:
    space_id = "benchmark-space"
    user_id = "benchmark-agent"
    raw_token = f"{TOKEN_PREFIX}benchmark-token"
    program_count = max(1, min(10, project_count))

    with session_factory() as session:
        session.add_all(
            [
                Space(
                    space_id=space_id,
                    name="Agent Benchmark Space",
                    slug="agent-benchmark-space",
                ),
                User(
                    user_id=user_id,
                    soeid="benchmark-agent",
                    email="benchmark-agent@example.com",
                    display_name="Benchmark Agent",
                    password_hash="not-used",
                    role="user",
                    is_active=True,
                    is_service_account=True,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                SpaceMembership(
                    space_id=space_id,
                    user_id=user_id,
                    role="member",
                    status="active",
                ),
                ApiToken(
                    user_id=user_id,
                    name="benchmark",
                    token_hash=hash_api_token(raw_token),
                    created_by_user_id=user_id,
                ),
            ]
        )

        programs = [
            Program(
                program_id=f"program-{index:03d}",
                space_id=space_id,
                program_name=f"Program {index:03d}",
            )
            for index in range(program_count)
        ]
        session.add_all(programs)

        projects: list[Project] = []
        solutions: list[Solution] = []
        tasks: list[Task] = []
        for project_index in range(project_count):
            project_id = f"project-{project_index:06d}"
            projects.append(
                Project(
                    project_id=project_id,
                    space_id=space_id,
                    program_id=programs[project_index % program_count].program_id,
                    project_name=f"Project {project_index:06d}",
                    status=ProjectStatus.active,
                    priority=(project_index % 5) + 1,
                )
            )
            for solution_index in range(solutions_per_project):
                solution_id = (
                    f"solution-{project_index:06d}-{solution_index:03d}"
                )
                solutions.append(
                    Solution(
                        solution_id=solution_id,
                        space_id=space_id,
                        project_id=project_id,
                        solution_name=f"Solution {solution_index:03d}",
                        version="1.0.0",
                        status=SolutionStatus.active,
                        rag_status=RagStatus.green,
                        priority=(solution_index % 5) + 1,
                    )
                )
                for task_index in range(tasks_per_solution):
                    tasks.append(
                        Task(
                            task_id=(
                                f"task-{project_index:06d}-"
                                f"{solution_index:03d}-{task_index:03d}"
                            ),
                            space_id=space_id,
                            project_id=project_id,
                            solution_id=solution_id,
                            task_name=f"Task {task_index:03d}",
                            status=TaskStatus.to_do,
                            priority=(task_index % 5) + 1,
                        )
                    )

        session.add_all(projects)
        session.add_all(solutions)
        session.add_all(tasks)
        session.commit()
        first_project = projects[0]
        first_project_id = first_project.project_id
        first_project_updated_at = first_project.updated_at.isoformat()

    return raw_token, space_id, first_project_id, first_project_updated_at


async def _measure_case(
    client: httpx.AsyncClient,
    *,
    name: str,
    method: str,
    path: str,
    headers: dict[str, str],
    iterations: int,
    query_counter: list[int],
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latencies_ms: list[float] = []
    query_counts: list[int] = []
    response_sizes: list[int] = []
    for _ in range(iterations):
        before_queries = query_counter[0]
        started = time.perf_counter()
        response = await client.request(
            method,
            path,
            headers=headers,
            json=json_body,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise RuntimeError(
                f"{name} returned {response.status_code}: {response.text}"
            )
        latencies_ms.append(elapsed_ms)
        query_counts.append(query_counter[0] - before_queries)
        response_sizes.append(len(response.content))

    return {
        "name": name,
        "method": method,
        "path": path,
        "iterations": iterations,
        "latency_ms": {
            "min": round(min(latencies_ms), 2),
            "p50": round(_percentile(latencies_ms, 0.50), 2),
            "p95": round(_percentile(latencies_ms, 0.95), 2),
            "max": round(max(latencies_ms), 2),
        },
        "queries": {
            "min": min(query_counts),
            "max": max(query_counts),
        },
        "response_bytes": {
            "min": min(response_sizes),
            "max": max(response_sizes),
        },
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sipm-agent-benchmark-") as temp_dir:
        db_path = Path(temp_dir) / "benchmark.db"
        engine = create_engine(
            f"sqlite+pysqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        Base.metadata.create_all(bind=engine)
        raw_token, space_id, project_id, project_updated_at = _seed_data(
            session_factory,
            project_count=args.projects,
            solutions_per_project=args.solutions_per_project,
            tasks_per_solution=args.tasks_per_solution,
        )

        query_counter = [0]

        @event.listens_for(engine, "before_cursor_execute")
        def _count_query(*_args):
            query_counter[0] += 1

        def _benchmark_db():
            with session_factory() as session:
                yield session

        app.dependency_overrides[deps_module.get_db] = _benchmark_db
        headers = {
            "Authorization": f"Bearer {raw_token}",
            "X-Space-Id": space_id,
        }
        cases = [
            {
                "name": "manifest",
                "method": "GET",
                "path": "/project-manager/api/agent/manifest",
            },
            {
                "name": "programs",
                "method": "GET",
                "path": "/project-manager/api/agent/programs",
            },
            {
                "name": "work_graph_default_page",
                "method": "GET",
                "path": "/project-manager/api/agent/work-graph?limit=50",
            },
            {
                "name": "work_graph_max_page",
                "method": "GET",
                "path": "/project-manager/api/agent/work-graph?limit=200",
            },
            {
                "name": "work_graph_project_detail",
                "method": "GET",
                "path": (
                    "/project-manager/api/agent/work-graph"
                    f"?project_id={project_id}&limit=1"
                ),
            },
            {
                "name": "validate_project_update",
                "method": "POST",
                "path": "/project-manager/api/agent/patches/validate",
                "json_body": {
                    "dry_run": True,
                    "operations": [
                        {
                            "client_operation_id": "benchmark-update",
                            "op": "update",
                            "entity": "project",
                            "id": project_id,
                            "if_updated_at": project_updated_at,
                            "fields": {"description": "Benchmark validation"},
                        }
                    ],
                },
            },
        ]

        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://benchmark",
                ) as client:
                    await client.get(
                        "/project-manager/api/agent/manifest",
                        headers=headers,
                    )
                    results = [
                        await _measure_case(
                            client,
                            name=case["name"],
                            method=case["method"],
                            path=case["path"],
                            headers=headers,
                            iterations=args.iterations,
                            query_counter=query_counter,
                            json_body=case.get("json_body"),
                        )
                        for case in cases
                    ]
        finally:
            app.dependency_overrides.clear()
            engine.dispose()

    return {
        "dataset": {
            "spaces": 1,
            "projects": args.projects,
            "solutions": args.projects * args.solutions_per_project,
            "tasks": (
                args.projects
                * args.solutions_per_project
                * args.tasks_per_solution
            ),
        },
        "environment": {
            "database": "temporary SQLite",
            "transport": "in-process ASGI",
            "iterations_per_case": args.iterations,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure repeatable local SIPM Agent API baselines."
    )
    parser.add_argument("--projects", type=int, default=250)
    parser.add_argument("--solutions-per-project", type=int, default=2)
    parser.add_argument("--tasks-per-solution", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    if min(
        args.projects,
        args.solutions_per_project,
        args.tasks_per_solution,
        args.iterations,
    ) < 1:
        parser.error("all numeric arguments must be at least 1")

    print(json.dumps(asyncio.run(_run(args)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
