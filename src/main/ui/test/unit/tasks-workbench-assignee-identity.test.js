import { describe, expect, it } from "vitest";
import { tasksWorkbenchRows } from "../../js/routes/tasks-workbench/filters.js";

function visibleTasks(preset, filters = {}) {
  const state = {
    user: { soeid: "first", display_name: "Alex" }, projects: [], solutions: [],
    tasks: [
      { task_id: "mine", assignee_user_soeid: "first", assignee: "Alex" },
      { task_id: "other", assignee_user_soeid: "second", assignee: "Alex" },
      { task_id: "legacy", assignee: "Alex" },
      { task_id: "blank", assignee: "" },
    ],
    tasksWorkbench: { filters, preset },
  };
  const ctx = { state, deriveTaskActionability: () => ({}), normalize: (v) => String(v || "").trim().toLowerCase(), isCompletedTaskStatus: () => false, numberOr: (v, d) => Number(v) || d, showCompletedOperationalWork: () => true, requestsClosedStatuses: () => false };
  return tasksWorkbenchRows(ctx).visibleRows.map((row) => row.task_id).sort();
}

describe("task assignee identity", () => {
  it("uses the selected ID over matching names, with a name fallback for legacy tasks", () => {
    expect(visibleTasks("all", { assignee: "first", assignee_name: "Alex" })).toEqual(["legacy", "mine"]);
  });
  it("uses the current user's ID for My tasks, with a name fallback for legacy tasks", () => {
    expect(visibleTasks("my")).toEqual(["legacy", "mine"]);
  });
  it("does not match blank names when the selected user has no name", () => {
    expect(visibleTasks("all", { assignee: "first", assignee_name: "" })).toEqual(["mine"]);
  });
});
