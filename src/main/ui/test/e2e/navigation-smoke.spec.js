import { expect, test } from "@playwright/test";


async function bootstrapUser(page, suffix) {
  await page.goto("/");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.locator('#register-form input[name="display_name"]').fill(`Nav Smoke ${suffix}`);
  await page.locator('#register-form input[name="soeid"]').fill(`nav${suffix}`);
  await page.locator('#register-form input[name="password"]').fill("TempPass123!");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("dashboard and planning routes load from the shared shell", async ({ page }) => {
  const suffix = Date.now().toString();
  await bootstrapUser(page, suffix);

  await page.locator('.nav-btn[data-view="dashboard"]').click();
  await expect(page.locator("#view-dashboard")).toHaveClass(/active/);
  await expect(page.locator("#dashboard-cards")).toBeVisible();

  await page.locator('.nav-btn[data-view="planning"]').click();
  await expect(page.locator("#view-planning")).toHaveClass(/active/);
  await expect(page.locator("#planning-board")).toBeVisible();

  await page.locator("#space-switcher-trigger").click();
  await expect(page.locator("#space-switcher-panel")).not.toHaveClass(/hidden/);
});
