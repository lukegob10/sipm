import { describe, expect, it, vi } from "vitest";

import { tasksWorkbenchRows, tasksWorkbenchSummary } from "../../js/routes/tasks-workbench/filters.js";

function createContext(tasks = [], overrides = {}) {
  const normalize = (value) => String(value || "").trim().toLowerCase();
  return {
    state: {
      tasks,
      projects: [{ project_id: "project-1", project_name: "Platform" }],
      solutions: [{ solution_id: "solution-1", solution_name: "Workflow" }],
      user: { display_name: "Test User", soeid: "tu12345" },
      tasksWorkbench: { filters: {}, preset: "all", sort: "default", visibleIds: [] },
    },
    deriveTaskActionability: vi.fn((task) => ({
      is_overdue: !!task.is_overdue,
      is_due_soon: !!task.is_due_soon,
      is_stale: !!task.is_stale,
      urgency_score: Number(task.urgency_score || 0),
    })),
    normalize,
    isCompletedTaskStatus: (value) => ["complete", "abandoned"].includes(normalize(value)),
    numberOr: (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback,
    showCompletedOperationalWork: () => false,
    requestsClosedStatuses: (value) => ["complete", "abandoned"].includes(normalize(value)),
    ...overrides,
  };
}

function task(taskId, overrides = {}) {
  return {
    task_id: taskId,
    task_name: taskId,
    project_id: "project-1",
    solution_id: "solution-1",
    status: "to_do",
    priority: 3,
    ...overrides,
  };
}

function visibleIds(ctx) {
  const result = tasksWorkbenchRows(ctx);
  const ids = result.visibleRows.map((row) => row.task_id);
  expect(ctx.state.tasksWorkbench.visibleIds).toEqual(ids);
  return ids;
}

describe("task workbench filtering", () => {
  it("uses the first matching parent, preserving empty and missing names", () => {
    const ctx = createContext([
      task("linked"),
      task("missing", { project_id: "missing", solution_id: "missing" }),
      task("empty", { project_id: "empty", solution_id: "empty" }),
      task("numeric", { project_id: 1, solution_id: 1 }),
    ]);
    ctx.state.projects.push(
      { project_id: "project-1", project_name: "Duplicate project" },
      { project_id: "empty", project_name: "" },
      { project_id: "empty", project_name: "Later project" },
      { project_id: "1", project_name: "String project" },
      { project_id: 1, project_name: "Numeric project" },
    );
    ctx.state.solutions.push(
      { solution_id: "solution-1", solution_name: "Duplicate solution" },
      { solution_id: "empty" },
      { solution_id: "empty", solution_name: "Later solution" },
      { solution_id: "1", solution_name: "String solution" },
      { solution_id: 1, solution_name: "Numeric solution" },
    );

    expect(tasksWorkbenchRows(ctx).allRows.map((row) => [row.project_name, row.solution_name])).toEqual([
      ["Platform", "Workflow"],
      ["", ""],
      ["", ""],
      ["Numeric project", "Numeric solution"],
    ]);
    ctx.state.tasksWorkbench.filters.search = "duplicate";
    expect(visibleIds(ctx)).toEqual([]);
  });

  it("keeps rows and summaries when parent collections or task collections are empty", () => {
    const ctx = createContext([task("orphan")]);
    ctx.state.projects = [];
    ctx.state.solutions = [];
    expect(tasksWorkbenchRows(ctx).visibleRows[0]).toMatchObject({ project_name: "", solution_name: "" });

    ctx.state.tasks = undefined;
    const { allRows, visibleRows } = tasksWorkbenchRows(ctx);
    expect(allRows).toEqual([]);
    expect(visibleRows).toEqual([]);
    expect(ctx.state.tasksWorkbench.visibleIds).toEqual([]);
    expect(tasksWorkbenchSummary(ctx, allRows, visibleRows)).toEqual({
      total: 0, visible: 0, hiddenClosed: 0, overdue: 0, dueSoon: 0, blocked: 0, unassigned: 0,
    });
  });

  it.each([
    ["task_name", " Release Title "],
    ["description", " Release Description "],
    ["acceptance_criteria", " Release Acceptance "],
    ["done_criteria", " Release Done "],
    ["assignee", " Release Owner "],
    ["status", " Release Status "],
  ])("searches normalized %s text", (field, value) => {
    const ctx = createContext([task("match", { [field]: value }), task("other")]);
    ctx.state.tasksWorkbench.filters.search = " RELEASE ";
    expect(visibleIds(ctx)).toEqual(["match"]);
  });

  it.each([" PLATFORM ", " WORKFLOW "])("searches current parent names with %s", (search) => {
    const ctx = createContext([task("linked"), task("missing", { project_id: "other", solution_id: "other" })]);
    ctx.state.tasksWorkbench.filters.search = search;
    expect(visibleIds(ctx)).toEqual(["linked"]);
  });

  it.each([
    [{ project_id: "project-1" }, ["assigned", "unassigned"]],
    [{ solution_id: "solution-1" }, ["assigned", "unassigned"]],
    [{ status: "in_progress" }, ["assigned"]],
    [{ priority_max: "2" }, ["assigned"]],
    [{ assignee: "TU12345", assignee_name: "Test User" }, ["name-only", "assigned"]],
    [{ assignee: "__unassigned__" }, ["unassigned"]],
    [{ project_id: "project-1", status: "in_progress", search: "platform", priority_max: "2" }, ["assigned"]],
  ])("preserves combined filter behavior for %j", (filters, expected) => {
    const ctx = createContext([
      task("assigned", { assignee_user_soeid: "tu12345", assignee: "Test User", status: "in_progress", priority: 2 }),
      task("name-only", { project_id: "other", solution_id: "other", assignee: " test USER ", priority: 0 }),
      task("unassigned", { assignee: "  " }),
    ]);
    ctx.state.tasksWorkbench.filters = filters;
    expect(visibleIds(ctx)).toEqual(expected);
  });

  it.each([
    ["my", ["mine-by-id", "mine-by-name"]],
    ["due_soon", ["mine-by-id"]],
    ["overdue", ["mine-by-name"]],
    ["blocked", ["blocked"]],
    ["unassigned", ["unassigned"]],
    ["stale", ["stale"]],
  ])("preserves the %s preset", (preset, expected) => {
    const ctx = createContext([
      task("mine-by-id", { assignee_user_soeid: "TU12345", is_due_soon: true }),
      task("mine-by-name", { assignee: " TEST USER ", is_overdue: true }),
      task("blocked", { blocked: true, assignee: "Other User" }),
      task("stale", { is_stale: true, assignee_user_soeid: "other" }),
      task("unassigned", { assignee: "  " }),
    ]);
    ctx.state.tasksWorkbench.preset = preset;
    expect(visibleIds(ctx)).toEqual(expected);
  });

  it("keeps closed tasks in all rows and summaries, with existing visibility overrides", () => {
    const ctx = createContext([
      task("open", { is_due_soon: true, blocked: true }),
      task("closed", { status: "complete", is_overdue: true }),
      task("abandoned", { status: "abandoned", assignee: "Other", is_stale: true }),
    ]);
    const { allRows, visibleRows } = tasksWorkbenchRows(ctx);
    expect(visibleRows.map((row) => row.task_id)).toEqual(["open"]);
    expect(tasksWorkbenchSummary(ctx, allRows, visibleRows)).toEqual({
      total: 3, visible: 1, hiddenClosed: 2, overdue: 1, dueSoon: 1, blocked: 1, unassigned: 2,
    });
    ctx.state.tasksWorkbench.filters.status = "complete";
    expect(visibleIds(ctx)).toEqual(["closed"]);
    ctx.state.tasksWorkbench.filters.status = "abandoned";
    expect(visibleIds(ctx)).toEqual(["abandoned"]);
    ctx.state.tasksWorkbench.filters = {};
    ctx.showCompletedOperationalWork = () => true;
    expect(visibleIds(ctx)).toEqual(["abandoned", "closed", "open"]);
  });

  it("preserves urgency, due date, priority and name ordering, including explicit name sorting", () => {
    const ctx = createContext([
      task("undated", { task_name: "Task 20" }),
      task("later", { task_name: "Task 10", due_date: "2026-09-09" }),
      task("normal", { task_name: "Task 3", due_date: "2026-09-08" }),
      task("urgent", { task_name: "Task 9", urgency_score: 90 }),
      task("priority", { task_name: "Task 2", due_date: "2026-09-08", priority: 1 }),
      task("name", { task_name: "Task 1", due_date: "2026-09-08", priority: 1 }),
    ]);
    expect(visibleIds(ctx)).toEqual(["urgent", "name", "priority", "normal", "later", "undated"]);
    ctx.state.tasksWorkbench.sort = "name-asc";
    expect(visibleIds(ctx)).toEqual(["name", "priority", "normal", "urgent", "later", "undated"]);
    ctx.state.tasksWorkbench.sort = "name-desc";
    expect(visibleIds(ctx)).toEqual(["undated", "later", "urgent", "normal", "priority", "name"]);
  });

  it("reflects in-place parent edits, reordering, deletion, insertion and complete state replacement", () => {
    const ctx = createContext([task("linked")]);
    const names = () => tasksWorkbenchRows(ctx).allRows.map((row) => [row.project_name, row.solution_name]);
    expect(names()).toEqual([["Platform", "Workflow"]]);
    ctx.state.projects[0].project_name = "Renamed project";
    ctx.state.solutions[0].solution_name = "Renamed solution";
    expect(names()).toEqual([["Renamed project", "Renamed solution"]]);
    ctx.state.projects.unshift({ project_id: "project-1", project_name: "First project" });
    ctx.state.solutions.unshift({ solution_id: "solution-1", solution_name: "First solution" });
    expect(names()).toEqual([["First project", "First solution"]]);
    ctx.state.projects.reverse();
    ctx.state.solutions.reverse();
    expect(names()).toEqual([["Renamed project", "Renamed solution"]]);
    ctx.state.projects.splice(0);
    ctx.state.solutions.splice(0);
    expect(names()).toEqual([["", ""]]);
    ctx.state.projects = [{ project_id: "new-project", project_name: "New space project" }];
    ctx.state.solutions = [{ solution_id: "new-solution", solution_name: "New space solution" }];
    ctx.state.tasks[0].project_id = "new-project";
    ctx.state.tasks[0].solution_id = "new-solution";
    expect(names()).toEqual([["New space project", "New space solution"]]);
  });

  it("derives fresh actionability without mutating source tasks or parents", () => {
    const ctx = createContext([task("first"), task("second")]);
    const original = JSON.parse(JSON.stringify({ tasks: ctx.state.tasks, projects: ctx.state.projects, solutions: ctx.state.solutions }));
    ctx.deriveTaskActionability.mockImplementation((row) => ({ urgency_score: row.task_id === "second" ? 10 : 0 }));
    expect(visibleIds(ctx)).toEqual(["second", "first"]);
    ctx.deriveTaskActionability.mockImplementation((row) => ({ urgency_score: row.task_id === "first" ? 20 : 0 }));
    expect(visibleIds(ctx)).toEqual(["first", "second"]);
    expect(ctx.deriveTaskActionability).toHaveBeenCalledTimes(4);
    expect({ tasks: ctx.state.tasks, projects: ctx.state.projects, solutions: ctx.state.solutions }).toEqual(original);
  });
});
