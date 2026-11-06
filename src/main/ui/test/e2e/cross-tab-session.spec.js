import { expect, test } from "@playwright/test";

test("a refresh for another account clears the old tab without logging out the new account", async ({ page }) => {
  const suffix = `${Date.now()}${Math.random().toString(16).slice(2)}`.slice(0, 14);
  const oldSoeid = `old${suffix}`.slice(0, 20);
  const newSoeid = `new${suffix}`.slice(0, 20);
  const oldProgram = `Private old program ${suffix}`;
  const register = async (target, soeid, displayName) => target.request.post("/project-manager/api/auth/register", {
    data: { soeid, display_name: displayName, password: "Password123" },
  });
  expect((await register(page, oldSoeid, "Original User A")).ok()).toBe(true);
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBe(true);
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBe(true);
  expect((await page.request.post("/project-manager/api/programs", { data: { program_name: oldProgram } })).ok()).toBe(true);
  // Hold live sync and unrelated background requests so the test exercises the
  // write's 401/refresh path instead of a separate request detecting B first.
  await page.routeWebSocket("**/ws**", () => {});
  await page.goto("/project-manager/");
  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.getByText(oldProgram, { exact: false }).first()).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-program").click();
  await page.locator('#program-form [name="program_name"]').fill("Trigger refresh");

  let writes = 0;
  let logouts = 0;
  await page.route("**/project-manager/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/auth/refresh")) return route.continue();
    if (url.pathname.endsWith("/auth/logout")) { logouts += 1; return route.continue(); }
    if (url.pathname.endsWith("/programs") && route.request().method() === "POST") {
      writes += 1;
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "expired" }) });
    }
    return route.abort();
  });
  const replacement = await page.context().newPage();
  expect((await register(replacement, newSoeid, "Replacement User B")).ok()).toBe(true);
  const refresh = page.waitForResponse((response) => response.url().endsWith("/auth/refresh"));
  await page.locator("#program-submit-btn").click();
  expect((await refresh).status()).toBe(409);
  await expect(page.locator("#auth-screen")).toBeVisible();
  await expect(page.locator("#app-shell")).toBeHidden();
  await expect(page.getByText(oldProgram, { exact: false }).first()).toBeHidden();
  expect(writes).toBe(1);
  expect(logouts).toBe(0);
  const current = await replacement.request.get("/project-manager/api/auth/me");
  expect(current.ok()).toBe(true);
  expect((await current.json()).soeid).toBe(newSoeid);
  await replacement.goto("/project-manager/");
  await expect(replacement.locator("#app-shell")).toBeVisible();
  await expect(replacement.locator("#current-user")).toContainText("Replacement User B");
});

for (const scenario of ["replacement", "same session"]) {
  test(`logout notification is scoped to its session: ${scenario}`, async ({ page }) => {
  const soeid = `logout${Date.now()}${Math.random().toString(16).slice(2)}`.slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: { soeid, display_name: "Same User", password: "Password123" },
  });
  expect(register.ok()).toBe(true);
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBe(true);
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBe(true);
  await page.goto("/project-manager/");
  await expect(page.locator("#app-shell")).toBeVisible();
  await page.waitForLoadState("networkidle");
  if (scenario === "replacement") {
    await page.route("**/project-manager/api/**", async (route) => {
      if (route.request().url().endsWith("/auth/logout")) return route.continue();
      await route.abort();
    });
  }
  const other = await page.context().newPage();
  if (scenario === "replacement") {
    const login = await other.request.post("/project-manager/api/auth/login", { data: { soeid, password: "Password123" } });
    expect(login.ok()).toBe(true);
  }
  await other.goto("/project-manager/");
  await expect(other.locator("#app-shell")).toBeVisible();
  await other.evaluate(() => {
    window.logoutStorageSeen = new Promise((resolve) => {
      const onStorage = (event) => {
        if (event.key !== "sipm-auth-logout-v1") return;
        window.removeEventListener("storage", onStorage);
        resolve();
      };
      window.addEventListener("storage", onStorage);
    });
  });
  await expect(page.locator("#app-shell")).toBeVisible();
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  await other.evaluate(() => Promise.race([
    window.logoutStorageSeen,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`No logout storage event: ${localStorage.getItem("sipm-auth-logout-v1")}`)), 5000)),
  ]));
  if (scenario === "replacement") {
    await expect(other.locator("#app-shell")).toBeVisible();
    expect((await other.request.get("/project-manager/api/auth/me")).ok()).toBe(true);
  } else {
    await expect(other.locator("#auth-screen")).toBeVisible();
  }
  });
}
