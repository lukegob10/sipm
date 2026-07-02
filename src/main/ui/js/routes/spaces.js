export function renderSpaces(ctx) {
  const { renderGovernanceHub } = ctx;
  if (typeof renderGovernanceHub === "function") {
    renderGovernanceHub();
  }
}

export function render(ctx) {
  renderSpaces(ctx);
}
