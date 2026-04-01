import { expect, test } from "@playwright/test";


async function loadAuthedApp(page) {
  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("proxy-bootstrap reaches deliverables and blocked create shows role error", async ({ page }) => {
  const suffix = Date.now().toString();
  await loadAuthedApp(page);

  await expect(page.locator("#view-master")).toHaveClass(/active/);
  await expect(page.locator("#master-table")).toBeVisible();

  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-project").click();
  await page.locator('#project-form input[name="project_name"]').fill(`UI Project ${suffix}`);
  await page.locator('#project-form input[name="sponsor"]').fill("UI Sponsor");
  await page.locator("#project-submit-btn").click();
  await expect(page.locator("#project-form-status")).toContainText("Insufficient space role");
});
