import {
  currentMonthToken,
  normalizeMonthToken,
  normalizePMDashboardSection,
  persistActiveSection,
  persistCapacityMonth,
} from "./storage.js";

function resolvePMDashboardApiBase(ctx) {
  return String(ctx?.apiBase || window.SIPM_API_BASE || "/api").replace(/\/+$/, "");
}

async function downloadPMDashboardReport(pmDashboardState) {
  const ctx = pmDashboardState.ctx || {};
  const activeSpaceId = String(ctx?.state?.activeSpace?.space_id || "").trim();
  const headers = {};
  if (activeSpaceId) headers["X-Space-Id"] = activeSpaceId;
  const response = await fetch(`${resolvePMDashboardApiBase(ctx)}/pm-dashboard/report.pdf`, {
    method: "GET",
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const text = await response.text();
    let message = `Download failed (${response.status})`;
    try {
      const payload = text ? JSON.parse(text) : null;
      if (payload?.detail) message = String(payload.detail);
      else if (text) message = text;
    } catch {
      if (text) message = text;
    }
    throw new Error(message);
  }
  const contentType = String(response.headers.get("content-type") || "").toLowerCase();
  if (!contentType.includes("application/pdf")) {
    throw new Error("Download failed: server did not return a PDF.");
  }
  const blob = await response.blob();
  const today = new Date().toISOString().slice(0, 10);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `pm-command-center-report-${today}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}

async function handlePMDashboardClick(event, pmDashboardState) {
  const target = event.target;
  if (!(target instanceof Element)) return;
  const actionEl = target.closest("[data-pm-dashboard-action]");
  if (!actionEl) return;
  const action = actionEl.getAttribute("data-pm-dashboard-action") || "";

  if (action === "set-focus-section") return;

  if (action === "download-report") {
    event.preventDefault();
    event.stopPropagation();
    try {
      await downloadPMDashboardReport(pmDashboardState);
      pmDashboardState.ctx?.setStatus?.("PM Command Center report downloaded.", "success");
    } catch (err) {
      console.error("PM Command Center report download failed", err);
      pmDashboardState.ctx?.setStatus?.(err?.message || "PDF download failed", "danger");
    }
    return;
  }

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
    void handlePMDashboardClick(event, pmDashboardState);
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
