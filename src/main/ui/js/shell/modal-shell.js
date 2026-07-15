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
    if (pendingConfirmResolve) {
      const staleResolver = pendingConfirmResolve;
      pendingConfirmResolve = null;
      staleResolver(false);
    }
    confirmReturnFocusEl = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    els.confirmModalTitle.textContent = title;
    els.confirmModalMessage.textContent = message;
    els.confirmModalConfirm.textContent = confirmLabel;
    els.confirmModalCancel.textContent = cancelLabel;
    els.confirmModal.classList.remove("hidden");
    window.setTimeout(() => {
      els.confirmModalConfirm?.focus();
    }, 0);
    return new Promise((resolve) => {
      pendingConfirmResolve = resolve;
    });
  }

  function bindConfirmModal() {
    if (!els.confirmModal || els.confirmModal._bound) return;
    const cancel = () => closeConfirmModal(false);
    const approve = () => closeConfirmModal(true);
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
