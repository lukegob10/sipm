import pytest

from backend.app import deps as deps_module
from backend.app.models import Project, Solution, Space, Subcomponent
from backend.app.services.spaces import SpaceContext
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus, SubcomponentStatus
from backend.main import app as fastapi_app


def _set_current_space(space_id: str):
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
        space_id=space_id,
        space_name="Strict Isolation Space",
        is_global_admin=False,
        space_role="space_admin",
    )


def _restore_current_space(original):
    if original is None:
        fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
    else:
        fastapi_app.dependency_overrides[deps_module.current_space] = original


def _ensure_space(db_sessionmaker, space_id: str, slug: str):
    with db_sessionmaker() as session:
        exists = session.query(Space).filter(Space.space_id == space_id).first()
        if not exists:
            session.add(Space(space_id=space_id, name=f"Space {slug}", slug=slug, is_active=True))
            session.commit()


@pytest.mark.anyio
async def test_projects_list_excludes_legacy_null_space_rows(client, db_sessionmaker):
    space_id = "strict-space-projects"
    _ensure_space(db_sessionmaker, space_id, "strict-space-projects")
    with db_sessionmaker() as session:
        session.add(
            Project(
                project_id="legacy-null-project",
                space_id=None,
                project_name="Legacy Null Project",
                status=ProjectStatus.not_started,
                sponsor="Legacy Sponsor",
            )
        )
        session.commit()

    original = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space(space_id)
        create_resp = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Strict Space Project", "sponsor": "Space Sponsor"},
        )
        assert create_resp.status_code == 201, create_resp.text

        list_resp = await client.get("/project-manager/api/projects/")
        assert list_resp.status_code == 200, list_resp.text
        names = {row["project_name"] for row in list_resp.json()}
        assert "Strict Space Project" in names
        assert "Legacy Null Project" not in names
    finally:
        _restore_current_space(original)


@pytest.mark.anyio
async def test_solutions_list_excludes_legacy_null_space_rows(client, db_sessionmaker):
    space_id = "strict-space-solutions"
    _ensure_space(db_sessionmaker, space_id, "strict-space-solutions")
    with db_sessionmaker() as session:
        legacy_project = Project(
            project_id="legacy-null-project-solutions",
            space_id=None,
            project_name="Legacy Null Project Solutions",
            status=ProjectStatus.not_started,
            sponsor="Legacy Sponsor",
        )
        session.add(legacy_project)
        session.flush()
        session.add(
            Solution(
                solution_id="legacy-null-solution",
                space_id=None,
                project_id=legacy_project.project_id,
                solution_name="Legacy Null Solution",
                version="0.1.0",
                status=SolutionStatus.not_started,
                rag_status=RagStatus.green,
                owner="Legacy Owner",
                assignee="Legacy Owner",
            )
        )
        session.commit()

    original = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space(space_id)
        project_resp = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Strict Space Project Solutions", "sponsor": "Space Sponsor"},
        )
        assert project_resp.status_code == 201, project_resp.text
        project_id = project_resp.json()["project_id"]
        solution_resp = await client.post(
            f"/project-manager/api/projects/{project_id}/solutions",
            json={"solution_name": "Strict Space Solution"},
        )
        assert solution_resp.status_code == 201, solution_resp.text

        list_resp = await client.get("/project-manager/api/solutions")
        assert list_resp.status_code == 200, list_resp.text
        names = {row["solution_name"] for row in list_resp.json()}
        assert "Strict Space Solution" in names
        assert "Legacy Null Solution" not in names
    finally:
        _restore_current_space(original)


@pytest.mark.anyio
async def test_subcomponents_list_excludes_legacy_null_space_rows(client, db_sessionmaker):
    space_id = "strict-space-subcomponents"
    _ensure_space(db_sessionmaker, space_id, "strict-space-subcomponents")

    original = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space(space_id)
        project_resp = await client.post(
            "/project-manager/api/projects/",
            json={"project_name": "Strict Space Project Subcomponents", "sponsor": "Space Sponsor"},
        )
        assert project_resp.status_code == 201, project_resp.text
        project_id = project_resp.json()["project_id"]
        solution_resp = await client.post(
            f"/project-manager/api/projects/{project_id}/solutions",
            json={"solution_name": "Strict Space Solution Subcomponents"},
        )
        assert solution_resp.status_code == 201, solution_resp.text
        solution_id = solution_resp.json()["solution_id"]

        create_sub_resp = await client.post(
            f"/project-manager/api/solutions/{solution_id}/subcomponents",
            json={"subcomponent_name": "Strict Space Subcomponent"},
        )
        assert create_sub_resp.status_code == 201, create_sub_resp.text

        with db_sessionmaker() as session:
            session.add(
                Subcomponent(
                    subcomponent_id="legacy-null-subcomponent",
                    space_id=None,
                    project_id=project_id,
                    solution_id=solution_id,
                    subcomponent_name="Legacy Null Subcomponent",
                    status=SubcomponentStatus.to_do,
                    assignee="Legacy Assignee",
                )
            )
            session.commit()

        list_resp = await client.get("/project-manager/api/subcomponents")
        assert list_resp.status_code == 200, list_resp.text
        names = {row["subcomponent_name"] for row in list_resp.json()}
        assert "Strict Space Subcomponent" in names
        assert "Legacy Null Subcomponent" not in names
    finally:
        _restore_current_space(original)
