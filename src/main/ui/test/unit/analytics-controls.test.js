import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

let renderAnalytics;
function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
const payload = { summary: { summary: { sessions: 12 }, daily: [] }, routes: { top_routes: [], top_workflows: [], recent_failures: [] }, performance: { summary: {}, routes: [] } };
function setup(api) {
  document.body.innerHTML = '<div id="analytics-root"></div><button id="outside">Outside</button>';
  const root = document.getElementById("analytics-root");
  const ctx = { els: { analyticsRoot: root }, state: { user: { user_id: "user" }, activeSpace: { space_id: "a", is_global_admin: true }, spaces: [{ space_id: "a", name: "A" }] }, usageAnalyticsEnabled: () => true, api };
  renderAnalytics(ctx);
  return root;
}

describe("analytics controls", () => {
  beforeEach(async () => { vi.resetModules(); ({ renderAnalytics } = await import("../../js/routes/analytics.js")); });
  afterEach(() => { document.body.innerHTML = ""; });

  it("keeps filter focus through change and completion without stealing it from outside", async () => {
    const first = deferred(); const second = deferred();
    const root = setup(vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise));
    expect(root.textContent).toContain("Loading analytics...");
    expect(root.textContent).not.toContain("No route views recorded yet.");
    first.resolve(payload);
    await vi.waitFor(() => expect(root.querySelector('[role="status"]').textContent).toBe("Ready"));
    const select = root.querySelector('[name="analytics-days"]');
    select.focus(); select.value = "30"; select.dispatchEvent(new Event("change", { bubbles: true }));
    expect(document.activeElement).toBe(root.querySelector('[name="analytics-days"]'));
    second.resolve(payload);
    await vi.waitFor(() => expect(root.querySelector('[role="status"]').textContent).toBe("Ready"));
    expect(document.activeElement).toBe(root.querySelector('[name="analytics-days"]'));
    document.getElementById("outside").focus();
    renderAnalytics({ els: { analyticsRoot: root }, state: { user: { user_id: "other" }, activeSpace: { space_id: "a", is_global_admin: true }, spaces: [{ space_id: "a", name: "A" }] }, usageAnalyticsEnabled: () => true, api: () => Promise.resolve(payload) });
    expect(document.activeElement.id).toBe("outside");
  });

  it("keeps reload focus and identifies retained data after refresh fails", async () => {
    const failure = deferred();
    const root = setup(vi.fn().mockResolvedValueOnce(payload).mockReturnValueOnce(failure.promise));
    await vi.waitFor(() => expect(root.querySelector('[role="status"]').textContent).toBe("Ready"));
    const reload = root.querySelector('[data-analytics-action="reload"]');
    reload.focus(); reload.click();
    expect(document.activeElement).toBe(root.querySelector('[data-analytics-action="reload"]'));
    failure.reject(new Error("Network unavailable"));
    await vi.waitFor(() => expect(root.querySelector('[role="status"]').textContent).toBe("Refresh failed; showing previous data"));
    expect(root.querySelector(".analytics-card strong").textContent).toBe("12");
    expect(root.textContent).toContain("Network unavailable");
    expect(document.activeElement).toBe(root.querySelector('[data-analytics-action="reload"]'));
  });
});
