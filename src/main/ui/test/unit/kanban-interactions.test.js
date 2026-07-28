import { describe, expect, it, vi } from "vitest";

import { createKanbanRouteController } from "../../js/routes/kanban/interactions.js";


function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function harness(api) {
  const state = {
    kanbanFilters: {},
    phases: [
      { phase_id: "development", phase_name: "Development" },
      { phase_id: "testing", phase_name: "Testing" },
    ],
    projects: [],
    solutions: [
      {
        solution_id: "solution-1",
        solution_name: "Build",
        project_id: "project-1",
        current_phase: "development",
      },
    ],
  };
  const renderKanban = vi.fn();
  const setStatus = vi.fn();
  const markIgnoreRefresh = vi.fn();
  const clearIgnoredRefresh = vi.fn();
  const trackWorkflow = vi.fn();
  const controller = createKanbanRouteController({
    state,
    els: {},
    kanbanViewStateKey: "kanban-test",
    writeStoredJson: vi.fn(),
    readStoredJsonState: vi.fn(() => ({ value: {}, recovered: false })),
    activeSpaceScopedStorageKey: (value) => value,
    bindDebouncedInput: vi.fn(),
    renderKanban,
    openProjectForm: vi.fn(),
    openSolutionModal: vi.fn(),
    hideClosedDeliverables: () => false,
    isClosedSolutionStatus: () => false,
    api,
    markIgnoreRefresh,
    ignoreNextRefresh: { delete: clearIgnoredRefresh },
    upsertById: (items, updated, idKey) => {
      const index = items.findIndex((item) => item[idKey] === updated[idKey]);
      items[index] = updated;
    },
    setStatus,
    phaseDisplayName: (phaseId) => state.phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
    trackWorkflow,
  });
  return {
    controller,
    state,
    renderKanban,
    setStatus,
    markIgnoreRefresh,
    clearIgnoredRefresh,
    trackWorkflow,
  };
}

describe("kanban route interactions", () => {
  it("optimistically moves a solution and persists its current phase", async () => {
    const request = deferred();
    const api = vi.fn(() => request.promise);
    const ctx = harness(api);

    const move = ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing");

    expect(ctx.state.solutions[0].current_phase).toBe("testing");
    expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(true);
    expect(ctx.renderKanban).toHaveBeenCalledTimes(1);
    expect(ctx.markIgnoreRefresh).toHaveBeenCalledWith("solutions");
    expect(api).toHaveBeenCalledWith("/solutions/solution-1", {
      method: "PATCH",
      body: JSON.stringify({ current_phase: "testing" }),
    });

    request.resolve({ ...ctx.state.solutions[0], updated_at: "2026-07-28T12:00:00Z" });
    await expect(move).resolves.toBe(true);

    expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(false);
    expect(ctx.renderKanban).toHaveBeenCalledTimes(2);
    expect(ctx.setStatus).toHaveBeenLastCalledWith("Build moved to Testing.", "success");
    expect(ctx.trackWorkflow).toHaveBeenCalledWith(
      "solutions",
      "update",
      "success",
      expect.objectContaining({ source: "kanban_drag", from_phase: "development", to_phase: "testing" }),
    );
  });

  it("restores the original phase when the save fails", async () => {
    const api = vi.fn().mockRejectedValue(new Error("Network unavailable"));
    const ctx = harness(api);

    await expect(ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing")).resolves.toBe(false);

    expect(ctx.state.solutions[0].current_phase).toBe("development");
    expect(ctx.clearIgnoredRefresh).toHaveBeenCalledWith("solutions");
    expect(ctx.setStatus).toHaveBeenLastCalledWith(
      "Could not move Build to Testing: Network unavailable",
      "danger",
    );
    expect(ctx.renderKanban).toHaveBeenCalledTimes(2);
    expect(ctx.trackWorkflow).toHaveBeenCalledWith(
      "solutions",
      "update",
      "failure",
      expect.objectContaining({ source: "kanban_drag", from_phase: "development", to_phase: "testing" }),
    );
  });
});
