import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadBoard,
  replaceWorkItemAssignment,
  unassignWorkItem,
} from "../../js/routes/planning/api.js";
import { boardState } from "../../js/routes/planning/state.js";
import { resetBoardState } from "../../js/routes/planning/storage.js";

const emptyBoard = {
  teams: [],
  people: [],
  projects: [],
  solutions: [],
  tasks: [],
  allocations: [],
};

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

async function waitFor(predicate) {
  for (let index = 0; index < 20; index += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("Timed out waiting for condition");
}

describe("planning board api", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetBoardState("space-1");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("queues the latest board load when the month changes during an in-flight load", async () => {
    const firstBoard = deferred();
    const calls = [];
    const ctx = {
      api: vi.fn(async (path) => {
        calls.push(path);
        if (path === "/planning/work-allocation/board?month=2026-03") {
          await firstBoard.promise;
          return {
            ...emptyBoard,
            projects: [{ id: "march-project", title: "March", fte_months: 0.25, residual_fte_months: 0.25, status: "active" }],
          };
        }
        if (path === "/planning/work-allocation/board?month=2026-04") {
          return {
            ...emptyBoard,
            projects: [{ id: "april-project", title: "April", fte_months: 0.5, residual_fte_months: 0.5, status: "active" }],
          };
        }
        throw new Error(`Unexpected path: ${path}`);
      }),
      noteRouteDataLoaded: vi.fn(),
    };

    boardState.month = "2026-03";
    const initialLoad = loadBoard(ctx);
    await waitFor(() => calls.includes("/planning/work-allocation/board?month=2026-03"));

    boardState.month = "2026-04";
    await loadBoard(ctx, { allocationsOnly: true });

    firstBoard.resolve();
    await initialLoad;
    await waitFor(() => boardState.data.projects.some((project) => project.id === "april-project"));

    expect(boardState.month).toBe("2026-04");
    expect(boardState.data.projects).toEqual([
      { id: "april-project", title: "April", fte_months: 0.5, residual_fte_months: 0.5, status: "active" },
    ]);
    expect(boardState.pendingLoadOptions).toBeNull();
  });

  it("moves a project back to backlog by clearing parent and child solution allocations", async () => {
    const calls = [];
    const ctx = {
      api: vi.fn(async (path, options = {}) => {
        calls.push({ path, method: options.method || "GET" });
        if (options.method === "DELETE") return null;
        if (path === "/planning/work-allocation/board?month=2026-03") {
          return {
            ...emptyBoard,
            projects: [{ id: "project-1", title: "Project", status: "active", fte_months: 1, residual_fte_months: 1 }],
            solutions: [{ id: "solution-1", project_id: "project-1", title: "Solution", status: "active", fte_months: 1 }],
          };
        }
        throw new Error(`Unexpected path: ${path}`);
      }),
    };
    boardState.ctx = ctx;
    boardState.month = "2026-03";
    boardState.data = {
      ...emptyBoard,
      projects: [{ id: "project-1", title: "Project", status: "active", fte_months: 1, residual_fte_months: 0.5 }],
      solutions: [{ id: "solution-1", project_id: "project-1", title: "Solution", status: "active", fte_months: 0.5 }],
      allocations: [
        { id: "alloc-project", work_item_type: "project", work_item_id: "project-1", assignee_type: "team", assignee_id: "team-1", month: "2026-03", fte_months_allocated: 0.5 },
        { id: "alloc-solution", work_item_type: "solution", work_item_id: "solution-1", assignee_type: "person", assignee_id: "person-1", month: "2026-03", fte_months_allocated: 0.5 },
      ],
    };

    await unassignWorkItem("project", "project-1", { pushUndo: true });

    expect(calls.filter((call) => call.method === "DELETE").map((call) => call.path)).toEqual([
      "/planning/work-allocation/allocations/alloc-project",
      "/planning/work-allocation/allocations/alloc-solution",
    ]);
  });

  it("replaces existing solution placements with one person assignment using full solution FTE", async () => {
    const posts = [];
    const deletes = [];
    const ctx = {
      api: vi.fn(async (path, options = {}) => {
        if (options.method === "DELETE") {
          deletes.push(path);
          return null;
        }
        if (options.method === "POST") {
          posts.push(JSON.parse(options.body));
          return {
            id: "alloc-new",
            work_item_type: "solution",
            work_item_id: "solution-1",
            assignee_type: "person",
            assignee_id: "person-1",
            month: "2026-03",
            fte_months_allocated: 0.75,
          };
        }
        if (path === "/planning/work-allocation/board?month=2026-03") {
          return {
            ...emptyBoard,
            people: [{ id: "person-1", name: "Taylor", team_id: "team-1" }],
            solutions: [{ id: "solution-1", project_id: "project-1", title: "Solution", status: "active", fte_months: 0.75, remaining_fte_months: 0 }],
            allocations: [{ id: "alloc-new", work_item_type: "solution", work_item_id: "solution-1", assignee_type: "person", assignee_id: "person-1", month: "2026-03", fte_months_allocated: 0.75 }],
          };
        }
        throw new Error(`Unexpected path: ${path}`);
      }),
    };
    boardState.ctx = ctx;
    boardState.month = "2026-03";
    boardState.data = {
      ...emptyBoard,
      people: [{ id: "person-1", name: "Taylor", team_id: "team-1" }],
      solutions: [{ id: "solution-1", project_id: "project-1", title: "Solution", status: "active", fte_months: 0.75, remaining_fte_months: 0 }],
      allocations: [
        { id: "alloc-team", work_item_type: "solution", work_item_id: "solution-1", assignee_type: "team", assignee_id: "team-1", month: "2026-03", fte_months_allocated: 0.25 },
        { id: "alloc-person", work_item_type: "solution", work_item_id: "solution-1", assignee_type: "person", assignee_id: "person-2", month: "2026-03", fte_months_allocated: 0.5 },
      ],
    };

    await replaceWorkItemAssignment("solution", "solution-1", "person", "person-1", { pushUndo: true });

    expect(deletes).toEqual([
      "/planning/work-allocation/allocations/alloc-team",
      "/planning/work-allocation/allocations/alloc-person",
    ]);
    expect(posts).toEqual([
      {
        work_item_type: "solution",
        work_item_id: "solution-1",
        assignee_type: "person",
        assignee_id: "person-1",
        month: "2026-03",
        fte_months_allocated: 0.75,
      },
    ]);
  });
});
