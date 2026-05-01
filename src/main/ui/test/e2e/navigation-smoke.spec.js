import { expect, test } from "@playwright/test";


async function loadAuthedApp(page) {
  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("dashboard and planning routes load from the shared shell", async ({ page }) => {
  await loadAuthedApp(page);

  await page.locator('.nav-btn[data-view="dashboard"]').click();
  await expect(page.locator("#view-dashboard")).toHaveClass(/active/);
  await expect(page.locator("#dashboard-space-capacity")).toBeVisible();
  await expect(page.locator("#dashboard-top-projects")).toBeVisible();

  await page.locator('.nav-btn[data-view="planning"]').click();
  await expect(page.locator("#view-planning")).toHaveClass(/active/);
  await expect(page.locator("#planning-board")).toBeVisible();

  await page.locator("#space-switcher-trigger").click();
  await expect(page.locator("#space-switcher-panel")).not.toHaveClass(/hidden/);
});
