from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
WORKBENCH_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench.js"
WORKBENCH_FILTERS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench" / "filters.js"
WORKBENCH_BULK_ACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench" / "bulk-actions.js"
WORKBENCH_DRAWER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench" / "drawer.js"
WORKBENCH_SAVED_VIEWS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench" / "saved-views.js"
WORKBENCH_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench" / "interactions.js"
WORKBENCH_OPTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench" / "options.js"


def test_workbench_route_renders_project_context_as_drilldown_link():
    text = WORKBENCH_ROUTE.read_text(encoding="utf-8")

    assert "function renderSubcomponentsWorkbenchProjectLink(label, projectId) {" in text
    assert "function renderSubcomponentsWorkbenchSolutionLink(label, solutionId) {" in text
    assert 'class="sub-workbench-context-link" data-scwb-action="open-project"' in text
    assert 'class="sub-workbench-context-link" data-scwb-action="open-solution"' in text
    assert 'data-project-id="${esc(targetId)}"' in text
    assert 'data-solution-id="${esc(targetId)}"' in text
    assert 'renderSubcomponentsWorkbenchProjectLink(row.project_name, row.project_id)' in text
    assert 'renderSubcomponentsWorkbenchSolutionLink(row.solution_name, row.solution_id)' in text


def test_workbench_project_context_link_reuses_existing_project_modal():
    app_text = APP_JS.read_text(encoding="utf-8")
    drawer_text = WORKBENCH_DRAWER.read_text(encoding="utf-8")
    interactions_text = WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/subcomponents-workbench/drawer.js";' in app_text
    assert "handleSubcomponentsWorkbenchTableClick(ctx, event)" in interactions_text
    assert "handleSubcomponentsWorkbenchContextClick(ctx, event)" in interactions_text
    assert "await saveSubcomponentsWorkbenchForm(ctx);" in interactions_text
    assert "await deleteActiveSubcomponentsWorkbenchItem(ctx);" in interactions_text
    assert "resetSubcomponentsWorkbenchEditor(ctx)" in interactions_text
    assert "await handleSubcomponentsWorkbenchShortcut(ctx, event);" in interactions_text
    assert "function openSubcomponentsWorkbenchProjectDrilldown(ctx, projectId) {" in drawer_text
    assert "function openSubcomponentsWorkbenchSolutionDrilldown(ctx, solutionId) {" in drawer_text
    assert "function renderSubcomponentsWorkbenchDrawerProjectLink(ctx, label, projectId) {" in drawer_text
    assert "function renderSubcomponentsWorkbenchDrawerSolutionLink(ctx, label, solutionId) {" in drawer_text
    assert "function renderSubcomponentsWorkbenchDrawerRepoContext(ctx, subcomponent) {" in drawer_text
    assert 'class="sub-workbench-context-link" data-scwb-context-action="open-project"' in drawer_text
    assert 'class="sub-workbench-context-link" data-scwb-context-action="open-solution"' in drawer_text
    assert "openProjectForm(project);" in drawer_text
    assert 'openSolutionModal(solution, "details");' in drawer_text
    assert 'const actionEl = event.target.closest("[data-scwb-action]");' in drawer_text
    assert 'const actionEl = event.target.closest("[data-scwb-context-action]");' in drawer_text
    assert 'renderSubcomponentsWorkbenchDrawerProjectLink(ctx, project, subcomponent.project_id)' in drawer_text
    assert 'renderSubcomponentsWorkbenchDrawerSolutionLink(ctx, solution, subcomponent.solution_id)' in drawer_text
    assert 'renderSubcomponentsWorkbenchDrawerRepoContext(ctx, subcomponent)' in drawer_text


def test_workbench_context_links_use_compact_local_styling():
    text = read_ui_styles(STYLES)

    assert ".sub-workbench-context-link {" in text
    assert "display: inline;" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "padding: 0;" in text
    assert "line-height: inherit;" in text
    assert ".sub-workbench-context-link:hover," in text
    assert ".sub-workbench-context-primary," in text
    assert ".sub-workbench-context-secondary {" in text
    assert ".sub-workbench-context-source {" in text


