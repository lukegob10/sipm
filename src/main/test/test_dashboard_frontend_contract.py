from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard.js"
DASHBOARD_COMMON = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "common.js"
DASHBOARD_PREFS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "prefs.js"
DASHBOARD_MODAL = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "modal.js"
DASHBOARD_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "interactions.js"
DASHBOARD_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "dashboard" / "render.js"
PROGRAM_DASHBOARD_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "program-dashboard" / "render.js"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"
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


def test_dashboard_theme_converges_toward_product_object_language():
    text = read_ui_styles(STYLES_CSS)

    assert "#view-dashboard .dashboard-capacity-card," in text
    assert "#view-dashboard #dashboard-backlog {" in text
    assert "border: 1px solid var(--product-border, var(--border));" in text
    assert "border-radius: 8px;" in text
    assert "background: var(--surface-sunken);" in text
    assert "box-shadow: none;" in text
    assert ".dashboard-table-shell {" in text
    assert "background: var(--data-canvas);" in text
    assert ".dashboard-main-table tbody tr:nth-child(even)," in text
    assert "background: var(--table-row-alt-bg);" in text
    assert "#view-dashboard .dashboard-condensed-table tbody tr:hover td {" in text
    assert "background: var(--hover);" in text
    assert "background: var(--table-header-bg);" in text
    assert "#view-dashboard .dashboard-main-head," in text
    assert "#view-dashboard .dashboard-card-head {" in text
    dashboard_head_block = text[text.index("#view-dashboard .dashboard-main-head,"):text.index("#view-dashboard .dashboard-title-block,")]
    assert "background: var(--section-header-bg);" in dashboard_head_block
    assert "color: var(--text-strong);" in dashboard_head_block
    assert "box-shadow: none;" in dashboard_head_block

def test_dashboard_chips_and_capacity_bars_use_compact_tokenized_styling():
    text = read_ui_styles(STYLES_CSS)

    assert "#view-dashboard .dashboard-condensed-table .pill {" in text
    assert "min-height: 18px;" in text
    assert "border-radius: 5px;" in text
    assert "background: var(--tone-positive-bg);" in text
    assert "background: var(--tone-warn-bg);" in text
    assert "background: var(--tone-danger-bg);" in text
    assert ".dashboard-fte-box {" in text
    assert "background: var(--panel-soft);" in text
    assert ".dashboard-util-bar {" in text
    assert "height: 5px;" in text
    assert ".dashboard-util-bar > span.positive {" in text
    assert "background: var(--tone-positive-border);" in text


def test_dashboard_space_snapshot_uses_compact_full_width_summary_row():
    render_text = DASHBOARD_RENDER.read_text(encoding="utf-8")
    style_text = read_ui_styles(STYLES_CSS)

    assert "dashboard-snapshot-bar" in render_text
    assert "dashboard-snapshot-stat" in render_text
    assert "dashboard-snapshot-stat-util" not in render_text
    assert "dashboard-util-bar" not in render_text[render_text.index("els.dashboardSpaceCapacity.innerHTML"):render_text.index("if (els.dashboardTopProjects)")]
    assert "Capacity and delivery pressure." not in render_text
    assert "Space Snapshot" not in render_text
    assert "Executive capacity summary for the current solution view." not in render_text
    assert "Coming (Fits FTE)" not in render_text
    assert "<span>Total Capacity</span>" in render_text
    assert "<strong>${formatFte(totalSpaceCapacity)} FTE-mo</strong>" in render_text
    assert "<span>Working Now</span>" in render_text
    assert "<strong>${formatFte(workingDemand)} FTE-mo</strong>" in render_text
    assert "<span>Utilization</span>" in render_text
    assert "<strong>${utilizationPct.toFixed(1)}%</strong>" in render_text
    assert "<span>Backlog</span>" not in render_text
    assert "<span>Headroom</span>" not in render_text

    assert "#view-dashboard .dashboard-capacity-card {" in style_text
    assert "padding: 7px 16px 7px 8px;" in style_text
    assert "box-sizing: border-box;" in style_text
    assert "justify-self: stretch;" in style_text
    assert "width: 100%;" in style_text
    assert ".dashboard-snapshot-bar {" in style_text
    assert "display: grid;" in style_text
    assert "grid-template-columns: repeat(3, max-content);" in style_text
    assert "justify-content: end;" in style_text
    assert "width: 100%;" in style_text
    assert "max-width: 100%;" in style_text
    assert "min-width: max-content;" in style_text
    assert "justify-content: flex-end;" in style_text
    assert "#view-dashboard .dashboard-capacity-card > .dashboard-util-wrap {" in style_text
    assert "#view-dashboard .dashboard-capacity-card > .dashboard-util-wrap .dashboard-util-bar {\n  display: none;" in style_text


