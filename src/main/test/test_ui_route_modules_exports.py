from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES_DIR = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes"
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"

EXPECTED_ROUTE_EXPORTS = {
    "access.js": ["renderAccess"],
    "ai.js": ["renderAI"],
    "master.js": ["renderMasterFilters", "renderMasterTable"],
    "subcomponents-workbench.js": ["renderSubcomponentsWorkbench"],
    "dashboard.js": ["renderDashboard"],
    "pm-dashboard.js": ["renderPMDashboard"],
    "kanban.js": ["renderKanban"],
    "calendar.js": ["renderCalendar", "openCalendarModal"],
    "planning.js": ["renderPlanning"],
    "team-capacity.js": ["renderTeamCapacity"],
    "spaces.js": ["renderSpaces"],
    "structure-studio.js": ["renderStructureStudio"],
    "workbench.js": ["renderWorkbench"],
}

EXPECTED_ROUTE_LOADERS = {
    "access": "./routes/access.js",
    "ai": "./routes/ai.js",
    "master": "./routes/master.js",
    "subcomponents-workbench": "./routes/subcomponents-workbench.js",
    "dashboard": "./routes/dashboard.js",
    "pm-dashboard": "./routes/pm-dashboard.js",
    "kanban": "./routes/kanban.js",
    "calendar": "./routes/calendar.js",
    "planning": "./routes/planning.js",
    "team-capacity": "./routes/team-capacity.js",
    "spaces": "./routes/spaces.js",
    "structure-studio": "./routes/structure-studio.js",
    "workbench": "./routes/workbench.js",
}


def test_route_modules_export_expected_entrypoints():
    for filename, exports in EXPECTED_ROUTE_EXPORTS.items():
        path = ROUTES_DIR / filename
        assert path.exists(), f"Missing route module: {path}"
        text = path.read_text(encoding="utf-8")
        for export_name in exports:
            assert f"export function {export_name}" in text, (
                f"{filename} must export `{export_name}`."
            )


def test_app_route_loader_registry_includes_split_views():
    app_text = APP_JS.read_text(encoding="utf-8")
    for view_name, import_path in EXPECTED_ROUTE_LOADERS.items():
        candidates = [
            f'{view_name}: () => import("{import_path}")',
            f'"{view_name}": () => import("{import_path}")',
            f"'{view_name}': () => import(\"{import_path}\")",
            f'{view_name}: () => import(`{import_path}?v=${{APP_ASSET_VERSION}}`)',
            f'"{view_name}": () => import(`{import_path}?v=${{APP_ASSET_VERSION}}`)',
            f"'{view_name}': () => import(`{import_path}?v=${{APP_ASSET_VERSION}}`)",
        ]
        assert any(candidate in app_text for candidate in candidates), (
            f"Missing lazy route loader mapping for {view_name}"
        )
