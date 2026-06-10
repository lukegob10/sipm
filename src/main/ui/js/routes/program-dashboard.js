import { createProgramDashboardState, renderProgramDashboardView } from "./program-dashboard/render.js";

const programDashboardState = createProgramDashboardState();

export function renderProgramDashboard(ctx) {
  renderProgramDashboardView(programDashboardState, ctx);
}

export function render(ctx) {
  renderProgramDashboard(ctx);
}
