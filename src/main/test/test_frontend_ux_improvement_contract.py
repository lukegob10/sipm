from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
PLANNING_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning.js"
PM_DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard.js"
SUBCOMPONENTS_WORKBENCH_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "subcomponents-workbench.js"


def test_master_remains_default_view_and_fallback():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'currentView: "master"' in text
    assert "function viewFromLocationPath" in text
    assert 'if (relative === "/" || relative === "") return "master";' in text
    assert 'return normalizeView(firstSegment);' in text


def test_route_hint_copy_removed_from_main_html_views():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "view-route-hint" not in text
    for route_hint in [
        "#/master",
        "#/subcomponents-workbench",
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


def test_index_includes_shared_planning_modal_shell():
    text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="planning-modal"' in text
    assert 'id="planning-modal-title"' in text
    assert 'id="planning-modal-body"' in text
    assert 'id="planning-modal-close"' in text


def test_frontend_ux_state_is_persisted_per_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")
    master_text = MASTER_ROUTE.read_text(encoding="utf-8")

    assert 'const MASTER_VIEW_STATE_KEY_PREFIX = "sipm-master-filters-v1";' in app_text
    assert 'const SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX = "sipm-subcomponents-workbench-state-v1";' in app_text
    assert 'const STORAGE_KEY_PREFIX = "sipm-planning-ui-v1";' in planning_text
    assert "persistMasterViewState" in app_text
    assert "persistSubcomponentsWorkbenchUiState" in app_text
    assert "persistViewState()" in planning_text
    assert "persistMasterViewState" in master_text


def test_master_invalid_preset_is_auto_cleared_and_persisted():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'const VALID_DELIVERABLE_PRESETS = new Set(["", "my", "overdue", "blocked"]);' in app_text
    assert 'state.deliverablesPreset = String(stored.deliverablesPreset || "");' in app_text
    assert "if (!VALID_DELIVERABLE_PRESETS.has(state.deliverablesPreset)) {" in app_text
    assert 'state.deliverablesPreset = "";' in app_text
    assert "if (changed) persistMasterViewState();" in app_text


def test_master_invalid_type_filter_is_auto_cleared_and_persisted():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'const VALID_DELIVERABLE_TYPES = new Set(["", "project", "solution"]);' in app_text
    assert 'state.filters = stored.filters && typeof stored.filters === "object" ? { ...stored.filters } : {};' in app_text
    assert 'if (!VALID_DELIVERABLE_TYPES.has(String(state.filters?.type || ""))) {' in app_text
    assert 'state.filters.type = "";' in app_text
    assert "if (changed) persistMasterViewState();" in app_text


def test_master_corrupt_scoped_view_state_is_rewritten_to_defaults():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "function readStoredJsonState(key, fallback) {" in app_text
    assert "console.warn(`Stored state for ${key} was not an object and will be reset.`);" in app_text
    assert "return { value: fallback, recovered: true };" in app_text
    assert "const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(MASTER_VIEW_STATE_KEY_PREFIX), {});" in app_text
    assert "let changed = recovered;" in app_text
    assert "if (changed) persistMasterViewState();" in app_text


def test_planning_person_search_is_persisted_per_space():
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert 'personSearch: boardState.personSearch || "",' in planning_text
    assert 'boardState.personSearch = String(stored.personSearch || "");' in planning_text
    assert 'if (target.id === "wab-person-search") {' in planning_text
    assert "persistViewState();" in planning_text[planning_text.index('if (target.id === "wab-person-search") {'):planning_text.index('if (target.id === "wab-new-team-name") {')]


def test_planning_top_panel_is_persisted_per_space():
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert 'topPanel: boardState.topPanel || "",' in planning_text
    assert 'boardState.topPanel = String(stored.topPanel || "");' in planning_text


def test_planning_invalid_team_filter_is_auto_cleared_and_persisted():
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert "function normalizePersistedBoardFilters() {" in planning_text
    assert "const validTeamIds = new Set((boardState.data.teams || []).map((team) => String(team?.id || \"\")).filter(Boolean));" in planning_text
    assert "boardState.teamFilter === UNASSIGNED_TEAM_ID" in planning_text
    assert 'boardState.teamFilter = "all";' in planning_text
    assert "normalizePersistedBoardFilters();" in planning_text


def test_planning_invalid_effort_filter_is_auto_cleared_and_persisted():
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert 'const VALID_EFFORT_FILTERS = new Set(["all", "small", "medium", "large"]);' in planning_text
    assert 'if (!VALID_EFFORT_FILTERS.has(String(boardState.effortFilter || "all"))) {' in planning_text
    assert 'boardState.effortFilter = "all";' in planning_text
    assert "if (changed) persistViewState();" in planning_text


def test_planning_invalid_month_token_is_auto_cleared_and_persisted():
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert "function isValidMonthToken(value) {" in planning_text
    assert "const month = Number(raw.slice(5, 7));" in planning_text
    assert "return Number.isInteger(month) && month >= 1 && month <= 12;" in planning_text
    assert "if (!isValidMonthToken(boardState.month)) {" in planning_text
    assert "boardState.month = currentMonthToken();" in planning_text
    assert "if (changed) persistViewState();" in planning_text


def test_planning_invalid_top_panel_is_auto_cleared_and_persisted():
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert 'const VALID_TOP_PANELS = new Set(["", "filters", "create", "guide", "tools"]);' in planning_text
    assert 'if (!VALID_TOP_PANELS.has(String(boardState.topPanel || ""))) {' in planning_text
    assert 'boardState.topPanel = "";' in planning_text
    assert "if (changed) persistViewState();" in planning_text


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
    assert "if (recovered) persistPlanningWindowViewState();" in app_text


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


def test_reset_password_ui_uses_temp_password_flow():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert "/auth/reset-password" in app_text
    assert 'name="soeid"' in html_text
    assert 'name="temp_password"' in html_text
    assert 'Use temporary password' in html_text
    assert "/auth/reset-password-with-token" not in app_text
    assert "verify-temp-form" not in html_text


def test_frontend_derives_project_manager_context_path_for_api_and_reset_routes():
    app_text = APP_JS.read_text(encoding="utf-8")
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")
    pm_dashboard_text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")

    assert "const APP_CONTEXT_PATH = (() => {" in app_text
    assert 'const API_BASE = `${APP_CONTEXT_PATH}/api` || "/api";' in app_text
    assert "function routePathForView(view)" in app_text
    assert "function syncPathForView(view, replace = false)" in app_text
    assert 'window.addEventListener("popstate"' in app_text
    assert 'buildAppUrl("/reset-password")' in app_text
    assert 'window.location.href = buildAppUrl("/reset-password");' in app_text
    assert 'window.location.href = buildAppUrl("/");' in app_text
    assert 'const url = new URL(buildWsUrl("/ws"));' in app_text
    assert "resolveApiBase(ctx)" in planning_text
    assert "viewHref," in app_text
    assert "const hrefFor = (view) => {" in pm_dashboard_text
    assert "/api/planning/work-allocation/report.pdf" not in planning_text
    assert "#/" not in pm_dashboard_text


def test_planning_route_uses_inline_forms_confirm_modal_and_keyboard_detail_controls():
    text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert "wab-create-form" in text
    assert "ctx?.showConfirmModal" in text
    assert "data-assign-target" in text
    assert "wab-modal-shell" in text
    assert 'action === "close-task-detail" || action === "close-task-modal"' in text
    assert 'if (key === "Escape" && boardState.selectedTaskId)' in text
    assert 'closest(".wab-task-chip")' in text
    assert "closeTaskDetail" in text
    assert "wab-person-search" in text
    assert "window.prompt" not in text
    assert "window.confirm" not in text


def test_app_shell_planning_allocation_delete_uses_shared_confirm_modal():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'title: "Delete Allocation?"' in text
    assert 'message: "Delete this allocation?"' in text
    assert 'confirmLabel: "Delete Allocation"' in text
    assert 'const confirmDelete = confirm("Delete this allocation?");' not in text


def test_subcomponents_workbench_saved_view_delete_uses_shared_confirm_modal():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'title: "Delete Saved View?"' in text
    assert 'message: `Delete saved view "${saved.name}"?`' in text
    assert 'confirmLabel: "Delete Saved View"' in text
    assert 'if (!confirm(`Delete saved view "${saved.name}"?`)) return;' not in text


def test_team_capacity_member_deactivate_uses_shared_confirm_modal():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'title: "Deactivate Member?"' in text
    assert 'message: "Deactivate this member? They will be hidden from the roster."' in text
    assert 'confirmLabel: "Deactivate Member"' in text
    assert 'if (!confirm("Deactivate this member? They will be hidden from the roster.")) return;' not in text


def test_subcomponents_workbench_saved_view_delete_without_selection_uses_inline_status():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'setSubcomponentsWorkbenchSavedStatus("Select a saved view to delete.");' in text
    assert 'alert("Select a saved view to delete.");' not in text


def test_subcomponents_workbench_saved_view_save_without_name_uses_inline_status():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'setSubcomponentsWorkbenchSavedStatus("Enter a view name before saving.");' in text
    assert 'alert("Enter a view name before saving.");' not in text


def test_subcomponents_workbench_bulk_actions_use_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="subcomponents-workbench-bulk-feedback"' in html_text
    assert "function setSubcomponentsWorkbenchBulkFeedback(message, tone = \"info\", autoClearMs = 0)" in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback("Choose a bulk action.", "error");' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback("Select at least one subcomponent.", "error");' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback("Select a status value.", "error");' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback("Enter a due date shift in whole days (e.g. 3 or -2).", "error");' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback("Unsupported bulk action.", "error");' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback(`Bulk update failed: ${err.message || err}`, "error");' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback(\n      `Updated ${selectedIds.length} subcomponent${selectedIds.length === 1 ? "" : "s"}.`,' in app_text
    assert 'alert("Choose a bulk action.");' not in app_text
    assert 'alert("Select at least one subcomponent.");' not in app_text
    assert 'alert("Select a status value.");' not in app_text
    assert 'alert("Enter a due date shift in whole days (e.g. 3 or -2).");' not in app_text
    assert 'alert("Unsupported bulk action.");' not in app_text
    assert 'alert(`Bulk update failed: ${err.message || err}`);' not in app_text


def test_subcomponents_workbench_delete_outcomes_use_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'deleteTargets.length === 1 ? "Deleting subcomponent…" : `Deleting ${deleteTargets.length} subcomponents…`' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback(\n        `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,\n        "error"\n      );' in app_text
    assert 'setSubcomponentsWorkbenchBulkFeedback(\n      `Deleted ${result.deletedIds.length} subcomponent${result.deletedIds.length === 1 ? "" : "s"}.`,\n      "success",\n      3200\n    );' in app_text
    assert 'setStatus(`Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`, "danger");' not in app_text
    assert 'setStatus(`Deleted ${result.deletedIds.length} subcomponent${result.deletedIds.length === 1 ? "" : "s"}.`, "positive");' not in app_text


def test_deliverables_bulk_actions_use_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="bulk-feedback"' in html_text
    assert "function setBulkFeedback(message, tone = \"info\", autoClearMs = 0)" in app_text
    assert 'setBulkFeedback("Updating deliverables…");' in app_text
    assert 'setBulkFeedback("Select a status first.", "error");' in app_text
    assert 'setBulkFeedback("Enter an owner name.", "error");' in app_text
    assert 'setBulkFeedback("Deliverables updated.", "success", 3200);' in app_text
    assert 'setBulkFeedback(`Bulk update failed: ${err.message}`, "error");' in app_text
    assert 'setStatus("Updating deliverables…");' not in app_text
    assert 'setStatus("Deliverables updated", "positive");' not in app_text
    assert 'alert("Select a status first.");' not in app_text
    assert 'alert("Enter an owner name.");' not in app_text
    assert 'alert(`Bulk update failed: ${err.message}`);' not in app_text


def test_deliverables_inline_field_updates_use_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "async function updateDeliverableField(type, id, field, value) {" in app_text
    assert "clearBulkFeedback();" in app_text
    assert 'setBulkFeedback("Saving deliverable change…");' in app_text
    assert 'setBulkFeedback("Deliverable updated.", "success", 2200);' in app_text
    assert 'setBulkFeedback(`Update failed: ${err.message}`, "error");' in app_text
    assert 'setStatus("Deliverable updated", "positive");' not in app_text
    assert 'setStatus("Deliverable update failed", "danger");' not in app_text
    assert 'alert(`Update failed: ${err.message}`);' not in app_text


def test_team_capacity_member_form_uses_inline_feedback():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="capacity-user-form-status"' in html_text
    assert "function setCapacityUserFormStatus(message, tone = \"info\", autoClearMs = 0)" in app_text
    assert 'setCapacityUserFormStatus("Select a member from the roster (or type an exact SOEID/name match) first.", "error");' in app_text
    assert 'setCapacityUserFormStatus(`Save failed: ${err.message}`, "error");' in app_text
    assert 'setCapacityUserFormStatus("Select a member first.", "error");' in app_text
    assert 'setCapacityUserFormStatus(`Delete failed: ${err.message}`, "error");' in app_text
    assert 'setCapacityUserFormStatus(`Saved member at ${timestampLabel()}.`, "success", 3200);' in app_text
    assert 'setCapacityUserFormStatus(`Member deactivated at ${timestampLabel()}.`, "success", 3200);' in app_text
    assert 'alert("Select a member from the roster (or type an exact SOEID/name match) first.");' not in app_text
    assert 'alert("Select a member first.");' not in app_text


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
    text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert "async function moveAssignment(allocationId, assigneeType, assigneeId" in text
    assert '`/planning/work-allocation/allocations/${encodeURIComponent(existing.id)}`' in text
    assert 'method: "PATCH"' in text
    assert 'kind: "move-assignment"' in text
    assert 'await moveAssignment(allocationId, "person", zone.personId, { pushUndo: true });' in text
    assert 'await moveAssignment(allocationId, "team", zone.teamId, { pushUndo: true });' in text


def test_operational_views_can_hide_completed_work_across_space():
    app_text = APP_JS.read_text(encoding="utf-8")
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    planning_text = PLANNING_ROUTE.read_text(encoding="utf-8")
    workbench_text = SUBCOMPONENTS_WORKBENCH_ROUTE.read_text(encoding="utf-8")

    assert 'id="completed-visibility-toggle"' in html_text
    assert 'const WORKSPACE_VIEW_PREFS_KEY_PREFIX = "sipm-workspace-prefs-v1";' in app_text
    assert 'workspacePrefs: { showCompleted: false },' in app_text
    assert "function renderCompletedVisibilityToggle()" in app_text
    assert "function showCompletedOperationalWork()" in app_text
    assert "if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;" in app_text
    assert "if (hideClosedDeliverables() && isClosedProjectStatus(project?.status)) return false;" in app_text
    assert "if (!showCompletedOperationalWork() && isCompletedSubcomponentStatus(sc.status)) return false;" in app_text
    assert "Completed items are hidden here. Use Show Completed in the top bar" in app_text
    assert "ctx?.state?.workspacePrefs?.showCompleted" in planning_text
    assert "completed or abandoned task" in planning_text
    assert "summary?.hiddenClosed" in workbench_text
