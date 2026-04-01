export function createModalShellController({ els, onPlanningModalAction }) {
  let pendingConfirmResolve = null;
  let confirmReturnFocusEl = null;

  function closePlanningModal() {
    if (els.planningModal) {
      els.planningModal.classList.add("hidden");
    }
    if (els.planningModalBody) {
      els.planningModalBody.innerHTML = "";
    }
  }

  function openPlanningModal(title, bodyHtml) {
    if (els.planningModalTitle) {
      els.planningModalTitle.textContent = title || "Details";
    }
    if (els.planningModalBody) {
      els.planningModalBody.innerHTML = bodyHtml || "";
    }
    els.planningModal?.classList.remove("hidden");
  }

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

  function bindPlanningModal() {
    if (els.planningModal && !els.planningModal._bound) {
      els.planningModal.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) return;
        const actionEl = event.target.closest("[data-planning-modal-action]");
        if (actionEl) {
          const action = actionEl.getAttribute("data-planning-modal-action") || "";
          const allocationId = actionEl.getAttribute("data-allocation-id") || "";
          if (typeof onPlanningModalAction === "function") {
            onPlanningModalAction(action, { allocationId, actionEl, event });
          }
          return;
        }
        if (event.target === els.planningModal || event.target.classList.contains("modal-backdrop")) {
          closePlanningModal();
        }
      });
      els.planningModal._bound = true;
    }
    if (els.planningModalClose && !els.planningModalClose._bound) {
      els.planningModalClose.addEventListener("click", closePlanningModal);
      els.planningModalClose._bound = true;
    }
  }

  return {
    bindConfirmModal,
    bindPlanningModal,
    closeConfirmModal,
    closePlanningModal,
    openPlanningModal,
    showConfirmModal,
  };
}
