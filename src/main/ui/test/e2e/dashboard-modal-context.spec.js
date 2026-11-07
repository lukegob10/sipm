import { expect, test } from "@playwright/test";

async function openPrivateDashboardConfig(page) {
  const soeid = `dash${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "Dashboard user", password: "Password123" } })).ok()).toBeTruthy();
  const spaces = await page.request.get("/project-manager/api/spaces");
  expect(spaces.ok()).toBeTruthy();
  const home = (await spaces.json())[0];
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post("/project-manager/api/programs", { data: { program_name: "Private program" } });
  expect(program.ok()).toBeTruthy();
  const project = await page.request.post("/project-manager/api/projects", { data: { program_id: (await program.json()).program_id, project_name: "Private project" } });
  expect(project.ok()).toBeTruthy();
  const solution = await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: "Private dashboard solution", version: "1" } });
  expect(solution.ok()).toBeTruthy();
  await page.goto("/project-manager/dashboard");
  await page.locator('[data-dashboard-action="open-config"]').first().click();
  await expect(page.locator("#dashboard-config-modal")).toBeVisible();
  await expect(page.locator("#dashboard-config-solutions")).toContainText("Private dashboard solution");
  return home;
}

test("dashboard table settings clear on sign-out", async ({ page }) => {
  await openPrivateDashboardConfig(page);
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  await expect(page.locator("#dashboard-config-modal")).toBeHidden();
  await expect(page.locator("#dashboard-config-solutions")).toBeEmpty();
});

test("dashboard table settings clear on space switch", async ({ page }) => {
  const home = await openPrivateDashboardConfig(page);
  await page.locator("#space-switcher-trigger").dispatchEvent("click");
  const switched = page.waitForResponse((response) => response.url().endsWith("/api/auth/active-space") && response.request().method() === "POST");
  await page.locator(`#space-switcher-all-list [data-space-switch="${home.space_id}"]`).dispatchEvent("click");
  expect((await switched).ok()).toBeTruthy();
  await expect(page.locator("#dashboard-config-modal")).toBeHidden();
  await expect(page.locator("#dashboard-config-solutions")).toBeEmpty();
});

test("dashboard settings restore focus after cancel and apply", async ({ page }) => {
  await openPrivateDashboardConfig(page);
  const opener = page.locator('#view-dashboard [data-dashboard-action="open-config"]');
  await expect(page.locator('#dashboard-config-section-tabs .tab.active')).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator('#dashboard-config-modal')).toBeHidden();
  await expect(opener).toBeFocused();
  await opener.click();
  await page.locator('[data-dashboard-action="apply-table-config"]').click();
  await expect(page.locator('#dashboard-config-modal')).toBeHidden();
  await expect(opener).toBeFocused();
});
