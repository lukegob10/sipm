import { expect, it, vi } from "vitest";
import { createTeamCapacityRouteController } from "../../js/routes/team-capacity/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";
function harness() {
  const state = { authed: true, user: { user_id: "u" }, activeSpace: { space_id: "s" }, capacitySelectedSoeid: "", users: [], teamCapacity: {} };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const els = { capacityTeamFilter: document.createElement("input"), capacityNameFilter: document.createElement("input") };
  const callbacks = new Map();
  const writeStoredJson = vi.fn();
  const renderTeamCapacity = vi.fn();
  const controller = createTeamCapacityRouteController({ state, els, teamCapacityViewStateKey: "key", writeStoredJson,
    readStoredJsonState: () => ({ value: { team_filter: "stored team", name_filter: "stored name" }, recovered: false }),
    activeSpaceScopedStorageKey: (key) => key, renderTeamCapacity,
    bindDebouncedInput: (el, onChange, _delay, onInput) => { if (el) callbacks.set(el, { onChange, onInput }); },
  });
  controller.bindTeamCapacityControls();
  return { state, lifetime, els, callbacks, writeStoredJson, renderTeamCapacity, controller };
}
it("retains both pending filters through same-context restore and refresh", () => {
  const h = harness();
  for (const [el, value] of [[h.els.capacityTeamFilter, "draft team"], [h.els.capacityNameFilter, "draft name"]]) {
    el.value = value; h.callbacks.get(el).onInput(value);
  }
  h.state.user = { user_id: "u" }; h.state.activeSpace = { space_id: "s" };
  h.controller.restoreTeamCapacityViewState();
  expect(h.els.capacityTeamFilter.value).toBe("draft team");
  expect(h.els.capacityNameFilter.value).toBe("draft name");
  h.callbacks.get(h.els.capacityTeamFilter).onChange("draft team");
  expect(h.writeStoredJson).toHaveBeenCalledOnce();
});
it.each(["session", "space"])("ignores an old %s filter timer after context changes", (field) => {
  const h = harness();
  const el = h.els.capacityTeamFilter;
  el.value = "old"; h.callbacks.get(el).onInput("old");
  h.lifetime[field]++;
  h.controller.restoreTeamCapacityViewState();
  h.callbacks.get(el).onChange("old");
  expect(el.value).toBe("stored team");
  expect(h.writeStoredJson).not.toHaveBeenCalled();
  expect(h.renderTeamCapacity).not.toHaveBeenCalled();
});
