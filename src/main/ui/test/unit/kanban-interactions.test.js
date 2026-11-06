import { describe, expect, it, vi } from "vitest";

import { createKanbanRouteController } from "../../js/routes/kanban/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";
import { bindDeliverablesTable } from "../../js/routes/master/interactions.js";


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
    trackWorkflow,
  };
}

describe("kanban route interactions", () => {
  it.each(["master", "kanban"])("blocks overlapping cross-surface writes when %s starts first", async (first) => {
    const pending = deferred();
    const api = vi.fn(() => pending.promise);
    const ctx = harness(api);
    const table = document.createElement("div");
    table.innerHTML = '<select data-field="status" data-type="solution" data-id="solution-1"><option value="active">Active</option></select>';
    bindDeliverablesTable({ state: ctx.state, els: { masterTable: table }, api, upsertById: vi.fn(), renderMasterTable: vi.fn(), renderDashboard: vi.fn(), renderKanban: vi.fn(), renderCalendar: vi.fn() });
    const change = () => table.querySelector("select").dispatchEvent(new Event("change", { bubbles: true }));
    if (first === "master") {
      change();
      await expect(ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing")).resolves.toBe(false);
      expect(ctx.setStatus).toHaveBeenLastCalledWith(expect.stringMatching(/being updated/), "danger");
    } else {
      const move = ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing");
      change();
      expect(table.querySelector('[role="alert"]').textContent).toMatch(/being updated/);
      pending.resolve({ ...ctx.state.solutions[0] });
      await move;
    }
    expect(api).toHaveBeenCalledTimes(1);
  });
  it("optimistically moves a solution and persists its current phase", async () => {
    const request = deferred();
    const api = vi.fn(() => request.promise);
    const ctx = harness(api);

    const move = ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing");

    expect(ctx.state.solutions[0].current_phase).toBe("testing");
    expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(true);
    expect(ctx.renderKanban).toHaveBeenCalledTimes(1);
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

  it.each(["session", "space"])("keeps the replacement %s move owned when the old move succeeds or fails", async (change) => {
    for (const outcome of ["success", "failure"]) {
      const first = deferred();
      const second = deferred();
      const api = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
      const ctx = harness(api);
      ctx.state.authed = true;
      ctx.state.user = { user_id: "user-1" };
      ctx.state.activeSpace = { space_id: "space-1" };
      const lifetime = { session: 1, space: 1 };
      registerMutationContextLifetime(ctx.state, () => lifetime);
      const oldMove = ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing");
      lifetime[change] += 1;
      // Keep IDs the same to model a relogin or space round trip.
      ctx.state.solutions = [{ solution_id: "solution-1", solution_name: "New context", project_id: "project-1", current_phase: "development" }];
      const newMove = ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing");
      expect(api).toHaveBeenCalledTimes(2);
      ctx.setStatus.mockClear();
      ctx.renderKanban.mockClear();
      ctx.trackWorkflow.mockClear();
      if (outcome === "success") first.resolve({ solution_id: "solution-1", solution_name: "Old private", current_phase: "testing" });
      else first.reject(new Error("Old failure"));
      await expect(oldMove).resolves.toBe(false);
      expect(ctx.state.solutions[0].solution_name).toBe("New context");
      expect(ctx.state.solutions[0].current_phase).toBe("testing");
      expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(true);
      expect(ctx.setStatus).not.toHaveBeenCalled();
      expect(ctx.renderKanban).not.toHaveBeenCalled();
      expect(ctx.trackWorkflow).not.toHaveBeenCalled();
      second.resolve({ ...ctx.state.solutions[0] });
      await expect(newMove).resolves.toBe(true);
      expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(false);
    }
  });

  it("keeps a same-session refresh in the same pending move", async () => {
    const pending = deferred();
    const ctx = harness(vi.fn().mockReturnValue(pending.promise));
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    const move = ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing");
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(true);
    await expect(ctx.controller.moveKanbanSolutionToPhase("solution-1", "development")).resolves.toBe(false);
    pending.resolve({ ...ctx.state.solutions[0], updated_at: "updated" });
    await expect(move).resolves.toBe(true);
    expect(ctx.state.solutions[0].updated_at).toBe("updated");
    expect(ctx.controller.isKanbanSolutionMovePending("solution-1")).toBe(false);
  });

  it("restores the original phase when the save fails", async () => {
    const api = vi.fn().mockRejectedValue(new Error("Network unavailable"));
    const ctx = harness(api);

    await expect(ctx.controller.moveKanbanSolutionToPhase("solution-1", "testing")).resolves.toBe(false);

    expect(ctx.state.solutions[0].current_phase).toBe("development");
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
