import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createModalShellController } from "../../js/shell/modal-shell.js";

function buildHarness() {
  document.body.innerHTML = `
    <button id="open-confirm">Open</button>
    <div id="idle-modal" class="hidden"><button id="idle-stay">Stay</button></div>
    <div id="confirm-modal" class="hidden">
      <button id="confirm-modal-close"></button>
      <h2 id="confirm-modal-title"></h2>
      <p id="confirm-modal-message"></p>
      <button id="confirm-modal-cancel"></button>
      <button id="confirm-modal-confirm"></button>
    </div>
  `;
  const els = {
    confirmModal: document.getElementById("confirm-modal"),
    confirmModalTitle: document.getElementById("confirm-modal-title"),
    confirmModalMessage: document.getElementById("confirm-modal-message"),
    confirmModalConfirm: document.getElementById("confirm-modal-confirm"),
    confirmModalCancel: document.getElementById("confirm-modal-cancel"),
    confirmModalClose: document.getElementById("confirm-modal-close"),
    idleModal: document.getElementById("idle-modal"),
  };
  const controller = createModalShellController({ els });
  controller.bindConfirmModal();
  return { controller, els, opener: document.getElementById("open-confirm") };
}

describe("modal shell controller", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not focus the hidden confirm button after an immediate close", async () => {
    const { controller, els, opener } = buildHarness();
    opener.focus();

    const result = controller.showConfirmModal();
    controller.closeConfirmModal(false);
    await expect(result).resolves.toBe(false);
    vi.runAllTimers();

    expect(els.confirmModal.classList.contains("hidden")).toBe(true);
    expect(document.activeElement).toBe(opener);
  });

  it("preserves the original focus target when replacing a pending confirmation", async () => {
    const { controller, els, opener } = buildHarness();
    opener.focus();

    const first = controller.showConfirmModal({ title: "First" });
    vi.runOnlyPendingTimers();
    expect(document.activeElement).toBe(els.confirmModalConfirm);

    const second = controller.showConfirmModal({ title: "Second" });
    await expect(first).resolves.toBe(false);
    controller.closeConfirmModal(false);
    await expect(second).resolves.toBe(false);

    expect(document.activeElement).toBe(opener);
  });

  it("keeps keyboard focus in the active confirmation and restores the opener", async () => {
    const { controller, els, opener } = buildHarness();
    opener.focus();
    const result = controller.showConfirmModal();
    vi.runOnlyPendingTimers();

    const tab = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    document.dispatchEvent(tab);
    expect(tab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(els.confirmModalClose);

    const reverseTab = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(reverseTab);
    expect(reverseTab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(els.confirmModalConfirm);

    els.confirmModalCancel.click();
    await expect(result).resolves.toBe(false);
    expect(document.activeElement).toBe(opener);
  });

  it("keeps containment active when a confirmation is replaced", async () => {
    const { controller, els, opener } = buildHarness();
    opener.focus();
    const first = controller.showConfirmModal();
    vi.runOnlyPendingTimers();
    const second = controller.showConfirmModal();
    await expect(first).resolves.toBe(false);
    vi.runOnlyPendingTimers();

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(els.confirmModalClose);
    els.confirmModalCancel.click();
    await expect(second).resolves.toBe(false);
    expect(document.activeElement).toBe(opener);
  });

  it("cancels only the confirmation when Escape also reaches underlying dialog handlers", async () => {
    const underlying = vi.fn();
    document.addEventListener("keydown", underlying);
    const { controller, els, opener } = buildHarness();
    opener.focus();
    const result = controller.showConfirmModal();
    vi.runOnlyPendingTimers();

    const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    els.confirmModalConfirm.dispatchEvent(escape);
    expect(escape.defaultPrevented).toBe(true);
    expect(underlying).not.toHaveBeenCalled();
    await expect(result).resolves.toBe(false);
    expect(document.activeElement).toBe(opener);
    document.removeEventListener("keydown", underlying);
  });

  it("leaves keyboard handling to an idle warning above the confirmation", async () => {
    const { controller, els } = buildHarness();
    const result = controller.showConfirmModal();
    els.idleModal.classList.remove("hidden");
    const stay = document.getElementById("idle-stay");
    stay.focus();
    vi.runOnlyPendingTimers();
    expect(document.activeElement).toBe(stay);
    const tab = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    stay.dispatchEvent(tab);
    expect(tab.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(stay);
    const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    stay.dispatchEvent(escape);
    expect(escape.defaultPrevented).toBe(false);
    expect(els.confirmModal.classList.contains("hidden")).toBe(false);
    controller.closeConfirmModal(false);
    await expect(result).resolves.toBe(false);
  });

  it("contains Tab in the visually topmost dynamic modal and ignores hidden or disabled controls", () => {
    buildHarness();
    document.body.insertAdjacentHTML("beforeend", `<div class="modal" id="dynamic-modal">
      <button id="first">First</button><button id="disabled" disabled>Disabled</button>
      <div aria-hidden="true"><button id="hidden">Hidden</button></div><button id="last">Last</button>
    </div>`);
    const modal = document.getElementById("dynamic-modal");
    modal.querySelectorAll("button").forEach((button) => vi.spyOn(button, "getClientRects").mockReturnValue([{}]));
    document.elementFromPoint = vi.fn(() => document.getElementById("last"));
    document.getElementById("last").focus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    expect(document.activeElement.id).toBe("first");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement.id).toBe("last");
    delete document.elementFromPoint;
  });

  it("uses the checked radio as its group's tab stop and handles an empty dialog", () => {
    buildHarness();
    document.body.insertAdjacentHTML("beforeend", `<div class="modal" id="dynamic-modal">
      <input type="radio" name="choice"><input id="checked" type="radio" name="choice" checked>
    </div>`);
    const modal = document.getElementById("dynamic-modal");
    modal.querySelectorAll("input").forEach((input) => vi.spyOn(input, "getClientRects").mockReturnValue([{}]));
    document.elementFromPoint = vi.fn(() => modal);
    document.getElementById("checked").focus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    expect(document.activeElement.id).toBe("checked");
    modal.replaceChildren();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(modal);
    delete document.elementFromPoint;
  });
});
