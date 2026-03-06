from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
PLANNING_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning.js"


def test_master_remains_default_view_and_fallback():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'currentView: "master"' in text
    assert 'if (!raw) return "master";' in text
    assert 'return "master";' in text


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


def test_reset_password_ui_uses_live_token_flow_only():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert "/auth/reset-password-with-token" in app_text
    assert 'params.get("token")' in app_text
    assert 'params.get("reset_token")' in app_text
    assert 'name="reset_token"' in html_text
    assert "/auth/verify-temp-password" not in app_text
    assert '/auth/reset-password"' not in app_text
    assert "verify-temp-form" not in html_text


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
