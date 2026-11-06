from datetime import datetime, timezone

import pytest

from backend.app.models import Program, Project, Solution, Task


@pytest.mark.anyio
@pytest.mark.parametrize("hidden_parent", ["deleted", "other-space"])
async def test_repository_inventory_excludes_solutions_with_invisible_projects(
    client, db_sessionmaker, hidden_parent
):
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", space_id="test-space", program_name="Program"))
        session.add_all([
            Project(project_id="visible", program_id="program", space_id="test-space", project_name="Visible"),
            Project(
                project_id="hidden", program_id="program", project_name="Hidden",
                space_id="other-space" if hidden_parent == "other-space" else "test-space",
                deleted_at=datetime.now(timezone.utc) if hidden_parent == "deleted" else None,
            ),
        ])
        session.add_all([
            Solution(
                solution_id="visible", project_id="visible", space_id="test-space", solution_name="Visible",
                github_repo_url="https://github.com/example/visible",
            ),
            Solution(
                solution_id="hidden", project_id="hidden", space_id="test-space", solution_name="Hidden",
                github_repo_url="https://github.com/example/hidden",
            ),
        ])
        session.add(Task(
            task_id="hidden", solution_id="hidden", project_id="hidden", space_id="test-space", task_name="Hidden",
            github_repo_url="https://github.com/example/hidden-task",
        ))
        session.commit()

    response = await client.get("/project-manager/api/repository-inventory")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["github_repo_url"] for row in rows] == ["https://github.com/example/visible"]
    assert rows[0]["project_names"] == ["Visible"]
    assert rows[0]["solution_count"] == 1

@pytest.mark.anyio
async def test_repository_inventory_groups_github_case_variants_deterministically(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(Program(program_id="p", space_id="test-space", program_name="Program"))
        session.add(Project(project_id="p", program_id="p", space_id="test-space", project_name="Project"))
        session.add_all([
            Solution(solution_id="s1", project_id="p", space_id="test-space", solution_name="One", github_repo_url="https://github.com/example/repo"),
            Solution(solution_id="s2", project_id="p", space_id="test-space", solution_name="Two", github_repo_url="https://github.com/Example/Repo"),
        ])
        session.add_all([
            Task(task_id="t1", solution_id="s1", project_id="p", space_id="test-space", task_name="Inherited"),
            Task(task_id="t2", solution_id="s2", project_id="p", space_id="test-space", task_name="Override", github_repo_url="https://github.com/EXAMPLE/REPO"),
        ])
        session.commit()
    response = await client.get("/project-manager/api/repository-inventory")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["github_repo_url"] == "https://github.com/EXAMPLE/REPO"
    assert rows[0]["repository_name"] == "EXAMPLE/REPO"
    assert rows[0]["solution_names"] == ["One", "Two"]
    assert rows[0]["solution_count"] == 2
    assert rows[0]["task_count"] == 2
    assert rows[0]["solution_attachment_count"] == 2
    assert rows[0]["task_override_count"] == 1


@pytest.mark.anyio
async def test_repository_inventory_keeps_distinct_malformed_legacy_urls(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(Program(program_id="p", space_id="test-space", program_name="Program"))
        session.add(Project(project_id="p", program_id="p", space_id="test-space", project_name="Project"))
        session.add_all([
            Solution(solution_id="s1", project_id="p", space_id="test-space", solution_name="One", github_repo_url="https://example.test/Owner/Repo"),
            Solution(solution_id="s2", project_id="p", space_id="test-space", solution_name="Two", github_repo_url="https://example.test/owner/repo"),
            Solution(solution_id="s3", project_id="p", space_id="test-space", solution_name="Three", github_repo_url="https://github.com/owner/repo/"),
            Solution(solution_id="s4", project_id="p", space_id="test-space", solution_name="Four", github_repo_url="https://github.com/owner/repo"),
        ])
        session.commit()
    response = await client.get("/project-manager/api/repository-inventory")
    assert response.status_code == 200
    assert len(response.json()) == 4
