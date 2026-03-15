from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_dashboard_route_uses_single_customize_tables_control_with_section_tabs():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")
    assert "Customize Tables" in text
    assert "renderDashboardConfigButton()" in text
    assert '"dashboard-card-action"' in text
    assert 'renderSectionActionButton("completed")' not in text
    assert 'renderSectionActionButton("upcoming")' not in text
    assert 'renderSectionActionButton("backlog")' not in text
    assert '"switch-config-section"' in text
    assert "dashboard-config-section-tabs" in text
    assert '"open-config"' in text
    assert 'class="dashboard-config-helper-link" data-dashboard-action="select-all-solutions"' in text
    assert 'class="dashboard-config-helper-link" data-dashboard-action="clear-solutions"' in text
    assert 'class="table dashboard-table-shell dashboard-interactive-table"' not in text
    assert 'role="button"' not in text


def test_dashboard_route_renders_solution_and_project_names_as_drilldown_links():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")
    assert '"open-solution"' in text
    assert '"open-project"' in text
    assert "dashboardSolutionLinkMarkup" in text
    assert "dashboardProjectLinkMarkup" in text
    assert "dashboard-solution-link" in text
    assert "dashboard-project-link" in text
    assert '"data-solution-id"' in text
    assert '"data-project-id"' in text
    assert "Open Solution" not in text
    assert 'dashboardProjectLinkMarkup(row.projectId, row.projectName, " strong")' in text
    assert '<div class="dashboard-cell-meta">${dashboardProjectLinkMarkup(row.projectId, row.projectName, " secondary")}</div>' not in text


def test_dashboard_route_handles_solution_and_project_drilldown_and_config_section_switching():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")
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
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert 'const DASHBOARD_PREFS_KEY_PREFIX = "sipm-dashboard-view-prefs-v4";' in text
    assert "prefsSpaceId: \"\"," in text
    assert "function currentDashboardSpaceId() {" in text
    assert "function dashboardPrefsStorageKey(spaceId = currentDashboardSpaceId()) {" in text
    assert "const scopedKey = dashboardPrefsStorageKey(spaceId);" in text
    assert "const raw = localStorage.getItem(scopedKey);" in text
    assert "localStorage.setItem(dashboardPrefsStorageKey(spaceId), JSON.stringify(dashboardState.prefs));" in text
    assert "function ensurePrefsLoaded(spaceId = currentDashboardSpaceId()) {" in text
    assert "dashboardState.prefs = loadPrefs(targetSpaceId);" in text
    assert 'ensurePrefsLoaded(state.activeSpace?.space_id || "no-space");' in text


def test_dashboard_scoped_prefs_fall_back_to_legacy_global_storage_once():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert 'const DASHBOARD_PREFS_LEGACY_KEY = "sipm-dashboard-view-prefs-v3";' in text
    assert "const scopedKey = dashboardPrefsStorageKey(spaceId);" in text
    assert "const persistLoadedPrefs = (prefs) => {" in text
    assert "const legacyRaw = localStorage.getItem(DASHBOARD_PREFS_LEGACY_KEY);" in text
    assert "const legacyParsed = normalizePrefs(JSON.parse(legacyRaw));" in text
    assert "localStorage.removeItem(DASHBOARD_PREFS_LEGACY_KEY);" in text
    assert "return persistLoadedPrefs(legacyParsed);" in text


def test_dashboard_default_prefs_are_seeded_into_scoped_storage():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert "if (!raw) {" in text
    assert "if (!legacyRaw) {" in text
    assert "const defaultPrefs = normalizePrefs(DEFAULT_PREFS);" in text
    assert "return persistLoadedPrefs(defaultPrefs);" in text


def test_dashboard_invalid_scoped_prefs_are_rewritten_after_normalization():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert "const parsed = JSON.parse(raw);" in text
    assert "const normalized = normalizePrefs(parsed);" in text
    assert "if (JSON.stringify(parsed) !== JSON.stringify(normalized)) {" in text
    assert "localStorage.setItem(scopedKey, JSON.stringify(normalized));" in text


def test_dashboard_malformed_scoped_prefs_fall_back_to_rewritten_defaults():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert "const defaultPrefs = normalizePrefs(DEFAULT_PREFS);" in text
    assert "localStorage.setItem(dashboardPrefsStorageKey(spaceId), JSON.stringify(defaultPrefs));" in text
    assert "return defaultPrefs;" in text


def test_dashboard_config_last_section_is_persisted_per_space():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert 'last_config_section: "main",' in text
    assert 'last_config_section: String(input?.last_config_section || DEFAULT_PREFS.last_config_section),' in text
    assert "if (!DASHBOARD_SECTIONS.includes(next.last_config_section)) next.last_config_section = DEFAULT_PREFS.last_config_section;" in text
    assert "dashboardState.prefs?.last_config_section" in text
    assert 'updatePrefs({ last_config_section: targetSection });' in text
    assert 'updatePrefs({ last_config_section: sectionId });' in text


def test_dashboard_stale_solution_selections_are_auto_cleared():
    text = DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert "function normalizeSectionSolutionSelections(sectionOptionsBySection = dashboardState.sectionOptions) {" in text
    assert "const validSolutionIds = new Set(" in text
    assert "const filteredIds = solutionIds.filter((solutionId) => validSolutionIds.has(String(solutionId || \"\").trim()));" in text
    assert "const normalizedIds = filteredIds.length ? filteredIds : null;" in text
    assert "dashboardState.prefs = normalizePrefs({" in text
    assert "savePrefs();" in text
    assert "normalizeSectionSolutionSelections(dashboardState.sectionOptions);" in text


def test_dashboard_drilldown_links_use_text_first_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".dashboard-solution-link {" in text
    assert ".dashboard-project-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert "text-underline-offset: 0.12em;" in text


def test_dashboard_config_helper_links_use_compact_local_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".dashboard-config-helper-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".dashboard-config-helper-link:hover," in text


def test_dashboard_card_action_uses_text_first_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".dashboard-card-action {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".dashboard-card-action:hover {" in text


def test_dashboard_risk_badges_use_quieter_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".dashboard-risk-badge {" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text
