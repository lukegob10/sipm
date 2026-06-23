from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
WORKBENCH_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench.js"
WORKBENCH_FILTERS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "filters.js"
WORKBENCH_BULK_ACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "bulk-actions.js"
WORKBENCH_DRAWER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "drawer.js"
WORKBENCH_SAVED_VIEWS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "saved-views.js"
WORKBENCH_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "interactions.js"
WORKBENCH_OPTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "tasks-workbench" / "options.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
TASKS_STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "tasks-workbench.css"


def test_workbench_route_renders_project_context_as_drilldown_link():
    text = WORKBENCH_ROUTE.read_text(encoding="utf-8")

    assert "function renderTasksWorkbenchProjectLink(label, projectId) {" in text
    assert "function renderTasksWorkbenchSolutionLink(label, solutionId) {" in text
    assert 'class="task-workbench-context-link" data-twb-action="open-project"' in text
    assert 'class="task-workbench-context-link" data-twb-action="open-solution"' in text
    assert 'data-project-id="${esc(targetId)}"' in text
    assert 'data-solution-id="${esc(targetId)}"' in text
    assert 'renderTasksWorkbenchProjectLink(row.project_name, row.project_id)' in text
    assert 'renderTasksWorkbenchSolutionLink(row.solution_name, row.solution_id)' in text


def test_workbench_project_context_link_reuses_existing_project_modal():
    app_text = APP_JS.read_text(encoding="utf-8")
    drawer_text = WORKBENCH_DRAWER.read_text(encoding="utf-8")
    interactions_text = WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/drawer.js";' in app_text
    assert "handleTasksWorkbenchTableClick(ctx, event)" in interactions_text
    assert "handleTasksWorkbenchContextClick(ctx, event)" in interactions_text
    assert "await saveTasksWorkbenchForm(ctx);" in interactions_text
    assert "await deleteActiveTasksWorkbenchItem(ctx);" in interactions_text
    assert "resetTasksWorkbenchEditor(ctx)" in interactions_text
    assert "await handleTasksWorkbenchShortcut(ctx, event);" in interactions_text
    assert "function openTasksWorkbenchProjectDrilldown(ctx, projectId) {" in drawer_text
    assert "function openTasksWorkbenchSolutionDrilldown(ctx, solutionId) {" in drawer_text
    assert "function renderTasksWorkbenchDrawerProjectLink(ctx, label, projectId) {" in drawer_text
    assert "function renderTasksWorkbenchDrawerSolutionLink(ctx, label, solutionId) {" in drawer_text
    assert "function renderTasksWorkbenchDrawerRepoContext(ctx, task) {" in drawer_text
    assert 'class="task-workbench-context-link" data-twb-context-action="open-project"' in drawer_text
    assert 'class="task-workbench-context-link" data-twb-context-action="open-solution"' in drawer_text
    assert "openProjectForm(project);" in drawer_text
    assert 'openSolutionModal(solution, "details");' in drawer_text
    assert 'const actionEl = event.target.closest("[data-twb-action]");' in drawer_text
    assert 'const actionEl = event.target.closest("[data-twb-context-action]");' in drawer_text
    assert 'renderTasksWorkbenchDrawerProjectLink(ctx, project, task.project_id)' in drawer_text
    assert 'renderTasksWorkbenchDrawerSolutionLink(ctx, solution, task.solution_id)' in drawer_text
    assert 'renderTasksWorkbenchDrawerRepoContext(ctx, task)' in drawer_text


def test_workbench_editor_uses_centered_modal_shell():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    drawer_text = WORKBENCH_DRAWER.read_text(encoding="utf-8")
    interactions_text = WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")
    styles_text = TASKS_STYLES.read_text(encoding="utf-8")

    assert 'id="tasks-workbench-drawer" class="modal task-workbench-editor-modal hidden"' in html_text
    assert 'role="dialog" aria-modal="true" aria-labelledby="tasks-workbench-editor-title"' in html_text
    assert 'class="modal-backdrop task-workbench-editor-backdrop"' in html_text
    assert 'id="tasks-workbench-editor-title" tabindex="-1">Edit Task</h3>' in html_text
    assert 'id="tasks-workbench-form" class="form compact"' in html_text
    assert 'form="tasks-workbench-form">Save Changes</button>' in html_text
    assert "task-workbench-layout-drawer-hidden" not in html_text
    assert 'els.tasksWorkbenchDrawer.setAttribute("aria-hidden", drawerOpen ? "false" : "true");' in drawer_text
    assert 'event.target?.classList?.contains("task-workbench-editor-backdrop")' in interactions_text
    assert ".task-workbench-editor-modal {" in styles_text
    assert ".task-workbench-editor-content {" in styles_text
    assert ".task-workbench-layout {" in styles_text
    assert "grid-template-columns: minmax(0, 1fr) minmax(320px, 360px);" not in styles_text


