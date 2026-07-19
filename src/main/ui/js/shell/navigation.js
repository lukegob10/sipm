const COMPACT_SHELL_QUERY = "(max-width: 900px)";

export function createShellNavigationController({ els, windowRef = window, documentRef = document }) {
  let bound = false;

  function isCompactShell() {
    return windowRef.matchMedia?.(COMPACT_SHELL_QUERY).matches ?? false;
  }

  function setNavigationOpen(open, { restoreFocus = false } = {}) {
    const nextOpen = Boolean(open && isCompactShell());
    els.appShell?.classList.toggle("nav-open", nextOpen);
    els.shellNavToggle?.setAttribute("aria-expanded", nextOpen ? "true" : "false");
    els.shellNavToggle?.setAttribute("aria-label", nextOpen ? "Close navigation" : "Open navigation");
    els.shellNavBackdrop?.classList.toggle("hidden", !nextOpen);
    if (!nextOpen && restoreFocus) els.shellNavToggle?.focus();
  }

  function setAccountMenuOpen(open, { restoreFocus = false } = {}) {
    const nextOpen = Boolean(open && isCompactShell());
    els.accountMenuShell?.classList.toggle("is-open", nextOpen);
    els.accountMenuToggle?.setAttribute("aria-expanded", nextOpen ? "true" : "false");
    if (!nextOpen && restoreFocus) els.accountMenuToggle?.focus();
  }

  function closeTransientShellUi() {
    setNavigationOpen(false);
    setAccountMenuOpen(false);
  }

  function bind() {
    if (bound) return;
    bound = true;

    els.shellNavToggle?.addEventListener("click", () => {
      const isOpen = els.appShell?.classList.contains("nav-open");
      setAccountMenuOpen(false);
      setNavigationOpen(!isOpen);
    });
    els.shellNavBackdrop?.addEventListener("click", () => setNavigationOpen(false, { restoreFocus: true }));
    els.navButtons?.forEach((button) => button.addEventListener("click", () => setNavigationOpen(false)));

    els.accountMenuToggle?.addEventListener("click", () => {
      const isOpen = els.accountMenuShell?.classList.contains("is-open");
      setNavigationOpen(false);
      setAccountMenuOpen(!isOpen);
    });
    els.accountMenuPanel?.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest("button")) setAccountMenuOpen(false);
    });

    documentRef.addEventListener("click", (event) => {
      if (!els.accountMenuShell?.classList.contains("is-open")) return;
      if (event.target instanceof Node && els.accountMenuShell.contains(event.target)) return;
      setAccountMenuOpen(false);
    });
    documentRef.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (els.accountMenuShell?.classList.contains("is-open")) {
        setAccountMenuOpen(false, { restoreFocus: true });
        return;
      }
      if (els.appShell?.classList.contains("nav-open")) {
        setNavigationOpen(false, { restoreFocus: true });
      }
    });
    windowRef.addEventListener("resize", () => {
      if (!isCompactShell()) closeTransientShellUi();
    });
  }

  return {
    bind,
    closeTransientShellUi,
    setNavigationOpen,
    setAccountMenuOpen,
  };
}
