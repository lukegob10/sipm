import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let createDashboardState, renderDashboardView;
let listeners;

describe("dashboard customization drafts", () => {
  beforeEach(async () => {
    vi.resetModules(); localStorage.clear();
    listeners = [];
    const addListener = document.addEventListener.bind(document);
    vi.spyOn(document, "addEventListener").mockImplementation((type, listener, options) => {
      listeners.push([type, listener, options]);
      addListener(type, listener, options);
    });
    document.body.innerHTML = '<div id="view-dashboard"><div id="top"></div></div>';
    ({ createDashboardState, renderDashboardView } = await import("../../js/routes/dashboard/render.js"));
  });
  afterEach(() => {
    listeners.forEach(([type, listener, options]) => document.removeEventListener(type, listener, options));
    vi.restoreAllMocks();
    document.body.innerHTML = ""; localStorage.clear();
  });

  it("preserves drafts during refresh and across tabs, then applies all edited sections", () => {
    const dashboard = createDashboardState();
    const state = { activeSpace: { space_id: "a" }, user: {}, projects: [{ project_id: "p", project_name: "Project" }], solutions: [{ solution_id: "s", solution_name: "Solution", project_id: "p", status: "active" }], tasks: [], users: [] };
    const ctx = { state, els: { dashboardTopProjects: document.getElementById("top") } };
    renderDashboardView(dashboard, ctx);
    document.querySelector('[data-dashboard-action="open-config"]').click();
    const modal = document.getElementById("dashboard-config-modal");
    const mainRisk = modal.querySelector('input[name="dashboard-config-column"][value="risk"]');
    mainRisk.checked = true;
    renderDashboardView(dashboard, ctx);
    expect(modal.querySelector('input[name="dashboard-config-column"][value="risk"]').checked).toBe(true);
    modal.querySelector('[data-dashboard-action="switch-config-section"][data-dashboard-section="completed"]').click();
    expect(document.activeElement.dataset.dashboardSection).toBe("completed");
    modal.querySelector('input[name="dashboard-config-column"][value="owner"]').checked = true;
    modal.querySelector('[data-dashboard-action="switch-config-section"][data-dashboard-section="main"]').click();
    expect(modal.querySelector('input[name="dashboard-config-column"][value="risk"]').checked).toBe(true);
    modal.querySelector('[data-dashboard-action="apply-table-config"]').click();
    expect(dashboard.prefs.sections.main.columns).toContain("risk");
    expect(dashboard.prefs.sections.completed.columns).toContain("owner");
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  it("resets hidden solution selections even when no solutions are visible, without saving on cancel", () => {
    const dashboard = createDashboardState();
    const ctx = { state: { activeSpace: { space_id: "a" }, user: {}, projects: [], solutions: [], tasks: [], users: [] }, els: { dashboardTopProjects: document.getElementById("top") } };
    renderDashboardView(dashboard, ctx);
    dashboard.prefs.sections.main.solution_ids = ["hidden"];
    const open = () => document.querySelector('[data-dashboard-action="open-config"]').click();
    open();
    let modal = document.getElementById("dashboard-config-modal");
    modal.querySelector('[data-dashboard-action="reset-table-config"]').click();
    modal.querySelector('[data-dashboard-action="close-config"]').click();
    expect(dashboard.prefs.sections.main.solution_ids).toEqual(["hidden"]);
    open();
    modal = document.getElementById("dashboard-config-modal");
    modal.querySelector('[data-dashboard-action="reset-table-config"]').click();
    modal.querySelector('[data-dashboard-action="apply-table-config"]').click();
    expect(dashboard.prefs.sections.main.solution_ids).toBeNull();
  });

  it("explains that bulk selection affects the visible list and retains hidden selections", () => {
    const dashboard = createDashboardState();
    const state = { activeSpace: { space_id: "a" }, user: {}, projects: [], solutions: [{ solution_id: "visible", solution_name: "Visible", status: "active" }], tasks: [], users: [] };
    const ctx = { state, els: { dashboardTopProjects: document.getElementById("top") } };
    renderDashboardView(dashboard, ctx);
    dashboard.prefs.sections.main.solution_ids = ["visible", "hidden"];
    document.querySelector('[data-dashboard-action="open-config"]').click();
    const modal = document.getElementById("dashboard-config-modal");
    expect(modal.querySelector('[data-dashboard-action="select-all-solutions"]').textContent).toBe("Select visible");
    expect(modal.querySelector('[data-dashboard-action="clear-solutions"]').textContent).toBe("Clear visible");
    expect(modal.querySelector("#dashboard-config-hidden-selections").textContent).toContain("1 selected solution is outside this list");
    modal.querySelector('[data-dashboard-action="clear-solutions"]').click();
    modal.querySelector('[data-dashboard-action="apply-table-config"]').click();
    expect(dashboard.prefs.sections.main.solution_ids).toEqual(["hidden"]);
  });
});
