from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES_DIR = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"

EXPECTED_ROUTE_EXPORTS = {
    "access.js": ["renderAccess", "render"],
    "master.js": ["renderMasterFilters", "renderMasterTable", "render"],
    "subcomponents-workbench.js": ["renderSubcomponentsWorkbench", "render"],
    "dashboard.js": ["renderDashboard", "render"],
    "pm-dashboard.js": ["renderPMDashboard", "render"],
    "gantt.js": ["renderGantt", "render"],
    "kanban.js": ["renderKanban", "render"],
    "calendar.js": ["renderCalendar", "openCalendarModal", "render"],
    "planning.js": ["renderPlanning", "render"],
    "team-capacity.js": ["renderTeamCapacity", "render"],
    "spaces.js": ["renderSpaces", "render"],
    "analytics.js": ["renderAnalytics", "render"],
}

EXPECTED_ROUTE_LOADERS = {
    "access": "./routes/access.js",
    "master": "./routes/master.js",
    "subcomponents-workbench": "./routes/subcomponents-workbench.js",
    "dashboard": "./routes/dashboard.js",
    "pm-dashboard": "./routes/pm-dashboard.js",
    "gantt": "./routes/gantt.js",
    "kanban": "./routes/kanban.js",
    "calendar": "./routes/calendar.js",
    "planning": "./routes/planning.js",
    "team-capacity": "./routes/team-capacity.js",
    "spaces": "./routes/spaces.js",
    "analytics": "./routes/analytics.js",
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
    app_text = ROUTER_JS.read_text(encoding="utf-8")
    for view_name, import_path in EXPECTED_ROUTE_LOADERS.items():
        candidates = [
            f"{view_name}: () => import(`../routes/{import_path.split('/')[-1]}?v=${{APP_ASSET_VERSION}}`)",
            f'"{view_name}": () => import(`../routes/{import_path.split("/")[-1]}?v=${{APP_ASSET_VERSION}}`)',
            f"'{view_name}': () => import(`../routes/{import_path.split('/')[-1]}?v=${{APP_ASSET_VERSION}}`)",
        ]
        assert any(candidate in app_text for candidate in candidates), (
            f"Missing lazy route loader mapping for {view_name}"
        )
