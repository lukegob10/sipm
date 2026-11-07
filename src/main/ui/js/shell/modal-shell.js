function bindModalTabContainment() {
  if (document._modalTabContainmentBound) return;
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || event.defaultPrevented) return;
    // The backdrop covers the viewport; hit-testing respects stacking contexts
    // and also finds dialogs inserted dynamically after the shell was bound.
    const modal = document.elementFromPoint?.(window.innerWidth / 2, window.innerHeight / 2)?.closest(".modal");
    if (!modal || modal.id === "confirm-modal" || modal.id === "idle-modal") return;
    const candidates = [...modal.querySelectorAll("a[href], button, input, select, textarea, [tabindex], [contenteditable='true']")]
      .filter((element) => element.tabIndex >= 0 && !element.matches(":disabled")
        && !element.closest("[inert], [aria-hidden='true']")
        && element.getClientRects().length && getComputedStyle(element).visibility === "visible");
    // Native Tab visits only the checked radio in a named group (or its first
    // eligible member), not every radio in that group.
    const tabbable = candidates.filter((element) => {
      if (element.tagName !== "INPUT" || element.type !== "radio" || !element.name) return true;
      const group = candidates.filter((other) => other.tagName === "INPUT" && other.type === "radio"
        && other.name === element.name && other.form === element.form);
      return element === (group.find((other) => other.checked) || group[0]);
    }).sort((a, b) => (a.tabIndex || Infinity) - (b.tabIndex || Infinity));
    if (!tabbable.length) {
      event.preventDefault();
      if (!modal.hasAttribute("tabindex")) modal.tabIndex = -1;
      modal.focus();
      return;
    }
    const focused = tabbable.indexOf(document.activeElement);
    if (focused === -1 || (event.shiftKey && focused === 0) || (!event.shiftKey && focused === tabbable.length - 1)) {
      event.preventDefault();
      tabbable[event.shiftKey ? tabbable.length - 1 : 0].focus();
    }
  });
  document._modalTabContainmentBound = true;
}

export function createModalShellController({ els }) {
  let pendingConfirmResolve = null;
  let confirmReturnFocusEl = null;

  function closeConfirmModal(result = false) {
    const resolver = pendingConfirmResolve;
    pendingConfirmResolve = null;
    if (els.confirmModal) {
      els.confirmModal.classList.add("hidden");
    }
    if (confirmReturnFocusEl && typeof confirmReturnFocusEl.focus === "function") {
      confirmReturnFocusEl.focus();
    }
    confirmReturnFocusEl = null;
    if (resolver) {
      resolver(result);
    }
  }

  function showConfirmModal(options = {}) {
    const title = String(options.title || "Confirm Action");
    const message = String(options.message || "Are you sure you want to continue?");
    const confirmLabel = String(options.confirmLabel || "Confirm");
    const cancelLabel = String(options.cancelLabel || "Cancel");
    if (
      !els.confirmModal
      || !els.confirmModalTitle
      || !els.confirmModalMessage
      || !els.confirmModalConfirm
      || !els.confirmModalCancel
    ) {
      console.warn("Confirm modal shell missing; canceling action.");
      return Promise.resolve(false);
    }
    const replacingPendingConfirmation = !!pendingConfirmResolve;
    if (replacingPendingConfirmation) {
      const staleResolver = pendingConfirmResolve;
      pendingConfirmResolve = null;
      staleResolver(false);
    }
    if (!replacingPendingConfirmation) {
      confirmReturnFocusEl = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    }
    els.confirmModalTitle.textContent = title;
    els.confirmModalMessage.textContent = message;
    els.confirmModalConfirm.textContent = confirmLabel;
    els.confirmModalCancel.textContent = cancelLabel;
    els.confirmModal.classList.remove("hidden");
    window.setTimeout(() => {
      if (!pendingConfirmResolve || els.confirmModal?.classList.contains("hidden")
          || (els.idleModal && !els.idleModal.classList.contains("hidden"))) return;
      els.confirmModalConfirm?.focus();
    }, 0);
    return new Promise((resolve) => {
      pendingConfirmResolve = resolve;
    });
  }

  function bindConfirmModal() {
    if (!els.confirmModal || els.confirmModal._bound) return;
    bindModalTabContainment();
    const cancel = () => closeConfirmModal(false);
    const approve = () => closeConfirmModal(true);
    // A confirmation can sit above another dialog with its own document-level
    // Escape handler. Consume the key before those handlers see it.
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || !pendingConfirmResolve || els.confirmModal.classList.contains("hidden")
          || (els.idleModal && !els.idleModal.classList.contains("hidden"))) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      cancel();
    }, true);
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Tab" || !pendingConfirmResolve || els.confirmModal.classList.contains("hidden")
          || (els.idleModal && !els.idleModal.classList.contains("hidden"))) return;
      const buttons = [els.confirmModalClose, els.confirmModalCancel, els.confirmModalConfirm]
        .filter((button) => button && !button.disabled && !button.hidden);
      if (!buttons.length) {
        event.preventDefault();
        return;
      }
      const focused = buttons.indexOf(document.activeElement);
      if (focused === -1 || (event.shiftKey && focused === 0) || (!event.shiftKey && focused === buttons.length - 1)) {
        event.preventDefault();
        buttons[event.shiftKey ? buttons.length - 1 : 0].focus();
      }
    });
    els.confirmModalClose?.addEventListener("click", cancel);
    els.confirmModalCancel?.addEventListener("click", cancel);
    els.confirmModalConfirm?.addEventListener("click", approve);
    els.confirmModal.querySelector(".modal-backdrop")?.addEventListener("click", cancel);
    els.confirmModal._bound = true;
  }

  return {
    bindConfirmModal,
    closeConfirmModal,
    showConfirmModal,
  };
}
