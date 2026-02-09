export function renderAccess(ctx) {
  const { renderGlobalAdminPanel } = ctx;
  if (typeof renderGlobalAdminPanel === "function") {
    renderGlobalAdminPanel();
  }
}
