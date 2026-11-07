import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createDashboardState, renderDashboardView } from "../../js/routes/dashboard/render.js";
import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";

afterEach(() => {
  document.body.innerHTML = "";
  localStorage.clear();
});

describe("dashboard Mine scope identity", () => {
  it.each([
    ["a different linked owner with the same display name", { owner_user_soeid: "other", owner: "Alex" }, false],
    ["an owner ID equal to the current user's display name", { owner_user_soeid: "Alex", owner: "Someone else" }, false],
    ["the current linked owner with a stale display name", { owner_user_soeid: " AX1 ", owner: "Old label" }, true],
    ["a legacy owner name without a linked ID", { owner: " alex " }, true],
    ["a similar legacy owner name", { owner: "Alexandra" }, false],
    ["an independently matching key stakeholder", { owner_user_soeid: "other", owner: "Someone else", key_stakeholder: "Alex" }, true],
  ])("handles %s", (_label, ownership, expected) => {
    document.body.innerHTML = '<div id="dashboard-top"></div>';
    const root = document.getElementById("dashboard-top");
    const dashboard = createDashboardState();
    dashboard.prefsSpaceId = "space";
    dashboard.prefs.scope = "mine";
    const state = {
      activeSpace: { space_id: "space" },
      user: { soeid: "ax1", display_name: "Alex" },
      projects: [], tasks: [], users: [],
      solutions: [{ solution_id: "candidate", solution_name: "Candidate", status: "active", ...ownership }],
    };

    renderDashboardView(dashboard, { state, els: { dashboardTopProjects: root } });

    expect(!!root.querySelector('[data-solution-id="candidate"]')).toBe(expected);
  });
});

describe("analytics render work", () => {
  let renderAnalytics;
  beforeEach(async () => {
    vi.resetModules();
    ({ renderAnalytics } = await import("../../js/routes/analytics.js"));
    document.body.innerHTML = '<div id="analytics-root"></div>';
  });

  it("renders loading once per initial or replacement query and renders completion once", async () => {
    let finish;
    const pending = new Promise((resolve) => { finish = resolve; });
    const api = vi.fn().mockReturnValueOnce(pending).mockReturnValue(new Promise(() => {}));
    const root = document.getElementById("analytics-root");
    const ctx = {
      state: { user: { user_id: "admin" }, activeSpace: { space_id: "one", is_global_admin: true }, spaces: [] },
      els: { analyticsRoot: root }, api, usageAnalyticsEnabled: () => true,
      noteViewRendered: vi.fn(), noteRouteDataLoaded: vi.fn(),
    };

    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledOnce();
    expect(root.textContent).toContain("Loading analytics...");
    expect(ctx.noteViewRendered).toHaveBeenCalledTimes(1);

    finish({ summary: { summary: { sessions: 12 }, daily: [] }, routes: { top_routes: [], top_workflows: [], recent_failures: [] }, performance: { summary: {}, routes: [] } });
    await vi.waitFor(() => expect(root.querySelector(".analytics-card strong")?.textContent).toBe("12"));
    expect(ctx.noteViewRendered).toHaveBeenCalledTimes(2);
    expect(ctx.noteRouteDataLoaded).toHaveBeenCalledOnce();

    ctx.noteViewRendered.mockClear();
    ctx.state.activeSpace = { space_id: "two", is_global_admin: true };
    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("Loading analytics...");
    expect(ctx.noteViewRendered).toHaveBeenCalledOnce();
  });
});

describe("forced governance list refreshes", () => {
  const lists = [
    ["admins", (controller, options) => controller.refreshGlobalAdmins(options), (state) => state.globalAdmins],
    ["available spaces", (controller, options) => controller.refreshRequestableSpaces(options), (state) => state.requestableSpaces],
    ["access requests", (controller, options) => controller.refreshAccessRequests(options), (state) => state.spaceAccessRequests],
    ["reviewable requests", (controller, options) => controller.refreshReviewableAccessRequests(options), (state) => state.reviewableAccessRequests],
    ["members", (controller, options) => controller.refreshSpaceMembers("target", options), (state) => state.spaceMembersBySpace.target],
    ["API tokens", (controller, options) => controller.refreshApiTokens("target", options), (state) => state.apiTokensByUser.target],
  ];

  function harness() {
    const state = {
      user: { user_id: "admin" }, activeSpace: { space_id: "space" },
      spaceMembersBySpace: {}, spaceMembersLoadedBySpace: {}, spaceMembersErrorBySpace: {},
      apiTokensByUser: {}, apiTokensLoadedByUser: {},
    };
    const api = vi.fn();
    const controller = createSpaceGovernanceController({ state, api, els: {},
      activeSpaceId: () => state.activeSpace.space_id, userIsGlobalAdmin: () => true,
      isSpaceGovernanceView: () => false,
    });
    return { state, api, controller };
  }

  it.each(lists)("deduplicates ordinary in-flight %s reads", async (_label, load, value) => {
    const { state, api, controller } = harness();
    let finish;
    api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const first = load(controller);
    const second = load(controller);
    expect(api).toHaveBeenCalledOnce();
    finish([{ marker: "current" }]);
    await Promise.all([first, second]);
    expect(value(state)).toEqual([{ marker: "current" }]);
  });

  it.each(lists)("starts a fresh %s read after a mutation and ignores an older snapshot", async (_label, load, value) => {
    const { state, api, controller } = harness();
    let finishOld;
    api.mockReturnValueOnce(new Promise((resolve) => { finishOld = resolve; }))
      .mockResolvedValueOnce([{ marker: "after mutation" }]);
    const older = load(controller);
    const fresh = load(controller, { force: true });
    expect(api).toHaveBeenCalledTimes(2);
    await fresh;
    finishOld([{ marker: "before mutation" }]);
    await older;
    expect(value(state)).toEqual([{ marker: "after mutation" }]);
  });

  it.each(lists)("ignores an older %s failure after a forced refresh succeeds", async (_label, load, value) => {
    const { state, api, controller } = harness();
    let failOld;
    api.mockReturnValueOnce(new Promise((_, reject) => { failOld = reject; }))
      .mockResolvedValueOnce([{ marker: "after mutation" }]);
    const older = load(controller);
    const fresh = load(controller, { force: true });
    expect(api).toHaveBeenCalledTimes(2);
    await fresh;
    failOld(new Error("older request failed"));
    await expect(older).resolves.toEqual([]);
    expect(value(state)).toEqual([{ marker: "after mutation" }]);
    expect(state.spaceMembersErrorBySpace.target).toBeUndefined();
    expect(state.globalAdminsError || state.requestableSpacesError || state.spaceAccessRequestsError || state.reviewableAccessRequestsError).toBeFalsy();
  });
});