def test_workbench_context_links_use_compact_local_styling():
    text = read_ui_styles(STYLES)

    assert ".task-workbench-context-link {" in text
    assert "display: inline;" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "padding: 0;" in text
    assert "line-height: inherit;" in text
    assert ".task-workbench-context-link:hover," in text
    assert ".task-workbench-context-primary," in text
    assert ".task-workbench-context-secondary {" in text
    assert ".task-workbench-context-source {" in text


def test_workbench_status_cells_use_shared_status_pills_and_compact_table_language():
    route_text = WORKBENCH_ROUTE.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES)

    assert 'import { statusPillMarkup } from "../utils/display-tokens.js";' in route_text
    assert "statusPillMarkup(row.status, statusLabel)" in route_text
    assert 'class="task-workbench-status-cell"' in route_text
    assert ".task-workbench-table thead th {" in styles_text
    assert "background: var(--table-header-bg);" in styles_text
    task_header_block = styles_text[
        styles_text.index("#view-tasks-workbench .task-workbench-table thead th {"):
        styles_text.index("#view-tasks-workbench .task-workbench-table tbody tr {")
    ]
    assert "color: var(--text-strong);" in task_header_block
    assert "box-shadow: none;" in task_header_block
    assert "#view-tasks-workbench .task-workbench-table tbody tr:nth-child(even) {" in styles_text
    assert "background: var(--table-row-alt-bg);" in styles_text
    assert ".task-workbench-table tbody tr:hover td {" in styles_text
    assert ".task-workbench-table .pill {" in styles_text
    assert "border-radius: 5px;" in styles_text


def test_workbench_task_table_columns_are_balanced_and_centered():
    styles_text = read_ui_styles(STYLES)

    task_column_block = styles_text[
        styles_text.index(".task-workbench-table th:nth-child(2),"):
        styles_text.index(".task-workbench-context {")
    ]
    scoped_cell_block = styles_text[
        styles_text.index("#view-tasks-workbench .task-workbench-table th,"):
        styles_text.index("#view-tasks-workbench .task-workbench-table thead th {")
    ]
    task_cell_block = styles_text[
        styles_text.index("#view-tasks-workbench .task-workbench-table tbody td:nth-child(2) {"):
        styles_text.index("#view-tasks-workbench .task-workbench-table tbody tr[data-id] {")
    ]

    assert "width: 26%;" in task_column_block
    assert "width: 18%;" in task_column_block
    assert "width: 14%;" in task_column_block
    assert "width: 12%;" in task_column_block
    assert "text-align: center;" in scoped_cell_block
    assert "text-align: center;" in task_cell_block
    assert "text-align: left;" not in task_cell_block
    assert "margin-inline: auto;" in styles_text


