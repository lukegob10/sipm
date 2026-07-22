from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "skills" / "sipm-agent" / "scripts" / "sipm_agent.py"
SPEC = importlib.util.spec_from_file_location("sipm_agent_skill", SCRIPT_PATH)
assert SPEC and SPEC.loader
sipm_agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sipm_agent)


def _records() -> tuple[dict, dict, dict]:
    task = {
        "task_id": "task-1",
        "project_id": "project-1",
        "solution_id": "solution-1",
        "task_name": "Implement assigned work",
        "status": "in_progress",
        "priority": 2,
        "due_date": "2026-08-01",
        "assignee": "Developer",
        "assignee_user_soeid": "dev1",
        "description": "Implement the API and skill workflow.",
        "blocked": True,
        "blocker_note": "Waiting for credentials",
        "acceptance_criteria": "Assigned work can be checked out.",
        "done_criteria": "Focused tests pass.",
        "effective_github_repo_url": "https://github.com/example/sipm",
    }
    solution = {
        "solution_id": "solution-1",
        "project_id": "project-1",
        "solution_name": "Developer Mode",
    }
    project = {
        "project_id": "project-1",
        "program_id": "program-1",
        "program_name": "SIPM",
        "project_name": "Project Manager",
    }
    return task, solution, project


def test_task_checkout_writes_a_complete_read_only_packet(tmp_path):
    task, solution, project = _records()
    files = sipm_agent.build_task_checkout_files(
        space_id="space-1",
        task=task,
        solution=solution,
        project=project,
    )

    result = sipm_agent.write_task_checkout(str(tmp_path / "checkout"), files)

    target = Path(result["checkout_path"])
    assert result["files"] == ["TASK.md", "context.json", "task.json"]
    assert json.loads((target / "task.json").read_text(encoding="utf-8")) == task
    context = json.loads((target / "context.json").read_text(encoding="utf-8"))
    assert context["space_id"] == "space-1"
    assert context["program"] == {
        "program_id": "program-1",
        "program_name": "SIPM",
    }
    markdown = (target / "TASK.md").read_text(encoding="utf-8")
    assert "Read-only checkout from SIPM" in markdown
    assert "https://github.com/example/sipm" in markdown
    assert "Waiting for credentials" in markdown
    assert "Assigned work can be checked out." in markdown


def test_task_checkout_refuses_to_overwrite_a_nonempty_folder(tmp_path):
    target = tmp_path / "checkout"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(SystemExit, match="must be empty"):
        sipm_agent.write_task_checkout(str(target), {"TASK.md": "new"})


def test_task_checkout_rejects_mismatched_hierarchy():
    task, solution, project = _records()
    solution["project_id"] = "different-project"

    with pytest.raises(SystemExit, match="Solution and project context do not match"):
        sipm_agent.build_task_checkout_files(
            space_id="space-1",
            task=task,
            solution=solution,
            project=project,
        )


def test_checkout_task_fetches_direct_context_and_returns_repo(tmp_path):
    task, solution, project = _records()

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_detail(self, entity_type, entity_id, *, space_id):
            self.calls.append((entity_type, entity_id, space_id))
            return {
                "task": task,
                "solution": solution,
                "project": project,
            }[entity_type]

    client = FakeClient()
    result = sipm_agent.checkout_task(
        client,
        space_id="space-1",
        task_id="task-1",
        output_dir=str(tmp_path / "checkout"),
    )

    assert client.calls == [
        ("task", "task-1", "space-1"),
        ("solution", "solution-1", "space-1"),
        ("project", "project-1", "space-1"),
    ]
    assert result["task_id"] == "task-1"
    assert result["github_repo_url"] == "https://github.com/example/sipm"
