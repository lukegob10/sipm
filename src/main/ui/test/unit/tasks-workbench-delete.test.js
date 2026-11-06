import { describe, expect, it, vi } from "vitest";

import { applyTasksWorkbenchBulkAction } from "../../js/routes/tasks-workbench/bulk-actions.js";
import {
  deleteActiveTasksWorkbenchItem,
  handleTasksWorkbenchShortcut,
} from "../../js/routes/tasks-workbench/drawer.js";

function cancelledDelete() {
  return vi.fn().mockResolvedValue({ cancelled: true, deletedIds: [], failed: [] });
}

function bulkUpdateContext(api) {
  const task = { task_id: "task-1", status: "to_do" };
  return {
    state: {
      user: { user_id: "user-1" },
      activeSpace: { space_id: "space-1" },
      tasks: [task],
      tasksWorkbench: { selected: new Set(["task-1"]) },
      myWork: { records: [{ task }], loading: true, loadRequestId: 7 },
    },
    els: {
      tasksWorkbenchBulkAction: { value: "status" },
      tasksWorkbenchBulkStatus: { value: "complete" },
    },
    api,
    upsertById: vi.fn((rows, row) => { rows[0] = row; }),
    renderTasksWorkbench: vi.fn(),
    setTasksWorkbenchBulkFeedback: vi.fn(),
  };
}

describe("bulk task update cache", () => {
  it("reloads My Work after completing tasks", async () => {
    const updated = { task_id: "task-1", project_id: "project-1", solution_id: "solution-1", task_name: "Task", status: "complete", priority: 3 };
    const ctx = bulkUpdateContext(vi.fn().mockResolvedValue([updated]));

    await applyTasksWorkbenchBulkAction(ctx);

    expect(ctx.state.tasks).toEqual([updated]);
    expect(ctx.state.myWork.records).toBeNull();
    expect(ctx.state.myWork.loading).toBe(false);
    expect(ctx.state.myWork.loadRequestId).toBeGreaterThan(7);
  });

  it("leaves replacement workspace tasks and My Work unchanged", async () => {
    let resolveUpdate;
    const ctx = bulkUpdateContext(vi.fn(() => new Promise((resolve) => { resolveUpdate = resolve; })));
    const pending = applyTasksWorkbenchBulkAction(ctx);
    ctx.state.activeSpace = { space_id: "space-2" };
    const records = [{ task: { task_id: "new-task", status: "to_do" } }];
    ctx.state.tasks = [records[0].task];
    ctx.state.myWork.records = records;
    resolveUpdate([{ task_id: "task-1", status: "complete" }]);
    await pending;

    expect(ctx.upsertById).not.toHaveBeenCalled();
    expect(ctx.renderTasksWorkbench).not.toHaveBeenCalled();
    expect(ctx.state.tasks).toEqual([records[0].task]);
    expect(ctx.state.myWork.records).toBe(records);
    expect(ctx.state.myWork.loadRequestId).toBe(7);
    expect(ctx.setTasksWorkbenchBulkFeedback).not.toHaveBeenCalled();
  });
});

describe("task deletion cancellation", () => {
  it("does not run workbench shortcuts while a confirmation is open", async () => {
    const deleteTasksById = cancelledDelete();
    const focus = vi.fn();
    const ctx = {
      state: { currentView: "tasks-workbench", tasksWorkbench: { selected: new Set(["task-1"]), drawerOpen: true } },
      els: { confirmModal: document.createElement("div"), tasksWorkbenchSearch: { focus } },
      deleteTasksById,
      renderTasksWorkbench: vi.fn(),
    };
    for (const key of ["/", "Delete", "Escape", "e", "ArrowDown"]) {
      const preventDefault = vi.fn();
      await handleTasksWorkbenchShortcut(ctx, { key, target: document.body, preventDefault });
      expect(preventDefault).not.toHaveBeenCalled();
    }
    expect(ctx.state.tasksWorkbench.drawerOpen).toBe(true);
    expect(deleteTasksById).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();
  });

  it("leaves shortcuts to other visible dialogs, but not hidden dialogs or its own drawer", async () => {
    const search = { focus: vi.fn() };
    const drawer = document.createElement("div");
    const other = document.createElement("div");
    drawer.className = other.className = "modal";
    drawer.getClientRects = other.getClientRects = () => [{ width: 100, height: 100 }];
    document.body.append(drawer, other);
    const ctx = {
      state: { currentView: "tasks-workbench", tasksWorkbench: { drawerOpen: true } },
      els: { tasksWorkbenchDrawer: drawer, tasksWorkbenchSearch: search },
    };
    const event = { key: "/", target: document.body, preventDefault: vi.fn() };
    try {
      await handleTasksWorkbenchShortcut(ctx, event);
      expect(search.focus).not.toHaveBeenCalled();
      other.classList.add("hidden");
      await handleTasksWorkbenchShortcut(ctx, event);
      expect(search.focus).toHaveBeenCalledTimes(1);
      expect(event.preventDefault).toHaveBeenCalledTimes(1);
    } finally {
      drawer.remove();
      other.remove();
    }
  });

  it("does not render after a cancelled workbench delete", async () => {
    const deleteTasksById = cancelledDelete();
    const renderTasksWorkbench = vi.fn();
    const cases = [
      () => deleteActiveTasksWorkbenchItem({
        state: { tasksWorkbench: {} },
        els: { tasksWorkbenchForm: Object.assign(document.createElement("form"), {
          innerHTML: '<input name="task_id" value="task-1">',
        }) },
        deleteTasksById,
        renderTasksWorkbench,
      }),
      () => applyTasksWorkbenchBulkAction({
        state: { tasksWorkbench: { selected: new Set(["task-1"]), activeTaskId: "" } },
        els: { tasksWorkbenchBulkAction: { value: "delete" } },
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
    expect(renderTasksWorkbench).not.toHaveBeenCalled();
  });
});
