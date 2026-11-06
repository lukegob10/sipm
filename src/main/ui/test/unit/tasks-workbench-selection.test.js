import { describe, expect, it, vi } from "vitest";
import { renderTasksWorkbench } from "../../js/routes/tasks-workbench.js";
import { bindTasksWorkbenchControls } from "../../js/routes/tasks-workbench/interactions.js";

describe("task workbench selection controls", () => {
  it("names checkboxes, reflects partial selection, and retains focus through table renders", () => {
    document.body.innerHTML = '<div id="table"></div>';
    const table = document.getElementById("table");
    const rows = [{ task_id: "1", task_name: 'First "task"', status: "to_do" }, { task_id: "2", task_name: "Second", status: "to_do" }];
    const wb = { selected: new Set(), visibleIds: ["1", "2"], sort: "default", filters: {}, savedViews: [] };
    const ctx = { state: { tasksWorkbench: wb }, els: { tasksWorkbenchTable: table }, bindDebouncedInput: vi.fn(), persistTasksWorkbenchUiState: vi.fn(), syncTasksWorkbenchBulkInputs: vi.fn(), clearTasksWorkbenchBulkFeedback: vi.fn(), updateTasksWorkbenchSelectionCount: vi.fn() };
    ctx.renderTasksWorkbench = () => renderTasksWorkbench({ els: ctx.els, rows, selectedIds: wb.selected, sort: wb.sort, formatStatus: (s) => s, summary: {} });
    ctx.renderTasksWorkbench();
    bindTasksWorkbenchControls(ctx);
    const header = () => table.querySelector("#scwb-select-all");
    const row = () => table.querySelector('.scwb-select-row[data-id="1"]');
    expect(header().getAttribute("aria-label")).toBe("Select all visible tasks");
    expect(row().getAttribute("aria-label")).toBe('Select task First "task"');
    row().focus(); row().click();
    expect(header().indeterminate).toBe(true);
    expect(header().checked).toBe(false);
    ctx.renderTasksWorkbench();
    expect(document.activeElement).toBe(row());
    expect(header().indeterminate).toBe(true);
    header().focus(); header().click();
    expect(document.activeElement).toBe(header());
    expect(header().checked).toBe(true);
    expect(header().indeterminate).toBe(false);
    const sort = () => table.querySelector("[data-twb-task-sort]");
    sort().focus(); sort().click();
    expect(document.activeElement).toBe(sort());
    expect(wb.sort).toBe("name-asc");
  });
});
