import { describe, expect, it, vi } from "vitest";
import { bindTasksWorkbenchSavedViewControls } from "../../js/routes/tasks-workbench/saved-views.js";
import { normalizeTasksWorkbenchUiState } from "../../js/routes/tasks-workbench/filters.js";

describe("task workbench saved views", () => {
  it("persists the applied filters and preset before returning", () => {
    document.body.innerHTML = '<select id="saved"><option value="">Select</option><option value="v1">My tasks</option></select>';
    const wb = { savedViews: [{ view_id: "v1", name: "My tasks", preset: "my", filters: { search: "release", status: "to_do" } }], selectedSavedViewId: "", preset: "all", sort: "default", filters: {}, selected: new Set(), activeTaskId: "" };
    const state = { tasksWorkbench: wb, loadedEntities: new Set() };
    let persisted;
    const ctx = { state, els: { tasksWorkbenchSavedSelect: document.getElementById("saved") }, normalize: (value) => String(value || "").toLowerCase(), persistTasksWorkbenchUiState: vi.fn(() => { persisted = { preset: wb.preset, filters: { ...wb.filters }, selectedSavedViewId: wb.selectedSavedViewId }; }), updateTasksWorkbenchSolutionOptions: vi.fn(), renderTasksWorkbench: vi.fn() };
    ctx.normalizeTasksWorkbenchUiState = (options) => normalizeTasksWorkbenchUiState(ctx, options);
    bindTasksWorkbenchSavedViewControls(ctx);
    ctx.els.tasksWorkbenchSavedSelect.value = "v1";
    ctx.els.tasksWorkbenchSavedSelect.dispatchEvent(new Event("change"));
    expect(persisted).toMatchObject({ preset: "my", filters: { search: "release", status: "to_do" }, selectedSavedViewId: "v1" });
  });
});