def test_workbench_drawer_context_surfaces_effective_repo_link():
    app_text = APP_JS.read_text(encoding="utf-8")
    drawer_text = WORKBENCH_DRAWER.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    html_text = (REPO_ROOT / "src" / "main" / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="subcomponent-repo-preview"' in html_text
    assert 'subcomponentRepoPreview: document.getElementById("subcomponent-repo-preview")' in dom_text
    assert "function effectiveSubcomponentRepoInfo(solutionId, overrideUrl) {" in app_text
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

    assert "export function normalizeSubcomponentsWorkbenchFilters(ctx, filters = {}) {" in text
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

    assert "export const VALID_SUBCOMPONENTS_WORKBENCH_STATUSES = new Set([" in text
    assert 'if (!VALID_SUBCOMPONENTS_WORKBENCH_STATUSES.has(next.status)) {' in text
    assert "export function normalizeSubcomponentsWorkbenchPriorityFilter(value) {" in text
    assert "const parsed = Number(raw);" in text
    assert "if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5) return \"\";" in text


def test_workbench_restore_and_saved_view_apply_reuse_filter_normalization():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = WORKBENCH_FILTERS.read_text(encoding="utf-8")
    saved_views_text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")
    options_text = WORKBENCH_OPTIONS.read_text(encoding="utf-8")

    restore_start = app_text.index("function restoreSubcomponentsWorkbenchUiState() {")
    restore_end = app_text.index("function canManageSpaceMembership")
    restore_slice = app_text[restore_start:restore_end]

    populate_start = app_text.index("function populateSelects() {")
    populate_end = app_text.index("if (els.allocationForm) {")
    populate_slice = app_text[populate_start:populate_end]

    assert "export function normalizeSubcomponentsWorkbenchUiState(ctx, { persist = false } = {}) {" in filters_text
    assert "normalizeWorkbenchUiState(createSubcomponentsWorkbenchContext());" in restore_slice
    assert "function applySubcomponentsWorkbenchSavedView(ctx, savedView) {" in saved_views_text
    assert "normalizeSubcomponentsWorkbenchUiState({ persist: true });" in saved_views_text
    assert "populateSubcomponentsWorkbenchOptions(createSubcomponentsWorkbenchContext(), { projectOptionsHtml: projectOpts });" in populate_slice
    assert "normalizeSubcomponentsWorkbenchUiState({ persist: true });" in options_text


def test_workbench_ui_state_corrupt_or_empty_storage_is_rewritten():
    text = APP_JS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX), {});" in text
    assert "if (recovered || !Object.keys(stored || {}).length) persistSubcomponentsWorkbenchUiState();" in text


def test_workbench_invalid_preset_is_auto_cleared_to_all():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = WORKBENCH_FILTERS.read_text(encoding="utf-8")

    assert "export const VALID_SUBCOMPONENTS_WORKBENCH_PRESETS = new Set([" in filters_text
    assert 'wb.preset = String(stored.preset || "all");' in app_text
    assert 'if (!VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(wb.preset || "all"))) {' in filters_text
    assert 'wb.preset = "all";' in filters_text
    assert "if (persist && (normalized.changed || changed)) persistSubcomponentsWorkbenchUiState();" in filters_text


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
    assert "if (selectionChanged) persistSubcomponentsWorkbenchUiState();" in text


def test_workbench_apply_saved_view_keeps_that_view_selected():
    text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert "function applySubcomponentsWorkbenchSavedView(ctx, savedView) {" in text
    assert "wb.selectedSavedViewId = savedView.view_id || wb.selectedSavedViewId || \"\";" in text


def test_workbench_saved_views_corrupt_or_invalid_storage_is_rewritten():
    text = WORKBENCH_SAVED_VIEWS.read_text(encoding="utf-8")

    assert "let recovered = false;" in text
    assert "if (Array.isArray(candidate)) {" in text
    assert "recovered = true;" in text
    assert 'preset: VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(row.preset || "all"))' in text
    assert "if (recovered || JSON.stringify(parsed) !== JSON.stringify(normalizedViews)) {" in text
    assert "persistSubcomponentsWorkbenchSavedViews(ctx);" in text
    assert "normalizeSubcomponentsWorkbenchUiState({ persist: true });" in text


def test_workbench_interactions_own_filter_and_selection_bindings():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = WORKBENCH_INTERACTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/subcomponents-workbench/interactions.js";' in app_text
    assert "function bindSubcomponentsWorkbenchControls(ctx) {" in interactions_text
    assert "function updateSubcomponentsWorkbenchSolutionOptions(ctx, projectId) {" in interactions_text
    assert 'const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");' in interactions_text
    assert 'bindDebouncedInput(els.subcomponentsWorkbenchSearch, (value) => {' in interactions_text
    assert 'els.subcomponentsWorkbenchProject.addEventListener("change", () => {' in interactions_text
    assert 'wb.filters.project_id = els.subcomponentsWorkbenchProject.value || "";' in interactions_text
    assert "updateSubcomponentsWorkbenchSolutionOptions(ctx, wb.filters.project_id);" in interactions_text
    assert 'els.subcomponentsWorkbenchTable.addEventListener("change", (event) => {' in interactions_text
    assert 'if (event.target.id === "scwb-select-all") {' in interactions_text


def test_workbench_options_population_is_route_local():
    app_text = APP_JS.read_text(encoding="utf-8")
    options_text = WORKBENCH_OPTIONS.read_text(encoding="utf-8")

    assert 'from "./routes/subcomponents-workbench/options.js";' in app_text
    assert "function populateSubcomponentsWorkbenchOptions(ctx, { projectOptionsHtml = \"\" } = {}) {" in options_text
    assert 'els.subcomponentsWorkbenchProject.innerHTML = `<option value="">All Projects</option>${projectOptionsHtml}`;' in options_text
    assert 'els.subcomponentsWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;' in options_text
    assert 'els.subcomponentsWorkbenchBulkAssignee.innerHTML = `<option value="">Unassigned</option>${userOptions}`;' in options_text
    assert "assigneeSel.onchange = () => {" in options_text
    assert "populateSubcomponentsWorkbenchOptions(createSubcomponentsWorkbenchContext(), { projectOptionsHtml: projectOpts });" in app_text
