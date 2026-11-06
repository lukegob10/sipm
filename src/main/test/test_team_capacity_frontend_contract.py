from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
PATHS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "paths.js"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"
TEAM_CAPACITY_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "team-capacity.js"
TEAM_CAPACITY_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "team-capacity" / "interactions.js"


def test_team_capacity_view_uses_dedicated_loader_pipeline():
    text = ROUTER_JS.read_text(encoding="utf-8")
    assert 'if (nextView === "team-capacity") {' in text
    assert "loadTeamCapacityData({ force: true })" in text


def test_users_csv_import_refreshes_team_capacity_pipeline():
    text = APP_JS.read_text(encoding="utf-8")
    start = text.index("async function uploadCsvFile(")
    upload = text[start:text.index("\n}", start)]
    assert 'const entities = kind === "users" ? ["users"]' in upload
    assert "dataStoreController.ensureEntityData(entities)" in upload
    assert '...(kind === "users" ? [loadTeamCapacityData({ force: true })] : [])' in upload
    assert 'if (kind === "users" && state.teamCapacity?.error)' in upload


def test_team_capacity_route_supports_explicit_load_state_rendering():
    text = TEAM_CAPACITY_ROUTE.read_text(encoding="utf-8")
    assert "teamCapacityState" in text
    assert "Last refreshed" in text
    assert "Refreshing..." in text
    assert "Space:" in text
    assert "Team Summary" in text
    assert "Roster" in text


def test_team_capacity_loader_is_space_aware_and_uses_extended_timeout():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/team-capacity/interactions.js";' in app_text
    assert "function loadTeamCapacityData(options = {}) {" in app_text
    assert "return teamCapacityRouteController.loadTeamCapacityData(options);" in app_text
    assert 'const requestedSpaceId = state.activeSpace?.space_id || "";' in interactions_text
    assert 'const spaceHeaders = { "X-Space-Id": requestedSpaceId };' in interactions_text
    assert 'api("/users?active_only=true", {' in interactions_text
    assert "timeoutMs: 45000," in interactions_text
    assert "headers: spaceHeaders," in interactions_text
    assert "signal: options.signal," in interactions_text
    assert 'state.teamCapacity.lastLoadedSpaceId = requestedSpaceId;' in interactions_text


def test_space_switch_reload_uses_team_capacity_pipeline_when_needed():
    app_text = APP_JS.read_text(encoding="utf-8")
    data_store_text = (REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "data-store.js").read_text(encoding="utf-8")
    assert "await reloadCurrentViewData({ force: true, preserveCapacitySelection: false });" in app_text
    assert 'if (state.currentView === "team-capacity") {' in data_store_text
    assert "return await loadTeamCapacityData({" in data_store_text
    assert "preserveSelection: preserveCapacitySelection," in data_store_text
    assert "signal: controller?.signal," in data_store_text
    switch_block = app_text[app_text.index("async function switchActiveSpace"):app_text.index("function applySpaceContext")]
    assert switch_block.count("clearDataState();") == 1
    assert switch_block.count("await reloadCurrentViewData(") == 1


def test_route_module_imports_use_standard_paths():
    paths_text = PATHS_JS.read_text(encoding="utf-8")
    router_text = ROUTER_JS.read_text(encoding="utf-8")
    assert "export const APP_ASSET_VERSION" not in paths_text
    assert 'team-capacity.js?v=' not in router_text
    assert 'team-capacity": () => import("../routes/team-capacity.js")' in router_text


def test_csv_download_upload_are_space_scoped():
    app = APP_JS.read_text(encoding="utf-8")
    csv = (REPO_ROOT / "src" / "main" / "ui" / "js" / "utils" / "csv-import.js").read_text(encoding="utf-8")
    import_start = csv.index("export async function requestCsvImport(")
    export_start = csv.index("export async function requestCsvExport(")
    for block in (csv[import_start:export_start], csv[export_start:]):
        assert 'headers["X-Space-Id"] = context.spaceId;' in block
        assert "isEntityMutationContextCurrent(state, context)" in block
    assert "requestCsvImport({ state, file, kind, apiBase: API_BASE, fetchImpl: sessionBoundFetch, context })" in app
    assert "requestCsvExport({ state, kind, apiBase: API_BASE, fetchImpl: sessionBoundFetch, context })" in app


def test_team_capacity_has_clear_filters_control():
    app_text = APP_JS.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS.read_text(encoding="utf-8")
    assert 'capacityClearFilters: document.getElementById("capacity-clear-filters")' in dom_text
    assert "function bindCapacityUsers() {" in app_text
    assert "return teamCapacityRouteController.bindTeamCapacityControls();" in app_text
    assert "if (els.capacityClearFilters) {" in interactions_text


def test_team_capacity_team_filter_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS.read_text(encoding="utf-8")

    assert 'const TEAM_CAPACITY_VIEW_STATE_KEY_PREFIX = "sipm-team-capacity-view-state-v1";' in app_text
    assert "const teamCapacityRouteController = createTeamCapacityRouteController({" in app_text
    assert "activeSpaceScopedStorageKey(teamCapacityViewStateKey)" in interactions_text
    assert 'team_filter: String(els.capacityTeamFilter?.value || ""),' in interactions_text
    assert "restoreTeamCapacityViewState();" in app_text


def test_team_capacity_name_filter_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS.read_text(encoding="utf-8")

    assert "function restoreTeamCapacityViewState() {" in app_text
    assert "return teamCapacityRouteController.restoreTeamCapacityViewState();" in app_text
    assert 'name_filter: String(els.capacityNameFilter?.value || ""),' in interactions_text
    assert '[els.capacityNameFilter, "name_filter"]' in interactions_text
    assert 'element.value = String(stored[key] || "");' in interactions_text
    assert 'bindDebouncedInput(element, () => {' in interactions_text
    assert 'isEntityMutationContextCurrent(state, pending.context)' in interactions_text
    assert "persistTeamCapacityViewState();" in interactions_text


def test_team_capacity_selected_user_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS.read_text(encoding="utf-8")

    assert 'selected_soeid: String(state.capacitySelectedSoeid || ""),' in interactions_text
    assert 'state.capacitySelectedSoeid = String(stored.selected_soeid || "");' in interactions_text
    assert "function selectCapacityUser(user, options = {}) {" in interactions_text
    assert "function clearCapacityUserForm(options = {}) {" in interactions_text
    assert "persistTeamCapacityViewState();" in interactions_text
    assert "function selectCapacityUser(user, options = {}) {" not in app_text
    assert "function clearCapacityUserForm(options = {}) {" not in app_text


def test_team_capacity_corrupt_scoped_view_state_is_rewritten_to_defaults():
    text = TEAM_CAPACITY_INTERACTIONS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(teamCapacityViewStateKey), {});" in text
    assert '[els.capacityTeamFilter, "team_filter"]' in text
    assert '[els.capacityNameFilter, "name_filter"]' in text
    assert 'element.value = String(stored[key] || "");' in text
    assert 'state.capacitySelectedSoeid = String(stored.selected_soeid || "");' in text
    assert "if (recovered) persistTeamCapacityViewState();" in text
