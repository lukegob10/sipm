import { expect, test } from "@playwright/test";


async function loadLocalAuthedApp(page, { createProject = false } = {}) {
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

  const personalSpace = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personalSpace.ok()).toBeTruthy();
  const activate = await page.request.post("/project-manager/api/auth/active-space", {
    data: { space_id: (await personalSpace.json()).space_id },
  });
  expect(activate.ok()).toBeTruthy();

  if (createProject) {
    const program = await page.request.post("/project-manager/api/programs", {
      data: { program_name: "Navigation Program" },
    });
    expect(program.ok()).toBeTruthy();
    const project = await page.request.post("/project-manager/api/projects", {
      data: { program_id: (await program.json()).program_id, project_name: "Navigation Project" },
    });
    expect(project.ok()).toBeTruthy();
  }

  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}


test("dashboard routes load from the shared shell", async ({ page }) => {
  await loadLocalAuthedApp(page);

  await page.locator('.nav-btn[data-view="dashboard"]').click();
  await expect(page.locator("#view-dashboard")).toHaveClass(/active/);
  await expect(page.locator("#dashboard-space-capacity")).toBeVisible();
  await expect(page.locator("#dashboard-top-projects")).toBeVisible();

  await page.locator('.nav-btn[data-view="program-dashboard"]').click();
  await expect(page.locator("#view-program-dashboard")).toHaveClass(/active/);
  await expect(page.locator("#program-dashboard-root")).toBeVisible();

  await page.locator("#space-switcher-trigger").click();
  await expect(page.locator("#space-switcher-panel")).not.toHaveClass(/hidden/);
});


test("Calendar becomes usable while earlier Deliverables and Roadmap task reads are pending", async ({ page }) => {
  let releaseTasks;
  const tasksHeld = new Promise((resolve) => { releaseTasks = resolve; });
  const taskRequests = [];
  await page.route("**/project-manager/api/tasks", async (route) => {
    taskRequests.push(route.request());
    await tasksHeld;
    await route.fulfill({ json: [] });
  });

  try {
    await loadLocalAuthedApp(page, { createProject: true });
    await expect.poll(() => taskRequests.length).toBeGreaterThan(0);
    await page.locator('.nav-btn[data-view="gantt"]').click();
    await expect(page.locator("#view-gantt")).toHaveClass(/active/);
    await page.locator('.nav-btn[data-view="calendar"]').click();
    await expect(page.locator("#view-calendar")).toHaveClass(/active/);
    await expect(page.locator("#calendar-grid .calendar-cell[data-day]").first()).toBeVisible();
    await expect(page.locator("#calendar-filter-project option")).toHaveText(["All", "Navigation Program / Navigation Project"]);

    const month = page.locator("#calendar-month");
    const originalMonth = await month.inputValue();
    await page.locator("#calendar-next").click();
    await expect(month).not.toHaveValue(originalMonth);
    await page.locator("#calendar-filter-owner").fill("draft filter");
    await expect(page.locator("#calendar-filter-owner")).toBeFocused();
    const updatedMonth = await month.inputValue();

    releaseTasks();
    await expect.poll(async () => (
      await Promise.all(taskRequests.map(async (request) => request.failure() || await request.response()))
    )).not.toContain(null);
    await expect(page.locator("#view-calendar")).toHaveClass(/active/);
    await expect(month).toHaveValue(updatedMonth);
    await expect(page.locator("#calendar-filter-owner")).toHaveValue("draft filter");
    await expect(page.locator("#calendar-filter-owner")).toBeFocused();
  } finally {
    releaseTasks();
  }
});
