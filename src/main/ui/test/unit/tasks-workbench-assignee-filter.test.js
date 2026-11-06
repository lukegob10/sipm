import { expect, it } from "vitest";
import { tasksWorkbenchRows } from "../../js/routes/tasks-workbench/filters.js";

it("does not match unrelated tasks when the assignee name is unavailable", () => {
  const state = {
    projects: [],
    solutions: [],
    user: {},
    tasks: [
      { task_id: "a", assignee_user_soeid: "alice", assignee: "" },
      { task_id: "b", assignee_user_soeid: "bob", assignee: "" },
      { task_id: "c", assignee_user_soeid: "", assignee: "" },
    ],
    tasksWorkbench: { filters: { assignee: "alice", assignee_name: "" }, preset: "all", sort: "default" },
  };
  const ctx = {
    state,
    normalize: (value) => String(value || "").trim().toLowerCase(),
    deriveTaskActionability: () => ({}),
    isCompletedTaskStatus: () => false,
    showCompletedOperationalWork: () => true,
    requestsClosedStatuses: () => false,
    numberOr: (value, fallback) => Number(value) || fallback,
  };
  expect(tasksWorkbenchRows(ctx).visibleRows.map((row) => row.task_id)).toEqual(["a"]);
});
