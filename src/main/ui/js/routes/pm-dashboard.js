import { createPMDashboardState, renderPMDashboardView } from "./pm-dashboard/render.js";

const pmDashboardState = createPMDashboardState();

export function renderPMDashboard(ctx) {
  renderPMDashboardView(pmDashboardState, ctx);
}

export function render(ctx) {
  renderPMDashboard(ctx);
}
