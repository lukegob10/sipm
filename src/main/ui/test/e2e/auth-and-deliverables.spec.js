import { expect, test } from "@playwright/test";


async function registerViaUi(page, suffix) {
  await page.goto("/");
  await page.locator("#auth-tab-register").click();
  await page.locator('#register-form input[name="display_name"]').fill(`UI Smoke ${suffix}`);
  await page.locator('#register-form input[name="soeid"]').fill(`ui${suffix}`);
  await page.locator('#register-form input[name="password"]').fill("TempPass123!");
  await page.locator('#register-form button[type="submit"]').click();
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("self-registration reaches deliverables and blocked create shows role error", async ({ page }) => {
  const suffix = Date.now().toString();
  await registerViaUi(page, suffix);

  await expect(page.locator("#view-master")).toHaveClass(/active/);
  await expect(page.locator("#master-table")).toBeVisible();

  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-project").click();
  await page.locator('#project-form input[name="project_name"]').fill(`UI Project ${suffix}`);
  await page.locator('#project-form input[name="sponsor"]').fill("UI Sponsor");
  await page.locator("#project-submit-btn").click();
  await expect(page.locator("#project-form-status")).toContainText("Insufficient space role");
});