def test_dashboard_solution_project_titles_use_gantt_like_dense_wrapping():
    text = read_ui_styles(STYLES_CSS)

    assert ".dashboard-solution-link {" in text
    assert "font-weight: 820;" in text
    assert "#view-dashboard .dashboard-condensed-table td.dashboard-col-solution .dashboard-solution-link," in text
    assert "-webkit-line-clamp: 2;" in text
    assert ".dashboard-project-link.strong {" in text
    assert "color: var(--text-strong);" in text
    assert ".dashboard-cell-meta .dashboard-project-link {" in text
    assert "color: var(--muted);" in text


def test_program_dashboard_has_light_theme_overrides():
    text = read_ui_styles(STYLES_CSS)

    assert ".product-route-panel {" in text
    assert ".product-surface {" in text
    assert ".theme-light .program-dashboard-stage {" in text
    assert ".theme-light .program-dashboard-status.pill.positive {" in text
    assert "program-dashboard-brandbar" not in text
    assert "program-dashboard-slide-footer" not in text


def test_program_dashboard_theme_converges_toward_gantt_object_language():
    text = read_ui_styles(STYLES_CSS)

    assert ".program-dashboard-table-shell {" in text
    assert ".program-dashboard-table-actions {" in text
    assert "justify-content: flex-start;" in text
    assert "background: var(--data-canvas);" in text
    assert "box-shadow: none;" in text
    assert ".program-dashboard-row-program .program-dashboard-level-marker {" in text
    assert "background: var(--text-strong);" in text
    assert ".program-dashboard-row-project .program-dashboard-level-marker {" in text
    assert "background: var(--project-pill-dot);" in text
    assert ".program-dashboard-row-solution .program-dashboard-level-marker {" in text
    assert "background: var(--solution-pill-dot);" in text
    assert ".program-dashboard-status.pill {" in text
    assert "border-radius: 5px;" in text
    assert "background: var(--tone-positive-bg);" in text
    assert "background: var(--tone-warn-bg);" in text
    assert "background: var(--tone-danger-bg);" in text
    assert ".program-dashboard-project-grid .program-dashboard-program-row .program-dashboard-grid-cell {" in text
    assert ".program-dashboard-project-grid .program-dashboard-project-row .program-dashboard-grid-cell {" in text
    assert "background: color-mix(in srgb, var(--panel) 86%, transparent);" in text
    grid_header_block = text[text.index(".program-dashboard-grid-header .program-dashboard-grid-cell {"):text.index(".program-dashboard-deliverable-cell {")]
    assert "background: var(--table-header-bg);" in grid_header_block
    assert "color: var(--text-strong);" in grid_header_block
    assert "box-shadow: none;" in grid_header_block
    assert "box-shadow: 0 0 9px" not in text[text.index(".program-dashboard-progress span {"):text.index(".program-dashboard-progress strong {")]


def test_dashboard_and_program_dashboard_use_shared_status_and_rag_display_tokens():
    common_text = DASHBOARD_COMMON.read_text(encoding="utf-8")
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    route_text = (REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "program-dashboard.js").read_text(encoding="utf-8")

    assert 'from "../../utils/display-tokens.js";' in common_text
    assert "ragPillMarkup as sharedRagPillMarkup" in common_text
    assert "statusPillMarkup" in common_text
    assert "export const ragPillMarkup = sharedRagPillMarkup;" in common_text
    assert "statusPillMarkup(row.statusRaw, formatStatusLabel(row.statusRaw))" in common_text
    assert "function ragStatusLabel" not in common_text

    assert 'import { statusPillMarkup } from "../../utils/display-tokens.js";' in render_text
    assert 'return statusPillMarkup(value, label, "program-dashboard-status");' in render_text
    assert "function statusTone" not in render_text
    assert 'from "./program-dashboard/render.js?v=program-dashboard-escalation-grid-v1";' in route_text


