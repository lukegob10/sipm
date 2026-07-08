import re
from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
PATHS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "paths.js"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"
SESSION_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "session.js"
LIVE_SYNC_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "live-sync.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
MODAL_SHELL_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "modal-shell.js"
TOPBAR_CREATE_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "topbar-create.js"
PROJECT_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "projects.js"
TASK_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "tasks.js"
SOLUTION_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "solutions.js"
CALENDAR_INTERACTIONS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "calendar" / "interactions.js"
KANBAN_INTERACTIONS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "kanban" / "interactions.js"
TEAM_CAPACITY_INTERACTIONS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "team-capacity" / "interactions.js"
SPACES_INTERACTIONS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "spaces" / "interactions.js"
SPACES_RENDER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "spaces" / "render.js"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
MASTER_ROUTE_TABLE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "table.js"
MASTER_ROUTE_FILTERS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "filters.js"
MASTER_ROUTE_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "interactions.js"
MASTER_ROUTE_QUICKSTART = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "quickstart.js"
PLANNING_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning.js"
PLANNING_STATE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "state.js"
PLANNING_COMMON = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "common.js"
PLANNING_STORAGE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "storage.js"
PLANNING_SELECTION = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "selection.js"
PLANNING_API = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "api.js"
PLANNING_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "interactions.js"
PLANNING_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "render.js"
PM_DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard.js"
PM_DASHBOARD_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "render.js"
TASKS_WORKBENCH_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench.js"
TASKS_WORKBENCH_BULK_ACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "bulk-actions.js"
TASKS_WORKBENCH_DRAWER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "drawer.js"
TASKS_WORKBENCH_SAVED_VIEWS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "saved-views.js"
TASKS_WORKBENCH_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "interactions.js"
TASKS_WORKBENCH_OPTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "options.js"


def test_master_remains_default_view_and_fallback():
    app_text = APP_JS.read_text(encoding="utf-8")
    router_text = ROUTER_JS.read_text(encoding="utf-8")
    assert 'currentView: "master"' in app_text
    assert "function viewFromLocationPath" in router_text
    assert 'if (relative === "/" || relative === "") return "master";' in router_text
    assert 'return normalizeView(firstSegment);' in router_text


def test_authenticated_shell_left_nav_matches_information_architecture():
    text = INDEX_HTML.read_text(encoding="utf-8")

    work_section = text[text.index('<p class="nav-label">Work</p>'):text.index('<p class="nav-label">Insight</p>')]
    insight_section = text[text.index('<p class="nav-label">Insight</p>'):text.index('<div id="nav-admin-section"')]
    admin_section = text[text.index('<p class="nav-label">Admin</p>'):text.index("</aside>")]

    assert [match.group(1) for match in re.finditer(r'data-view="([^"]+)"', work_section)] == [
        "master",
        "tasks-workbench",
        "planning",
    ]
    assert [match.group(1) for match in re.finditer(r'data-view="([^"]+)"', insight_section)] == [
        "pm-dashboard",
        "dashboard",
        "program-dashboard",
        "kanban",
        "calendar",
        "gantt",
    ]
    assert [match.group(1) for match in re.finditer(r'data-view="([^"]+)"', admin_section)] == [
        "spaces",
        "team-capacity",
        "analytics",
    ]


def test_authenticated_shell_brand_uses_compact_logo_lockup():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    assert '<div class="brand" aria-label="SIPM">' in html_text
    assert 'class="brand-mark" aria-hidden="true">' in html_text
    assert 'class="brand-mark-svg" viewBox="0 0 32 32" focusable="false"' in html_text
    assert 'class="brand-mark-frame"' in html_text
    assert 'class="brand-mark-accent"' in html_text
    assert 'class="brand-name">SIPM</span>' in html_text
    assert 'class="brand-subtitle">Portfolio Manager</span>' not in html_text
    assert ".brand {" in styles_text
    assert "display: flex;" in styles_text
    assert ".brand::before {" in styles_text
    assert ".brand-mark {" in styles_text
    assert ".brand-mark-svg {" in styles_text
    assert ".brand-mark-accent {" in styles_text
    assert ".brand-mark-dot.accent {" in styles_text
    assert ".brand-subtitle {" in styles_text
    assert ".theme-light .brand {" in styles_text
    assert ".brand {\n    display: none;" in styles_text


