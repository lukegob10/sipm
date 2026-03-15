from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
WORKBENCH_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench.js"


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
    text = APP_JS.read_text(encoding="utf-8")

    assert "function openSubcomponentsWorkbenchProjectDrilldown(projectId) {" in text
    assert "function openSubcomponentsWorkbenchSolutionDrilldown(solutionId) {" in text
    assert "function renderSubcomponentsWorkbenchDrawerProjectLink(label, projectId) {" in text
    assert "function renderSubcomponentsWorkbenchDrawerSolutionLink(label, solutionId) {" in text
    assert "function renderSubcomponentsWorkbenchDrawerRepoContext(subcomponent) {" in text
    assert 'class="sub-workbench-context-link" data-scwb-context-action="open-project"' in text
    assert 'class="sub-workbench-context-link" data-scwb-context-action="open-solution"' in text
    assert "openProjectForm(project);" in text
    assert 'openSolutionModal(solution, "details");' in text
    assert 'const actionEl = e.target.closest("[data-scwb-action]");' in text
    assert 'if (action === "open-project") {' in text
    assert 'if (action === "open-solution") {' in text
    assert 'const actionEl = event.target.closest("[data-scwb-context-action]");' in text
    assert 'if (action === "open-project") {' in text
    assert 'if (action === "open-solution") {' in text
    assert 'renderSubcomponentsWorkbenchDrawerProjectLink(project, subcomponent.project_id)' in text
    assert 'renderSubcomponentsWorkbenchDrawerSolutionLink(solution, subcomponent.solution_id)' in text
    assert 'renderSubcomponentsWorkbenchDrawerRepoContext(subcomponent)' in text


def test_workbench_context_links_use_compact_local_styling():
    text = STYLES.read_text(encoding="utf-8")

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
    html_text = (REPO_ROOT / "src" / "main" / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="subcomponent-repo-preview"' in html_text
    assert 'subcomponentRepoPreview: document.getElementById("subcomponent-repo-preview")' in app_text
    assert "function effectiveSubcomponentRepoInfo(solutionId, overrideUrl) {" in app_text
    assert 'return { url: override, source: "override" };' in app_text
    assert 'return { url: inherited, source: "inherited" };' in app_text
    assert 'return { url: "", source: "none" };' in app_text
    assert 'Repo: <span class="muted">Not set</span>' in app_text
    assert 'className: "repo-external-link-inline"' in app_text


def test_workbench_team_meta_uses_quieter_styling():
    text = STYLES.read_text(encoding="utf-8")

    assert ".wab-team-meta span {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text


def test_workbench_section_counts_use_quieter_styling():
    text = STYLES.read_text(encoding="utf-8")

    assert ".wab-section-count {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text


def test_workbench_invalid_project_filter_is_auto_cleared():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function normalizeSubcomponentsWorkbenchFilters(filters = {}) {" in text
    assert 'if (state.loadedEntities?.has("projects")) {' in text
    assert 'const validProjectIds = new Set((state.projects || []).map((project) => project.project_id));' in text
    assert 'if (next.project_id && !validProjectIds.has(next.project_id)) {' in text
    assert 'next.project_id = "";' in text


def test_workbench_invalid_solution_filter_is_auto_cleared_with_project_scope():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'if (state.loadedEntities?.has("solutions")) {' in text
    assert "const filteredSolutions = next.project_id" in text
    assert '.filter((solution) => solution.project_id === next.project_id)' in text
    assert 'const validSolutionIds = new Set(filteredSolutions.map((solution) => solution.solution_id));' in text
    assert 'if (next.solution_id && !validSolutionIds.has(next.solution_id)) {' in text
    assert 'next.solution_id = "";' in text


def test_workbench_invalid_assignee_filter_is_auto_cleared_against_loaded_users():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'if (state.loadedEntities?.has("users")) {' in text
    assert "const usersBySoeid = new Map(" in text
    assert 'if (next.assignee === "__unassigned__") {' in text
    assert "const displayName = usersBySoeid.get(next.assignee) || \"\";" in text
    assert "if (!displayName) {" in text
    assert 'next.assignee = "";' in text
    assert 'next.assignee_name = "";' in text


def test_workbench_invalid_status_and_priority_filters_are_normalized():
    text = APP_JS.read_text(encoding="utf-8")

    assert "const VALID_SUBCOMPONENTS_WORKBENCH_STATUSES = new Set([" in text
    assert 'if (!VALID_SUBCOMPONENTS_WORKBENCH_STATUSES.has(next.status)) {' in text
    assert "function normalizeSubcomponentsWorkbenchPriorityFilter(value) {" in text
    assert "const parsed = Number(raw);" in text
    assert "if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5) return \"\";" in text


def test_workbench_restore_and_saved_view_apply_reuse_filter_normalization():
    text = APP_JS.read_text(encoding="utf-8")

    restore_start = text.index("function restoreSubcomponentsWorkbenchUiState() {")
    restore_end = text.index("function canManageSpaceMembership")
    restore_slice = text[restore_start:restore_end]

    apply_start = text.index("function applySubcomponentsWorkbenchSavedView(savedView) {")
    apply_end = text.index("function isTypingInputTarget(target) {")
    apply_slice = text[apply_start:apply_end]

    populate_start = text.index("function populateSelects() {")
    populate_end = text.index("if (els.allocationForm) {")
    populate_slice = text[populate_start:populate_end]

    assert "function normalizeSubcomponentsWorkbenchUiState({ persist = false } = {}) {" in text
    assert "normalizeSubcomponentsWorkbenchUiState();" in restore_slice
    assert "normalizeSubcomponentsWorkbenchUiState({ persist: true });" in apply_slice
    assert "normalizeSubcomponentsWorkbenchUiState({ persist: true });" in populate_slice


def test_workbench_ui_state_corrupt_or_empty_storage_is_rewritten():
    text = APP_JS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX), {});" in text
    assert "if (recovered || !Object.keys(stored || {}).length) persistSubcomponentsWorkbenchUiState();" in text


