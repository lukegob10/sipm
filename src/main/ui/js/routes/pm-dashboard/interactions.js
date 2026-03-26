import { currentMonthToken, normalizeMonthToken, persistCapacityMonth } from "./storage.js";

export function bindPMDashboardEvents(pmDashboardState, rerender) {
  const viewRoot = typeof document !== "undefined" ? document.getElementById("view-pm-dashboard") : null;
  if (!viewRoot || pmDashboardState.bound) return;
  pmDashboardState.bound = true;

  viewRoot.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-pm-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-pm-dashboard-action") || "";

    if (action === "open-project") {
      event.preventDefault();
      const projectId = String(actionEl.getAttribute("data-project-id") || "");
      if (typeof pmDashboardState.ctx?.openPMDashboardProjectDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardProjectDrilldown(projectId);
      }
      return;
    }

    if (action === "open-solution") {
      event.preventDefault();
      const solutionId = String(actionEl.getAttribute("data-solution-id") || "");
      if (typeof pmDashboardState.ctx?.openPMDashboardSolutionDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardSolutionDrilldown(solutionId);
      }
      return;
    }

    if (action === "open-capacity-allocations") {
      event.preventDefault();
      const assigneeKey = String(actionEl.getAttribute("data-assignee-key") || "");
      const detail = pmDashboardState.capacityDrilldowns.get(assigneeKey);
      if (!detail) return;
      if (typeof pmDashboardState.ctx?.openPMDashboardCapacityDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardCapacityDrilldown({
          key: detail.key,
          label: detail.label,
          allocated: detail.allocated,
          capacity: detail.capacity,
          utilization: detail.utilization,
          scopeLabel: pmDashboardState.capacityScopeLabel,
          allocations: detail.allocations,
        });
      }
      return;
    }

    if (action === "open-subcomponent") {
      event.preventDefault();
      const subcomponentId = String(actionEl.getAttribute("data-subcomponent-id") || "");
      if (typeof pmDashboardState.ctx?.openPMDashboardSubcomponentDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardSubcomponentDrilldown(subcomponentId);
      }
    }
  });

  viewRoot.addEventListener("change", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-pm-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-pm-dashboard-action") || "";
    if (action !== "set-capacity-month") return;
    const nextMonth = normalizeMonthToken(event.target.value) || currentMonthToken();
    pmDashboardState.capacityMonth = nextMonth;
    persistCapacityMonth(pmDashboardState.capacitySpaceId, nextMonth);
    rerender();
  });
}
