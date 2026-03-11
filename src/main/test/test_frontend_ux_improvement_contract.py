from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
PLANNING_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning.js"
PM_DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard.js"
SUBCOMPONENTS_WORKBENCH_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench.js"


def test_master_remains_default_view_and_fallback():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'currentView: "master"' in text
    assert "function viewFromLocationPath" in text
    assert 'if (relative === "/" || relative === "") return "master";' in text
    assert 'return normalizeView(firstSegment);' in text


def test_route_hint_copy_removed_from_main_html_views():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "view-route-hint" not in text
    for route_hint in [
        "#/master",
        "#/subcomponents-workbench",
        "#/dashboard",
        "#/pm-dashboard",
        "#/kanban",
        "#/calendar",
        "#/planning",
        "#/team-capacity",
        "#/spaces",
        "#/access",
    ]:
        assert route_hint not in text


def test_frontend_ux_state_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")
    master_text = MASTER_ROUTE.read_text(encoding="utf-8")

    assert 'const MASTER_VIEW_STATE_KEY_PREFIX = "sipm-master-filters-v1";' in app_text
    assert 'const SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX = "sipm-subcomponents-workbench-state-v1";' in app_text
    assert 'const STORAGE_KEY_PREFIX = "sipm-planning-ui-v1";' in planning_text
    assert "persistMasterViewState" in app_text
    assert "persistSubcomponentsWorkbenchUiState" in app_text
    assert "persistViewState()" in planning_text
    assert "persistMasterViewState" in master_text


def test_reset_password_ui_uses_temp_password_flow():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert "/auth/reset-password" in app_text
    assert 'name="soeid"' in html_text
    assert 'name="temp_password"' in html_text
    assert 'Use temporary password' in html_text
    assert "/auth/reset-password-with-token" not in app_text
    assert "verify-temp-form" not in html_text


def test_frontend_derives_project_manager_context_path_for_api_and_reset_routes():
    app_text = APP_JS.read_text(encoding="utf-8")
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")
    pm_dashboard_text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert "const APP_CONTEXT_PATH = (() => {" in app_text
    assert 'const API_BASE = `${APP_CONTEXT_PATH}/api` || "/api";' in app_text
    assert "function routePathForView(view)" in app_text
    assert "function syncPathForView(view, replace = false)" in app_text
    assert 'window.addEventListener("popstate"' in app_text
    assert 'buildAppUrl("/reset-password")' in app_text
    assert 'window.location.href = buildAppUrl("/reset-password");' in app_text
    assert 'window.location.href = buildAppUrl("/");' in app_text
    assert 'const url = new URL(buildWsUrl("/ws"));' in app_text
    assert "resolveApiBase(ctx)" in planning_text
    assert "viewHref," in app_text
    assert "const hrefFor = (view) => {" in pm_dashboard_text
    assert "/api/planning/work-allocation/report.pdf" not in planning_text
    assert "#/" not in pm_dashboard_text


def test_planning_route_uses_inline_forms_confirm_modal_and_keyboard_detail_controls():
    text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert "wab-inline-forms-planning" in text
    assert "ctx?.showConfirmModal" in text
    assert "data-assign-target" in text
    assert 'if (key === "Escape" && boardState.selectedTaskId)' in text
    assert 'closest(".wab-task-chip")' in text
    assert "closeTaskDetail" in text
    assert "wab-person-search" in text
    assert "window.prompt" not in text
    assert "window.confirm" not in text


def test_operational_views_can_hide_completed_work_across_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")
    workbench_text = SUBCOMPONENTS_WORKBENCH_ROUTE.read_text(encoding="utf-8")

    assert 'id="completed-visibility-toggle"' in html_text
    assert 'const WORKSPACE_VIEW_PREFS_KEY_PREFIX = "sipm-workspace-prefs-v1";' in app_text
    assert 'workspacePrefs: { showCompleted: false },' in app_text
    assert "function renderCompletedVisibilityToggle()" in app_text
    assert "function showCompletedOperationalWork()" in app_text
    assert "if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;" in app_text
    assert "if (hideClosedDeliverables() && isClosedProjectStatus(project?.status)) return false;" in app_text
    assert "if (!showCompletedOperationalWork() && isCompletedSubcomponentStatus(sc.status)) return false;" in app_text
    assert "Completed items are hidden here. Use Show Completed in the top bar" in app_text
    assert "ctx?.state?.workspacePrefs?.showCompleted" in planning_text
    assert "completed or abandoned task" in planning_text
    assert "summary?.hiddenClosed" in workbench_text