def test_route_hint_copy_removed_from_main_html_views():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "view-route-hint" not in text
    for route_hint in [
        "#/master",
        "#/tasks-workbench",
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


def test_work_object_views_use_consistent_product_shells():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    for view_id in ("view-master", "view-gantt", "view-kanban", "view-calendar", "view-planning"):
        section_start = html_text.index(f'id="{view_id}"')
        section_text = html_text[section_start:section_start + 220]
        assert 'class="panel product-route-panel"' in section_text

    assert ".object-shell {" in styles_text
    assert "#view-master #master-table {" in styles_text
    assert ".gantt-scroll {" in styles_text
    assert ".kanban {" in styles_text
    assert ".calendar {" in styles_text
    assert "#view-planning #planning-board {" in styles_text
    assert "var(--product-border" in styles_text


def test_shared_typography_tokens_define_compact_product_scale():
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    for token in (
        "--font-size-route-title:",
        "--font-size-section-title:",
        "--font-size-card-title:",
        "--font-size-body:",
        "--font-size-table:",
        "--font-size-table-header:",
        "--font-size-label:",
        "--font-size-meta:",
        "--font-size-chip:",
        "--font-size-control:",
        "--font-size-display:",
        "--font-size-display-compact:",
        "--font-size-icon-action:",
    ):
        assert token in styles_text

    assert "--view-title-font-size: var(--font-size-route-title);" in styles_text
    assert "body {" in styles_text
    assert "font-size: var(--font-size-body);" in styles_text
    assert ".table th {" in styles_text
    assert "font-size: var(--font-size-table-header);" in styles_text


def test_route_styles_use_typography_tokens_instead_of_raw_font_sizes():
    style_paths = [
        REPO_ROOT / "src" / "main" / "ui" / "styles.css",
        REPO_ROOT / "src" / "main" / "ui" / "styles" / "base.css",
    ]
    style_paths.extend((REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes").glob("*.css"))

    raw_font_size = re.compile(r"font-size:\s*(?:\d+(?:\.\d+)?px|\d+(?:\.\d+)?rem|clamp\(|calc\()", re.IGNORECASE)
    offenders = []
    for path in style_paths:
        text = path.read_text(encoding="utf-8")
        for match in raw_font_size.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}:{match.group(0)}")

    assert offenders == []


def test_modernized_work_views_map_visible_typography_to_shared_roles():
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    assert "--master-row-font-size: var(--font-size-table);" in styles_text
    assert "--task-workbench-row-font-size: var(--font-size-table);" in styles_text
    assert ".program-dashboard-grid-cell {" in styles_text
    assert ".program-dashboard-grid-header .program-dashboard-grid-cell {" in styles_text
    assert "font-size: var(--font-size-table);" in styles_text
    assert ".dashboard-main-table thead th," in styles_text
    assert ".gantt-title {" in styles_text
    assert ".pm-kpi-value {" in styles_text
    assert "font-size: var(--font-size-display);" in styles_text


def test_topbar_create_menu_exists_in_authenticated_shell():
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="app-shell"' in html_text
    assert 'id="topbar-create-shell"' in html_text
    assert 'id="topbar-create-toggle"' in html_text
    assert 'class="primary"' in html_text[html_text.index('id="topbar-create-toggle"') - 80:html_text.index('id="topbar-create-toggle"') + 120]
    assert 'aria-haspopup="menu"' in html_text
    assert 'id="topbar-create-panel"' in html_text
    assert 'id="topbar-create-project"' in html_text
    assert 'id="topbar-create-solution"' in html_text
    assert 'id="topbar-create-task"' in html_text
    assert 'id="create-project"' not in html_text
    assert 'id="create-solution"' not in html_text


def test_task_create_picker_modal_exists_in_shell():
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="task-create-picker-modal"' in html_text
    assert 'id="task-create-picker-title"' in html_text
    assert 'id="task-create-picker-form"' in html_text
    assert 'id="task-create-picker-select"' in html_text
    assert 'id="task-create-picker-close"' in html_text
    assert 'id="task-create-picker-cancel"' in html_text
    assert 'id="task-create-picker-status"' in html_text


def test_index_includes_shared_planning_modal_shell():
    text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="planning-modal"' in text
    assert 'id="planning-modal-title"' in text
    assert 'id="planning-modal-body"' in text
    assert 'id="planning-modal-close"' in text


def test_solution_and_task_forms_use_sticky_modal_footer_actions():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    assert 'class="modal-sticky-chrome"' in html_text
    assert 'id="solution-submit-btn"' in html_text
    assert 'id="task-submit-btn"' in html_text
    assert 'class="modal-form-footer full-span"' in html_text
    assert ".modal-form-footer {" in styles_text
    assert "position: sticky;" in styles_text
    assert "bottom: 0;" in styles_text
    assert ".modal-sticky-chrome {" in styles_text
    assert ".modal-sticky-chrome .modal-header-sticky {" in styles_text
    assert "#solution-form .modal-form-footer," in styles_text
    assert "#task-form .modal-form-footer {" in styles_text


def test_frontend_ux_state_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    planning_state_text = PLANNING_STATE.read_text(encoding="utf-8")
    planning_storage_text = PLANNING_STORAGE.read_text(encoding="utf-8")
    master_text = MASTER_ROUTE.read_text(encoding="utf-8")

    assert 'const MASTER_VIEW_STATE_KEY_PREFIX = "sipm-master-filters-v1";' in app_text
    assert 'const TASKS_WORKBENCH_UI_STATE_KEY_PREFIX = "sipm-tasks-workbench-state-v1";' in app_text
    assert 'const SPACE_GOVERNANCE_VIEW_STATE_KEY_PREFIX = "sipm-space-governance-state-v1";' in app_text
    assert 'const STORAGE_KEY_PREFIX = "sipm-planning-ui-v1";' in planning_state_text
    assert "persistMasterViewState" in app_text
    assert "collapsed: Array.from(state.masterCollapsed || [])," in app_text
    assert "state.masterCollapsed = normalizeMasterCollapsedKeys(stored.collapsed);" in app_text
    assert "persistSpaceGovernanceViewState" in app_text
    assert "restoreSpaceGovernanceViewState();" in app_text
    assert "persistTasksWorkbenchUiState" in app_text
    assert "persistViewState()" in planning_storage_text
    assert "persistMasterViewState" in master_text


def test_topbar_create_menu_reuses_existing_create_modals_and_keyboard_menu_pattern():
    app_text = APP_JS.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    topbar_text = TOPBAR_CREATE_JS.read_text(encoding="utf-8")

    assert 'topbarCreateToggle: document.getElementById("topbar-create-toggle")' in dom_text
    assert 'topbarCreatePanel: document.getElementById("topbar-create-panel")' in dom_text
    assert 'topbarCreateProject: document.getElementById("topbar-create-project")' in dom_text
    assert 'topbarCreateSolution: document.getElementById("topbar-create-solution")' in dom_text
    assert 'topbarCreateTask: document.getElementById("topbar-create-task")' in dom_text
    assert 'createProjectBtn: document.getElementById("create-project")' not in dom_text
    assert 'createSolutionBtn: document.getElementById("create-solution")' not in dom_text
    assert "function bindTopbarCreateMenu() {" in topbar_text
    assert 'const topbarCreateMenuItems = () => Array.from(els.topbarCreatePanel?.querySelectorAll("[role=\'menuitem\']") || []);' in topbar_text
    assert 'if (event.key !== "Enter" && event.key !== " " && event.key !== "ArrowDown") return;' in topbar_text
    assert "document._topbarCreateMenuCloseBound" in topbar_text
    assert 'closeTopbarCreateMenu({ restoreFocus: false });' in topbar_text
    assert "openProjectForm(null);" in topbar_text
    assert 'openSolutionModal(null, "details");' in topbar_text
    assert "handleTopbarTaskCreate" in topbar_text
    assert "bindTopbarCreateMenu();" in app_text
    assert "closeTopbarCreateMenu({ restoreFocus: false });" in topbar_text


def test_project_modal_workflow_moves_into_shared_entities_layer():
    app_text = APP_JS.read_text(encoding="utf-8")
    project_text = PROJECT_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'from "./entities/projects.js";' in app_text
    assert "const projectEntityController = createProjectEntityController({" in app_text
    assert "function openProjectForm(project = null) {" in app_text
    assert "return projectEntityController.openProjectForm(project);" in app_text
    assert "function closeProjectForm() {" in app_text
    assert "return projectEntityController.closeProjectForm();" in app_text
    assert "function bindProjectForm() {" in app_text
    assert "return projectEntityController.bindProjectForm();" in app_text
    assert "function setProjectFormVisibility(show) {" not in app_text
    assert "function setProjectActionButtonLabel(isEditing) {" not in app_text
    assert "function fillProjectForm(project = null) {" not in app_text
    assert "export function createProjectEntityController({" in project_text
    assert "function bindProjectForm() {" in project_text
    assert "function fillProjectForm(project = null) {" in project_text
    assert "function setProjectActionButtonLabel(isEditing) {" in project_text


def test_solution_modal_workflow_moves_into_shared_entities_layer():
    app_text = APP_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'from "./entities/solutions.js";' in app_text
    assert "const solutionEntityController = createSolutionEntityController({" in app_text
    assert "function bindSolutionForm() {" in app_text
    assert "return solutionEntityController.bindSolutionForm();" in app_text
    assert "function setTaskCreateAvailability(solutionId) {" in app_text
    assert "return solutionEntityController.setTaskCreateAvailability(solutionId);" in app_text
    assert 'function openSolutionModal(solution = null, tab = "details") {' in app_text
    assert "return solutionEntityController.openSolutionModal(solution, tab);" in app_text
    assert "function closeSolutionModal() {" in app_text
    assert "return solutionEntityController.closeSolutionModal();" in app_text
    assert "function buildSolutionPayload(data) {" not in app_text
    assert "function fillSolutionForm(solution = null) {" not in app_text
    assert "function setSolutionActionButtonLabel(isEditing) {" not in app_text
    assert "export function createSolutionEntityController({" in solution_text
    assert "export function buildSolutionPayload(data, { hoursFromFteInput }) {" in solution_text
    assert "function fillSolutionForm(solution = null) {" in solution_text
    assert "function setSolutionActionButtonLabel(isEditing) {" in solution_text
    assert "function setTaskCreateAvailability(solutionId) {" in solution_text


def test_task_modal_workflow_moves_into_shared_entities_layer():
    app_text = APP_JS.read_text(encoding="utf-8")
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'from "./entities/tasks.js";' in app_text
    assert "const taskEntityController = createTaskEntityController({" in app_text
    assert "function setTaskActionButtonLabel(isEditing) {" in app_text
    assert "return taskEntityController.setTaskActionButtonLabel(isEditing);" in app_text
    assert "function setTaskFormVisibility(show) {" in app_text
    assert "return taskEntityController.setTaskFormVisibility(show);" in app_text
    assert "function showTaskForm(solution) {" in app_text
    assert "return taskEntityController.showTaskForm(solution);" in app_text
    assert "function fillTaskForm(task) {" in app_text
    assert "return taskEntityController.fillTaskForm(task);" in app_text
    assert "function bindTaskForm() {" in app_text
    assert "return taskEntityController.bindTaskForm();" in app_text
    assert "function buildTaskPayload(data) {" not in app_text
    assert "function prepareTaskCreateForm(solution, options = {}) {" not in app_text
    assert "export function createTaskEntityController({" in task_text
    assert "export function buildTaskPayload(" in task_text
    assert "function prepareTaskCreateForm(solution, options = {}) {" in task_text
    assert "function fillTaskForm(task) {" in task_text
    assert "function bindTaskForm() {" in task_text


def test_calendar_controls_and_persistence_move_into_route_local_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    calendar_text = CALENDAR_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert 'from "./routes/calendar/interactions.js";' in app_text
    assert "const calendarRouteController = createCalendarRouteController({" in app_text
    assert "function persistCalendarViewState() {" in app_text
    assert "return calendarRouteController.persistCalendarViewState();" in app_text
    assert "function restoreCalendarViewState() {" in app_text
    assert "return calendarRouteController.restoreCalendarViewState();" in app_text
    assert "calendarRouteController.bindCalendarRouteControls();" in app_text
    assert "function formatMonthInputValue(date) {" not in app_text
    assert "function parseMonthInputValue(value) {" not in app_text
    assert "function openCalendarProjectDrilldown(projectId)" not in app_text
    assert "function openCalendarModal(day)" not in app_text
    assert "export function createCalendarRouteController({" in calendar_text
    assert "function formatMonthInputValue(date) {" in calendar_text
    assert "function parseMonthInputValue(value) {" in calendar_text
    assert "function openCalendarProjectDrilldown(projectId) {" in calendar_text
    assert "function openCalendarModal(day) {" in calendar_text


def test_kanban_controls_and_persistence_move_into_route_local_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    kanban_text = KANBAN_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert 'from "./routes/kanban/interactions.js";' in app_text
    assert "const kanbanRouteController = createKanbanRouteController({" in app_text
    assert "function filteredSolutionsForKanban() {" in app_text
    assert "return kanbanRouteController.filteredSolutionsForKanban();" in app_text
    assert "function persistKanbanViewState() {" in app_text
    assert "return kanbanRouteController.persistKanbanViewState();" in app_text
    assert "function restoreKanbanViewState() {" in app_text
    assert "return kanbanRouteController.restoreKanbanViewState();" in app_text
    assert "kanbanRouteController.bindKanbanRouteControls();" in app_text
    assert "function openKanbanProjectDrilldown(projectId) {" in app_text
    assert "return kanbanRouteController.openKanbanProjectDrilldown(projectId);" in app_text
    assert "function openKanbanSolutionDrilldown(solutionId) {" in app_text
    assert "return kanbanRouteController.openKanbanSolutionDrilldown(solutionId);" in app_text
    assert "export function createKanbanRouteController({" in kanban_text
    assert "function filteredSolutionsForKanban() {" in kanban_text
    assert "function persistKanbanViewState() {" in kanban_text
    assert "function restoreKanbanViewState() {" in kanban_text
    assert "function bindKanbanRouteControls() {" in kanban_text


def test_topbar_task_create_uses_solution_context_or_picker():
    topbar_text = TOPBAR_CREATE_JS.read_text(encoding="utf-8")

    assert "function taskCreateCandidateSolutions() {" in topbar_text
    assert "function taskCreateSolutionLabel(solution) {" in topbar_text
    assert "function openTaskCreatePicker(selectedSolutionId = \"\") {" in topbar_text
    assert "function handleTopbarTaskCreate() {" in topbar_text
    assert 'openSolutionModal(null, "details");' in topbar_text
    assert 'setDeliverableFormNotice(els.solutionFormStatus, "Create a solution first, then add tasks.", "error");' in topbar_text
    assert "if (solutions.length === 1) {" in topbar_text
    assert "continueTaskCreateForSolution(solutions[0]);" in topbar_text
    assert "openTaskCreatePicker(currentOpenSolutionId);" in topbar_text
    assert "showTaskForm(solution);" in topbar_text


def test_task_create_picker_modal_is_bound_for_submit_close_and_escape():
    app_text = APP_JS.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    topbar_text = TOPBAR_CREATE_JS.read_text(encoding="utf-8")

    assert 'taskCreatePickerModal: document.getElementById("task-create-picker-modal")' in dom_text
    assert "function bindTaskCreatePicker() {" in topbar_text
    assert 'els.taskCreatePickerClose.addEventListener("click", closeTaskCreatePicker);' in topbar_text
    assert 'els.taskCreatePickerCancel.addEventListener("click", closeTaskCreatePicker);' in topbar_text
    assert 'els.taskCreatePickerModal.querySelector(".modal-backdrop")?.addEventListener("click", closeTaskCreatePicker);' in topbar_text
    assert 'setDeliverableFormNotice(els.taskCreatePickerStatus, "Choose a solution first.", "error");' in topbar_text
    assert 'if (els.taskCreatePickerModal && !els.taskCreatePickerModal.classList.contains("hidden")) {' in app_text
    assert "closeTaskCreatePicker();" in app_text
    assert "bindTaskCreatePicker();" in app_text


def test_topbar_create_menu_uses_compact_topbar_menu_styling():
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    assert ".topbar-create-menu {" in styles_text
    assert ".topbar-create-panel {" in styles_text
    assert ".topbar-create-panel.hidden {" in styles_text
    assert '.topbar-create-menu > #topbar-create-toggle {' in styles_text
    assert "#topbar-create-toggle::after {" in styles_text
    assert "color: currentColor;" in styles_text
    assert ".topbar-create-item {" in styles_text


def test_master_query_filter_is_auto_cleared_and_persisted():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")

    assert "VALID_DELIVERABLE_PRESETS" not in filters_text
    assert "deliverablesPreset" not in app_text
    assert 'const normalized = normalizeMasterFilters(rawFilters);' in app_text
    assert "if (normalized.changed) changed = true;" in app_text
    assert "if (changed) persistMasterViewState();" in app_text


def test_master_query_filter_discards_legacy_field_filters():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")

    assert "VALID_DELIVERABLE_TYPES" not in filters_text
    assert 'const rawFilters = stored.filters && typeof stored.filters === "object" ? { ...stored.filters } : {};' in app_text
    assert "export function normalizeMasterFilters(filters = {}) {" in filters_text
    assert 'Object.keys(source).some((key) => key !== "query")' in filters_text
    assert 'state.filters = normalized.filters;' in app_text
    assert "if (changed) persistMasterViewState();" in app_text


def test_master_query_filter_supports_free_text_and_field_tokens():
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")

    assert "function tokenizeQuery(query) {" in filters_text
    assert "field:value" not in filters_text
    assert "MASTER_QUERY_FIELDS" in filters_text
    assert 'tokens.push(MASTER_QUERY_FIELDS.has(field) ? { field, value }' in filters_text
    assert "freeTextHaystack(ctx, program, project, solution, tasks).includes(value)" in filters_text


def test_master_priority_and_progress_query_filters_use_existing_numeric_semantics():
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")

    assert "function numericFieldMatches(ctx, field, value, solution) {" in filters_text
    assert 'if (field === "priority") return Number(solution?.priority) <= target;' in filters_text
    assert 'if (field === "progress") return Number(ctx.solutionProgress?.(solution) || 0) <= target;' in filters_text


def test_master_deliverables_presets_do_not_hide_project_rows_or_columns():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")
    interactions_text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")
    route_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")

    assert "engineering" not in filters_text
    assert "presetEngineering" not in interactions_text
    assert "VALID_DELIVERABLE_TYPES" not in filters_text
    assert 'Object.keys(source).some((key) => key !== "query")' in filters_text
    assert 'id="filter-type"' not in route_text
    assert 'value="project"' not in route_text
    assert 'value="solution"' not in route_text
    assert "<th>Version</th>" in route_text
    assert "<th>Repo</th>" not in route_text
    assert "setDeliverablesPreset" not in interactions_text
    assert 'state.filters = normalized.filters;' in app_text


def test_master_legacy_repo_presence_filter_self_heals_out_of_storage():
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")

    assert "VALID_DELIVERABLE_REPO_PRESENCE" not in filters_text
    assert "MASTER_QUERY_FIELDS" in filters_text
    assert "repo_presence" not in filters_text
    assert 'Object.keys(source).some((key) => key !== "query")' in filters_text


def test_solution_and_task_forms_include_github_repo_fields():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'Primary GitHub Repo' in html_text
    assert 'name="github_repo_url"' in html_text
    assert 'GitHub Repo Override' in html_text
    assert 'id="task-repo-preview"' in html_text
    assert 'github_repo_url: nullableTextValue(data.get("github_repo_url")),' in solution_text
    assert 'github_repo_url: nullableTextValue(data.get("github_repo_url")),' in task_text
    assert "function updateTaskRepoPreview(solutionId, overrideUrl) {" in app_text


def test_solution_modal_includes_documents_tab_and_controls():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'data-tab="documents"' in html_text
    assert 'data-tab-panel="documents"' in html_text
    assert 'id="solution-document-file"' in html_text
    assert 'id="solution-document-upload"' in html_text
    assert 'id="solution-documents-list"' in html_text
    assert 'id="solution-documents-status"' in html_text
    assert 'solutionDocumentsList: document.getElementById("solution-documents-list")' in dom_text
    assert 'solutionDocumentFile: document.getElementById("solution-document-file")' in dom_text
    assert 'function renderSolutionDocuments(solutionId, options = {}) {' in app_text
    assert 'if (tab === "documents") {' in app_text
    assert "renderSolutionDocuments(solutionId);" in app_text
    assert "bindSolutionDocumentControls();" in app_text
    assert "renderSolutionDocuments(solution.solution_id);" in solution_text
    assert "Save the solution to upload documents." in solution_text


def test_master_corrupt_scoped_view_state_is_rewritten_to_defaults():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "function readStoredJsonState(key, fallback) {" in app_text
    assert "console.warn(`Stored state for ${key} was not an object and will be reset.`);" in app_text
    assert "return { value: fallback, recovered: true };" in app_text
    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(MASTER_VIEW_STATE_KEY_PREFIX), {});" in app_text
    assert "let changed = recovered;" in app_text
    assert "if (changed) persistMasterViewState();" in app_text


def test_planning_person_search_is_persisted_per_space():
    storage_text = PLANNING_STORAGE.read_text(encoding="utf-8")
    interactions_text = PLANNING_INTERACTIONS.read_text(encoding="utf-8")

    assert 'personSearch: boardState.personSearch || "",' in storage_text
    assert 'boardState.personSearch = String(stored.personSearch || "");' in storage_text
    assert 'if (target.id === "wab-person-search") {' in interactions_text
    assert "persistViewState();" in interactions_text[interactions_text.index('if (target.id === "wab-person-search") {'):interactions_text.index('if (target.id === "wab-new-team-name") {')]


def test_planning_top_panel_is_persisted_per_space():
    state_text = PLANNING_STATE.read_text(encoding="utf-8")
    storage_text = PLANNING_STORAGE.read_text(encoding="utf-8")

    assert 'topPanel: ""' in state_text
    assert 'topPanel: boardState.topPanel || "",' in storage_text
    assert 'boardState.topPanel = String(stored.topPanel || "");' in storage_text


def test_planning_invalid_team_filter_is_auto_cleared_and_persisted():
    planning_text = PLANNING_STORAGE.read_text(encoding="utf-8")
    api_text = PLANNING_API.read_text(encoding="utf-8")

    assert "function normalizePersistedBoardFilters() {" in planning_text
    assert "const validTeamIds = new Set((boardState.data.teams || []).map((team) => String(team?.id || \"\")).filter(Boolean));" in planning_text
    assert "boardState.teamFilter === UNASSIGNED_TEAM_ID" in planning_text
    assert 'boardState.teamFilter = "all";' in planning_text
    assert "normalizePersistedBoardFilters();" in api_text


def test_planning_invalid_effort_filter_is_auto_cleared_and_persisted():
    state_text = PLANNING_STATE.read_text(encoding="utf-8")
    planning_text = PLANNING_STORAGE.read_text(encoding="utf-8")

    assert 'const VALID_EFFORT_FILTERS = new Set(["all", "small", "medium", "large"]);' in state_text
    assert 'if (!VALID_EFFORT_FILTERS.has(String(boardState.effortFilter || "all"))) {' in planning_text
    assert 'boardState.effortFilter = "all";' in planning_text
    assert "if (changed) persistViewState();" in planning_text


def test_planning_invalid_month_token_is_auto_cleared_and_persisted():
    state_text = PLANNING_STATE.read_text(encoding="utf-8")
    planning_text = PLANNING_STORAGE.read_text(encoding="utf-8")

    assert "function isValidMonthToken(value) {" in state_text
    assert "const month = Number(raw.slice(5, 7));" in state_text
    assert "return Number.isInteger(month) && month >= 1 && month <= 12;" in state_text
    assert "if (!isValidMonthToken(boardState.month)) {" in planning_text
    assert "boardState.month = currentMonthToken();" in planning_text
    assert "if (changed) persistViewState();" in planning_text


def test_planning_invalid_top_panel_is_auto_cleared_and_persisted():
    state_text = PLANNING_STATE.read_text(encoding="utf-8")
    planning_text = PLANNING_STORAGE.read_text(encoding="utf-8")

    assert 'const VALID_TOP_PANELS = new Set(["", "filters", "create", "guide", "tools"]);' in state_text
    assert 'if (!VALID_TOP_PANELS.has(String(boardState.topPanel || ""))) {' in planning_text
    assert 'boardState.topPanel = "";' in planning_text
    assert "if (changed) persistViewState();" in planning_text


def test_planning_corrupt_scoped_view_state_is_rewritten_to_defaults():
    planning_text = PLANNING_STORAGE.read_text(encoding="utf-8")

    assert "function readStoredState(spaceId) {" in planning_text
    assert 'if (!raw) return { value: {}, recovered: false };' in planning_text
    assert 'if (parsed && typeof parsed === "object") return { value: parsed, recovered: false };' in planning_text
    assert 'return { value: {}, recovered: true };' in planning_text
    assert "const { value: stored, recovered } = readStoredState(spaceId);" in planning_text
    assert "if (recovered || !Object.keys(stored || {}).length) persistViewState();" in planning_text


def test_planning_window_selection_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'planningWindowSelectedId: "",' in app_text
    assert 'const PLANNING_WINDOW_VIEW_STATE_KEY_PREFIX = "sipm-planning-window-state-v1";' in app_text
    assert "function persistPlanningWindowViewState() {" in app_text
    assert 'selected_window_id: String(state.planningWindowSelectedId || ""),' in app_text
    assert "function restorePlanningWindowViewState() {" in app_text
    assert 'state.planningWindowSelectedId = String(stored.selected_window_id || "");' in app_text
    assert "restorePlanningWindowViewState();" in app_text


def test_planning_window_corrupt_scoped_view_state_is_rewritten_to_defaults():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(PLANNING_WINDOW_VIEW_STATE_KEY_PREFIX), {});" in app_text
    assert 'state.planningWindowSelectedId = String(stored.selected_window_id || "");' in app_text
    assert "if (recovered || !Object.keys(stored || {}).length) persistPlanningWindowViewState();" in app_text


