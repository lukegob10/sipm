import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { Linter } from "eslint";
import { describe, expect, it, vi } from "vitest";

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
    tasksWorkbench: { selected: new Set(["task-1", "task-2"]), activeTaskId: "task-1" },
  };
  const api = vi.fn().mockResolvedValue(undefined);
  const showConfirmModal = vi.fn().mockResolvedValue(true);
  const markIgnoreRefresh = vi.fn();
  const removeById = vi.fn((rows, id, field) => {
    const index = rows.findIndex((row) => row[field] === id);
    if (index !== -1) rows.splice(index, 1);
  });
  const deleteTasks = runInNewContext(`${deleteSource}\ndeleteTasksById;`, {
    state, api, showConfirmModal, markIgnoreRefresh, removeById,
    captureEntityMutationContext, isEntityMutationContextCurrent,
    describeTasksForDelete: (ids) => ({ ids, previewText: "selected tasks" }),
  });
  return { state, api, showConfirmModal, markIgnoreRefresh, removeById, deleteTasks };
}

describe("task deletion session boundaries", () => {
  it("confirms once and updates the current task selection after a completed batch", async () => {
    const { state, api, markIgnoreRefresh, deleteTasks } = harness();

    const result = await deleteTasks(["task-1", "task-2"]);

    expect(result).toEqual({ cancelled: false, deletedIds: ["task-1", "task-2"], failed: [] });
    expect(api.mock.calls.map(([path]) => path)).toEqual(["/tasks/task-1", "/tasks/task-2"]);
    expect(markIgnoreRefresh).toHaveBeenCalledExactlyOnceWith("tasks");
    expect(state.tasks).toEqual([]);
    expect([...state.tasksWorkbench.selected]).toEqual([]);
    expect(state.tasksWorkbench.activeTaskId).toBe("");
  });

  it.each(["space", "session"])("does not submit an old confirmation after a %s change", async (change) => {
    const { state, api, showConfirmModal, markIgnoreRefresh, deleteTasks } = harness();
    const confirmation = deferred();
    showConfirmModal.mockReturnValue(confirmation.promise);
    const pending = deleteTasks(["task-1"]);

    if (change === "space") state.activeSpace = { space_id: "space-2" };
    else state.user = { user_id: "user-1" };
    confirmation.resolve(true);

    expect(await pending).toEqual({ cancelled: true, deletedIds: [], failed: [] });
    expect(api).not.toHaveBeenCalled();
    expect(markIgnoreRefresh).not.toHaveBeenCalled();
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
