from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
TEAM_CAPACITY_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "team-capacity.js"


def test_team_capacity_view_uses_dedicated_loader_pipeline():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'if (nextView === "team-capacity") {' in text
    assert "loadTeamCapacityData({ force: true })" in text


def test_users_csv_import_refreshes_team_capacity_pipeline():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'if (kind === "users") {' in text
    assert "await loadTeamCapacityData({ force: true });" in text


def test_team_capacity_route_supports_explicit_load_state_rendering():
    text = TEAM_CAPACITY_ROUTE.read_text(encoding="utf-8")
    assert "teamCapacityState" in text
    assert "Last refreshed" in text
    assert "Refreshing..." in text
    assert "Space:" in text
    assert "Team Summary" in text
    assert "Roster" in text


def test_team_capacity_loader_is_space_aware_and_uses_extended_timeout():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'const requestedSpaceId = state.activeSpace?.space_id || "";' in text
    assert 'const spaceHeaders = { "X-Space-Id": requestedSpaceId };' in text
    assert 'api("/users?active_only=true", { timeoutMs: 45000, headers: spaceHeaders })' in text
    assert 'api("/resource-allocations", { timeoutMs: 45000, headers: spaceHeaders })' in text
    assert 'state.teamCapacity.lastLoadedSpaceId = requestedSpaceId;' in text


def test_space_switch_reload_uses_team_capacity_pipeline_when_needed():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'if (state.currentView === "team-capacity") {' in text
    assert "await loadTeamCapacityData({ force: true, preserveSelection: false });" in text


def test_route_module_imports_are_asset_versioned():
    text = APP_JS.read_text(encoding="utf-8")
    assert "const APP_ASSET_VERSION" in text
    assert '?v=${APP_ASSET_VERSION}' in text


def test_csv_download_upload_are_space_scoped():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'headers["X-Space-Id"] = state.activeSpace.space_id;' in text


def test_team_capacity_has_clear_filters_control():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'capacityClearFilters: document.getElementById("capacity-clear-filters")' in text
    assert "if (els.capacityClearFilters)" in text