def test_planning_window_stale_selection_self_heals_to_live_option_set():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'const prev = els.planningWindowSelect.value || state.planningWindowSelectedId || "";' in app_text
    assert "let nextSelectedId = \"\";" in app_text
    assert "if (prev && state.planningWindows.find((w) => w.window_id === prev)) {" in app_text
    assert "nextSelectedId = prev;" in app_text
    assert "} else if (state.planningWindows.length) {" in app_text
    assert "nextSelectedId = state.planningWindows[0].window_id;" in app_text
    assert "state.planningWindowSelectedId = nextSelectedId;" in app_text
    assert "if (prev !== nextSelectedId) persistPlanningWindowViewState();" in app_text


def test_auth_screen_uses_local_login_register_and_reset_flow():
    session_text = SESSION_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="login-form"' in html_text
    assert 'id="register-form"' in html_text
    assert 'id="reset-screen"' in html_text
    assert 'id="auth-tab-register"' in html_text
    assert '/auth/login' in session_text
    assert '/auth/register' in session_text
    assert '/auth/reset-password' in session_text


def test_frontend_derives_project_manager_context_path_for_api_and_reset_routes():
    app_text = APP_JS.read_text(encoding="utf-8")
    paths_text = PATHS_JS.read_text(encoding="utf-8")
    router_text = ROUTER_JS.read_text(encoding="utf-8")
    session_text = SESSION_JS.read_text(encoding="utf-8")
    live_sync_text = LIVE_SYNC_JS.read_text(encoding="utf-8")
    planning_text = PLANNING_API.read_text(encoding="utf-8")
    pm_dashboard_text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")

    assert "export const APP_CONTEXT_PATH = (() => {" in paths_text
    assert 'export const API_BASE = `${APP_CONTEXT_PATH}/api` || "/api";' in paths_text
    assert "function routePathForView(view)" in router_text
    assert "function syncPathForView(view, replace = false)" in router_text
    assert 'window.addEventListener("popstate"' in app_text
    assert 'const me = await api("/auth/me");' in session_text
    assert 'setStatus("Checking session...", "warn");' in session_text
    assert 'const url = new URL(buildWsUrl("/ws"));' in live_sync_text
    assert "resolveApiBase(ctx)" in planning_text
    assert "viewHref," in app_text
    assert "const hrefFor = (view) => {" in pm_dashboard_text
    assert "/api/planning/work-allocation/report.pdf" not in planning_text
    assert "#/" not in pm_dashboard_text


