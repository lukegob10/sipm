import { expect, test } from "@playwright/test";

test("roster reports loading and failure, then supports keyboard selection", async ({ page }) => {
  const soeid = `roster${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "Roster User", password: "Password123" } })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  let release;
  let failRequests = true;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/users?active_only=true", async (route) => {
    if (failRequests) {
      await held;
      await route.fulfill({ status: 503, json: { detail: "Roster temporarily unavailable" } });
    } else {
      await route.continue();
    }
  });
  try {
    await page.goto("/project-manager/team-capacity");
    const roster = page.locator("#capacity-user-list");
    await expect(roster).toContainText("Loading roster...");
    await expect(roster).not.toContainText("No users found in the active space");
    release();
    await expect(roster).toContainText("Roster unavailable. Try reloading.");
    await expect(roster).toContainText("Team summary unavailable.");
    failRequests = false;
    await page.locator("#capacity-reload").click();
    const member = roster.getByRole("button", { name: `Select Roster User (${soeid})` });
    await expect(member).toBeVisible();
    await member.focus();
    await page.keyboard.press("Enter");
    await expect(member).toBeFocused();
    await expect(member).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('#capacity-user-form [name="soeid"]')).toHaveValue(soeid);
  } finally {
    release();
  }
});
