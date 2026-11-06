import { describe, expect, it, vi } from "vitest";
import { createTeamCapacityRouteController } from "../../js/routes/team-capacity/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function harness() {
  document.body.innerHTML = '<form id="capacity"><input name="soeid" value="target"><input name="display_name" value="Target"><input name="team_tag" value="Team"><input name="capacity_fte_month" value="1"></form><button id="delete">Deactivate</button>';
  const state = { authed: true, user: { user_id: "admin" }, activeSpace: { space_id: "one", space_name: "One" }, teamCapacity: {}, users: [{ soeid: "target", display_name: "Target" }], capacitySelectedSoeid: "target", currentView: "team-capacity" };
  const els = { capacityUserForm: document.getElementById("capacity"), capacityUserDelete: document.getElementById("delete") };
  const api = vi.fn();
  const showConfirmModal = vi.fn();
  const setCapacityUserFormStatus = vi.fn();
  const handleAuthError = vi.fn(() => false);
  const controller = createTeamCapacityRouteController({
    state, els, api, showConfirmModal, setCapacityUserFormStatus, handleAuthError,
    applyEntityData: vi.fn((_key, value) => { state.users = value; }), renderTeamCapacity: vi.fn(), populateSelects: vi.fn(),
    writeStoredJson: vi.fn(), readStoredJsonState: () => ({ value: {}, recovered: false }), activeSpaceScopedStorageKey: () => "key",
    bindDebouncedInput: vi.fn(), clearCapacityUserFormStatus: vi.fn(), userCapacityFteMonth: () => 1,
    formatFte: () => "1.00", numberOr: (value) => Number(value), timestampLabel: () => "now",
  });
  controller.bindTeamCapacityControls();
  return { state, els, api, controller, showConfirmModal, setCapacityUserFormStatus, handleAuthError };
}