def test_planning_route_uses_inline_forms_confirm_modal_and_title_drilldown_controls():
    render_text = PLANNING_RENDER.read_text(encoding="utf-8")
    api_text = PLANNING_API.read_text(encoding="utf-8")
    interactions_text = PLANNING_INTERACTIONS.read_text(encoding="utf-8")
    selection_text = PLANNING_SELECTION.read_text(encoding="utf-8")

    assert "wab-create-form" in render_text
    assert "ctx?.showConfirmModal" in api_text
    assert "data-assign-target" in render_text
    assert "wab-modal-shell" not in render_text
    assert 'data-wab-action="open-project"' in render_text
    assert 'data-wab-action="open-solution"' in render_text
    assert "openPlanningProjectDrilldown" in api_text
    assert "openPlanningSolutionDrilldown" in api_text
    assert 'action === "close-task-detail" || action === "close-task-modal"' in api_text
    assert 'if (key === "Escape" && boardState.selectedTaskId)' in interactions_text
    assert 'closest(".wab-task-chip")' in interactions_text
    assert "closeTaskDetail" in selection_text
    assert "wab-person-search" in render_text
    assert "window.prompt" not in api_text
    assert "window.confirm" not in api_text


def test_app_shell_planning_allocation_delete_uses_shared_confirm_modal():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'title: "Delete Allocation?"' in text
    assert 'message: "Delete this allocation?"' in text
    assert 'confirmLabel: "Delete Allocation"' in text
    assert 'const confirmDelete = confirm("Delete this allocation?");' not in text


