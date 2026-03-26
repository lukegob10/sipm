import { expect, test } from "@playwright/test";


async function registerViaUi(page, suffix) {
  await page.goto("/");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.locator('#register-form input[name="display_name"]').fill(`UI Smoke ${suffix}`);
  await page.locator('#register-form input[name="soeid"]').fill(`ui${suffix}`);
  await page.locator('#register-form input[name="password"]').fill("TempPass123!");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("auth flow can create project, solution, and task from the shell", async ({ page }) => {
  const suffix = Date.now().toString();
  await registerViaUi(page, suffix);

  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-project").click();
  await page.locator('#project-form input[name="project_name"]').fill(`UI Project ${suffix}`);
  await page.locator('#project-form input[name="sponsor"]').fill("UI Sponsor");
  await page.locator("#project-submit-btn").click();
  await expect(page.locator("#project-form-status")).toContainText("Created project");

  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-solution").click();
  await page.locator('#solution-form input[name="solution_name"]').fill(`UI Solution ${suffix}`);
  await page.locator('#solution-form select[name="project_id"]').selectOption({ label: `UI Project ${suffix}` });
  await page.locator('#solution-form input[name="owner"]').fill("UI Owner");
  await page.locator("#solution-submit-btn").click();
  await expect(page.locator("#solution-form-status")).toContainText("Created solution");

  await page.locator("#show-subcomponent-form").click();
  await page.locator('#subcomponent-form input[name="subcomponent_name"]').fill(`UI Task ${suffix}`);
  await page.locator('#subcomponent-form input[name="assignee"]').fill("Engineer UI");
  await page.locator("#subcomponent-submit-btn").click();
  await expect(page.locator("#subcomponent-form-status")).toContainText("Created");

  await expect(page.locator("#master-table")).toContainText(`UI Project ${suffix}`);
  await expect(page.locator("#master-table")).toContainText(`UI Solution ${suffix}`);
  await expect(page.locator("#solution-subcomponent-table")).toContainText(`UI Task ${suffix}`);
});
