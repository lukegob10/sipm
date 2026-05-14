import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadBoard } from "../../js/routes/planning/api.js";
import { boardState } from "../../js/routes/planning/state.js";
import { resetBoardState } from "../../js/routes/planning/storage.js";

const emptyBoard = {
  teams: [],
  people: [],
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
            tasks: [{ id: "march-task", title: "March", fte_months: 0.25, status: "backlog" }],
          };
        }
        if (path === "/planning/work-allocation/tasks?month=2026-04") {
          return [{ id: "april-task", title: "April", fte_months: 0.5, status: "backlog" }];
        }
        if (path === "/planning/work-allocation/allocations?month=2026-04") {
          return [];
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
    await waitFor(() => boardState.data.tasks.some((task) => task.id === "april-task"));

    expect(boardState.month).toBe("2026-04");
    expect(boardState.data.tasks).toEqual([
      { id: "april-task", title: "April", fte_months: 0.5, status: "backlog" },
    ]);
    expect(boardState.pendingLoadOptions).toBeNull();
  });
});
