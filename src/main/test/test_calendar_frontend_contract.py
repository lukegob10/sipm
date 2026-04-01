from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
CALENDAR_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "calendar.js"
CALENDAR_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "calendar" / "interactions.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_calendar_view_passes_solution_and_subcomponent_filters_to_route_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = CALENDAR_INTERACTIONS.read_text(encoding="utf-8")

    assert "filteredSolutionsForCalendar," in app_text
    assert "filteredSubcomponentsForCalendar," in app_text
    assert "mod.openCalendarModal(day, {" in interactions_text


def test_calendar_solution_filtering_is_independent_from_deliverables_master_filters():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function filteredSolutionsForCalendar() {" in text
    assert "return (state.solutions || []).filter((s) => {" in text
    assert "if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;" in text
    assert "const base = filteredSolutions();" not in text[text.index("function filteredSolutionsForCalendar() {"):text.index("function filteredSubcomponentsForCalendar() {")]


def test_calendar_month_state_is_restored_and_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = CALENDAR_INTERACTIONS.read_text(encoding="utf-8")

    assert 'const CALENDAR_VIEW_STATE_KEY_PREFIX = "sipm-calendar-view-state-v1";' in app_text
    assert "function persistCalendarViewState() {" in app_text
    assert "return calendarRouteController.persistCalendarViewState();" in app_text
    assert "function restoreCalendarViewState() {" in app_text
    assert "return calendarRouteController.restoreCalendarViewState();" in app_text
    assert "activeSpaceScopedStorageKey(calendarViewStateKey)" in interactions_text
    assert 'month: formatMonthInputValue(state.calendarMonth || new Date()),' in interactions_text
    assert "filters: {" in interactions_text
    assert 'project: state.calendarFilters?.project || "",' in interactions_text
    assert 'owner: state.calendarFilters?.owner || "",' in interactions_text
    assert 'const parsedMonth = parseMonthInputValue(stored.month || "");' in interactions_text
    assert "state.calendarFilters = {" in interactions_text
    assert "restoreCalendarViewState();" in app_text
    assert "persistCalendarViewState();" in app_text


def test_calendar_corrupt_scoped_view_state_is_rewritten_to_defaults():
    text = CALENDAR_INTERACTIONS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(calendarViewStateKey), {});" in text
    assert 'project: String(stored.filters?.project || ""),' in text
    assert 'owner: String(stored.filters?.owner || ""),' in text
    assert "if (recovered) persistCalendarViewState();" in text


def test_calendar_owner_filter_control_is_restored_from_persisted_state():
    text = CALENDAR_INTERACTIONS.read_text(encoding="utf-8")

    assert 'owner: String(stored.filters?.owner || ""),' in text
    assert "bindDebouncedInput(els.calendarFilterOwner, (value) => {" in text
    assert "state.calendarFilters.owner = value;" in text


def test_calendar_invalid_project_filter_is_auto_cleared_when_projects_refresh():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function normalizeScopedProjectFilter(filterState) {" in text
    assert 'const currentProjectId = String(filterState.project || "");' in text
    assert "filterState.project = \"\";" in text
    assert "const calendarProjectFilterChanged = normalizeScopedProjectFilter(state.calendarFilters);" in text
    assert "if (calendarProjectFilterChanged) {" in text
    assert "persistCalendarViewState();" in text


def test_calendar_invalid_owner_filter_is_auto_cleared_when_it_matches_no_current_owner_or_assignee():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function normalizeScopedOwnerFilter(filterState, { includeSolutions = true, includeSubcomponents = false } = {}) {" in text
    assert 'const calendarOwnerFilterChanged = normalizeScopedOwnerFilter(state.calendarFilters, {' in text
    assert "includeSubcomponents: true," in text
    assert 'filterState.owner = "";' in text
    assert "if (calendarOwnerFilterChanged) {" in text
    assert "persistCalendarViewState();" in text


def test_calendar_route_renders_solution_and_subcomponent_sections():
    text = CALENDAR_ROUTE.read_text(encoding="utf-8")
    assert "Solutions" in text
    assert "Subcomponents" in text
    assert "calendar-stream-label" in text
    assert "modal-section-title" in text


def test_calendar_route_renders_drilldown_actions_for_modal_items():
    text = CALENDAR_ROUTE.read_text(encoding="utf-8")
    assert "function renderCalendarPreviewTitle(item, type, titleField) {" in text
    assert 'data-calendar-preview-action="open-solution"' in text
    assert 'class="calendar-preview-link"' in text
    assert 'class="calendar-modal-action-link modal-item-action"' in text
    assert 'actionButtonMarkup("open-project"' in text
    assert 'actionButtonMarkup("open-solution"' in text
    assert 'actionButtonMarkup("open-subcomponent"' in text
    assert "Open Project" in text
    assert "Open Solution" in text
    assert "Open Work Item" in text


def test_calendar_modal_actions_reuse_existing_detail_surfaces():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = CALENDAR_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/calendar/interactions.js";' in app_text
    assert "calendarRouteController.bindCalendarRouteControls();" in app_text
    assert "function openCalendarProjectDrilldown(projectId)" in interactions_text
    assert "openProjectForm(project)" in interactions_text
    assert "function openCalendarSolutionDrilldown(solutionId)" in interactions_text
    assert 'openSolutionModal(solution, "details")' in interactions_text
    assert "function openCalendarSubcomponentDrilldown(subcomponentId)" in interactions_text
    assert 'openSolutionModal(solution, "subcomponents")' in interactions_text
    assert "fillSubcomponentForm(subcomponent)" in interactions_text
    assert 'const previewActionEl = e.target.closest("[data-calendar-preview-action]")' in interactions_text
    assert 'if (action === "open-solution") {' in interactions_text
    assert 'closest("[data-calendar-action]")' in interactions_text
    assert 'if (action === "open-project") {' in interactions_text


def test_calendar_preview_link_uses_text_first_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".calendar-preview-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".calendar-preview-link:hover {" in text
    assert "text-underline-offset: 0.12em;" in text


def test_calendar_modal_action_links_use_compact_local_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".calendar-modal-action-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".calendar-modal-action-link:hover," in text


def test_calendar_day_cells_use_flatter_container_chrome():
    text = read_ui_styles(STYLES_CSS)

    assert ".calendar-cell {" in text
    assert "box-shadow: none;" in text
    assert ".calendar-cell.today {" in text
    assert "box-shadow: var(--selected-ring-strong);" in text


def test_calendar_day_counts_use_quieter_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".calendar-count {" in text
    assert "background: transparent;" in text
    assert "border-radius: 0;" in text
    assert "padding: 0;" in text
