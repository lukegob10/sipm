import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  document.body.innerHTML = "";
});

async function harness(api) {
  vi.resetModules();
  const { renderAnalytics } = await import("../../js/routes/analytics.js");
  document.body.innerHTML = '<div id="analytics-root"></div>';
  const ctx = {
    state: { user: { user_id: "user" }, activeSpace: { space_id: "space", is_global_admin: true }, spaces: [] },
    els: { analyticsRoot: document.getElementById("analytics-root") },
    usageAnalyticsEnabled: () => true,
    api,
  };
  renderAnalytics(ctx);
  return ctx;
}

const valid = () => ({ summary: { summary: { sessions: 1 }, daily: [] }, routes: { top_routes: [], top_workflows: [], recent_failures: [] }, performance: { summary: {}, routes: [] } });

it.each([null, {}, { summary: null }, { ...valid(), summary: { summary: {}, daily: [null] } },
  { ...valid(), routes: { ...valid().routes, top_routes: [null] } }, { ...valid(), performance: [] },
  { ...valid(), summary: { summary: {} } }, { ...valid(), routes: {} },
  { ...valid(), performance: { routes: [] } }, { ...valid(), performance: { summary: {} } }])(
  "reports an invalid dashboard response without repeatedly loading (%j)", async (response) => {
    const api = vi.fn().mockResolvedValueOnce(response).mockResolvedValueOnce(valid());
    const ctx = await harness(api);
    await vi.waitFor(() => expect(ctx.els.analyticsRoot.textContent).toContain("Usage analytics returned an invalid response."));
    expect(api).toHaveBeenCalledTimes(1);
    ctx.els.analyticsRoot.querySelector('[data-analytics-action="reload"]').click();
    await vi.waitFor(() => expect(ctx.els.analyticsRoot.querySelector(".analytics-card strong")?.textContent).toBe("1"));
    expect(api).toHaveBeenCalledTimes(2);
  }
);

it("escapes metric values before inserting analytics markup", async () => {
  const injected = '<img src=x onerror="alert(1)">';
  const response = valid();
  response.summary.summary.sessions = injected;
  response.summary.daily = [{ date: "2026-01-01", sessions: injected }];
  const ctx = await harness(vi.fn().mockResolvedValue(response));
  await vi.waitFor(() => expect(ctx.els.analyticsRoot.querySelector(".analytics-card strong")?.textContent).toBe(injected));
  expect(ctx.els.analyticsRoot.querySelector("img")).toBeNull();
  expect(ctx.els.analyticsRoot.textContent).toContain(injected);
});
