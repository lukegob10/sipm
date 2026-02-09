export function renderSpaces(ctx) {
  const { renderSpaceAdminPanel, renderSpaceMembershipPanel } = ctx;
  if (typeof renderSpaceAdminPanel === "function") {
    renderSpaceAdminPanel();
  }
  if (typeof renderSpaceMembershipPanel === "function") {
    renderSpaceMembershipPanel();
  }
}
