import { createProgramDashboardState, renderProgramDashboardView } from "./program-dashboard/render.js?v=program-dashboard-columns-v3";

const programDashboardState = createProgramDashboardState();

export function renderProgramDashboard(ctx) {
  renderProgramDashboardView(programDashboardState, ctx);
}

export function render(ctx) {
  renderProgramDashboard(ctx);
}
