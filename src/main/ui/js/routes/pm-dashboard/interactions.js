import {
  currentMonthToken,
  normalizeMonthToken,
  normalizePMDashboardSection,
  persistActiveSection,
  persistCapacityMonth,
} from "./storage.js";

function handlePMDashboardClick(event, pmDashboardState, rerender) {
  const target = event.target;
  if (!(target instanceof Element)) return;
  const actionEl = target.closest("[data-pm-dashboard-action]");
  if (!actionEl) return;
  const action = actionEl.getAttribute("data-pm-dashboard-action") || "";

  if (action === "set-focus-section") return;

  if (action === "open-project") {
    event.preventDefault();
    event.stopPropagation();
    const projectId = String(actionEl.getAttribute("data-project-id") || "");
    if (typeof pmDashboardState.ctx?.openPMDashboardProjectDrilldown === "function") {
      pmDashboardState.ctx.openPMDashboardProjectDrilldown(projectId);
    }
    return;
  }

  if (action === "open-solution") {
    event.preventDefault();
    event.stopPropagation();
    const solutionId = String(actionEl.getAttribute("data-solution-id") || "");
    if (typeof pmDashboardState.ctx?.openPMDashboardSolutionDrilldown === "function") {
      pmDashboardState.ctx.openPMDashboardSolutionDrilldown(solutionId);
    }
    return;
  }

  if (action === "open-capacity-allocations") {
    event.preventDefault();
    event.stopPropagation();
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

  if (action === "open-task") {
    event.preventDefault();
    event.stopPropagation();
    const taskId = String(actionEl.getAttribute("data-task-id") || "");
    if (typeof pmDashboardState.ctx?.openPMDashboardTaskDrilldown === "function") {
      pmDashboardState.ctx.openPMDashboardTaskDrilldown(taskId);
    }
  }
}

export function bindPMDashboardEvents(pmDashboardState, rerender) {
  const viewRoot = typeof document !== "undefined" ? document.getElementById("view-pm-dashboard") : null;
  if (!viewRoot || pmDashboardState.bound) return;
  pmDashboardState.bound = true;

  viewRoot.addEventListener("click", (event) => {
    handlePMDashboardClick(event, pmDashboardState, rerender);
  }, { capture: true });

  viewRoot.addEventListener("change", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-pm-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-pm-dashboard-action") || "";
    if (action === "set-focus-section") {
      const sectionId = normalizePMDashboardSection(actionEl.getAttribute("data-pm-dashboard-section"));
      pmDashboardState.activeSection = sectionId;
      persistActiveSection(sectionId);
      rerender();
      return;
    }
    if (action !== "set-capacity-month") return;
    const nextMonth = normalizeMonthToken(event.target.value) || currentMonthToken();
    pmDashboardState.capacityMonth = nextMonth;
    persistCapacityMonth(pmDashboardState.capacitySpaceId, nextMonth);
    rerender();
  });
}