def test_workbench_drawer_context_surfaces_effective_repo_link():
    app_text = APP_JS.read_text(encoding="utf-8")
    drawer_text = WORKBENCH_DRAWER.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    html_text = (REPO_ROOT / "src" / "main" / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="task-repo-preview"' in html_text
    assert 'taskRepoPreview: document.getElementById("task-repo-preview")' in dom_text
    assert "function effectiveTaskRepoInfo(solutionId, overrideUrl) {" in app_text
    assert 'return { url: override, source: "override" };' in app_text
    assert 'return { url: inherited, source: "inherited" };' in app_text
    assert 'return { url: "", source: "none" };' in app_text
    assert 'Repo: <span class="muted">Not set</span>' in drawer_text
    assert 'className: "repo-external-link-inline"' in drawer_text


def test_workbench_team_meta_uses_quieter_styling():
    text = read_ui_styles(STYLES)

    assert ".wab-team-meta span {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text


def test_workbench_section_counts_use_quieter_styling():
    text = read_ui_styles(STYLES)

    assert ".wab-section-count {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text


def test_workbench_invalid_project_filter_is_auto_cleared():
    text = WORKBENCH_FILTERS.read_text(encoding="utf-8")

    assert "export function normalizeTasksWorkbenchFilters(ctx, filters = {}) {" in text
    assert 'if (state.loadedEntities?.has("projects")) {' in text
    assert 'const validProjectIds = new Set((state.projects || []).map((project) => project.project_id));' in text
    assert 'if (next.project_id && !validProjectIds.has(next.project_id)) {' in text
    assert 'next.project_id = "";' in text


def test_workbench_invalid_solution_filter_is_auto_cleared_with_project_scope():
    text = WORKBENCH_FILTERS.read_text(encoding="utf-8")

    assert 'if (state.loadedEntities?.has("solutions")) {' in text
    assert "const filteredSolutions = next.project_id" in text
    assert '.filter((solution) => solution.project_id === next.project_id)' in text
    assert 'const validSolutionIds = new Set(filteredSolutions.map((solution) => solution.solution_id));' in text
    assert 'if (next.solution_id && !validSolutionIds.has(next.solution_id)) {' in text
    assert 'next.solution_id = "";' in text


def test_workbench_invalid_assignee_filter_is_auto_cleared_against_loaded_users():
    text = WORKBENCH_FILTERS.read_text(encoding="utf-8")

    assert 'if (state.loadedEntities?.has("users")) {' in text
    assert "const usersBySoeid = new Map(" in text
    assert 'if (next.assignee === "__unassigned__") {' in text
    assert "const displayName = usersBySoeid.get(next.assignee) || \"\";" in text
    assert "if (!displayName) {" in text
    assert 'next.assignee = "";' in text
    assert 'next.assignee_name = "";' in text


def test_workbench_invalid_status_and_priority_filters_are_normalized():
    text = WORKBENCH_FILTERS.read_text(encoding="utf-8")

    assert "export const VALID_TASKS_WORKBENCH_STATUSES = new Set([" in text
    assert 'if (!VALID_TASKS_WORKBENCH_STATUSES.has(next.status)) {' in text
    assert "export function normalizeTasksWorkbenchPriorityFilter(value) {" in text
    assert "const parsed = Number(raw);" in text
    assert "if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5) return \"\";" in text


def test_workbench_restore_and_saved_view_apply_reuse_filter_normalization():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = WORKBENCH_FILTERS.read_text(encoding="utf-8")
    saved_views_text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")
    options_text = WORKBENCH_OPTIONS.read_text(encoding="utf-8")

    restore_start = app_text.index("function restoreTasksWorkbenchUiState() {")
    restore_end = app_text.index("function canManageSpaceMembership")
    restore_slice = app_text[restore_start:restore_end]

    populate_start = app_text.index("function populateSelects() {")
    populate_end = app_text.index("if (els.allocationForm) {")
    populate_slice = app_text[populate_start:populate_end]

    assert "export function normalizeTasksWorkbenchUiState(ctx, { persist = false } = {}) {" in filters_text
    assert "normalizeWorkbenchUiState(createTasksWorkbenchContext());" in restore_slice
    assert "function applyTasksWorkbenchSavedView(ctx, savedView) {" in saved_views_text
    assert "normalizeTasksWorkbenchUiState({ persist: true });" in saved_views_text
    assert "populateTasksWorkbenchOptions(createTasksWorkbenchContext(), { projectOptionsHtml: projectOpts });" in populate_slice
    assert "normalizeTasksWorkbenchUiState({ persist: true });" in options_text


def test_workbench_ui_state_corrupt_or_empty_storage_is_rewritten():
    text = APP_JS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(TASKS_WORKBENCH_UI_STATE_KEY_PREFIX), {});" in text
    assert "if (recovered || !Object.keys(stored || {}).length) persistTasksWorkbenchUiState();" in text


