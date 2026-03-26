from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard.js"
DASHBOARD_COMMON = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "common.js"
DASHBOARD_PREFS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "prefs.js"
DASHBOARD_MODAL = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "modal.js"
DASHBOARD_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "interactions.js"
DASHBOARD_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "render.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_dashboard_route_uses_single_customize_tables_control_with_section_tabs():
    route_text = DASHBOARD_ROUTE.read_text(encoding="utf-8")
    modal_text = DASHBOARD_MODAL.read_text(encoding="utf-8")
    render_text = DASHBOARD_RENDER.read_text(encoding="utf-8")

    assert 'import { createDashboardState, renderDashboardView } from "./dashboard/render.js";' in route_text
    assert "Customize Tables" in modal_text
    assert "renderDashboardConfigButton()" in render_text
    assert '"dashboard-card-action"' in modal_text
    assert 'renderSectionActionButton("completed")' not in render_text
    assert 'renderSectionActionButton("upcoming")' not in render_text
    assert 'renderSectionActionButton("backlog")' not in render_text
    assert '"switch-config-section"' in modal_text
    assert "dashboard-config-section-tabs" in modal_text
    assert '"open-config"' in modal_text
    assert 'class="dashboard-config-helper-link" data-dashboard-action="select-all-solutions"' in modal_text
    assert 'class="dashboard-config-helper-link" data-dashboard-action="clear-solutions"' in modal_text
    assert 'class="table dashboard-table-shell dashboard-interactive-table"' not in render_text
    assert 'role="button"' not in render_text


def test_dashboard_route_renders_solution_and_project_names_as_drilldown_links():
    common_text = DASHBOARD_COMMON.read_text(encoding="utf-8")
    render_text = DASHBOARD_RENDER.read_text(encoding="utf-8")
    assert '"open-solution"' in common_text
    assert '"open-project"' in common_text
    assert "dashboardSolutionLinkMarkup" in common_text
    assert "dashboardProjectLinkMarkup" in common_text
    assert "dashboard-solution-link" in common_text
    assert "dashboard-project-link" in common_text
    assert 'data-solution-id="' in common_text
    assert 'data-project-id="' in common_text
    assert "Open Solution" not in common_text
    assert 'dashboardProjectLinkMarkup(row.projectId, row.projectName, " strong")' in common_text
    assert '<div class="dashboard-cell-meta">${dashboardProjectLinkMarkup(row.projectId, row.projectName, " secondary")}</div>' not in render_text


def test_dashboard_route_handles_solution_and_project_drilldown_and_config_section_switching():
    text = DASHBOARD_INTERACTIONS.read_text(encoding="utf-8")
    assert 'if (action === "open-solution") {' in text
    assert 'if (typeof dashboardState.ctx?.openDashboardSolutionDrilldown === "function") {' in text
    assert 'if (action === "open-project") {' in text
    assert 'if (typeof dashboardState.ctx?.openDashboardProjectDrilldown === "function") {' in text
    assert 'if (action === "open-config") {' in text
    assert 'if (action === "switch-config-section") {' in text
    assert 'document.addEventListener("click", (event) => {' in text


def test_dashboard_drilldown_helpers_reuse_existing_solution_and_project_modals():
    text = APP_JS.read_text(encoding="utf-8")
    assert "function openDashboardSolutionDrilldown(solutionId)" in text
    assert "function openDashboardProjectDrilldown(projectId)" in text
    assert 'openSolutionModal(solution, "details")' in text
    assert "openProjectForm(project)" in text


def test_dashboard_prefs_are_scoped_per_space():
    common_text = DASHBOARD_COMMON.read_text(encoding="utf-8")
    prefs_text = DASHBOARD_PREFS.read_text(encoding="utf-8")
    render_text = DASHBOARD_RENDER.read_text(encoding="utf-8")

    assert 'const DASHBOARD_PREFS_KEY_PREFIX = "sipm-dashboard-view-prefs-v4";' in common_text
    assert 'prefsSpaceId: "",' in prefs_text
    assert "function currentDashboardSpaceId(dashboardState) {" in prefs_text
    assert 'function dashboardPrefsStorageKey(spaceId = "no-space") {' in prefs_text
    assert "const scopedKey = dashboardPrefsStorageKey(spaceId);" in prefs_text
    assert "const raw = localStorage.getItem(scopedKey);" in prefs_text
    assert "localStorage.setItem(dashboardPrefsStorageKey(spaceId), JSON.stringify(dashboardState.prefs));" in prefs_text
    assert "function ensurePrefsLoaded(dashboardState, spaceId = currentDashboardSpaceId(dashboardState)) {" in prefs_text
    assert "dashboardState.prefs = loadPrefs(targetSpaceId);" in prefs_text
    assert 'ensurePrefsLoaded(dashboardState, state.activeSpace?.space_id || "no-space");' in render_text


