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
  await expect(page.locator("#connection-status")).toContainText("Sync live");
}

async function uploadCsv(page, kind, csvText) {
  await page.locator("#csv-actions-toggle").click();
  await page.locator(`#${kind}-upload`).click();
  await page.locator("#csv-upload-file").setInputFiles({
    name: `${kind}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(csvText),
  });
  await page.locator("#csv-submit-upload").click();
  await expect(page.locator("#csv-upload-modal")).toHaveClass(/hidden/);
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

test("project CSV import renders immediately on the active deliverables screen", async ({ page }) => {
  const suffix = Date.now().toString();
  const projectName = `CSV Project ${suffix}`;
  await loadLocalAuthedApp(page);

  await uploadCsv(
    page,
    "projects",
    [
      "project_name,status,description,success_criteria,sponsor,sponsor_user_soeid,strategic_objective,priority",
      `${projectName},not_started,CSV imported project,,CSV Sponsor,,,3`,
    ].join("\n"),
  );

  await expect(page.locator("#master-table")).toContainText(projectName);
});

test("solution CSV import renders immediately on the active deliverables screen", async ({ page }) => {
  const suffix = Date.now().toString();
  const projectName = `CSV Solution Project ${suffix}`;
  const solutionName = `CSV Solution ${suffix}`;
  await loadLocalAuthedApp(page);

  await uploadCsv(
    page,
    "solutions",
    [
      "project_name,solution_name,version,status,owner,assignee,priority,due_date,current_phase,github_repo_url",
      `${projectName},${solutionName},0.1.0,not_started,CSV Owner,CSV Owner,3,,,`,
    ].join("\n"),
  );

  await expect(page.locator("#master-table")).toContainText(projectName);
  await expect(page.locator("#master-table")).toContainText(solutionName);
});

test("live sync pushes CSV imports to another active deliverables screen", async ({ page, context }) => {
  const suffix = Date.now().toString();
  const projectName = `Synced CSV Project ${suffix}`;
  await loadLocalAuthedApp(page);

  const secondPage = await context.newPage();
  await secondPage.goto("/");
  await expect(secondPage.locator("#app-shell")).toBeVisible();
  await expect(secondPage.locator("#connection-status")).toContainText("Sync live");

  await uploadCsv(
    secondPage,
    "projects",
    [
      "project_name,status,description,success_criteria,sponsor,sponsor_user_soeid,strategic_objective,priority",
      `${projectName},not_started,CSV imported synced project,,CSV Sponsor,,,3`,
    ].join("\n"),
  );

  await expect(page.locator("#master-table")).toContainText(projectName);
});
