import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { Linter } from "eslint";
import { describe, expect, it, vi } from "vitest";
import { invalidateMyWorkRecords } from "../../js/utils/my-work-state.js";

import {
  captureEntityMutationContext,
  isEntityMutationContextCurrent,
} from "../../js/utils/form-state.js";

const appSource = readFileSync(resolve("src/main/ui/js/app.js"), "utf8");
let deleteSource;
const diagnostics = new Linter().verify(appSource, [{
  languageOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: { extract: { rules: { deletion: { create: () => ({
    FunctionDeclaration(node) {
      if (node.id.name === "deleteTasksById") deleteSource = appSource.slice(...node.range);
    },
  }) } } } },
  rules: { "extract/deletion": "error" },
}]);
if (diagnostics.length || !deleteSource) throw new Error("Could not load the app task deletion helper");

function deferred() {
  let resolve;
  const promise = new Promise((complete) => { resolve = complete; });
  return { promise, resolve };
}

function harness() {
  const state = {
    user: { user_id: "user-1" },
    activeSpace: { space_id: "space-1" },
    tasks: [{ task_id: "task-1" }, { task_id: "task-2" }],
    myWork: {
      records: [{ task: { task_id: "task-1" } }, { task: { task_id: "task-2" } }],
      loading: true,
      loadRequestId: 7,
      selectedTaskId: "task-1",
    },
    tasksWorkbench: { selected: new Set(["task-1", "task-2"]), activeTaskId: "task-1" },
  };
  const api = vi.fn().mockResolvedValue(undefined);
  const showConfirmModal = vi.fn().mockResolvedValue(true);
  const removeById = vi.fn((rows, id, field) => {
    const index = rows.findIndex((row) => row[field] === id);
    if (index !== -1) rows.splice(index, 1);
  });
  const deleteTasks = runInNewContext(`${deleteSource}\ndeleteTasksById;`, {
    state, api, showConfirmModal, removeById,
    captureEntityMutationContext, isEntityMutationContextCurrent, invalidateMyWorkRecords,
    describeTasksForDelete: (ids) => ({ ids, previewText: "selected tasks" }),
  });
  return { state, api, showConfirmModal, removeById, deleteTasks };
}

describe("task deletion session boundaries", () => {
  it("does not send a deletion when confirmation is cancelled", async () => {
    const { state, api, showConfirmModal, deleteTasks } = harness();
    showConfirmModal.mockResolvedValue(false);
    expect(await deleteTasks(["task-1"])).toEqual({ cancelled: true, deletedIds: [], failed: [] });
    expect(api).not.toHaveBeenCalled();
    expect(state.tasks).toHaveLength(2);
  });

  it("confirms once and updates the current task selection after a completed batch", async () => {
    const { state, api, deleteTasks } = harness();

    const result = await deleteTasks(["task-1", "task-2"]);

    expect(result).toEqual({ cancelled: false, deletedIds: ["task-1", "task-2"], failed: [] });
    expect(api.mock.calls.map(([path]) => path)).toEqual(["/tasks/task-1", "/tasks/task-2"]);
    expect(state.tasks).toEqual([]);
    expect([...state.tasksWorkbench.selected]).toEqual([]);
    expect(state.tasksWorkbench.activeTaskId).toBe("");
    expect(state.myWork.records).toBeNull();
    expect(state.myWork.loading).toBe(false);
    expect(state.myWork.loadRequestId).toBeGreaterThan(7);
  });

  it("keeps My Work unchanged when every task deletion fails", async () => {
    const { state, api, deleteTasks } = harness();
    const records = state.myWork.records;
    api.mockRejectedValue(new Error("Permission denied"));

    const result = await deleteTasks(["task-1"]);

    expect(result.deletedIds).toEqual([]);
    expect(result.failed).toHaveLength(1);
    expect(state.myWork.records).toBe(records);
    expect(state.myWork.loadRequestId).toBe(7);
  });

  it.each(["space", "session"])("does not submit an old confirmation after a %s change", async (change) => {
    const { state, api, showConfirmModal, deleteTasks } = harness();
    const confirmation = deferred();
    showConfirmModal.mockReturnValue(confirmation.promise);
    const pending = deleteTasks(["task-1"]);

    if (change === "space") state.activeSpace = { space_id: "space-2" };
    else state.user = { user_id: "user-1" };
    confirmation.resolve(true);

    expect(await pending).toEqual({ cancelled: true, deletedIds: [], failed: [] });
    expect(api).not.toHaveBeenCalled();
  });

  it("stops a pending batch and leaves replacement workspace state untouched", async () => {
    const { state, api, removeById, deleteTasks } = harness();
    const firstDelete = deferred();
    api.mockReturnValueOnce(firstDelete.promise);
    const pending = deleteTasks(["task-1", "task-2"]);
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));

    state.activeSpace = { space_id: "space-2" };
    const replacementTasks = [{ task_id: "new-task" }];
    const replacementWorkbench = { selected: new Set(["new-task"]), activeTaskId: "new-task" };
    state.tasks = replacementTasks;
    state.tasksWorkbench = replacementWorkbench;
    firstDelete.resolve();

    expect(await pending).toEqual({ cancelled: true, deletedIds: [], failed: [] });
    expect(api).toHaveBeenCalledTimes(1);
    expect(removeById).not.toHaveBeenCalled();
    expect(state.tasks).toBe(replacementTasks);
    expect(state.tasksWorkbench).toBe(replacementWorkbench);
    expect([...replacementWorkbench.selected]).toEqual(["new-task"]);
    expect(replacementWorkbench.activeTaskId).toBe("new-task");
  });
});
