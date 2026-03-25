export function renderSpaces(ctx) {
  const { renderGovernanceHub } = ctx;
  if (typeof renderGovernanceHub === "function") {
    renderGovernanceHub("current-space");
  }
}

export function render(ctx) {
  renderSpaces(ctx);
}