def test_program_dashboard_projects_grid_uses_deliverable_column_only():
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")

    assert "<th>Sub-Area</th>" not in render_text
    assert "<th>Project / Solution</th>" not in render_text
    assert 'class="program-dashboard-project-grid" role="table" aria-label="Projects and solutions"' in render_text
    assert '{ key: "deliverable", label: "Deliverable", className: "program-dashboard-deliverable-cell" }' in render_text
    assert '{ key: "owner", label: "Solution / Owner", className: "program-dashboard-owner-cell" }' in render_text
    assert '{ key: "start", label: "Start", className: "program-dashboard-date-cell program-dashboard-start-cell" }' in render_text
    assert '{ key: "end", label: "End", className: "program-dashboard-date-cell program-dashboard-end-cell" }' in render_text
    assert '{ key: "status", label: "Status", className: "program-dashboard-status-cell" }' in render_text
    assert '{ key: "phase", label: "Phase", className: "program-dashboard-phase-cell" }' in render_text
    assert '{ key: "escalation", label: "Escalation", className: "program-dashboard-escalation-cell" }' in render_text
    assert '{ key: "progress", label: "% Complete", className: "program-dashboard-progress-cell" }' in render_text
    assert 'label: "Owner"' not in render_text
    assert 'label: "Sponsor / Owner"' not in render_text
    header_order = [
        'key: "deliverable"',
        'key: "owner"',
        'key: "start"',
        'key: "end"',
        'key: "status"',
        'key: "phase"',
        'key: "escalation"',
        'key: "progress"',
    ]
    header_positions = [render_text.index(token) for token in header_order]
    assert header_positions == sorted(header_positions)
    assert "const PROJECT_GRID_COLUMN_DEFS = [" in render_text
    assert "function projectGridRow" in render_text
    assert "function projectGridHeaderRow" in render_text


def test_program_dashboard_phase_column_reuses_deliverables_phase_display():
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    router_text = ROUTER_JS.read_text(encoding="utf-8")

    assert '"program-dashboard": ["phases", "programs", "projects", "solutions"],' in router_text
    assert "phaseDisplayName: displayPhase," in render_text
    assert "phaseDisplayName(solution.current_phase)" in render_text
    assert "displayValue(solution.current_phase)" not in render_text


def test_program_dashboard_escalation_column_sits_between_phase_and_percent_complete():
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    text = read_ui_styles(STYLES_CSS)

    assert 'key: "phase", label: "Phase"' in render_text
    assert 'key: "escalation", label: "Escalation"' in render_text
    assert 'key: "progress", label: "% Complete"' in render_text
    header_order = [
        'key: "phase"',
        'key: "escalation"',
        'key: "progress"',
    ]
    assert [render_text.index(token) for token in header_order] == sorted(render_text.index(token) for token in header_order)
    assert "program-dashboard-escalation-cell" in render_text
    assert 'escalation: "",' in render_text
    assert 'escalation: esc(displayValue(solution.escalation, "")),' in render_text
    assert ".program-dashboard-escalation-cell {" in text
    project_grid_cell_rules = text[text.index(".program-dashboard-deliverable-cell {"):text.index(".program-dashboard-group-row td,")]
    assert "grid-column:" not in project_grid_cell_rules
    assert ".program-dashboard-progress-cell {\n  justify-content: center;" in text
    assert "overflow-wrap: anywhere;" in text


def test_program_dashboard_projects_remain_collapsible_headers():
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "apiBase: API_BASE," in app_text
    assert "collapsedProjectIds: new Set()," in render_text
    assert "collapsedProgramIds: new Set()," in render_text
    assert 'data-program-dashboard-action="toggle-program"' in render_text
    assert 'data-program-dashboard-action="toggle-project"' in render_text
    assert 'data-program-dashboard-action="expand-projects"' in render_text
    assert 'data-program-dashboard-action="collapse-projects"' in render_text
    assert 'data-program-dashboard-action="download-pdf"' in render_text
    assert "/programs/dashboard/report.pdf" in render_text
    assert 'className: `program-dashboard-program-row ${programCollapsed ? "program-dashboard-program-row-collapsed" : ""}`' in render_text
    assert 'className: `program-dashboard-group-row program-dashboard-project-row ${collapsed ? "program-dashboard-group-row-collapsed" : ""}`' in render_text
    assert 'className: "program-dashboard-child-row"' in render_text


