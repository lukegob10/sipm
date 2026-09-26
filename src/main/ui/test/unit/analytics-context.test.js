import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let renderAnalytics;

function deferred() {
  let resolve;
  const promise = new Promise((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function dashboardPayload(sessions) {
  return {
    summary: {
      summary: { sessions },
      daily: [],
    },
    routes: {},
    performance: { summary: {}, routes: [] },
  };
}

function createContext({ spaceId, userId, api }) {
  return {
    state: {
      user: userId ? { user_id: userId } : null,
      spaces: [
        { space_id: "analytics-space-a", name: "Space A" },
        { space_id: "analytics-space-b", name: "Space B" },
      ],
      activeSpace: { space_id: spaceId, is_global_admin: true },
    },
    els: { analyticsRoot: document.getElementById("analytics-root") },
    usageAnalyticsEnabled: () => true,
    api,
    noteRouteDataLoaded: vi.fn(),
    noteViewRendered: vi.fn(),
  };
}

async function waitForSessions(root, value) {
  await vi.waitFor(() => {
    expect(root.querySelector(".analytics-card strong")?.textContent).toBe(String(value));
  });
}

describe("analytics route context changes", () => {
  beforeEach(async () => {
    vi.resetModules();
    ({ renderAnalytics } = await import("../../js/routes/analytics.js"));
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("reloads current-space data after the active space changes", async () => {
    document.body.innerHTML = '<div id="analytics-root"></div>';
    const root = document.getElementById("analytics-root");
    const api = vi.fn()
      .mockResolvedValueOnce(dashboardPayload(11))
      .mockResolvedValueOnce(dashboardPayload(22));
    const ctx = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-space", api });

    renderAnalytics(ctx);
    await waitForSessions(root, 11);

    ctx.state.activeSpace = { space_id: "analytics-space-b", is_global_admin: true };
    renderAnalytics(ctx);

    expect(api).toHaveBeenCalledTimes(2);
    expect(api).toHaveBeenNthCalledWith(2, "/analytics/dashboard?days=7");
    await waitForSessions(root, 22);
    expect(root.querySelector(".analytics-card strong").textContent).not.toBe("11");
  });

  it("preserves explicit all-space and specific-space queries when the active space changes", async () => {
    document.body.innerHTML = '<div id="analytics-root"></div>';
    const root = document.getElementById("analytics-root");
    const api = vi.fn()
      .mockResolvedValueOnce(dashboardPayload(1))
      .mockResolvedValueOnce(dashboardPayload(2))
      .mockResolvedValueOnce(dashboardPayload(3))
      .mockResolvedValueOnce(dashboardPayload(4))
      .mockResolvedValueOnce(dashboardPayload(5))
      .mockResolvedValueOnce(dashboardPayload(6));
    const ctx = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-scope", api });

    renderAnalytics(ctx);
    await waitForSessions(root, 1);

    const scope = root.querySelector('[name="analytics-scope"]');
    scope.value = "all";
    scope.dispatchEvent(new Event("change", { bubbles: true }));
    await waitForSessions(root, 2);
    expect(api).toHaveBeenNthCalledWith(2, "/analytics/dashboard?days=7&all_spaces=true");

    ctx.state.activeSpace = { space_id: "analytics-space-b", is_global_admin: true };
    renderAnalytics(ctx);

    expect(root.querySelector('[name="analytics-scope"]').value).toBe("all");
    expect(api).toHaveBeenNthCalledWith(3, "/analytics/dashboard?days=7&all_spaces=true");
    await waitForSessions(root, 3);

    const specificScope = root.querySelector('[name="analytics-scope"]');
    specificScope.value = "space";
    specificScope.dispatchEvent(new Event("change", { bubbles: true }));
    await waitForSessions(root, 4);
    expect(api).toHaveBeenNthCalledWith(4, "/analytics/dashboard?days=7&space_id=analytics-space-a");

    ctx.state.activeSpace = { space_id: "analytics-space-a", is_global_admin: true };
    renderAnalytics(ctx);
    ctx.state.activeSpace = { space_id: "analytics-space-b", is_global_admin: true };
    renderAnalytics(ctx);
    expect(root.querySelector('[name="analytics-scope"]').value).toBe("space");
    expect(root.querySelector('[name="analytics-space"]').value).toBe("analytics-space-a");
    expect(api).toHaveBeenNthCalledWith(6, "/analytics/dashboard?days=7&space_id=analytics-space-a");
    await waitForSessions(root, 6);
  });

  it("ignores an older space response when the newer response resolves first", async () => {
    document.body.innerHTML = '<div id="analytics-root"></div>';
    const root = document.getElementById("analytics-root");
    const oldRequest = deferred();
    const newRequest = deferred();
    const api = vi.fn().mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    const ctx = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-race", api });

    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(1);

    ctx.state.activeSpace = { space_id: "analytics-space-b", is_global_admin: true };
    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(2);

    newRequest.resolve(dashboardPayload(22));
    await waitForSessions(root, 22);
    oldRequest.resolve(dashboardPayload(11));
    await Promise.resolve();
    await Promise.resolve();

    expect(root.querySelector(".analytics-card strong").textContent).toBe("22");
  });

  it("reloads when the route state context object is replaced", async () => {
    document.body.innerHTML = '<div id="analytics-root"></div>';
    const root = document.getElementById("analytics-root");
    const oldRequest = deferred();
    const api = vi.fn()
      .mockReturnValueOnce(oldRequest.promise)
      .mockResolvedValueOnce(dashboardPayload(55));
    const firstContext = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-context", api });
    const replacementContext = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-context", api });

    renderAnalytics(firstContext);
    renderAnalytics(replacementContext);

    expect(api).toHaveBeenCalledTimes(2);
    await waitForSessions(root, 55);
    oldRequest.resolve(dashboardPayload(11));
    await Promise.resolve();
    await Promise.resolve();
    expect(root.querySelector(".analytics-card strong").textContent).toBe("55");
  });

  it("reloads when the same user or active-space identity receives a new object", async () => {
    document.body.innerHTML = '<div id="analytics-root"></div>';
    const root = document.getElementById("analytics-root");
    const api = vi.fn()
      .mockResolvedValueOnce(dashboardPayload(11))
      .mockResolvedValueOnce(dashboardPayload(22))
      .mockResolvedValueOnce(dashboardPayload(33));
    const ctx = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-same-id", api });

    renderAnalytics(ctx);
    await waitForSessions(root, 11);

    ctx.state.user = { user_id: "analytics-user-same-id" };
    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(2);
    await waitForSessions(root, 22);

    ctx.state.activeSpace = { space_id: "analytics-space-a", is_global_admin: true };
    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(3);
    await waitForSessions(root, 33);
  });

  it("clears the prior user's report on logout and ignores its late response", async () => {
    document.body.innerHTML = '<div id="analytics-root"></div>';
    const root = document.getElementById("analytics-root");
    const oldRequest = deferred();
    const api = vi.fn()
      .mockReturnValueOnce(oldRequest.promise)
      .mockResolvedValueOnce(dashboardPayload(42));
    const ctx = createContext({ spaceId: "analytics-space-a", userId: "analytics-user-old", api });

    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(1);

    ctx.state.user = null;
    ctx.state.activeSpace.is_global_admin = false;
    renderAnalytics(ctx);
    expect(root.textContent).toContain("Global admin access required");

    ctx.state.user = { user_id: "analytics-user-new" };
    ctx.state.activeSpace.is_global_admin = true;
    renderAnalytics(ctx);
    expect(api).toHaveBeenCalledTimes(2);
    await waitForSessions(root, 42);

    oldRequest.resolve(dashboardPayload(99));
    await Promise.resolve();
    await Promise.resolve();
    expect(root.querySelector(".analytics-card strong").textContent).toBe("42");
  });
});