def test_dashboard_scoped_prefs_fall_back_to_legacy_global_storage_once():
    common_text = DASHBOARD_COMMON.read_text(encoding="utf-8")
    text = DASHBOARD_PREFS.read_text(encoding="utf-8")

    assert 'const DASHBOARD_PREFS_LEGACY_KEY = "sipm-dashboard-view-prefs-v3";' in common_text
    assert "const scopedKey = dashboardPrefsStorageKey(spaceId);" in text
    assert "const persistLoadedPrefs = (prefs) => {" in text
    assert "const legacyRaw = localStorage.getItem(DASHBOARD_PREFS_LEGACY_KEY);" in text
    assert "const legacyParsed = normalizePrefs(JSON.parse(legacyRaw));" in text
    assert "localStorage.removeItem(DASHBOARD_PREFS_LEGACY_KEY);" in text
    assert "return persistLoadedPrefs(legacyParsed);" in text


def test_dashboard_default_prefs_are_seeded_into_scoped_storage():
    text = DASHBOARD_PREFS.read_text(encoding="utf-8")

    assert "if (!raw) {" in text
    assert "if (!legacyRaw) {" in text
    assert "const defaultPrefs = normalizePrefs(DEFAULT_PREFS);" in text
    assert "return persistLoadedPrefs(defaultPrefs);" in text


def test_dashboard_invalid_scoped_prefs_are_rewritten_after_normalization():
    text = DASHBOARD_PREFS.read_text(encoding="utf-8")

    assert "const parsed = JSON.parse(raw);" in text
    assert "const normalized = normalizePrefs(parsed);" in text
    assert "if (JSON.stringify(parsed) !== JSON.stringify(normalized)) {" in text
    assert "localStorage.setItem(scopedKey, JSON.stringify(normalized));" in text


def test_dashboard_malformed_scoped_prefs_fall_back_to_rewritten_defaults():
    text = DASHBOARD_PREFS.read_text(encoding="utf-8")

    assert "const defaultPrefs = normalizePrefs(DEFAULT_PREFS);" in text
    assert "localStorage.setItem(dashboardPrefsStorageKey(spaceId), JSON.stringify(defaultPrefs));" in text
    assert "return defaultPrefs;" in text


def test_dashboard_config_last_section_is_persisted_per_space():
    prefs_text = DASHBOARD_PREFS.read_text(encoding="utf-8")
    modal_text = DASHBOARD_MODAL.read_text(encoding="utf-8")
    interactions_text = DASHBOARD_INTERACTIONS.read_text(encoding="utf-8")

    assert 'lastConfigSection: "main",' in prefs_text
    assert 'last_config_section: String(input?.last_config_section || DEFAULT_PREFS.last_config_section),' in prefs_text
    assert "if (!DASHBOARD_SECTIONS.includes(next.last_config_section)) next.last_config_section = DEFAULT_PREFS.last_config_section;" in prefs_text
    assert "dashboardState.prefs?.last_config_section" in modal_text
    assert 'updatePrefs(dashboardState, { last_config_section: targetSection });' in modal_text
    assert 'updatePrefs(dashboardState, { last_config_section: sectionId });' in interactions_text


def test_dashboard_stale_solution_selections_are_auto_cleared():
    prefs_text = DASHBOARD_PREFS.read_text(encoding="utf-8")
    render_text = DASHBOARD_RENDER.read_text(encoding="utf-8")

    assert "function normalizeSectionSolutionSelections(" in prefs_text
    assert "const validSolutionIds = new Set(" in prefs_text
    assert 'const filteredIds = solutionIds.filter((solutionId) => validSolutionIds.has(String(solutionId || "").trim()));' in prefs_text
    assert "const normalizedIds = filteredIds.length ? filteredIds : null;" in prefs_text
    assert "dashboardState.prefs = normalizePrefs({" in prefs_text
    assert "savePrefs(dashboardState);" in prefs_text
    assert "normalizeSectionSolutionSelections(dashboardState, dashboardState.sectionOptions);" in render_text


def test_dashboard_drilldown_links_use_text_first_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".dashboard-solution-link {" in text
    assert ".dashboard-project-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert "text-underline-offset: 0.12em;" in text


def test_dashboard_config_helper_links_use_compact_local_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".dashboard-config-helper-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".dashboard-config-helper-link:hover," in text


def test_dashboard_card_action_uses_text_first_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".dashboard-card-action {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".dashboard-card-action:hover {" in text


def test_dashboard_risk_badges_use_quieter_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".dashboard-risk-badge {" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text
