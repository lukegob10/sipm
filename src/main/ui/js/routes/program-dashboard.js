import { createProgramDashboardState, renderProgramDashboardView } from "./program-dashboard/render.js?v=program-dashboard-grid-v2";

const programDashboardState = createProgramDashboardState();

export function renderProgramDashboard(ctx) {
  renderProgramDashboardView(programDashboardState, ctx);
}

export function render(ctx) {
  renderProgramDashboard(ctx);
}
