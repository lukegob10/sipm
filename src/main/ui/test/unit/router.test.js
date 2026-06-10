import { beforeEach, describe, expect, it, vi } from "vitest";

import { createRouterController } from "../../js/shell/router.js";


function buildRouterHarness() {
  document.body.innerHTML = `
    <button class="nav-btn" data-view="master"></button>
    <button class="nav-btn" data-view="gantt"></button>
    <button class="nav-btn" data-view="program-dashboard"></button>
    <button class="nav-btn" data-view="team-capacity"></button>
    <button class="nav-btn" data-view="spaces"></button>
    <button class="nav-btn" data-view="analytics"></button>
    <section class="view" id="view-master"></section>
    <section class="view" id="view-gantt"></section>
    <section class="view" id="view-program-dashboard"></section>
    <section class="view" id="view-team-capacity"></section>
    <section class="view" id="view-spaces"></section>
    <section class="view" id="view-analytics"></section>
  `;

  const state = {
    authed: true,
    currentView: "master",
    activeSpace: { space_id: "space-1", space_role: "space_admin" },
    tasksWorkbench: {},
  };
  const els = {
    navButtons: document.querySelectorAll(".nav-btn"),
    views: document.querySelectorAll(".view"),
  };

  const loadData = vi.fn().mockResolvedValue(undefined);
  const loadTeamCapacityData = vi.fn().mockResolvedValue(undefined);
  const renderActiveView = vi.fn();
  const routeModuleLoaders = {
    master: vi.fn().mockResolvedValue({}),
    gantt: vi.fn().mockResolvedValue({}),
    "program-dashboard": vi.fn().mockResolvedValue({}),
    "team-capacity": vi.fn().mockResolvedValue({}),
    spaces: vi.fn().mockResolvedValue({}),
    analytics: vi.fn().mockResolvedValue({}),
  };
  const controller = createRouterController({
    state,
    els,
    renderActiveView,
    userIsGlobalAdmin: () => false,
    isSpaceAdminRole: (role) => role === "space_admin",
    usageAnalyticsEnabled: () => false,
    loadData,
    loadTeamCapacityData,
    routeModuleLoaders,
  });
  return { controller, state, loadData, loadTeamCapacityData, renderActiveView, routeModuleLoaders };
}


describe("router controller", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/project-manager/");
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("normalizes context-path locations into route views", () => {
    const { controller } = buildRouterHarness();

    expect(controller.viewFromLocationPath("/")).toBe("master");
    expect(controller.viewFromLocationPath("/gantt")).toBe("gantt");
    expect(controller.viewFromLocationPath("/program-dashboard")).toBe("program-dashboard");
    expect(controller.viewFromLocationPath("/spaces")).toBe("spaces");
    expect(controller.appRelativePath("/dashboard")).toBe("/dashboard");
  });

  it("keeps governance routes admin-only while allowing team capacity for members", () => {
    const { controller } = buildRouterHarness();

    expect(controller.resolveAccessibleView("team-capacity")).toBe("team-capacity");
    expect(controller.resolveAccessibleView("spaces")).toBe("spaces");
    expect(controller.resolveAccessibleView("access")).toBe("access");
    expect(controller.resolveAccessibleView("analytics")).toBe("master");
    expect(controller.resolveAccessibleView("unknown")).toBe("master");
  });

  it("allows member users to access team capacity and agent approvals but not platform access", () => {
    const { controller, state } = buildRouterHarness();
    state.activeSpace = { space_id: "space-1", space_role: "member" };

    expect(controller.resolveAccessibleView("team-capacity")).toBe("team-capacity");
    expect(controller.resolveAccessibleView("spaces")).toBe("spaces");
    expect(controller.resolveAccessibleView("access")).toBe("master");
  });

  it("allows analytics for global admins when the feature is enabled", () => {
    document.body.innerHTML = `
      <button class="nav-btn" data-view="analytics"></button>
      <section class="view" id="view-analytics"></section>
    `;
    const state = {
      authed: true,
      currentView: "master",
      activeSpace: { space_id: "space-1", space_role: "space_admin" },
      tasksWorkbench: {},
    };
    const controller = createRouterController({
      state,
      els: {
        navButtons: document.querySelectorAll(".nav-btn"),
        views: document.querySelectorAll(".view"),
      },
      renderActiveView: vi.fn(),
      userIsGlobalAdmin: () => true,
      isSpaceAdminRole: () => true,
      usageAnalyticsEnabled: () => true,
      loadData: vi.fn().mockResolvedValue(undefined),
      loadTeamCapacityData: vi.fn().mockResolvedValue(undefined),
    });

    expect(controller.resolveAccessibleView("analytics")).toBe("analytics");
  });

  it("loads route data when authenticated", async () => {
    const { controller, state, loadData } = buildRouterHarness();

    controller.setView("master");
    expect(state.currentView).toBe("master");
    await vi.waitFor(() => expect(loadData).toHaveBeenCalled());
    expect(loadData).toHaveBeenCalledWith(expect.objectContaining({ entities: ["phases", "programs", "projects", "solutions"] }));
  });

  it("loads Gantt route data from existing work entities", async () => {
    const { controller, state, loadData } = buildRouterHarness();

    controller.setView("gantt");
    expect(state.currentView).toBe("gantt");
    await vi.waitFor(() => expect(loadData).toHaveBeenCalled());
    expect(loadData).toHaveBeenCalledWith(expect.objectContaining({ entities: ["programs", "projects", "solutions", "tasks"] }));
  });

  it("loads program dashboard data from program-scoped work entities", async () => {
    const { controller, state, loadData } = buildRouterHarness();

    controller.setView("program-dashboard");
    expect(state.currentView).toBe("program-dashboard");
    await vi.waitFor(() => expect(loadData).toHaveBeenCalled());
    expect(loadData).toHaveBeenCalledWith(expect.objectContaining({ entities: ["programs", "projects", "solutions", "tasks"] }));
  });

  it("does not render authenticated data routes before the route module and data store are ready", async () => {
    const { controller, loadData, renderActiveView, routeModuleLoaders } = buildRouterHarness();

    controller.setView("gantt");

    expect(renderActiveView).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(routeModuleLoaders.gantt).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(loadData).toHaveBeenCalledTimes(1));
    expect(renderActiveView).not.toHaveBeenCalled();
  });

  it("waits for the team-capacity route module before forcing team-capacity data", async () => {
    const { controller, loadTeamCapacityData, renderActiveView, routeModuleLoaders } = buildRouterHarness();

    controller.setView("team-capacity");

    expect(renderActiveView).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(routeModuleLoaders["team-capacity"]).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(loadTeamCapacityData).toHaveBeenCalledWith({ force: true }));
    expect(renderActiveView).not.toHaveBeenCalled();
  });
});