def test_program_dashboard_project_solution_column_uses_gantt_like_title_styling():
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    text = read_ui_styles(STYLES_CSS)

    assert "function hierarchyLabelMarkup" in render_text
    assert "program-dashboard-label-content program-dashboard-depth-${esc(depth)} program-dashboard-row-${esc(rowType)}" in render_text
    assert "program-dashboard-item-cell" in render_text
    assert "program-dashboard-level-marker" in render_text
    assert ".program-dashboard-project-grid {" in text
    assert ".program-dashboard-grid-row {" in text
    assert ".program-dashboard-grid-cell {" in text
    assert "grid-template-columns: minmax(260px, 2fr) minmax(150px, 0.95fr)" in text
    assert "minmax(190px, 1.2fr) minmax(138px, 0.9fr)" in text
    assert 'className: "program-dashboard-date-cell program-dashboard-start-cell"' in render_text
    assert 'className: "program-dashboard-date-cell program-dashboard-end-cell"' in render_text
    project_grid_cell_rules = text[text.index(".program-dashboard-deliverable-cell {"):text.index(".program-dashboard-group-row td,")]
    assert "grid-column:" not in project_grid_cell_rules
    assert "column-gap: 1px;" in text
    assert ".program-dashboard-deliverable-cell {" in text
    assert "white-space: normal;" in text
    assert ".program-dashboard-project-grid .program-dashboard-deliverable-cell .program-dashboard-link {" in text
    assert "-webkit-line-clamp: 2;" in text
    assert ".program-dashboard-grid-row:not(.program-dashboard-grid-header):hover .program-dashboard-grid-cell" not in text
    assert ".program-dashboard-link:hover,\n.program-dashboard-link:focus-visible {\n  background: transparent;" in text
    assert ".program-dashboard-label-content {" in text
    assert ".program-dashboard-item-cell {" in text
    assert "grid-template-columns: 18px 8px minmax(0, 1fr);" in text
    assert ".program-dashboard-depth-2 {" in text
    assert "--program-dashboard-indent: 26px;" in text
    assert ".program-dashboard-depth-3 {" in text
    assert "--program-dashboard-indent: 52px;" in text
    assert ".program-dashboard-level-marker {" in text
    assert ".program-dashboard-project-link {" in text
    assert ".program-dashboard-solution-link {" in text
    assert "font-weight: 750;" in text
    assert "width: 100%;" in text
    assert ".program-dashboard-progress-cell {\n  justify-content: center;" in text
    assert ".program-dashboard-progress {\n  display: grid;" in text
    assert "border: 1px solid var(--border-strong);" in text
    assert "background: color-mix(in srgb, var(--tone-positive-border) 82%, var(--accent-strong));" in text


def test_program_dashboard_removes_open_tasks_and_uses_multi_program_picker():
    render_text = PROGRAM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    text = read_ui_styles(STYLES_CSS)

    assert "Open Tasks" not in render_text
    assert "Open Tasks & Milestones" not in render_text
    assert "renderTasksTable" not in render_text
    assert "function taskEntityMarkup" not in render_text
    assert "program-dashboard-task" not in render_text
    assert "openProgramDashboardTaskDrilldown" not in render_text
    assert "activeTab" not in render_text
    assert "selectedProgramIds: []," in render_text
    assert "prefs.selectedProgramIds" in render_text
    assert "Multiple selected" in render_text
    assert 'data-program-dashboard-control="program"' in render_text
    assert 'type="checkbox"' in render_text
    assert ".program-dashboard-picker-menu summary {" in text
    assert ".program-dashboard-picker-options {" in text
    assert ".program-dashboard-picker-option {" in text
    assert ".program-dashboard-tabs" not in text
    assert ".program-dashboard-task" not in text
    program_table_block = text[text.index(".program-dashboard-grid-cell {"):text.index(".program-dashboard-group-row td,")]
    assert "border-right:" not in program_table_block


def test_dashboard_routes_use_shared_product_route_shell():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert '<section id="view-dashboard" class="view">' in html_text
    assert '<section id="view-program-dashboard" class="view">' in html_text
    assert '<section id="view-pm-dashboard" class="view">' in html_text
    assert html_text.count('class="panel product-route-panel"') >= 3
    assert "#view-program-dashboard > .panel {" in styles_text
    assert ".dashboard-table-shell {" in styles_text
    assert ".pm-table-wrap {" in styles_text
    assert "var(--product-table-head" in styles_text
