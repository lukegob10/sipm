from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECTS_PACKAGE = (
    REPO_ROOT / "src" / "main" / "backend" / "app" / "routes" / "projects"
)
PROJECTS_INIT = PROJECTS_PACKAGE / "__init__.py"
PROJECTS_COMMON = PROJECTS_PACKAGE / "common.py"
PROJECTS_READ = PROJECTS_PACKAGE / "read.py"
PROJECTS_WRITE = PROJECTS_PACKAGE / "write.py"
PROJECTS_IMPORT_EXPORT = PROJECTS_PACKAGE / "import_export.py"
LEGACY_PROJECTS_MODULE = (
    REPO_ROOT / "src" / "main" / "backend" / "app" / "routes" / "projects.py"
)


def test_projects_routes_are_split_into_a_package_with_compatibility_reexports():
    assert PROJECTS_PACKAGE.is_dir()
    assert PROJECTS_INIT.exists()
    assert PROJECTS_COMMON.exists()
    assert PROJECTS_READ.exists()
    assert PROJECTS_WRITE.exists()
    assert PROJECTS_IMPORT_EXPORT.exists()
    assert not LEGACY_PROJECTS_MODULE.exists()

    init_text = PROJECTS_INIT.read_text(encoding="utf-8")
    assert "from .import_export import router as import_export_router" in init_text
    assert "from .read import list_projects, router as read_router" in init_text
    assert "from .write import create_project, router as write_router" in init_text
    normalized_init = " ".join(init_text.split())
    assert 'router.add_api_route( "", list_projects' in normalized_init
    assert 'router.add_api_route( "/", list_projects' in normalized_init
    assert 'router.add_api_route( "", create_project,' in normalized_init
    assert 'router.add_api_route( "/", create_project,' in normalized_init
    assert "router.include_router(import_export_router)" in init_text
    assert "router.include_router(read_router)" in init_text
    assert "router.include_router(write_router)" in init_text
    assert (
        "_is_project_name_conflict_integrity_error = ( _common._is_project_name_conflict_integrity_error )"
        in normalized_init
    )
