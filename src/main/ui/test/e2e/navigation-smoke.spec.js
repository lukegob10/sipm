import { expect, test } from "@playwright/test";


async function loadLocalAuthedApp(page) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const soeid = `nav${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: {
      soeid,
      display_name: "Navigation Smoke User",
      password: "Password123",
    },
  });
  expect(register.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("dashboard and planning routes load from the shared shell", async ({ page }) => {
  await loadLocalAuthedApp(page);

  await page.locator('.nav-btn[data-view="dashboard"]').click();
  await expect(page.locator("#view-dashboard")).toHaveClass(/active/);
  await expect(page.locator("#dashboard-space-capacity")).toBeVisible();
  await expect(page.locator("#dashboard-top-projects")).toBeVisible();

  await page.locator('.nav-btn[data-view="program-dashboard"]').click();
  await expect(page.locator("#view-program-dashboard")).toHaveClass(/active/);
  await expect(page.locator("#program-dashboard-root")).toBeVisible();

  await page.locator('.nav-btn[data-view="planning"]').click();
  await expect(page.locator("#view-planning")).toHaveClass(/active/);
  await expect(page.locator("#planning-board")).toBeVisible();

  await page.locator("#space-switcher-trigger").click();
  await expect(page.locator("#space-switcher-panel")).not.toHaveClass(/hidden/);
});
