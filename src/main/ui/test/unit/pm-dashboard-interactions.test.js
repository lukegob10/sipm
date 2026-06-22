import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { bindPMDashboardEvents } from "../../js/routes/pm-dashboard/interactions.js";
import { createPMDashboardState, renderPMDashboardView } from "../../js/routes/pm-dashboard/render.js";

function click(selector) {
  const el = document.querySelector(selector);
  expect(el).toBeTruthy();
  el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

describe("PM dashboard interactions", () => {
  let state;
  let rerender;

  beforeEach(() => {
    window.localStorage.clear();
    document.body.innerHTML = `
      <section id="view-pm-dashboard">
        <nav id="pm-dashboard-focus-nav">
        </nav>
        <input id="pm-focus-health" type="radio" name="pm-dashboard-focus-section" value="health" data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="health" />
        <button type="button" data-pm-dashboard-action="open-project" data-project-id="project-1">Project</button>
        <button type="button" data-pm-dashboard-action="open-solution" data-solution-id="solution-1">Solution</button>
        <button type="button" data-pm-dashboard-action="open-task" data-task-id="task-1">Task</button>
        <button type="button" data-pm-dashboard-action="open-capacity-allocations" data-assignee-key="soeid-1">Capacity</button>
        <input type="month" data-pm-dashboard-action="set-capacity-month" value="2026-07" />
      </section>
    `;
    state = {
      bound: false,
      activeSection: "actions",
      capacitySpaceId: "space-1",
      capacityMonth: "2026-06",
      capacityScopeLabel: "Current month | Planning deliverable assignments only",
      capacityDrilldowns: new Map([
        ["soeid-1", {
          key: "soeid-1",
          label: "Ada Lovelace",
          allocated: 1.25,
          capacity: 1,
          utilization: 125,
          allocations: [{ allocation_id: "alloc-1" }],
        }],
      ]),
      ctx: {
        openPMDashboardProjectDrilldown: vi.fn(),
        openPMDashboardSolutionDrilldown: vi.fn(),
        openPMDashboardTaskDrilldown: vi.fn(),
        openPMDashboardCapacityDrilldown: vi.fn(),
      },
    };
    rerender = vi.fn();
    bindPMDashboardEvents(state, rerender);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    document.body.innerHTML = "";
  });

  it("switches focused sections from the section selector", () => {
    const input = document.getElementById("pm-focus-health");
    input.checked = true;
    input.dispatchEvent(new Event("change", { bubbles: true }));

    expect(state.activeSection).toBe("health");
    expect(window.localStorage.getItem("sipm-pm-dashboard-ui-v1:active-section")).toBe("health");
    expect(rerender).toHaveBeenCalledTimes(1);
  });

  it("opens all PM dashboard drilldown actions", () => {
    click('[data-pm-dashboard-action="open-project"]');
    click('[data-pm-dashboard-action="open-solution"]');
    click('[data-pm-dashboard-action="open-task"]');
    click('[data-pm-dashboard-action="open-capacity-allocations"]');

    expect(state.ctx.openPMDashboardProjectDrilldown).toHaveBeenCalledWith("project-1");
    expect(state.ctx.openPMDashboardSolutionDrilldown).toHaveBeenCalledWith("solution-1");
    expect(state.ctx.openPMDashboardTaskDrilldown).toHaveBeenCalledWith("task-1");
    expect(state.ctx.openPMDashboardCapacityDrilldown).toHaveBeenCalledWith({
      key: "soeid-1",
      label: "Ada Lovelace",
      allocated: 1.25,
      capacity: 1,
      utilization: 125,
      scopeLabel: "Current month | Planning deliverable assignments only",
      allocations: [{ allocation_id: "alloc-1" }],
    });
  });

  it("persists capacity month changes and rerenders", () => {
    const input = document.querySelector('[data-pm-dashboard-action="set-capacity-month"]');
    input.value = "2026-08";
    input.dispatchEvent(new Event("change", { bubbles: true }));

    expect(state.capacityMonth).toBe("2026-08");
    expect(window.localStorage.getItem("sipm-pm-dashboard-ui-v1:space-1")).toBe("2026-08");
    expect(rerender).toHaveBeenCalledTimes(1);
  });

  it("keeps only one focused section active when switching focus tabs", () => {
    document.body.innerHTML = `
      <section id="view-pm-dashboard">
        <div id="pm-dashboard-summary"></div>
        <div class="pm-focus-shell">
          <input id="pm-focus-actions" class="pm-focus-radio" type="radio" name="pm-dashboard-focus-section" value="actions" checked data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="actions" />
          <input id="pm-focus-health" class="pm-focus-radio" type="radio" name="pm-dashboard-focus-section" value="health" data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="health" />
          <input id="pm-focus-risks" class="pm-focus-radio" type="radio" name="pm-dashboard-focus-section" value="risks" data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="risks" />
          <input id="pm-focus-timeline" class="pm-focus-radio" type="radio" name="pm-dashboard-focus-section" value="timeline" data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="timeline" />
          <input id="pm-focus-capacity" class="pm-focus-radio" type="radio" name="pm-dashboard-focus-section" value="capacity" data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="capacity" />
          <input id="pm-focus-status" class="pm-focus-radio" type="radio" name="pm-dashboard-focus-section" value="status" data-pm-dashboard-action="set-focus-section" data-pm-dashboard-section="status" />
          <nav id="pm-dashboard-focus-nav" class="pm-focus-nav">
            <label id="pm-focus-label-actions" class="pm-focus-nav-button active" for="pm-focus-actions"></label>
            <label id="pm-focus-label-health" class="pm-focus-nav-button" for="pm-focus-health"></label>
            <label id="pm-focus-label-risks" class="pm-focus-nav-button" for="pm-focus-risks"></label>
            <label id="pm-focus-label-timeline" class="pm-focus-nav-button" for="pm-focus-timeline"></label>
            <label id="pm-focus-label-capacity" class="pm-focus-nav-button" for="pm-focus-capacity"></label>
            <label id="pm-focus-label-status" class="pm-focus-nav-button" for="pm-focus-status"></label>
          </nav>
          <div class="pm-focus-pane">
            <section class="pm-dashboard-card" id="pm-dashboard-actions"></section>
            <section class="pm-dashboard-card" id="pm-dashboard-health"></section>
            <section class="pm-dashboard-card" id="pm-dashboard-risks"></section>
            <section class="pm-dashboard-card" id="pm-dashboard-timeline"></section>
            <section class="pm-dashboard-card" id="pm-dashboard-capacity"></section>
            <section class="pm-dashboard-card" id="pm-dashboard-status"></section>
          </div>
        </div>
      </section>
    `;
    const dashboardState = createPMDashboardState();
    const ctx = {
      state: {
        activeSpace: { space_id: "space-1", space_name: "Space One" },
        projects: [{ project_id: "project-1", project_name: "Project One" }],
        solutions: [],
        tasks: [],
        users: [],
        allocations: [],
      },
      els: {
        pmDashboardSummary: document.getElementById("pm-dashboard-summary"),
        pmDashboardActions: document.getElementById("pm-dashboard-actions"),
        pmDashboardHealth: document.getElementById("pm-dashboard-health"),
        pmDashboardRisks: document.getElementById("pm-dashboard-risks"),
        pmDashboardTimeline: document.getElementById("pm-dashboard-timeline"),
        pmDashboardCapacity: document.getElementById("pm-dashboard-capacity"),
        pmDashboardStatus: document.getElementById("pm-dashboard-status"),
      },
      formatStatus: (status) => status,
      viewHref: (view) => `/${view}`,
      assigneeKeyFromAlloc: () => "unassigned",
      assigneeLabelFromKey: (key) => key,
      allocationFteMonths: () => 0,
      userCapacityFteMonth: () => 1,
      formatFte: (value) => Number(value).toFixed(2),
    };
    const activePanels = () => Array.from(document.querySelectorAll(".pm-dashboard-card.active")).map((el) => el.id);
    const activeLabels = () => Array.from(document.querySelectorAll(".pm-focus-nav-button.active")).map((el) => el.id);

    renderPMDashboardView(dashboardState, ctx);

    expect(activePanels()).toEqual(["pm-dashboard-actions"]);
    expect(document.getElementById("pm-dashboard-actions").getAttribute("aria-hidden")).toBe("false");

    const healthInput = document.getElementById("pm-focus-health");
    healthInput.checked = true;
    healthInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(activePanels()).toEqual(["pm-dashboard-health"]);
    expect(activeLabels()).toEqual(["pm-focus-label-health"]);
    expect(document.getElementById("pm-dashboard-actions").getAttribute("aria-hidden")).toBe("true");
    expect(document.getElementById("pm-dashboard-health").getAttribute("aria-hidden")).toBe("false");

    const risksInput = document.getElementById("pm-focus-risks");
    risksInput.checked = true;
    risksInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(activePanels()).toEqual(["pm-dashboard-risks"]);
    expect(activeLabels()).toEqual(["pm-focus-label-risks"]);
    expect(document.getElementById("pm-dashboard-actions").getAttribute("aria-hidden")).toBe("true");
    expect(document.getElementById("pm-dashboard-health").getAttribute("aria-hidden")).toBe("true");
    expect(document.getElementById("pm-dashboard-risks").getAttribute("aria-hidden")).toBe("false");
  });
});
