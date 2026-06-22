import { createProgramDashboardState, renderProgramDashboardView } from "./program-dashboard/render.js?v=program-dashboard-escalation-grid-v1";

const programDashboardState = createProgramDashboardState();

export function renderProgramDashboard(ctx) {
  renderProgramDashboardView(programDashboardState, ctx);
}

export function render(ctx) {
  renderProgramDashboard(ctx);
}