def test_workbench_invalid_preset_is_auto_cleared_to_all():
    text = APP_JS.read_text(encoding="utf-8")

    assert "const VALID_SUBCOMPONENTS_WORKBENCH_PRESETS = new Set([" in text
    assert 'wb.preset = String(stored.preset || "all");' in text
    assert 'if (!VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(wb.preset || "all"))) {' in text
    assert 'wb.preset = "all";' in text
    assert "if (persist && (normalized.changed || changed)) persistSubcomponentsWorkbenchUiState();" in text


def test_workbench_selected_saved_view_id_is_persisted_and_restored():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'selectedSavedViewId: wb.selectedSavedViewId || "",' in text
    assert 'wb.selectedSavedViewId = String(stored.selectedSavedViewId || "");' in text


def test_workbench_saved_view_selection_self_heals_when_saved_view_disappears():
    text = APP_JS.read_text(encoding="utf-8")

    assert "if (wb.selectedSavedViewId && wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId)) {" in text
    assert "} else if (wb.selectedSavedViewId) {" in text
    assert 'wb.selectedSavedViewId = "";' in text
    assert "selectionChanged = true;" in text
    assert "if (selectionChanged) persistSubcomponentsWorkbenchUiState();" in text


def test_workbench_apply_saved_view_keeps_that_view_selected():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function applySubcomponentsWorkbenchSavedView(savedView) {" in text
    assert "wb.selectedSavedViewId = savedView.view_id || wb.selectedSavedViewId || \"\";" in text


def test_workbench_saved_views_corrupt_or_invalid_storage_is_rewritten():
    text = APP_JS.read_text(encoding="utf-8")

    assert "let recovered = false;" in text
    assert "if (Array.isArray(candidate)) {" in text
    assert "recovered = true;" in text
    assert 'preset: VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(row.preset || "all"))' in text
    assert "if (recovered || JSON.stringify(parsed) !== JSON.stringify(normalizedViews)) {" in text
    assert "persistSubcomponentsWorkbenchSavedViews();" in text
    assert "normalizeSubcomponentsWorkbenchUiState({ persist: true });" in text