def test_app_shell_confirm_modal_is_required_and_never_falls_back_to_browser_confirm():
    modal_text = MODAL_SHELL_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="confirm-modal"' in html_text
    assert 'id="confirm-modal-title"' in html_text
    assert 'id="confirm-modal-message"' in html_text
    assert 'id="confirm-modal-close"' in html_text
    assert 'id="confirm-modal-cancel"' in html_text
    assert 'id="confirm-modal-confirm"' in html_text
    assert 'console.warn("Confirm modal shell missing; canceling action.");' in modal_text
    assert "return Promise.resolve(false);" in modal_text
    assert "Promise.resolve(confirm(message));" not in modal_text


def test_tasks_workbench_saved_view_delete_uses_shared_confirm_modal():
    app_text = APP_JS.read_text(encoding="utf-8")
    saved_views_text = TASKS_WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/saved-views.js";' in app_text
    assert 'title: "Delete Saved View?"' in saved_views_text
    assert 'message: `Delete saved view "${saved.name}"?`' in saved_views_text
    assert 'confirmLabel: "Delete Saved View"' in saved_views_text
    assert 'if (!confirm(`Delete saved view "${saved.name}"?`)) return;' not in saved_views_text


def test_team_capacity_member_deactivate_uses_shared_confirm_modal():
    app_text = APP_JS.read_text(encoding="utf-8")
    text = TEAM_CAPACITY_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert 'from "./routes/team-capacity/interactions.js";' in app_text
    assert 'title: "Deactivate Member?"' in text
    assert 'message: "Deactivate this member? They will be hidden from the roster."' in text
    assert 'confirmLabel: "Deactivate Member"' in text
    assert 'if (!confirm("Deactivate this member? They will be hidden from the roster.")) return;' not in text


