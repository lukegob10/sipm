import { createDashboardState, renderDashboardView } from "./dashboard/render.js?v=dashboard-snapshot-kpis-v4";

const dashboardState = createDashboardState();

export function renderDashboard(ctx) {
  renderDashboardView(dashboardState, ctx);
}

export function render(ctx) {
  renderDashboard(ctx);
}
