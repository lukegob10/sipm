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

test("password recovery provides a visible return to sign in", async ({ page }) => {
  await page.goto("/project-manager/reset-password");
  await expect(page.locator("#reset-screen")).toBeVisible();
  await expect(page.locator("#reset-back-link")).toHaveText("Back to sign in");
  await page.locator("#reset-back-link").click();
  await expect(page.locator("#auth-screen")).toBeVisible();
});


test("startup stays visible and recovers to sign in when session bootstrap fails", async ({ page }) => {
  await page.route("**/project-manager/api/auth/me", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Session store unavailable" }),
    });
  });

  await page.goto("/");
  await expect(page.locator("#startup-screen")).toBeVisible();
  await expect(page.locator("#auth-screen")).toBeVisible();
  await expect(page.locator("#auth-notice")).toContainText("could not finish opening your session");
  await expect(page.locator("#startup-screen")).toBeHidden();
});


test("local login becomes usable without follow-up context requests", async ({ page }) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const soeid = `login${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: {
      soeid,
      display_name: "Login Performance User",
      password: "Password123",
    },
  });
  expect(register.ok()).toBeTruthy();
  const logout = await page.request.post("/project-manager/api/auth/logout");
  expect(logout.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.locator("#auth-screen")).toBeVisible();

  const loginRequests = [];
  const redundantContextRequests = [];
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname === "/project-manager/api/auth/login") loginRequests.push(pathname);
    if (
      pathname === "/project-manager/api/users/me/preferences"
      || pathname === "/project-manager/api/spaces"
      || pathname === "/project-manager/api/auth/active-space"
    ) {
      redundantContextRequests.push(pathname);
    }
  });

  await page.locator('#login-form input[name="soeid"]').fill(soeid);
  await page.locator('#login-form input[name="password"]').fill("Password123");
  await page.locator('#login-form input[name="password"]').press("Enter");

  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.locator("#view-spaces")).toHaveClass(/active/);
  expect(loginRequests).toHaveLength(1);
  expect(redundantContextRequests).toEqual([]);
});


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
