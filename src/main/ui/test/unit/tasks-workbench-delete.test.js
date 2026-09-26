import { describe, expect, it, vi } from "vitest";

import { applyTasksWorkbenchBulkAction } from "../../js/routes/tasks-workbench/bulk-actions.js";
import {
  deleteActiveTasksWorkbenchItem,
  handleTasksWorkbenchShortcut,
} from "../../js/routes/tasks-workbench/drawer.js";

function cancelledDelete() {
  return vi.fn().mockResolvedValue({ cancelled: true, deletedIds: [], failed: [] });
}

describe("task deletion cancellation", () => {
  it("does not mark a refresh or render after a cancelled workbench delete", async () => {
    const deleteTasksById = cancelledDelete();
    const marker = vi.fn();
    const renderTasksWorkbench = vi.fn();
    const cases = [
      () => deleteActiveTasksWorkbenchItem({
        els: { tasksWorkbenchForm: Object.assign(document.createElement("form"), {
          innerHTML: '<input name="task_id" value="task-1">',
        }) },
        markIgnoreRefresh: marker,
        deleteTasksById,
        renderTasksWorkbench,
      }),
      () => applyTasksWorkbenchBulkAction({
        state: { tasksWorkbench: { selected: new Set(["task-1"]), activeTaskId: "" } },
        els: { tasksWorkbenchBulkAction: { value: "delete" } },
        markIgnoreRefresh: marker,
        deleteTasksById,
        renderTasksWorkbench,
        setTasksWorkbenchBulkFeedback: vi.fn(),
      }),
      () => handleTasksWorkbenchShortcut({
        state: {
          currentView: "tasks-workbench",
          tasksWorkbench: { selected: new Set(["task-1"]), activeTaskId: "", drawerOpen: false },
        },
        els: {},
        markIgnoreRefresh: marker,
        deleteTasksById,
        renderTasksWorkbench,
      }, {
        key: "Delete",
        target: document.body,
        preventDefault: vi.fn(),
      }),
    ];

    for (const runCase of cases) {
      await runCase();
    }

    expect(deleteTasksById).toHaveBeenCalledTimes(3);
    expect(marker).not.toHaveBeenCalled();
    expect(renderTasksWorkbench).not.toHaveBeenCalled();
  });
});