def test_tasks_workbench_saved_view_delete_without_selection_uses_inline_status():
    text = TASKS_WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert 'setTasksWorkbenchSavedStatus(ctx, "Select a saved view to delete.");' in text
    assert 'alert("Select a saved view to delete.");' not in text


def test_tasks_workbench_saved_view_save_without_name_uses_inline_status():
    text = TASKS_WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert 'setTasksWorkbenchSavedStatus(ctx, "Enter a view name before saving.");' in text
    assert 'alert("Enter a view name before saving.");' not in text


def test_tasks_workbench_bulk_actions_use_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")
    bulk_text = TASKS_WORKBENCH_BULK_ACTIONS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="tasks-workbench-bulk-feedback"' in html_text
    assert "function setTasksWorkbenchBulkFeedback(message, tone = \"info\", autoClearMs = 0)" in app_text
    assert 'setTasksWorkbenchBulkFeedback("Choose a bulk action.", "error");' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback("Select at least one task.", "error");' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback("Select a status value.", "error");' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback("Enter a due date shift in whole days (e.g. 3 or -2).", "error");' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback("Unsupported bulk action.", "error");' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback(`Bulk update failed: ${err.message || err}`, "error");' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback(\n      `Updated ${selectedIds.length} task${selectedIds.length === 1 ? "" : "s"}.`,' in bulk_text
    assert 'alert("Choose a bulk action.");' not in bulk_text
    assert 'alert("Select at least one task.");' not in bulk_text
    assert 'alert("Select a status value.");' not in bulk_text
    assert 'alert("Enter a due date shift in whole days (e.g. 3 or -2).");' not in bulk_text
    assert 'alert("Unsupported bulk action.");' not in bulk_text
    assert 'alert(`Bulk update failed: ${err.message || err}`);' not in bulk_text