def test_workbench_invalid_preset_is_auto_cleared_to_all():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = WORKBENCH_FILTERS.read_text(encoding="utf-8")

    assert "export const VALID_TASKS_WORKBENCH_PRESETS = new Set([" in filters_text
    assert 'wb.preset = String(stored.preset || "all");' in app_text
    assert 'if (!VALID_TASKS_WORKBENCH_PRESETS.has(String(wb.preset || "all"))) {' in filters_text
    assert 'wb.preset = "all";' in filters_text
    assert "if (persist && (normalized.changed || changed)) persistTasksWorkbenchUiState();" in filters_text


def test_workbench_selected_saved_view_id_is_persisted_and_restored():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'selectedSavedViewId: wb.selectedSavedViewId || "",' in text
    assert 'wb.selectedSavedViewId = String(stored.selectedSavedViewId || "");' in text


def test_workbench_saved_view_selection_self_heals_when_saved_view_disappears():
    text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert "if (wb.selectedSavedViewId && wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId)) {" in text
    assert "} else if (wb.selectedSavedViewId) {" in text
    assert 'wb.selectedSavedViewId = "";' in text
    assert "selectionChanged = true;" in text
    assert "if (selectionChanged) persistTasksWorkbenchUiState();" in text


def test_workbench_apply_saved_view_keeps_that_view_selected():
    text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert "function applyTasksWorkbenchSavedView(ctx, savedView) {" in text
    assert "wb.selectedSavedViewId = savedView.view_id || wb.selectedSavedViewId || \"\";" in text


def test_workbench_saved_views_corrupt_or_invalid_storage_is_rewritten():
    text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert "let recovered = false;" in text
    assert "if (Array.isArray(candidate)) {" in text
    assert "recovered = true;" in text
    assert 'preset: VALID_TASKS_WORKBENCH_PRESETS.has(String(row.preset || "all"))' in text
    assert "if (recovered || JSON.stringify(parsed) !== JSON.stringify(normalizedViews)) {" in text
    assert "persistTasksWorkbenchSavedViews(ctx);" in text
    assert "normalizeTasksWorkbenchUiState({ persist: true });" in text


def test_workbench_interactions_own_filter_and_selection_bindings():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/interactions.js";' in app_text
    assert "function bindTasksWorkbenchControls(ctx) {" in interactions_text
    assert "function updateTasksWorkbenchSolutionOptions(ctx, projectId) {" in interactions_text
    assert 'const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");' in interactions_text
    assert 'bindDebouncedInput(els.tasksWorkbenchSearch, (value) => {' in interactions_text
    assert 'els.tasksWorkbenchProject.addEventListener("change", () => {' in interactions_text
    assert 'wb.filters.project_id = els.tasksWorkbenchProject.value || "";' in interactions_text
    assert "updateTasksWorkbenchSolutionOptions(ctx, wb.filters.project_id);" in interactions_text
    assert 'els.tasksWorkbenchTable.addEventListener("change", (event) => {' in interactions_text
    assert 'if (event.target.id === "scwb-select-all") {' in interactions_text


def test_workbench_options_population_is_route_local():
    app_text = APP_JS.read_text(encoding="utf-8")
    options_text = WORKBENCH_OPTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/tasks-workbench/options.js";' in app_text
    assert "function populateTasksWorkbenchOptions(ctx, { projectOptionsHtml = \"\" } = {}) {" in options_text
    assert 'els.tasksWorkbenchProject.innerHTML = `<option value="">All Projects</option>${projectOptionsHtml}`;' in options_text
    assert 'els.tasksWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;' in options_text
    assert 'els.tasksWorkbenchBulkAssignee.innerHTML = `<option value="">Unassigned</option>${userOptions}`;' in options_text
    assert "assigneeSel.onchange = () => {" in options_text
    assert "populateTasksWorkbenchOptions(createTasksWorkbenchContext(), { projectOptionsHtml: projectOpts });" in app_text


def test_workbench_context_wrappers_delegate_through_enriched_context():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "let ctx = null;" in app_text
    assert "ctx = createShellContext(base, {" in app_text
    assert "normalizeTasksWorkbenchUiState: (options) => normalizeWorkbenchUiState(ctx, options)," in app_text
    assert "updateTasksWorkbenchSolutionOptions: (projectId) => updateWorkbenchSolutionOptions(ctx, projectId)," in app_text
    assert "clearTasksWorkbenchFilters: () => clearWorkbenchFilters(ctx)," in app_text
