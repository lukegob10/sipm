from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
KANBAN_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "kanban.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_kanban_route_renders_solution_titles_as_drilldown_links():
    text = KANBAN_ROUTE.read_text(encoding="utf-8")

    assert "function renderKanbanSolutionLink(label, solutionId) {" in text
    assert 'function renderKanbanProjectLink(label, projectId, className = "") {' in text
    assert 'data-kanban-action="open-project"' in text
    assert 'data-project-id="${esc(targetId)}"' in text
    assert 'class="kanban-project-link${classToken}"' in text
    assert 'renderKanbanProjectLink(projName, pid)' in text
    assert 'renderKanbanProjectLink(proj, s.project_id, "secondary")' not in text
    assert 'data-kanban-action="open-solution"' in text
    assert 'data-solution-id="${esc(targetId)}"' in text
    assert 'return `<button type="button" class="kanban-solution-link"' in text
    assert 'class="kanban-card-title"' in text
    assert 'renderKanbanSolutionLink(s.solution_name, s.solution_id)' in text


def test_kanban_route_handles_solution_drilldown_clicks():
    text = KANBAN_ROUTE.read_text(encoding="utf-8")

    assert "const kanbanState = {" in text
    assert 'document.getElementById("view-kanban")' in text
    assert 'const actionEl = event.target.closest("[data-kanban-action]")' in text
    assert 'if (action === "open-project") {' in text
    assert 'kanbanState.ctx?.openKanbanProjectDrilldown' in text
    assert 'if (action === "open-solution") {' in text
    assert 'kanbanState.ctx.openKanbanSolutionDrilldown(solutionId);' in text
    assert "kanbanState.ctx = ctx;" in text
    assert "bindKanbanEvents();" in text


def test_kanban_drilldown_helper_reuses_existing_solution_modal():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function openKanbanProjectDrilldown(projectId) {" in text
    assert "openProjectForm(project);" in text
    assert "function openKanbanSolutionDrilldown(solutionId) {" in text
    assert 'openSolutionModal(solution, "details");' in text
    assert "openKanbanProjectDrilldown," in text
    assert "openKanbanSolutionDrilldown," in text


def test_kanban_solution_filtering_is_independent_from_deliverables_master_filters():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function filteredSolutionsForKanban() {" in text
    assert "return (state.solutions || []).filter((s) => {" in text
    assert "if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;" in text
    assert "const base = filteredSolutions();" not in text[text.index("function filteredSolutionsForKanban() {"):text.index("function filteredSolutionsForCalendar() {")]


def test_kanban_filter_state_is_restored_and_persisted_per_space():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'const KANBAN_VIEW_STATE_KEY_PREFIX = "sipm-kanban-view-state-v1";' in text
    assert "function persistKanbanViewState() {" in text
    assert "activeSpaceScopedStorageKey(KANBAN_VIEW_STATE_KEY_PREFIX)" in text
    assert "function restoreKanbanViewState() {" in text
    assert "state.kanbanFilters = {" in text
    assert "restoreKanbanViewState();" in text
    assert "persistKanbanViewState();" in text


def test_kanban_corrupt_scoped_view_state_is_rewritten_to_defaults():
    text = APP_JS.read_text(encoding="utf-8")

    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(KANBAN_VIEW_STATE_KEY_PREFIX), {});" in text
    assert 'project: String(stored.filters?.project || ""),' in text
    assert 'owner: String(stored.filters?.owner || ""),' in text
    assert "if (recovered) persistKanbanViewState();" in text


def test_kanban_owner_filter_control_is_restored_from_persisted_state():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'owner: String(stored.filters?.owner || ""),' in text
    assert "if (els.kanbanFilterOwner) {" in text
    assert 'els.kanbanFilterOwner.value = state.kanbanFilters.owner || "";' in text


def test_kanban_invalid_project_filter_is_auto_cleared_when_projects_refresh():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function normalizeScopedProjectFilter(filterState) {" in text
    assert 'const currentProjectId = String(filterState.project || "");' in text
    assert "filterState.project = \"\";" in text
    assert "const kanbanProjectFilterChanged = normalizeScopedProjectFilter(state.kanbanFilters);" in text
    assert "if (kanbanProjectFilterChanged) {" in text
    assert "persistKanbanViewState();" in text


def test_kanban_invalid_owner_filter_is_auto_cleared_when_it_matches_no_current_solution_owner():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function normalizeScopedOwnerFilter(filterState, { includeSolutions = true, includeSubcomponents = false } = {}) {" in text
    assert 'const kanbanOwnerFilterChanged = normalizeScopedOwnerFilter(state.kanbanFilters, { includeSolutions: true });' in text
    assert 'filterState.owner = "";' in text
    assert "if (kanbanOwnerFilterChanged) {" in text
    assert "persistKanbanViewState();" in text


def test_kanban_uses_dense_title_link_style():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".kanban-card {" in text
    assert "background: var(--panel);" in text
    assert "box-shadow: none;" in text
    assert ".kanban-project {" in text
    assert "border: 1px solid var(--border);" in text
    assert "background: var(--panel);" in text
    assert ".kanban-card-title {" in text
    assert ".kanban-project-link {" in text
    assert ".kanban-project-link.secondary {" not in text
    assert ".kanban-project-link.secondary:hover {" not in text
    assert ".kanban-project-link:hover {" in text
    assert ".kanban-project-link:focus-visible {" in text
    assert ".kanban-solution-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert "text-underline-offset: 0.12em;" in text
    assert ".kanban-solution-link:hover {" in text
    assert ".kanban-solution-link:focus-visible {" in text


def test_light_theme_preserves_subtle_kanban_project_surface():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".theme-light .kanban-project {" in text
    assert "background: var(--panel);" in text
    assert "box-shadow: none;" in text


def test_kanban_solution_container_uses_quieter_chrome():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".kanban-solution {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "background: transparent;" in text