describe("team capacity session isolation", () => {
  it("rejects a confirmation after selecting away and back to the same member", async () => {
    const h = harness();
    h.state.users.push({ soeid: "other", display_name: "Other" });
    const confirmation = deferred();
    h.showConfirmModal.mockReturnValue(confirmation.promise);
    h.els.capacityUserDelete.click();
    const input = h.els.capacityUserForm.querySelector('[name="display_name"]');
    input.value = "Other"; input.dispatchEvent(new Event("input", { bubbles: true }));
    input.value = "Target"; input.dispatchEvent(new Event("input", { bubbles: true }));
    confirmation.resolve(true);
    await Promise.resolve(); await Promise.resolve();
    expect(h.api).not.toHaveBeenCalled();
  });
  it("does not deactivate after the session changes during confirmation", async () => {
    const h = harness();
    const confirmation = deferred();
    h.showConfirmModal.mockReturnValue(confirmation.promise);
    h.els.capacityUserDelete.click();
    h.state.user = { user_id: "replacement" };
    confirmation.resolve(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.api).not.toHaveBeenCalled();
  });

  it("does not refresh or notify a replacement session after a save", async () => {
    const h = harness();
    const save = deferred();
    h.api.mockReturnValue(save.promise);
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    h.state.user = { user_id: "replacement" };
    save.resolve({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.api).toHaveBeenCalledTimes(1);
    expect(h.setCapacityUserFormStatus).not.toHaveBeenCalled();
  });

  it("ignores an old roster authorization failure after a replacement login", async () => {
    const h = harness();
    const load = deferred();
    h.api.mockReturnValue(load.promise);
    const pending = h.controller.loadTeamCapacityData({ force: true });
    h.state.user = { user_id: "replacement" };
    load.reject(Object.assign(new Error("old failure"), { status: 401 }));
    await pending;
    expect(h.handleAuthError).not.toHaveBeenCalled();
    expect(h.state.teamCapacity.error).toBe("");
  });

  it("resets the form without recursively dispatching resets", () => {
    const h = harness();
    const events = vi.fn();
    h.els.capacityUserForm.addEventListener("reset", events);
    h.els.capacityUserForm.dispatchEvent(new Event("reset", { bubbles: true, cancelable: true }));
    expect(events).toHaveBeenCalledTimes(1);
    expect(h.els.capacityUserForm.querySelector('[name="soeid"]').value).toBe("");
    expect(h.state.capacitySelectedSoeid).toBe("");
  });

  it("does not deactivate a different selection after confirmation", async () => {
    const h = harness();
    const confirmation = deferred();
    h.showConfirmModal.mockReturnValue(confirmation.promise);
    h.els.capacityUserDelete.click();
    h.els.capacityUserForm.querySelector('[name="soeid"]').value = "other";
    confirmation.resolve(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.api).not.toHaveBeenCalled();
  });

  it("serializes saves and preserves edits made while saving", async () => {
    const h = harness();
    const save = deferred();
    h.api.mockReturnValueOnce(save.promise).mockResolvedValueOnce([{ soeid: "target", display_name: "Target" }]);
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(h.api).toHaveBeenCalledTimes(1);
    h.els.capacityUserForm.querySelector('[name="team_tag"]').value = "new draft";
    h.setCapacityUserFormStatus.mockClear();
    save.resolve({});
    await vi.waitFor(() => expect(h.api).toHaveBeenCalledTimes(2));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.els.capacityUserForm.querySelector('[name="team_tag"]').value).toBe("new draft");
    expect(h.setCapacityUserFormStatus).not.toHaveBeenCalled();
  });

  it("keeps a pending save and its completion through same-session refresh", async () => {
    const h = harness();
    registerMutationContextLifetime(h.state, () => ({ session: 1, space: 1 }));
    const save = deferred();
    h.api.mockReturnValueOnce(save.promise).mockResolvedValueOnce([{ soeid: "target", display_name: "Target", team_tag: "Updated" }]);
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    h.state.user = { user_id: "admin" };
    h.state.activeSpace = { space_id: "one", space_name: "One" };
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(h.api).toHaveBeenCalledTimes(1);
    save.resolve({});
    await vi.waitFor(() => expect(h.setCapacityUserFormStatus).toHaveBeenCalledWith("Saved member at now.", "success", 3200));
    expect(h.state.teamCapacity.loading).toBe(false);
  });

  it("clears the roster loading indicator after the user object refreshes", async () => {
    const h = harness();
    registerMutationContextLifetime(h.state, () => ({ session: 1, space: 1 }));
    const load = deferred();
    h.api.mockReturnValue(load.promise);
    const pending = h.controller.loadTeamCapacityData({ force: true });
    h.state.user = { user_id: "admin" };
    h.state.activeSpace = { space_id: "one", space_name: "One" };
    load.resolve([{ soeid: "target", display_name: "Target" }]);
    await pending;
    expect(h.state.teamCapacity.loading).toBe(false);
    expect(h.state.teamCapacity.lastLoadedAt).toBeTruthy();
  });

  it("saves and refreshes the selected member in the current session", async () => {
    const h = harness();
    h.api.mockResolvedValueOnce({}).mockResolvedValueOnce([{ soeid: "target", display_name: "Target", team_tag: "Updated" }]);
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(h.setCapacityUserFormStatus).toHaveBeenCalledWith("Saved member at now.", "success", 3200));
    expect(h.els.capacityUserForm.querySelector('[name="team_tag"]').value).toBe("Updated");
  });

  it("reports a successful save when the following roster refresh fails", async () => {
    const h = harness();
    h.api.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("Roster unavailable"));
    h.els.capacityUserForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(h.setCapacityUserFormStatus).toHaveBeenCalledWith(expect.stringContaining("saved, but refresh failed"), "error"));
  });

  it("does not replace an in-progress edit when roster loading finishes", async () => {
    const h = harness();
    const load = deferred();
    h.api.mockReturnValue(load.promise);
    const pending = h.controller.loadTeamCapacityData({ force: true });
    h.els.capacityUserForm.querySelector('[name="team_tag"]').value = "draft";
    load.resolve([{ soeid: "target", display_name: "Target", team_tag: "Server" }]);
    await pending;
    expect(h.els.capacityUserForm.querySelector('[name="team_tag"]').value).toBe("draft");
  });

  it("deactivates and clears the original member in the current session", async () => {
    const h = harness();
    h.showConfirmModal.mockResolvedValue(true);
    h.api.mockResolvedValueOnce({}).mockResolvedValueOnce([]);
    h.els.capacityUserDelete.click();
    await vi.waitFor(() => expect(h.setCapacityUserFormStatus).toHaveBeenCalledWith("Member deactivated at now.", "success", 3200));
    expect(h.els.capacityUserForm.querySelector('[name="soeid"]').value).toBe("");
    expect(h.els.capacityUserForm.querySelector('[name="display_name"]').value).toBe("");
  });

  it("does not clear a different edit when deactivation completes", async () => {
    const h = harness();
    const save = deferred();
    h.showConfirmModal.mockResolvedValue(true);
    h.api.mockReturnValueOnce(save.promise).mockResolvedValueOnce([]);
    h.els.capacityUserDelete.click();
    await vi.waitFor(() => expect(h.api).toHaveBeenCalledTimes(1));
    h.els.capacityUserForm.querySelector('[name="soeid"]').value = "other";
    h.els.capacityUserForm.querySelector('[name="team_tag"]').value = "draft";
    save.resolve({});
    await vi.waitFor(() => expect(h.api).toHaveBeenCalledTimes(2));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.els.capacityUserForm.querySelector('[name="soeid"]').value).toBe("other");
    expect(h.els.capacityUserForm.querySelector('[name="team_tag"]').value).toBe("draft");
    expect(h.setCapacityUserFormStatus).not.toHaveBeenCalled();
  });

  it("releases a superseded load when the same user changes space context", async () => {
    const h = harness();
    const load = deferred();
    h.api.mockReturnValue(load.promise);
    const pending = h.controller.loadTeamCapacityData({ force: true });
    h.state.activeSpace = { space_id: "two" };
    load.resolve([]);
    await pending;
    expect(h.state.teamCapacity.loading).toBe(false);
    expect(h.state.users).toEqual([{ soeid: "target", display_name: "Target" }]);
  });

  it("reports an invalid roster response without replacing the roster", async () => {
    const h = harness();
    h.api.mockResolvedValue({ unexpected: true });
    await h.controller.loadTeamCapacityData({ force: true });
    expect(h.state.users).toEqual([{ soeid: "target", display_name: "Target" }]);
    expect(h.state.teamCapacity.error).toContain("invalid response");
  });
});
