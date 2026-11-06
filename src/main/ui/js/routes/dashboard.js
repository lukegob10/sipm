import { createDashboardState, renderDashboardView } from "./dashboard/render.js";
import { resetDashboardConfigForContext } from "./dashboard/modal.js";

const dashboardState = createDashboardState();

export function resetDashboardForContext() {
  resetDashboardConfigForContext(dashboardState);
}

export function renderDashboard(ctx) {
  renderDashboardView(dashboardState, ctx);
}

export function render(ctx) {
  renderDashboard(ctx);
}
