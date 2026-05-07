import { expect, test } from "@playwright/test";


async function loadLocalAuthedApp(page) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const soeid = `ui${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: {
      soeid,
      display_name: "UI Smoke User",
      password: "Password123",
    },
  });
  expect(register.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("local login reaches deliverables and creates a project", async ({ page }) => {
  const suffix = Date.now().toString();
  await loadLocalAuthedApp(page);

  await expect(page.locator("#view-master")).toHaveClass(/active/);
  await expect(page.locator("#master-table")).toBeVisible();

  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-project").click();
  await page.locator('#project-form input[name="project_name"]').fill(`UI Project ${suffix}`);
  await page.locator('#project-form input[name="sponsor"]').fill("UI Sponsor");
  await page.locator("#project-submit-btn").click();
  await expect(page.locator("#project-form-status")).toContainText("Created project");
});
