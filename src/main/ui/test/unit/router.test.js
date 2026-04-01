import { beforeEach, describe, expect, it, vi } from "vitest";

import { createRouterController } from "../../js/shell/router.js";


function buildRouterHarness() {
  document.body.innerHTML = `
    <button class="nav-btn" data-view="master"></button>
    <button class="nav-btn" data-view="spaces"></button>
    <button class="nav-btn" data-view="analytics"></button>
    <section class="view" id="view-master"></section>
    <section class="view" id="view-spaces"></section>
    <section class="view" id="view-analytics"></section>
  `;

  const state = {
    authed: true,
    currentView: "master",
    activeSpace: { space_id: "space-1", space_role: "space_admin" },
    subcomponentsWorkbench: {},
  };
  const els = {
    navButtons: document.querySelectorAll(".nav-btn"),
    views: document.querySelectorAll(".view"),
  };

  const loadData = vi.fn().mockResolvedValue(undefined);
  const loadTeamCapacityData = vi.fn().mockResolvedValue(undefined);
  const renderActiveView = vi.fn();
  const controller = createRouterController({
    state,
    els,
    renderActiveView,
    userIsGlobalAdmin: () => false,
    isSpaceAdminRole: (role) => role === "space_admin",
    usageAnalyticsEnabled: () => false,
    loadData,
    loadTeamCapacityData,
  });
  return { controller, state, loadData, renderActiveView };
}


describe("router controller", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/project-manager/");
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("normalizes context-path locations into route views", () => {
    const { controller } = buildRouterHarness();

    expect(controller.viewFromLocationPath("/")).toBe("master");
    expect(controller.viewFromLocationPath("/spaces")).toBe("spaces");
    expect(controller.appRelativePath("/dashboard")).toBe("/dashboard");
  });

  it("blocks admin routes for non-admin users", () => {
    const { controller } = buildRouterHarness();

    expect(controller.resolveAccessibleView("spaces")).toBe("spaces");
    expect(controller.resolveAccessibleView("access")).toBe("access");
    expect(controller.resolveAccessibleView("analytics")).toBe("master");
    expect(controller.resolveAccessibleView("unknown")).toBe("master");
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
      subcomponentsWorkbench: {},
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
    await Promise.resolve();
    expect(loadData).toHaveBeenCalledWith({ entities: ["phases", "projects", "solutions"] });
  });
});
