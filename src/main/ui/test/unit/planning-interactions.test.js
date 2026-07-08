import { beforeEach, describe, expect, it, vi } from "vitest";

import { bindPlanningBoardEvents } from "../../js/routes/planning/interactions.js";
import { renderPlanningView } from "../../js/routes/planning/render.js";
import { boardState } from "../../js/routes/planning/state.js";
import { resetBoardState } from "../../js/routes/planning/storage.js";

async function waitFor(predicate) {
  for (let index = 0; index < 20; index += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("Timed out waiting for condition");
}

function dropEventWithData(data = {}) {
  const event = new Event("drop", { bubbles: true, cancelable: true });
  const values = new Map(Object.entries(data));
  Object.defineProperty(event, "dataTransfer", {
    value: {
      getData: (key) => values.get(key) || "",
    },
  });
  return event;
}

describe("planning board interactions", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetBoardState("space-1");
    boardState.month = "2026-03";
  });

  it("moves an existing person project allocation to a team when drag data lacks the allocation id", async () => {
    const root = document.createElement("div");
    const calls = [];
    const updatedAllocation = {
      id: "alloc-project",
      work_item_type: "project",
      work_item_id: "project-1",
      assignee_type: "team",
      assignee_id: "team-1",
      assignee_name: "Delivery",
      month: "2026-03",
      fte_months_allocated: 1,
    };
    const ctx = {
      els: { planningBoard: root },
      state: { workspacePrefs: { showCompleted: false } },
      api: vi.fn(async (path, options = {}) => {
        calls.push({ path, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : null });
        if (options.method === "PATCH") return updatedAllocation;
        if (path === "/planning/work-allocation/board?month=2026-03") {
          return {
            teams: [{ id: "team-1", name: "Delivery" }],
            people: [{ id: "person-1", name: "Taylor", team_id: "team-1", capacity_fte_months: 1 }],
            projects: [{ id: "project-1", title: "Project", status: "active", fte_months: 1, residual_fte_months: 1 }],
            solutions: [],
            tasks: [],
            allocations: [updatedAllocation],
          };
        }
        throw new Error(`Unexpected API call: ${path}`);
      }),
      refreshFromServer: vi.fn(),
    };
    boardState.ctx = ctx;
    boardState.data = {
      teams: [{ id: "team-1", name: "Delivery" }],
      people: [{ id: "person-1", name: "Taylor", team_id: "team-1", capacity_fte_months: 1 }],
      projects: [{ id: "project-1", title: "Project", status: "active", fte_months: 1, residual_fte_months: 1 }],
      solutions: [],
      tasks: [],
      allocations: [
        {
          id: "alloc-project",
          work_item_type: "project",
          work_item_id: "project-1",
          assignee_type: "person",
          assignee_id: "person-1",
          assignee_name: "Taylor",
          month: "2026-03",
          fte_months_allocated: 1,
        },
      ],
    };

    renderPlanningView(root);
    bindPlanningBoardEvents();
    boardState.dragItem = {
      kind: "project",
      workItemType: "project",
      workItemId: "project-1",
    };

    root.querySelector(".wab-team-assignment-zone").dispatchEvent(dropEventWithData({
      "application/x-wab-kind": "project",
      "application/x-wab-work-item-type": "project",
      "application/x-wab-work-item-id": "project-1",
      "text/plain": "project:project-1",
    }));

    await waitFor(() => calls.some((call) => call.method === "PATCH"));

    expect(calls.filter((call) => call.method === "PATCH")).toEqual([
      {
        path: "/planning/work-allocation/allocations/alloc-project",
        method: "PATCH",
        body: {
          assignee_type: "team",
          assignee_id: "team-1",
          fte_months_allocated: 1,
        },
      },
    ]);
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });
});
