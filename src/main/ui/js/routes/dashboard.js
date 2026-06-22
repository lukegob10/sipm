import { createDashboardState, renderDashboardView } from "./dashboard/render.js";

const dashboardState = createDashboardState();

export function renderDashboard(ctx) {
  renderDashboardView(dashboardState, ctx);
}

export function render(ctx) {
  renderDashboard(ctx);
}
