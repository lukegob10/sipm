import { expect, test } from "@playwright/test";

test("analytics controls retain keyboard focus while filters and reload complete", async ({ page }) => {
  const soeid = `analytics${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "Analytics User", password: "Password123" } })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.route("**/api/auth/bootstrap", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, is_global_admin: true, usage_analytics_enabled: true } } });
  });
  let release;
  let held = false;
  await page.route("**/api/analytics/dashboard?*", async (route) => {
    if (held) await new Promise((resolve) => { release = resolve; });
    await route.fulfill({ json: { summary: { summary: { sessions: 12 }, daily: [] }, routes: { top_routes: [], top_workflows: [], recent_failures: [] }, performance: { summary: {}, routes: [] } } });
  });
  await page.goto("/");
  await page.locator('.nav-btn[data-view="analytics"]').click();
  const root = page.locator("#analytics-root");
  await expect(root.getByRole("status")).toHaveText("Ready");
  held = true;
  const days = root.locator('[name="analytics-days"]');
  await days.focus();
  await days.selectOption("30");
  await expect(days).toBeFocused();
  await expect.poll(() => typeof release).toBe("function");
  release();
  await expect(root.getByRole("status")).toHaveText("Ready");
  await expect(days).toBeFocused();
  held = false;
  const reload = root.getByRole("button", { name: "Reload" });
  await reload.focus();
  await page.keyboard.press("Enter");
  await expect(root.getByRole("status")).toHaveText("Ready");
  await expect(reload).toBeFocused();
});
