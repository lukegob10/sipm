import { expect, test } from "@playwright/test";


async function loadLocalAuthedApp(page) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const soeid = `ui${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const programName = `UI Smoke Program ${suffix}`;
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: {
      soeid,
      display_name: "UI Smoke User",
      password: "Password123",
    },
  });
  expect(register.ok()).toBeTruthy();

  const personalSpace = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personalSpace.ok()).toBeTruthy();
  const activate = await page.request.post("/project-manager/api/auth/active-space", {
    data: { space_id: (await personalSpace.json()).space_id },
  });
  expect(activate.ok()).toBeTruthy();

  const program = await page.request.post("/project-manager/api/programs", {
    data: {
      program_name: programName,
      description: "Program for local smoke project creation.",
    },
  });
  expect(program.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();

  return { programId: (await program.json()).program_id, programName };
}


test("local login reaches deliverables and creates a project", async ({ page }) => {
  const suffix = Date.now().toString();
  const projectName = `UI Project ${suffix}`;
  const { programId, programName } = await loadLocalAuthedApp(page);

  try {
    await expect(page.locator("#view-master")).toHaveClass(/active/);
    await expect(page.locator("#master-table")).toBeVisible();

    await page.locator("#topbar-create-toggle").click();
    await page.locator("#topbar-create-project").click();
    await page.locator('#project-form select[name="program_id"]').selectOption({ label: programName });
    await page.locator('#project-form input[name="project_name"]').fill(projectName);
    await page.locator('#project-form input[name="sponsor"]').fill("UI Sponsor");
    await page.locator("#project-submit-btn").click();
    await expect(page.locator("#project-form-status")).toContainText("Created project");
  } finally {
    const projects = await page.request.get("/project-manager/api/projects");
    if (projects.ok()) {
      const project = (await projects.json()).find((row) => row.project_name === projectName && row.sponsor === "UI Sponsor");
      if (project) await page.request.delete(`/project-manager/api/projects/${project.project_id}`);
    }
    await page.request.delete(`/project-manager/api/programs/${programId}`);
  }
});
