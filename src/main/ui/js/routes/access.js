export function renderAccess(ctx) {
  const { renderGovernanceHub } = ctx;
  if (typeof renderGovernanceHub === "function") {
    renderGovernanceHub("platform-access");
  }
}

export function render(ctx) {
  renderAccess(ctx);
}
