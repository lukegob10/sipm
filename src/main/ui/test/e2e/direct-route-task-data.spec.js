import { expect, test } from "@playwright/test";

async function createWork(page, prefix) {
  const soeid = `${prefix}${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "Direct Route User", password: "Password123" } })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post("/project-manager/api/programs", { data: { program_name: "Direct Program" } });
  expect(program.ok()).toBeTruthy();
  const project = await page.request.post("/project-manager/api/projects", { data: { program_id: (await program.json()).program_id, project_name: "Direct Project" } });
  expect(project.ok()).toBeTruthy();
  const solution = await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: "Direct Solution", version: "1", status: "active" } });
  expect(solution.ok()).toBeTruthy();
  const task = await page.request.post(`/project-manager/api/solutions/${(await solution.json()).solution_id}/tasks`, { data: { task_name: "Direct blocked task", blocked: true, due_date: "2026-05-14" } });
  expect(task.ok()).toBeTruthy();
}

test("direct Calendar loads tasks while remaining usable during the task request", async ({ page }) => {
  await createWork(page, "directcal");
  let release; let requested = false;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/tasks", async (route) => { requested = true; await held; await route.continue(); });
  try {
    await page.goto("/project-manager/calendar");
    await expect.poll(() => requested).toBe(true);
    const month = page.locator("#calendar-month");
    await month.fill("2026-05"); await month.dispatchEvent("change");
    await expect(page.locator('#calendar-grid .calendar-cell[data-day="14"]')).toBeVisible();
    await expect(month).toHaveValue("2026-05");
    release();
    await expect(page.locator("#calendar-grid")).toContainText("Direct blocked task");
    await expect(month).toHaveValue("2026-05");
  } finally { release(); }
});

test("direct Dashboard computes blocked-task counts", async ({ page }) => {
  await createWork(page, "directdash");
  await page.goto("/project-manager/dashboard");
  await expect(page.locator("#dashboard-top-projects")).toContainText("Direct Solution");
  await page.locator('[data-dashboard-action="open-config"]').click();
  await page.locator('input[name="dashboard-config-column"][value="blocked_tasks"]').check();
  await page.locator('[data-dashboard-action="apply-table-config"]').click();
  const cell = page.locator("#dashboard-top-projects tr").filter({ hasText: "Direct Solution" }).locator(".dashboard-col-blocked_tasks");
  await expect(cell).toHaveText("1");
});
