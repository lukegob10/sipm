import { describe, expect, it, vi } from "vitest";
import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";
import { captureAgentChangeRequestContext, sameAgentChangeRequestContext } from "../../js/routes/spaces/change-request-context.js";

function harness(markup) {
  document.body.innerHTML = `<div id="shell">${markup}</div>`;
  delete document._spaceGovernanceEscapeBound;
  const shell = document.getElementById("shell");
  const state = {
    user: { user_id: "admin" }, activeSpace: { space_id: "space" }, currentView: "spaces",
    apiTokensByUser: {}, apiTokensLoadedByUser: {}, issuedApiToken: null, platformPasswordReset: null,
    spaceMembersLoadedBySpace: {}, spaceMembersBySpace: {}, spaces: [],
  };
  const api = vi.fn();
  const showConfirmModal = vi.fn();
  const setSpaceGovernanceNotice = vi.fn();
  const switchActiveSpace = vi.fn().mockResolvedValue(true);
  const renderGovernanceHub = vi.fn();
  const controller = createSpaceGovernanceController({
    state, els: { spaceGovernanceShell: shell, spaceCreateModalForm: shell.querySelector("#create-form"),
      spaceMemberModalForm: shell.querySelector("#member-form") }, api, activeSpaceId: () => state.activeSpace?.space_id,
    userIsGlobalAdmin: () => true, isSpaceGovernanceView: (view) => ["spaces", "access"].includes(view), renderGovernanceHub,
    normalize: (value) => String(value || "").toLowerCase(), showConfirmModal, setSpaceGovernanceNotice,
    buildResetPageUrl: () => "/reset", buildAppUrl: (path) => path, refreshFromServer: vi.fn(),
    canManageSpaceMembership: () => true, spaceNameForId: () => "Target", switchActiveSpace,
    clearDeliverableFormNotice: vi.fn(), setDeliverableFormNotice: vi.fn(), refreshSpaceContext: vi.fn(),
  });
  controller.bindSpaceAdminControls();
  return { state, api, shell, showConfirmModal, setSpaceGovernanceNotice, switchActiveSpace, renderGovernanceHub };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

describe("governance secrets across sessions", () => {
  it("keeps a one-time password and blocks duplicate issuance through a same-session refresh", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    registerMutationContextLifetime(state, () => ({ session: 1, space: 1 }));
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    const submit = () => shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    submit();
    state.user = { user_id: "admin" };
    state.activeSpace = { space_id: "space" };
    submit();
    expect(api).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("progress"), "error", expect.any(Number)));
    pending.resolve({ temp_password: "one-time-secret", expires_at: "later" });
    await vi.waitFor(() => expect(state.platformPasswordReset?.temp_password).toBe("one-time-secret"));
  });

  it("keeps an access request pending and clears its indicator after a same-session refresh", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<button data-space-action="request-space-access" data-space-id="space">Request</button>');
    registerMutationContextLifetime(state, () => ({ session: 1, space: 1 }));
    const pending = deferred();
    api.mockReturnValueOnce(pending.promise).mockResolvedValue([]);
    shell.querySelector("button").click();
    state.user = { user_id: "admin" };
    state.activeSpace = { space_id: "space" };
    shell.querySelector("button").click();
    expect(api).toHaveBeenCalledTimes(1);
    pending.resolve({});
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.any(String), "success", expect.any(Number)));
    expect(state.accessRequestSubmittingSpaceId).toBe("");
  });

  it("does not expose an old reset secret or unlock a new reset after same-account re-login", async () => {
    const { state, api, shell } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(state, () => lifetime);
    const old = deferred();
    const current = deferred();
    api.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const submit = () => shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    submit();
    lifetime.session += 1;
    state.user = { user_id: "admin" };
    submit();
    old.resolve({ temp_password: "old-secret" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.platformPasswordReset).toBeNull();
    submit();
    expect(api).toHaveBeenCalledTimes(2);
    current.resolve({ temp_password: "new-secret" });
    await vi.waitFor(() => expect(state.platformPasswordReset?.temp_password).toBe("new-secret"));
  });

  it("finishes personal-space creation after its intended switch and same-session refresh", async () => {
    const { state, api, shell, switchActiveSpace, setSpaceGovernanceNotice } = harness('<form id="space-personal-create-form"></form>');
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(state, () => lifetime);
    api.mockResolvedValue({ space_id: "new-space", name: "New" });
    switchActiveSpace.mockImplementation(async () => {
      state.user = { user_id: "admin" };
      state.activeSpace = { space_id: "new-space" };
      lifetime.space += 1;
      return true;
    });
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("Created"), "success", expect.any(Number)));
    expect(state.lobbyPersonalSpaceCreating).toBe(false);
  });

  it("isolates governance context across same-account new sessions and space round trips", () => {
    const { state } = harness("");
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(state, () => lifetime);
    const capture = () => captureAgentChangeRequestContext(state, () => state.activeSpace.space_id);
    const initial = capture();
    state.user = { user_id: "admin" };
    state.activeSpace = { space_id: "space" };
    expect(sameAgentChangeRequestContext(initial, capture())).toBe(true);
    lifetime.session += 1;
    expect(sameAgentChangeRequestContext(initial, capture())).toBe(false);
    const next = capture();
    lifetime.space += 1;
    state.activeSpace = { space_id: "other" };
    lifetime.space += 1;
    state.activeSpace = { space_id: "space" };
    expect(sameAgentChangeRequestContext(next, capture())).toBe(false);
  });

  it("shows a returned reset password in the same session", async () => {
    const { state, api, shell } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    api.mockResolvedValue({ temp_password: "fresh-secret", expires_at: "later" });
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(state.platformPasswordReset?.temp_password).toBe("fresh-secret"));
  });

  it("shows a newly issued API token in the same session", async () => {
    const { state, api, shell } = harness('<form id="user-api-token-form"><input name="soeid" value="target"><input name="name" value="test"></form>');
    api.mockResolvedValueOnce({ token: "fresh-token", user_id: "target" }).mockResolvedValueOnce([]);
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(state.issuedApiToken?.token).toBe("fresh-token"));
  });

  it("shows the issued secret immediately, blocks duplicate issuance and reports a failed list refresh", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="user-api-token-form"><input name="soeid" value="target"><input name="name" value="test"></form>');
    const issued = deferred();
    const list = deferred();
    api.mockReturnValueOnce(issued.promise).mockReturnValueOnce(list.promise);
    const submit = () => shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    submit(); submit();
    expect(api).toHaveBeenCalledTimes(1);
    issued.resolve({ token: "one-time", user_id: "target" });
    await vi.waitFor(() => expect(state.issuedApiToken?.token).toBe("one-time"));
    expect(api).toHaveBeenCalledTimes(2);
    list.resolve(Promise.reject(new Error("list unavailable")));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("Token issued"), "error", expect.any(Number)));
    expect(state.issuedApiToken?.token).toBe("one-time");
  });

  it("retains an issued token without taking focus or changing view after navigation", async () => {
    const { state, api, shell, renderGovernanceHub } = harness('<form id="user-api-token-form"><input name="soeid" value="target"><input name="name" value="test"></form>');
    const issued = deferred();
    api.mockReturnValueOnce(issued.promise).mockResolvedValueOnce([]);
    state.spaceAdminSection = "platform-access";
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    state.currentView = "master";
    state.spaceAdminSection = "current-space";
    issued.resolve({ token: "one-time", user_id: "target" });
    await vi.waitFor(() => expect(state.issuedApiToken?.token).toBe("one-time"));
    expect(state.currentView).toBe("master");
    expect(state.spaceAdminSection).toBe("current-space");
    expect(renderGovernanceHub).not.toHaveBeenCalled();
  });

  it("warns on malformed token issuance without issuing a second request", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="user-api-token-form"><input name="soeid" value="target"><input name="name" value="test"></form>');
    api.mockResolvedValue({ user_id: "target" });
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("may have succeeded"), "error", expect.any(Number)));
    expect(state.issuedApiToken).toBeNull();
    expect(api).toHaveBeenCalledTimes(1);
  });

  it.each(["toggle-space-active", "delete-space-member", "toggle-public-program-dashboard",
    "revoke-api-token", "revoke-global-admin", "grant-global-admin"])(
    "does not submit %s after its confirmation changes session", async (action) => {
      const markup = `<button data-space-action="${action}" data-space-id="space" data-membership-id="member" data-soeid="target" data-user-id="target" data-token-id="token">Action</button>`;
      const { state, api, shell, showConfirmModal } = harness(markup);
      const pending = deferred();
      showConfirmModal.mockReturnValue(pending.promise);
      api.mockResolvedValue({});
      shell.querySelector("button").click();
      state.user = { user_id: "admin" };
      pending.resolve(true);
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(api).not.toHaveBeenCalled();
    }
  );

  it.each(["toggle-public-program-dashboard", "revoke-api-token"])(
    "completes %s in the original session", async (action) => {
      const markup = `<button data-space-action="${action}" data-space-id="space" data-user-id="target" data-token-id="token">Action</button>`;
      const { api, shell, showConfirmModal, setSpaceGovernanceNotice } = harness(markup);
      showConfirmModal.mockResolvedValue(true);
      api.mockResolvedValueOnce({ space_id: "space", name: "Space" }).mockResolvedValueOnce([]);
      shell.querySelector("button").click();
      await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.any(String), "success", expect.any(Number)));
    }
  );

  it.each(["toggle-public-program-dashboard", "revoke-api-token"])(
    "ignores a delayed %s response after the session changes", async (action) => {
      const markup = `<button data-space-action="${action}" data-space-id="space" data-user-id="target" data-token-id="token">Action</button>`;
      const { state, api, shell, showConfirmModal, setSpaceGovernanceNotice } = harness(markup);
      const pending = deferred();
      showConfirmModal.mockResolvedValue(true);
      api.mockReturnValue(pending.promise);
      shell.querySelector("button").click();
      await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
      state.user = { user_id: "admin" };
      pending.resolve({ space_id: "space", name: "Space" });
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(api).toHaveBeenCalledTimes(1);
      expect(setSpaceGovernanceNotice).not.toHaveBeenCalled();
    }
  );

  it.each(["request-space-access", "cancel-access-request", "approve-access-request", "reject-access-request"])(
    "ignores a delayed %s result after the session changes", async (action) => {
      const markup = `<button data-space-action="${action}" data-space-id="space" data-request-id="request">Action</button>`;
      const { state, api, shell, setSpaceGovernanceNotice } = harness(markup);
      const pending = deferred();
      api.mockReturnValue(pending.promise);
      shell.querySelector("button").click();
      await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
      state.user = { user_id: "admin" };
      state.accessRequestSubmittingSpaceId = "new-session-request";
      pending.resolve({});
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(api).toHaveBeenCalledTimes(1);
      expect(setSpaceGovernanceNotice).not.toHaveBeenCalled();
      expect(state.accessRequestSubmittingSpaceId).toBe("new-session-request");
    }
  );

  it("clears the old request indicator when the same user changes spaces", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<button data-space-action="request-space-access" data-space-id="space">Request</button>');
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    shell.querySelector("button").click();
    state.activeSpace = { space_id: "other" };
    pending.resolve({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.accessRequestSubmittingSpaceId).toBe("");
    expect(setSpaceGovernanceNotice).not.toHaveBeenCalled();
  });

  it("serializes access requests and allows another after completion", async () => {
    const { state, api, shell } = harness('<button data-space-action="request-space-access" data-space-id="first">First</button><button data-space-action="request-space-access" data-space-id="second">Second</button>');
    const pending = deferred();
    api.mockReturnValueOnce(pending.promise).mockResolvedValue([]);
    const [first, second] = shell.querySelectorAll("button");
    first.click();
    first.click();
    second.click();
    expect(api).toHaveBeenCalledTimes(1);
    expect(state.accessRequestSubmittingSpaceId).toBe("first");
    pending.resolve({});
    await vi.waitFor(() => expect(state.accessRequestSubmittingSpaceId).toBe(""));
    second.click();
    await vi.waitFor(() => expect(api).toHaveBeenCalledWith("/spaces/second/access-requests", expect.objectContaining({ method: "POST" })));
  });

  it("completes an access request in the original session", async () => {
    const { api, shell, setSpaceGovernanceNotice } = harness('<button data-space-action="request-space-access" data-space-id="space">Request</button>');
    api.mockResolvedValueOnce({}).mockResolvedValue([]);
    shell.querySelector("button").click();
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.any(String), "success", expect.any(Number)));
  });

  it("switches into a newly created personal space in the original session", async () => {
    const { api, shell, switchActiveSpace, setSpaceGovernanceNotice } = harness('<form id="space-personal-create-form"></form>');
    api.mockResolvedValue({ space_id: "new-space", name: "New" });
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.any(String), "success", expect.any(Number)));
    expect(switchActiveSpace).toHaveBeenCalledWith("new-space");
  });

  it("finishes a global-admin grant in the original session", async () => {
    const { api, shell, setSpaceGovernanceNotice } = harness('<form id="space-platform-access-form"><input name="soeid" value="target"></form>');
    api.mockResolvedValueOnce({}).mockResolvedValueOnce([]);
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.any(String), "success", expect.any(Number)));
  });

  it("does not switch a replacement session into a space created by the prior session", async () => {
    const { state, api, shell, switchActiveSpace, setSpaceGovernanceNotice } = harness('<form id="space-personal-create-form"></form>');
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    state.user = { user_id: "admin" };
    pending.resolve({ space_id: "old-space", name: "Old" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.spaces).toEqual([]);
    expect(switchActiveSpace).not.toHaveBeenCalled();
    expect(setSpaceGovernanceNotice).not.toHaveBeenCalled();
  });

  it("does not refresh or notify a replacement session after a global-admin grant", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="space-platform-access-form"><input name="soeid" value="target"></form>');
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    state.user = { user_id: "admin" };
    pending.resolve({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api).toHaveBeenCalledTimes(1);
    expect(setSpaceGovernanceNotice).not.toHaveBeenCalled();
  });

  it.each([
    ["space creation", '<form id="create-form"><input name="name" value="New"></form>', "#create-form"],
    ["member addition", '<form id="member-form"><input name="space_id" value="space"><input name="soeid" value="target"></form>', "#member-form"],
  ])("completes %s in the original session", async (_name, markup, selector) => {
    const { api, shell, setSpaceGovernanceNotice } = harness(markup);
    api.mockResolvedValueOnce({ space_id: "space", name: "Space" }).mockResolvedValueOnce([]);
    shell.querySelector(selector).dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.any(String), "success", expect.any(Number)));
  });

  it.each([
    ["space creation", '<form id="create-form"><input name="name" value="New"></form>', "#create-form"],
    ["member addition", '<form id="member-form"><input name="space_id" value="space"><input name="soeid" value="target"></form>', "#member-form"],
  ])("ignores a delayed %s response after the session changes", async (_name, markup, selector) => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness(markup);
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    shell.querySelector(selector).dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    state.user = { user_id: "admin" };
    pending.resolve({ space_id: "space", name: "Space" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api).toHaveBeenCalledTimes(1);
    expect(setSpaceGovernanceNotice).not.toHaveBeenCalled();
  });

  it("prevents overlapping reset issuance and permits a later retry", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    const pending = deferred();
    api.mockReturnValueOnce(pending.promise).mockResolvedValueOnce({ temp_password: "second", expires_at: "later" });
    const submit = () => shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    submit();
    submit();
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("progress"), "error", expect.any(Number)));
    expect(api).toHaveBeenCalledTimes(1);
    pending.resolve({ temp_password: "first", expires_at: "later" });
    await vi.waitFor(() => expect(state.platformPasswordReset?.temp_password).toBe("first"));
    submit();
    await vi.waitFor(() => expect(state.platformPasswordReset?.temp_password).toBe("second"));
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("clears an older displayed password when a new issuance fails", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    state.platformPasswordReset = { temp_password: "obsolete" };
    api.mockRejectedValueOnce(new Error("network failure"));
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith("network failure", "error", expect.any(Number)));
    expect(state.platformPasswordReset).toBeNull();
  });

  it("does not let an older session release a newer reset in progress", async () => {
    const { state, api, shell, setSpaceGovernanceNotice } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    const old = deferred();
    const current = deferred();
    api.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const submit = () => shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    submit();
    state.user = { user_id: "admin" };
    submit();
    old.resolve({ temp_password: "old", expires_at: "later" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    submit();
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("progress"), "error", expect.any(Number)));
    expect(api).toHaveBeenCalledTimes(2);
    current.resolve({ temp_password: "new", expires_at: "later" });
    await vi.waitFor(() => expect(state.platformPasswordReset?.temp_password).toBe("new"));
  });

  it("does not issue a reset after confirmation changes the session", async () => {
    const { state, api, shell, showConfirmModal } = harness('<button data-space-action="issue-password-reset" data-soeid="target">Reset</button>');
    const pending = deferred();
    showConfirmModal.mockReturnValue(pending.promise);
    shell.querySelector("button").click();
    state.user = { user_id: "admin" };
    pending.resolve(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api).not.toHaveBeenCalled();
  });

  it("does not display a reset password returned to an earlier session", async () => {
    const { state, api, shell } = harness('<form id="space-password-reset-form"><input name="soeid" value="target"></form>');
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    state.user = { user_id: "admin" };
    pending.resolve({ temp_password: "old-secret", expires_at: "later" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.platformPasswordReset).toBeNull();
  });

  it("does not display an API token returned to an earlier session", async () => {
    const { state, api, shell } = harness('<form id="user-api-token-form"><input name="soeid" value="target"><input name="name" value="test"></form>');
    const pending = deferred();
    api.mockReturnValue(pending.promise);
    shell.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    state.user = { user_id: "admin" };
    pending.resolve({ token: "old-token", user_id: "target" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.issuedApiToken).toBeNull();
  });
});
