import { expect, test } from "@playwright/test";

test("repository retry keeps keyboard focus and search editable during loading", async ({ page }) => {
  const soeid = `repofocus${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "Repository User", password: "Password123" } })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  expect((await page.request.patch("/project-manager/api/users/me/preferences", { data: { developer_mode_enabled: true } })).ok()).toBeTruthy();
  let failRequests = true; let release;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/repository-inventory", async (route) => {
    if (failRequests) await route.fulfill({ status: 503, json: { detail: "Inventory offline" } });
    else { await held; await route.fulfill({ json: [] }); }
  });
  try {
    await page.goto("/project-manager/repositories");
    const root = page.locator("#repository-inventory-root");
    await expect(root).toContainText("Repositories unavailable");
    await expect(root).not.toContainText("No repositories match this search");
    await expect(root).not.toContainText("0 unique repositories");
    failRequests = false;
    const retry = root.getByRole("button", { name: "Try again" });
    await retry.focus(); await page.keyboard.press("Enter");
    await expect(root.locator("[data-repository-loading-focus]")).toBeFocused();
    const search = root.getByRole("searchbox", { name: "Search repositories and entities" });
    await search.focus(); await search.fill("draft query");
    await expect(search).toBeFocused();
    release();
    await expect(root).toContainText("No repositories attached");
    await expect(search).toBeFocused();
    await expect(search).toHaveValue("draft query");
  } finally { release(); }
});
