import { expect, test } from "@playwright/test";

test("a refreshed program save completes once and stays guarded while pending", async ({ page }) => {
  const soeid = `refresh${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", {
    data: { soeid, display_name: "Refresh Test", password: "Password123" },
  })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", {
    data: { space_id: (await personal.json()).space_id },
  })).ok()).toBeTruthy();
  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();

  let calls = 0;
  let releaseRetry;
  const retryHeld = new Promise((resolve) => { releaseRetry = resolve; });
  await page.route("**/project-manager/api/programs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    calls += 1;
    if (calls === 1) {
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Expired access token" }) });
    } else if (calls === 2) {
      await retryHeld;
      await route.continue();
    } else {
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Duplicate submission" }) });
    }
  });
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-program").click();
  await page.locator('#program-form [name="program_name"]').fill("Refresh save regression");
  await page.locator("#program-submit-btn").click();
  await expect.poll(() => calls).toBe(2);
  await page.locator("#program-form").dispatchEvent("submit");
  await page.waitForTimeout(200);
  const callsWhilePending = calls;
  releaseRetry();
  await expect(page.locator("#program-submit-btn")).toBeEnabled();
  const savedId = await page.locator('#program-form [name="program_id"]').inputValue();
  expect(callsWhilePending).toBe(2);
  expect(savedId).not.toBe("");
  await expect(page.locator("#program-form-status")).toContainText("Created program");
});
