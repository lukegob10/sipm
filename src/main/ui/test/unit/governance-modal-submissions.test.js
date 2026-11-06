import { describe, expect, it, vi } from "vitest";
import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";

function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

function harness(kind) {
  document.body.innerHTML = `<div id="modal" class="modal hidden"><form id="form">${kind === "create"
    ? '<input name="name" value=""><input name="slug" value="">'
    : '<input name="space_id"><input name="soeid"><input name="role" value="member"><input name="status" value="active">'}</form><p id="status"></p></div>`;
  delete document._spaceGovernanceEscapeBound;
  const modal = document.getElementById("modal");
  const form = document.getElementById("form");
  const status = document.getElementById("status");
  const state = { authed: true, user: { user_id: "admin" }, activeSpace: { space_id: "space", name: "Space" },
    currentView: "spaces", spaceMembersLoadedBySpace: {}, spaceMembersBySpace: {} };
  const api = vi.fn();
  const notice = vi.fn();
  const formNotice = vi.fn();
  const refreshSpaceContext = vi.fn().mockResolvedValue();
  const els = kind === "create"
    ? { spaceCreateModal: modal, spaceCreateModalForm: form, spaceCreateStatus: status }
    : { spaceMemberModal: modal, spaceMemberModalForm: form, spaceMemberStatus: status };
  const controller = createSpaceGovernanceController({ state, els, api, activeSpaceId: () => state.activeSpace?.space_id,
    userIsGlobalAdmin: () => true, canManageSpaceMembership: () => true,
    effectiveDirectorySpaces: () => [state.activeSpace], spaceNameForId: () => "Space",
    clearDeliverableFormNotice: vi.fn(), setDeliverableFormNotice: formNotice,
    setSpaceGovernanceNotice: notice, refreshSpaceContext, renderGovernanceHub: vi.fn(), isSpaceGovernanceView: () => false });
  controller.bindSpaceAdminControls();
  const open = () => kind === "create" ? controller.openSpaceCreateModal() : controller.openSpaceMemberModal("space");
  const close = () => kind === "create" ? controller.closeSpaceCreateModal() : controller.closeSpaceMemberModal();
  const input = form.querySelector(kind === "create" ? '[name="name"]' : '[name="soeid"]');
  const submit = () => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  return { state, modal, form, input, api, notice, formNotice, refreshSpaceContext, open, close, submit };
}

describe.each(["create", "member"])("%s modal submission", (kind) => {
  it("prevents duplicate writes and preserves a reopened editor when the old write completes", async () => {
    const h = harness(kind);
    const pending = deferred();
    h.api.mockReturnValueOnce(pending.promise).mockResolvedValue([]);
    h.open(); h.input.value = "first"; h.submit(); h.submit();
    expect(h.api).toHaveBeenCalledTimes(1);
    h.close(); h.open(); h.input.value = "new draft";
    pending.resolve(kind === "create" ? { space_id: "new", name: "first" } : {});
    await vi.waitFor(() => expect(h.notice).toHaveBeenCalledWith(expect.stringMatching(/Created|Added/), "success", expect.any(Number)));
    expect(h.modal.classList.contains("hidden")).toBe(false);
    expect(h.input.value).toBe("new draft");
    if (kind === "create") expect(h.state.spaceAdminSection).not.toBe("space-directory");
  });

  it("preserves edits made while saving", async () => {
    const h = harness(kind);
    const pending = deferred();
    h.api.mockReturnValueOnce(pending.promise).mockResolvedValue([]);
    h.open(); h.input.value = "first"; h.submit(); h.input.value = "changed";
    pending.resolve(kind === "create" ? { space_id: "new", name: "first" } : {});
    await vi.waitFor(() => expect(h.formNotice).toHaveBeenCalledWith(expect.anything(), expect.stringContaining("Newer edits"), "success"));
    expect(h.modal.classList.contains("hidden")).toBe(false);
    expect(h.input.value).toBe("changed");
  });

  it("does not put an old failure into a reopened editor", async () => {
    const h = harness(kind);
    const pending = deferred();
    h.api.mockReturnValueOnce(pending.promise);
    h.open(); h.input.value = "first"; h.submit();
    h.close(); h.open(); h.input.value = "new draft";
    h.formNotice.mockClear();
    pending.reject(new Error("old failure"));
    await vi.waitFor(() => expect(h.api).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.formNotice).not.toHaveBeenCalled();
    expect(h.input.value).toBe("new draft");
  });

  it("does not let an old request block a replacement session", async () => {
    const h = harness(kind);
    const old = deferred();
    const current = deferred();
    h.api.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise).mockResolvedValue([]);
    h.open(); h.input.value = "first"; h.submit();
    h.state.user = { user_id: "admin" };
    h.close(); h.open(); h.input.value = "second"; h.submit();
    expect(h.api).toHaveBeenCalledTimes(2);
    old.resolve(kind === "create" ? { space_id: "old", name: "first" } : {});
    await new Promise((resolve) => setTimeout(resolve, 0));
    h.submit();
    expect(h.api).toHaveBeenCalledTimes(2);
    current.resolve(kind === "create" ? { space_id: "new", name: "second" } : {});
    await vi.waitFor(() => expect(h.modal.classList.contains("hidden")).toBe(true));
  });

  it("reports a committed write when the subsequent refresh fails", async () => {
    const h = harness(kind);
    h.api.mockResolvedValueOnce(kind === "create" ? { space_id: "new", name: "first" } : {})
      .mockRejectedValueOnce(new Error("offline"));
    if (kind === "create") h.refreshSpaceContext.mockRejectedValueOnce(new Error("offline"));
    h.open(); h.input.value = "first"; h.submit();
    await vi.waitFor(() => expect(h.notice).toHaveBeenCalledWith(expect.stringMatching(/created, but|added, but/i), "error", expect.any(Number)));
  });
});

it("does not redirect the governance view after a create refresh if the editor was reopened", async () => {
  const h = harness("create");
  const refresh = deferred();
  h.refreshSpaceContext.mockReturnValueOnce(refresh.promise);
  h.api.mockResolvedValueOnce({ space_id: "new", name: "first" });
  h.open(); h.input.value = "first"; h.submit();
  await vi.waitFor(() => expect(h.modal.classList.contains("hidden")).toBe(true));
  h.open(); h.input.value = "next draft";
  refresh.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(h.state.spaceAdminSection).not.toBe("space-directory");
  expect(h.modal.classList.contains("hidden")).toBe(false);
  expect(h.input.value).toBe("next draft");
});
