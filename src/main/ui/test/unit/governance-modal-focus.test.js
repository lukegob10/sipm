import { describe, expect, it, vi } from "vitest";
import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";

function harness() {
  document.body.innerHTML = `
    <button id="opener">Open</button><button id="elsewhere">Elsewhere</button>
    <div id="create" class="modal hidden"><form><input name="name"></form></div>
    <div id="member" class="modal hidden"><form><input name="space_id"><input name="soeid"></form></div>
    <div id="space-directory-modal" class="modal hidden"><button>Close</button><button data-space-action="open-member-modal" data-space-id="s">Add</button></div>`;
  const state = { authed: true, currentView: "spaces", user: { user_id: "u" }, activeSpace: { space_id: "s" } };
  const els = {
    spaceCreateModal: document.querySelector("#create"),
    spaceCreateModalForm: document.querySelector("#create form"),
    spaceMemberModal: document.querySelector("#member"),
    spaceMemberModalForm: document.querySelector("#member form"),
    spaceDirectoryModal: document.querySelector("#space-directory-modal"),
    spaceDirectoryModalClose: document.querySelector("#space-directory-modal button"),
  };
  const opener = document.querySelector("#opener");
  opener.getClientRects = () => [{ width: 10, height: 10 }];
  const controller = createSpaceGovernanceController({
    state, els, activeSpaceId: () => "s", userIsGlobalAdmin: () => true,
    canManageSpaceMembership: () => true, effectiveDirectorySpaces: () => [{ space_id: "s", space_kind: "shared" }],
    clearDeliverableFormNotice: vi.fn(), renderSpaceDirectoryModal: vi.fn(),
  });
  return { state, els, opener, controller, elsewhere: document.querySelector("#elsewhere") };
}

describe("governance dialog focus", () => {
  it.each([
    ["Create", "spaceCreateModalForm", "name"],
    ["Member", "spaceMemberModalForm", "soeid"],
    ["Directory", "spaceDirectoryModal", null],
  ])("focuses %s immediately and restores its opener", (kind, field, name) => {
    const { controller, opener, els } = harness();
    opener.focus();
    controller[`openSpace${kind}Modal`]("s");
    expect(document.activeElement).toBe(name ? els[field].querySelector(`[name="${name}"]`) : els.spaceDirectoryModalClose);
    controller[`closeSpace${kind}Modal`]();
    expect(document.activeElement).toBe(opener);
  });

  it("returns to the directory launcher after moving to the member dialog", () => {
    const { controller, opener, els } = harness();
    controller.bindSpaceAdminControls();
    opener.focus(); controller.openSpaceDirectoryModal("s");
    els.spaceDirectoryModal.querySelector('[data-space-action="open-member-modal"]').click();
    expect(els.spaceDirectoryModal.classList.contains("hidden")).toBe(true);
    expect(document.activeElement).toBe(els.spaceMemberModalForm.querySelector('[name="soeid"]'));
    controller.closeSpaceMemberModal();
    expect(document.activeElement).toBe(opener);
  });

  it("does not restore focus after a session change or forced close", () => {
    const { state, controller, opener, elsewhere } = harness();
    opener.focus(); controller.openSpaceCreateModal();
    state.user = { user_id: "u" };
    elsewhere.focus(); controller.closeSpaceCreateModal();
    expect(document.activeElement).toBe(elsewhere);
    opener.focus(); controller.openSpaceCreateModal(); elsewhere.focus();
    controller.closeSpaceCreateModal({ restoreFocus: false });
    expect(document.activeElement).toBe(elsewhere);
  });
});
