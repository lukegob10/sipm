import { describe, expect, it, vi } from "vitest";
import { createKanbanRouteController } from "../../js/routes/kanban/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";

function harness() {
  const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" },
    kanbanFilters: { project: "", owner: "" }, phases: [], projects: [], solutions: [] };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  let onInput;
  let onChange;
  const writeStoredJson = vi.fn();
  const renderKanban = vi.fn();
  const controller = createKanbanRouteController({
    state, els: { kanbanFilterOwner: document.createElement("input") }, kanbanViewStateKey: "kanban-test",
    writeStoredJson, readStoredJsonState: () => ({ value: { filters: { owner: "stored", project: "" } }, recovered: false }),
    activeSpaceScopedStorageKey: (key) => key,
    bindDebouncedInput: (_element, change, _delay, input) => { onInput = input; onChange = change; },
    renderKanban,
  });
  controller.bindKanbanRouteControls();
  return { state, lifetime, controller, writeStoredJson, renderKanban,
    input: (value) => onInput?.(value), change: (value) => onChange(value) };
}

describe("Kanban owner filter context", () => {
  it.each([
    ["session", false], ["space", false], ["session", true], ["space", true],
  ])("discards delayed owner input after a %s change (restored: %s)", (change, restore) => {
    const h = harness();
    h.input("private old filter");
    expect(h.controller.getPendingOwner()).toBe("private old filter");
    h.lifetime[change] += 1;
    expect(h.controller.getPendingOwner()).toBeNull();
    if (restore) h.controller.restoreKanbanViewState();
    h.writeStoredJson.mockClear();
    h.renderKanban.mockClear();
    h.change("private old filter");
    expect(h.state.kanbanFilters.owner).toBe(restore ? "stored" : "");
    expect(h.writeStoredJson).not.toHaveBeenCalled();
    expect(h.renderKanban).not.toHaveBeenCalled();
  });

  it("keeps pending owner input when the same session refresh restores its filters", () => {
    const h = harness();
    h.input("draft owner");
    h.state.user = { user_id: "user-1" };
    h.state.activeSpace = { space_id: "space-1" };
    h.controller.restoreKanbanViewState();
    expect(h.state.kanbanFilters.owner).toBe("draft owner");
    h.change("draft owner");
    expect(h.state.kanbanFilters.owner).toBe("draft owner");
    expect(h.writeStoredJson).toHaveBeenCalledTimes(1);
    expect(h.renderKanban).toHaveBeenCalledTimes(1);
  });
});