def test_tasks_workbench_delete_outcomes_use_inline_feedback():
    bulk_text = TASKS_WORKBENCH_BULK_ACTIONS.read_text(encoding="utf-8")

    assert 'deleteTargets.length === 1 ? "Deleting task…" : `Deleting ${deleteTargets.length} tasks…`' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback(\n        `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,\n        "error"\n      );' in bulk_text
    assert 'setTasksWorkbenchBulkFeedback(\n      `Deleted ${result.deletedIds.length} task${result.deletedIds.length === 1 ? "" : "s"}.`,\n      "success",\n      3200\n    );' in bulk_text
    assert 'setStatus(`Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`, "danger");' not in bulk_text
    assert 'setStatus(`Deleted ${result.deletedIds.length} task${result.deletedIds.length === 1 ? "" : "s"}.`, "positive");' not in bulk_text


def test_tasks_workbench_modal_editor_behaviors_are_route_local():
    app_text = APP_JS.read_text(encoding="utf-8")
    drawer_text = TASKS_WORKBENCH_DRAWER.read_text(encoding="utf-8")
    interactions_text = TASKS_WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/drawer.js";' in app_text
    assert 'id="tasks-workbench-drawer" class="modal task-workbench-editor-modal hidden"' in html_text
    assert 'id="tasks-workbench-editor-title" tabindex="-1">Edit Task</h3>' in html_text
    assert 'form="tasks-workbench-form">Save Changes</button>' in html_text
    assert "function syncTasksWorkbenchDrawer(ctx) {" in drawer_text
    assert 'els.tasksWorkbenchDrawer.setAttribute("aria-hidden", drawerOpen ? "false" : "true");' in drawer_text
    assert "function fillTasksWorkbenchForm(ctx, task) {" in drawer_text
    assert "async function saveTasksWorkbenchForm(ctx) {" in drawer_text
    assert "async function deleteActiveTasksWorkbenchItem(ctx) {" in drawer_text
    assert "async function handleTasksWorkbenchShortcut(ctx, event) {" in drawer_text
    assert "syncTasksWorkbenchDrawer(workbenchCtx);" in app_text
    assert "fillTasksWorkbenchForm(workbenchCtx, active);" in app_text
    assert "await saveTasksWorkbenchForm(ctx);" in interactions_text
    assert "await deleteActiveTasksWorkbenchItem(ctx);" in interactions_text
    assert 'els.tasksWorkbenchDrawer.addEventListener("click", (event) => {' in interactions_text
    assert 'event.target?.classList?.contains("task-workbench-editor-backdrop")' in interactions_text
    assert "await handleTasksWorkbenchShortcut(ctx, event);" in interactions_text


def test_tasks_workbench_control_bindings_are_route_local():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = TASKS_WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/interactions.js";' in app_text
    assert "bindWorkbenchControls(createTasksWorkbenchContext());" in app_text
    assert "function bindTasksWorkbenchControls(ctx) {" in interactions_text
    assert 'const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");' in interactions_text
    assert 'bindDebouncedInput(els.tasksWorkbenchSearch, (value) => {' in interactions_text
    assert 'els.tasksWorkbenchProject.addEventListener("change", () => {' in interactions_text
    assert "updateTasksWorkbenchSolutionOptions(ctx, wb.filters.project_id);" in interactions_text
    assert 'els.tasksWorkbenchTable.addEventListener("change", (event) => {' in interactions_text
    assert 'const rowCheck = event.target.closest(".scwb-select-row");' in interactions_text
    assert "bindTasksWorkbenchSavedViewControls(ctx);" in interactions_text


def test_tasks_workbench_option_population_is_route_local():
    app_text = APP_JS.read_text(encoding="utf-8")
    options_text = TASKS_WORKBENCH_OPTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/options.js";' in app_text
    assert "function populateTasksWorkbenchOptions(ctx, { projectOptionsHtml = \"\" } = {}) {" in options_text
    assert 'const users = state.users' in options_text
    assert 'els.tasksWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;' in options_text
    assert 'els.tasksWorkbenchBulkAssignee.innerHTML = `<option value="">Unassigned</option>${userOptions}`;' in options_text
    assert "normalizeTasksWorkbenchUiState({ persist: true });" in options_text
    assert "populateTasksWorkbenchOptions(createTasksWorkbenchContext(), { projectOptionsHtml: projectOpts });" in app_text


def test_deliverables_bulk_actions_are_removed_from_deliverables_route():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="bulk-feedback"' not in html_text
    assert 'id="deliverables-bulk-toolbar"' not in html_text
    assert 'id="deliverables-select-all"' not in html_text
    assert 'class="deliverable-select"' not in interactions_text
    assert "applyBulkDeliverableAction" not in interactions_text
    assert "deliverableSelection" not in interactions_text
    assert "updateBulkSelectionCount" not in app_text
    assert 'setStatus("Updating deliverables…");' not in app_text
    assert 'setStatus("Deliverables updated", "positive");' not in app_text
    assert 'alert("Select a status first.");' not in interactions_text
    assert 'alert("Enter an owner name.");' not in interactions_text
    assert 'alert(`Bulk update failed: ${err.message}`);' not in interactions_text


def test_deliverables_inline_field_updates_do_not_depend_on_bulk_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")

    assert "async function updateDeliverableField(ctx, type, id, field, value) {" in interactions_text
    assert "clearBulkFeedback" not in interactions_text
    assert "setBulkFeedback" not in interactions_text
    assert "clearBulkFeedback" not in app_text
    assert "setBulkFeedback" not in app_text
    assert 'setStatus("Deliverable updated", "positive");' not in app_text
    assert 'setStatus("Deliverable update failed", "danger");' not in app_text
    assert 'alert(`Update failed: ${err.message}`);' not in interactions_text


def test_icon_only_controls_have_accessible_tooltips_and_svg_icons():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    master_table_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")
    planning_render_text = PLANNING_RENDER.read_text(encoding="utf-8")
    spaces_render_text = SPACES_RENDER_JS.read_text(encoding="utf-8")
    styles_text = read_ui_styles(REPO_ROOT / "src" / "main" / "ui" / "styles.css")

    assert "\u270e" not in master_table_text
    assert "\uff0b" not in master_table_text
    assert 'data-action="edit" data-type="solution" data-id="${safeSolutionId}" aria-label="Edit solution" title="Edit" data-tooltip="Edit"' in master_table_text
    assert 'data-action="add-task" data-type="solution" data-id="${safeSolutionId}" aria-label="Add task" title="Add task" data-tooltip="Add task"' in master_table_text
    assert 'class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"' in master_table_text

    assert "\u25c0" not in html_text
    assert "\u25b6" not in html_text
    assert 'id="calendar-prev" class="secondary icon-btn" aria-label="Previous month" title="Previous month" data-tooltip="Previous month"' in html_text
    assert 'id="calendar-next" class="secondary icon-btn" aria-label="Next month" title="Next month" data-tooltip="Next month"' in html_text

    assert 'data-wab-action="delete-team"' in planning_render_text
    assert ">Delete Team</button>" in planning_render_text
    assert 'title="Delete team">x</button>' not in planning_render_text

    assert 'class="secondary modal-close-x" id="tasks-workbench-close" aria-label="Close task editor" title="Close" data-tooltip="Close"' in html_text
    assert 'class="secondary modal-close-x" data-space-action="clear-api-token-result" aria-label="Close API token dialog" title="Close" data-tooltip="Close"' in spaces_render_text
    assert re.search(r'class="[^"]*modal-close-x[^"]*"[^>]*>\s*(?:&times;|x|\u00d7)\s*</button>', html_text) is None
    assert re.search(r'class="[^"]*modal-close-x[^"]*"[^>]*>\s*x\s*</button>', spaces_render_text) is None

    assert ".icon-btn[data-tooltip]::after" in styles_text
    assert ".modal-close-x[data-tooltip]::after" in styles_text
    assert ".icon-btn-svg" in styles_text


def test_team_capacity_member_form_uses_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert 'id="capacity-user-form-status"' in html_text
    assert "function setCapacityUserFormStatus(message, tone = \"info\", autoClearMs = 0)" in app_text
    assert 'setCapacityUserFormStatus("Select a member from the roster (or type an exact SOEID/name match) first.", "error");' in interactions_text
    assert 'setCapacityUserFormStatus(`Save failed: ${err.message}`, "error");' in interactions_text
    assert 'setCapacityUserFormStatus("Select a member first.", "error");' in interactions_text
    assert 'setCapacityUserFormStatus(`Delete failed: ${err.message}`, "error");' in interactions_text
    assert 'setCapacityUserFormStatus(`Saved member at ${timestampLabel()}.`, "success", 3200);' in interactions_text
    assert 'setCapacityUserFormStatus(`Member deactivated at ${timestampLabel()}.`, "success", 3200);' in interactions_text
    assert 'alert("Select a member from the roster (or type an exact SOEID/name match) first.");' not in interactions_text
    assert 'alert("Select a member first.");' not in interactions_text


def test_planning_allocation_delete_failure_uses_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'if (els.allocationStatus) els.allocationStatus.textContent = `Delete failed: ${err.message}`;' in app_text
    assert 'alert(`Delete failed: ${err.message}`);' not in app_text


def test_planning_allocation_save_failure_uses_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'if (els.allocationStatus) els.allocationStatus.textContent = `Save failed: ${err.message || err}`;' in app_text
    assert 'alert(`Save failed: ${err.message || err}`);' not in app_text


def test_planning_window_required_fields_uses_in_app_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'setStatus("Name, start, and end are required to create a planning window.", "danger");' in app_text
    assert 'alert("Name, start, and end are required to create a planning window.");' not in app_text


def test_planning_window_save_failure_uses_in_app_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'setStatus(`Window create failed: ${err.message}`, "danger");' in app_text
    assert 'alert(`Window create failed: ${err.message}`);' not in app_text


def test_planning_dragging_assigned_task_moves_existing_allocation_instead_of_creating_duplicate():
    api_text = PLANNING_API.read_text(encoding="utf-8")
    interactions_text = PLANNING_INTERACTIONS.read_text(encoding="utf-8")

    assert "async function moveAssignment(allocationId, assigneeType, assigneeId" in api_text
    assert '`/planning/work-allocation/allocations/${encodeURIComponent(existing.id)}`' in api_text
    assert 'method: "PATCH"' in api_text
    assert 'kind: "move-assignment"' in api_text
    assert 'await moveAssignment(allocationId, "person", zone.personId, { pushUndo: true });' in interactions_text
    assert 'await moveAssignment(allocationId, "team", zone.teamId, { pushUndo: true });' in interactions_text


def test_operational_views_can_hide_completed_work_across_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")
    planning_common_text = PLANNING_COMMON.read_text(encoding="utf-8")
    planning_render_text = PLANNING_RENDER.read_text(encoding="utf-8")
    workbench_text = TASKS_WORKBENCH_ROUTE.read_text(encoding="utf-8")

    assert 'id="completed-visibility-toggle"' in html_text
    assert 'const WORKSPACE_VIEW_PREFS_KEY_PREFIX = "sipm-workspace-prefs-v1";' in app_text
    assert 'workspacePrefs: { showCompleted: false },' in app_text
    assert "function renderCompletedVisibilityToggle()" in app_text
    assert "function showCompletedOperationalWork()" in app_text
    assert "if (hideClosedDeliverables() && isClosedSolutionStatus(solution.status)) return false;" in filters_text
    assert "if (hideClosedDeliverables() && isClosedProjectStatus(project?.status)) return false;" in filters_text
    assert "if (!showCompletedOperationalWork() && isCompletedTaskStatus(sc.status)) return false;" in app_text
    assert "Completed items are hidden here. Use Show Completed in the top bar" in app_text
    assert "ctx?.state?.workspacePrefs?.showCompleted" in planning_common_text
    assert "completed or abandoned task" in planning_render_text
    assert "summary?.hiddenClosed" in workbench_text


def test_workspace_prefs_corrupt_or_empty_state_is_rewritten_to_defaults():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "function restoreWorkspaceViewPreferences() {" in app_text
    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(WORKSPACE_VIEW_PREFS_KEY_PREFIX), {});" in app_text
    assert "const nextShowCompleted = stored.showCompleted === true;" in app_text
    assert "if (recovered || !Object.keys(stored || {}).length || stored.showCompleted !== nextShowCompleted) {" in app_text
    assert "persistWorkspaceViewPreferences();" in app_text


def test_calendar_kanban_and_team_capacity_seed_default_scoped_state():
    app_text = APP_JS.read_text(encoding="utf-8")
    calendar_text = CALENDAR_INTERACTIONS_JS.read_text(encoding="utf-8")
    kanban_text = KANBAN_INTERACTIONS_JS.read_text(encoding="utf-8")
    team_capacity_text = TEAM_CAPACITY_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert "function restoreCalendarViewState() {" in app_text
    assert "return calendarRouteController.restoreCalendarViewState();" in app_text
    assert "state.calendarMonth = parsedMonth || state.calendarMonth || new Date();" in calendar_text
    assert "if (recovered || !Object.keys(stored || {}).length || !parsedMonth) persistCalendarViewState();" in calendar_text
    assert "function restoreKanbanViewState() {" in app_text
    assert "return kanbanRouteController.restoreKanbanViewState();" in app_text
    assert "if (recovered || !Object.keys(stored || {}).length) persistKanbanViewState();" in kanban_text
    assert "function restoreTeamCapacityViewState() {" in app_text
    assert "return teamCapacityRouteController.restoreTeamCapacityViewState();" in app_text
    assert "if (recovered || !Object.keys(stored || {}).length) persistTeamCapacityViewState();" in team_capacity_text


def test_team_capacity_controls_and_persistence_move_into_route_local_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = TEAM_CAPACITY_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert 'from "./routes/team-capacity/interactions.js";' in app_text
    assert "const teamCapacityRouteController = createTeamCapacityRouteController({" in app_text
    assert "function bindCapacityUsers() {" in app_text
    assert "return teamCapacityRouteController.bindTeamCapacityControls();" in app_text
    assert "function restoreTeamCapacityViewState() {" in app_text
    assert "return teamCapacityRouteController.restoreTeamCapacityViewState();" in app_text
    assert "async function loadTeamCapacityData(options = {}) {" in app_text
    assert "return teamCapacityRouteController.loadTeamCapacityData(options);" in app_text
    assert "export function createTeamCapacityRouteController({" in interactions_text
    assert "function bindTeamCapacityControls() {" in interactions_text
    assert "async function loadTeamCapacityData(options = {}) {" in interactions_text
    assert "function persistTeamCapacityViewState() {" in interactions_text
    assert "function restoreTeamCapacityViewState() {" in interactions_text


def test_space_governance_modal_and_action_bindings_move_into_route_local_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = SPACES_INTERACTIONS_JS.read_text(encoding="utf-8")
    render_text = SPACES_RENDER_JS.read_text(encoding="utf-8")

    assert 'from "./routes/spaces/interactions.js' in app_text
    assert 'from "./routes/spaces/render.js' in app_text
    assert 'from "./routes/spaces/interactions.js?v=' not in app_text
    assert 'from "./routes/spaces/render.js?v=' not in app_text
    assert "const spaceGovernanceController = createSpaceGovernanceController({" in app_text
    assert "const spaceGovernanceRenderer = createSpaceGovernanceRenderer({" in app_text
    assert "function bindSpaceAdminControls() {" in app_text
    assert "return spaceGovernanceController.bindSpaceAdminControls();" in app_text
    assert "function renderGovernanceHub(preferredSection = \"\") {" in app_text
    assert "const result = spaceGovernanceRenderer.renderGovernanceHub(preferredSection);" in app_text
    assert "persistSpaceGovernanceViewState();" in app_text
    assert "export function createSpaceGovernanceController({" in interactions_text
    assert "function openSpaceCreateModal() {" in interactions_text
    assert "async function handleSpaceGovernanceAction(button) {" in interactions_text
    assert 'els.spaceGovernanceShell.addEventListener("submit", async (event) => {' in interactions_text
    assert 'data-space-action="copy-temp-password"' not in interactions_text
    assert "export function createSpaceGovernanceRenderer({" in render_text
    assert "function renderPlatformPasswordResetResult() {" in render_text
    assert 'data-space-action="copy-temp-password"' in render_text
