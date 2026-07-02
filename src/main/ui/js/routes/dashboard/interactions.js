import { DASHBOARD_SECTIONS, DEFAULT_PREFS, num } from "./common.js";
import { updatePrefs } from "./prefs.js";
import {
  applyModalConfig,
  closeDashboardConfigModal,
  ensureDashboardConfigModal,
  moveModalColumn,
  openDashboardConfigModal,
  renderDashboardConfigModal,
  resetModalDraft,
  setAllModalSolutionChecks,
} from "./modal.js";

function resetDashboardPages(dashboardState, sectionIds = DASHBOARD_SECTIONS) {
  dashboardState.pages = dashboardState.pages || {};
  sectionIds.forEach((sectionId) => {
    dashboardState.pages[sectionId] = 1;
  });
}

export function bindDashboardEvents(dashboardState, rerender) {
  const viewRoot = typeof document !== "undefined" ? document.getElementById("view-dashboard") : null;
  if (!viewRoot || dashboardState.bound) return;
  dashboardState.bound = true;

  viewRoot.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    if (target.id === "dashboard-main-scope") {
      updatePrefs(dashboardState, { scope: target.value || DEFAULT_PREFS.scope });
      resetDashboardPages(dashboardState);
      rerender();
      return;
    }

    if (target.id === "dashboard-main-sort") {
      updatePrefs(dashboardState, { sort: target.value || DEFAULT_PREFS.sort });
      resetDashboardPages(dashboardState, ["main"]);
      rerender();
      return;
    }

    if (target.id === "dashboard-main-rows") {
      updatePrefs(dashboardState, { rows: num(target.value, DEFAULT_PREFS.rows) });
      resetDashboardPages(dashboardState, ["main"]);
      rerender();
      return;
    }

    if (target.id === "dashboard-main-horizon") {
      updatePrefs(dashboardState, { horizon_days: num(target.value, DEFAULT_PREFS.horizon_days) });
      resetDashboardPages(dashboardState, ["completed"]);
      rerender();
    }
  });

  viewRoot.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-dashboard-action") || "";

    if (action === "reset-view") {
      updatePrefs(dashboardState, {
        scope: DEFAULT_PREFS.scope,
        sort: DEFAULT_PREFS.sort,
        rows: DEFAULT_PREFS.rows,
        horizon_days: DEFAULT_PREFS.horizon_days,
      });
      resetDashboardPages(dashboardState);
      rerender();
      return;
    }

    if (action === "page") {
      event.preventDefault();
      const sectionId = String(actionEl.getAttribute("data-dashboard-section") || "");
      const direction = String(actionEl.getAttribute("data-dashboard-page-direction") || "");
      if (!DASHBOARD_SECTIONS.includes(sectionId)) return;
      dashboardState.pages = dashboardState.pages || {};
      const currentPage = Math.max(1, num(dashboardState.pages[sectionId], 1));
      dashboardState.pages[sectionId] = Math.max(1, currentPage + (direction === "next" ? 1 : -1));
      rerender();
      return;
    }

    if (action === "open-solution") {
      event.preventDefault();
      const solutionId = String(actionEl.getAttribute("data-solution-id") || "");
      if (typeof dashboardState.ctx?.openDashboardSolutionDrilldown === "function") {
        dashboardState.ctx.openDashboardSolutionDrilldown(solutionId);
      }
      return;
    }

    if (action === "open-project") {
      event.preventDefault();
      const projectId = String(actionEl.getAttribute("data-project-id") || "");
      if (typeof dashboardState.ctx?.openDashboardProjectDrilldown === "function") {
        dashboardState.ctx.openDashboardProjectDrilldown(projectId);
      }
      return;
    }

    if (action === "open-config") {
      event.preventDefault();
      const sectionId = String(
        actionEl.getAttribute("data-dashboard-section")
        || dashboardState.prefs?.last_config_section
        || dashboardState.lastConfigSection
        || "main"
      );
      openDashboardConfigModal(dashboardState, sectionId);
      renderDashboardConfigModal(dashboardState, sectionId, {
        columnDefsBySection: dashboardState.columnDefsBySection || {},
      });
      const activeTab = ensureDashboardConfigModal()?.querySelector(".dashboard-config-section-tabs .tab.active");
      if (activeTab instanceof HTMLElement) activeTab.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-dashboard-action") || "";

    if (action === "close-config") {
      closeDashboardConfigModal(dashboardState);
      return;
    }
    if (action === "select-all-solutions") {
      setAllModalSolutionChecks(true);
      return;
    }
    if (action === "clear-solutions") {
      setAllModalSolutionChecks(false);
      return;
    }
    if (action === "switch-config-section") {
      event.preventDefault();
      const sectionId = String(actionEl.getAttribute("data-dashboard-section") || "");
      if (!DASHBOARD_SECTIONS.includes(sectionId)) return;
      dashboardState.modalSection = sectionId;
      dashboardState.lastConfigSection = sectionId;
      updatePrefs(dashboardState, { last_config_section: sectionId });
      renderDashboardConfigModal(dashboardState, sectionId, {
        columnDefsBySection: dashboardState.columnDefsBySection || {},
      });
      return;
    }
    if (action === "move-column-up") {
      moveModalColumn("up", String(actionEl.getAttribute("data-column-id") || ""));
      return;
    }
    if (action === "move-column-down") {
      moveModalColumn("down", String(actionEl.getAttribute("data-column-id") || ""));
      return;
    }
    if (action === "reset-table-config") {
      resetModalDraft(dashboardState, dashboardState.columnDefsBySection || {});
      return;
    }
    if (action === "apply-table-config") {
      applyModalConfig(dashboardState, rerender);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!dashboardState.modalSection) return;
    closeDashboardConfigModal(dashboardState);
  });
}
