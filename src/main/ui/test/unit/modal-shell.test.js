import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createModalShellController } from "../../js/shell/modal-shell.js";

function buildHarness() {
  document.body.innerHTML = `
    <button id="open-confirm">Open</button>
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
});
