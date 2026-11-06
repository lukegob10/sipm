import { expect, test } from "@playwright/test";

async function chooseCsvFile(page, trigger, file) {
  const pending = page.waitForEvent("filechooser");
  await page.locator(trigger).click();
  await (await pending).setFiles(file);
}


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
  await page.route("**/project-manager/api/auth/bootstrap", async (route) => {
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
      pathname === "/project-manager/api/auth/bootstrap"
      || pathname === "/project-manager/api/users/me/preferences"
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

for (const scenario of [
  { name: "deliverables", path: "/project-manager/", view: "master", developerMode: false },
  { name: "deep link", path: "/project-manager/team-capacity", view: "team-capacity", developerMode: false },
  { name: "developer landing", path: "/project-manager/", view: "my-work", developerMode: true },
]) {
  test(`valid session reopening preserves ${scenario.name} with one context request`, async ({ page }) => {
    await loadLocalAuthedApp(page);
    const preferences = await page.request.patch("/project-manager/api/users/me/preferences", {
      data: { developer_mode_enabled: scenario.developerMode },
    });
    expect(preferences.ok()).toBeTruthy();
    const sessionCookies = (cookies) => cookies.filter((cookie) => ["access_token", "refresh_token"].includes(cookie.name));
    const before = sessionCookies(await page.context().cookies());
    const contextPaths = new Set([
      "/auth/bootstrap", "/auth/me", "/auth/login", "/auth/refresh", "/spaces", "/auth/active-space", "/users/me/preferences",
    ].map((path) => `/project-manager/api${path}`));
    const requests = [];
    page.on("request", (request) => {
      const path = new URL(request.url()).pathname;
      if (contextPaths.has(path)) requests.push(path);
    });
    await page.goto(scenario.path);
    await expect(page.locator("#app-shell")).toBeVisible();
    await expect(page.locator(`#view-${scenario.view}`)).toHaveClass(/active/);
    expect(requests).toEqual(["/project-manager/api/auth/bootstrap"]);
    expect(sessionCookies(await page.context().cookies())).toEqual(before);
  });
}

test("CSV import does not duplicate or close a newly opened upload modal", async ({ page }) => {
  await loadLocalAuthedApp(page);
  let releaseImport;
  let requests = 0;
  const held = new Promise((resolve) => { releaseImport = resolve; });
  await page.route("**/project-manager/api/projects/import", async (route) => {
    requests += 1;
    await held;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ created: 1, updated: 0, errors: [] }) });
  });
  await page.locator("#csv-actions-toggle").click();
  await page.locator("#projects-upload").click();
  await chooseCsvFile(page, "#csv-dropzone", { name: "projects.csv", mimeType: "text/csv", buffer: Buffer.from("project_name\nExample") });
  await page.locator("#csv-submit-upload").click();
  await expect.poll(() => requests).toBe(1);
  await expect(page.locator("#csv-submit-upload")).toBeDisabled();
  await page.locator("#csv-submit-upload").dispatchEvent("click");
  await expect(page.locator("#csv-submit-upload")).toBeDisabled();
  expect(requests).toBe(1);
  await page.locator("#csv-upload-close").click();
  await page.locator("#csv-actions-toggle").click();
  await page.locator("#solutions-upload").click();
  await expect(page.locator("#csv-upload-title")).toHaveText("Upload Solutions CSV");
  releaseImport();
  await expect(page.locator("#projects-import-result")).toContainText("Created 1");
  await expect(page.locator("#csv-upload-modal")).toBeVisible();
  await expect(page.locator("#csv-upload-title")).toHaveText("Upload Solutions CSV");
  expect(requests).toBe(1);
});

test("a CSV export does not download after sign-out", async ({ page }) => {
  await loadLocalAuthedApp(page);
  let releaseExport;
  let receivedExport;
  const started = new Promise((resolve) => { receivedExport = resolve; });
  const held = new Promise((resolve) => { releaseExport = resolve; });
  await page.evaluate(() => {
    window.csvObjectUrlsCreated = 0;
    const original = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob) => { window.csvObjectUrlsCreated += 1; return original(blob); };
  });
  await page.route("**/project-manager/api/projects/export", async (route) => {
    receivedExport();
    await held;
    await route.fulfill({ status: 200, contentType: "text/csv", body: "project_name\nprivate" });
  });
  await page.locator("#csv-actions-toggle").click();
  await page.locator("#projects-download").click();
  await started;
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  const response = page.waitForResponse("**/project-manager/api/projects/export");
  releaseExport();
  await response;
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.csvObjectUrlsCreated)).toBe(0);
});

test("a CSV export downloads in the originating session", async ({ page }) => {
  await loadLocalAuthedApp(page);
  await page.route("**/project-manager/api/projects/export", (route) => route.fulfill({
    status: 200, contentType: "text/csv", body: "project_name\nExample",
  }));
  await page.locator("#csv-actions-toggle").click();
  const download = page.waitForEvent("download");
  await page.locator("#projects-download").click();
  expect((await download).suggestedFilename()).toBe("projects.csv");
  await expect(page.locator("#projects-import-result")).toContainText("Downloaded projects.csv");
});

test("CSV import reports when the follow-up refresh fails", async ({ page }) => {
  await loadLocalAuthedApp(page);
  await page.route("**/project-manager/api/projects/import", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ created: 1, updated: 0, errors: [] }),
  }));
  await page.route("**/project-manager/api/projects", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Refresh unavailable" }),
  }));
  await page.locator("#csv-actions-toggle").click();
  await page.locator("#projects-upload").click();
  await chooseCsvFile(page, "#csv-dropzone", { name: "projects.csv", mimeType: "text/csv", buffer: Buffer.from("project_name\nExample") });
  await page.locator("#csv-submit-upload").click();
  await expect(page.locator("#csv-upload-status")).toContainText("Refresh failed");
  await expect(page.locator("#csv-upload-status")).toContainText("Created 1");
  await expect(page.locator("#csv-upload-modal")).toBeVisible();
  await expect(page.locator("#csv-upload-file-name")).toHaveText("No file selected");
});

test("roster import reports a failed capacity refresh", async ({ page }) => {
  await loadLocalAuthedApp(page);
  await page.goto("/project-manager/team-capacity");
  await expect(page.locator("#capacity-user-list table").first()).toBeVisible();
  await expect(page.locator("#capacity-user-list")).not.toContainText("Refreshing...");
  await page.route("**/project-manager/api/users/import", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ created: 1, updated: 0, errors: [] }),
  }));
  await page.route((url) => url.pathname.endsWith("/api/users") && url.searchParams.get("active_only") === "true", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Capacity unavailable" }),
  }));
  await chooseCsvFile(page, "#roster-upload", { name: "roster.csv", mimeType: "text/csv", buffer: Buffer.from("soeid,display_name\nuser,User") });
  await expect(page.locator("#roster-import-result")).toContainText("Refresh failed");
  await expect(page.locator("#roster-import-result")).toContainText("Created 1");
});

test("team capacity reset clears the member form without recursive resets", async ({ page }) => {
  await loadLocalAuthedApp(page);
  await page.goto("/project-manager/team-capacity");
  const form = page.locator("#capacity-user-form");
  await expect(form).toBeVisible();
  await form.locator('[name="display_name"]').fill("Unfinished member");
  await form.locator('[name="team_tag"]').fill("Draft team");
  await form.locator('[name="capacity_fte_month"]').fill("0.5");
  await form.locator('button[type="reset"]').click();
  await expect(form.locator('[name="display_name"]')).toHaveValue("");
  await expect(form.locator('[name="team_tag"]')).toHaveValue("");
  await expect(form.locator('[name="capacity_fte_month"]')).toHaveValue("1.00");
});

test("team capacity draft does not carry into another login", async ({ page }) => {
  await loadLocalAuthedApp(page);
  await page.goto("/project-manager/team-capacity");
  const form = page.locator("#capacity-user-form");
  await expect(form).toBeVisible();
  await form.locator('[name="display_name"]').fill("Previous session draft");
  await form.locator('[name="team_tag"]').fill("Previous team");
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  const soeid = `other${Date.now()}`.slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "Second user", password: "Password123" } });
  expect(register.ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  const activate = await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } });
  expect(activate.ok()).toBeTruthy();
  await page.locator('#login-form [name="soeid"]').fill(soeid);
  await page.locator('#login-form [name="password"]').fill("Password123");
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page.locator("#app-shell")).toBeVisible();
  await page.locator('.nav-btn[data-view="team-capacity"]').dispatchEvent("click");
  await expect(form).toBeVisible();
  await expect(form.locator('[name="display_name"]')).toHaveValue("");
  await expect(form.locator('[name="team_tag"]')).toHaveValue("");
});

test("deliverable editor is cleared on sign-out", async ({ page }) => {
  await loadLocalAuthedApp(page);
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-program").click();
  await expect(page.locator("#program-modal")).toBeVisible();
  await page.locator('#program-form [name="program_name"]').fill("Private unfinished program");
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  await expect(page.locator("#program-modal")).toHaveClass(/hidden/);
  await expect(page.locator('#program-form [name="program_name"]')).toHaveValue("");
});

test("an old program save cannot block or unlock a new session's save", async ({ page }) => {
  await loadLocalAuthedApp(page);
  let releaseOld;
  let releaseNew;
  let finishOld;
  let calls = 0;
  const oldHeld = new Promise((resolve) => { releaseOld = resolve; });
  const newHeld = new Promise((resolve) => { releaseNew = resolve; });
  const oldCompleted = new Promise((resolve) => { finishOld = resolve; });
  await page.route("**/project-manager/api/programs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    calls += 1;
    const old = calls === 1;
    await (old ? oldHeld : newHeld);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ program_id: old ? "old" : "new", program_name: old ? "Old" : "New" }) });
    if (old) finishOld();
  });
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-program").click();
  await page.locator('#program-form [name="program_name"]').fill("Old");
  await page.locator("#program-submit-btn").click();
  await expect.poll(() => calls).toBe(1);
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  const soeid = `new${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "New user", password: "Password123" } })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.locator('#login-form [name="soeid"]').fill(soeid);
  await page.locator('#login-form [name="password"]').fill("Password123");
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page.locator("#app-shell")).toBeVisible();
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-program").click();
  await page.locator('#program-form [name="program_name"]').fill("New");
  await page.locator("#program-submit-btn").click();
  await expect.poll(() => calls).toBe(2);
  releaseOld();
  await oldCompleted;
  await page.waitForTimeout(100);
  await expect(page.locator("#program-submit-btn")).toBeDisabled();
  await expect(page.locator("#program-form")).toHaveAttribute("aria-busy", "true");
  releaseNew();
  await expect(page.locator("#program-submit-btn")).toBeEnabled();
});

test("late documents from a prior solution do not replace the current solution", async ({ page }) => {
  const { programId } = await loadLocalAuthedApp(page);
  const projectResponse = await page.request.post("/project-manager/api/projects", { data: { program_id: programId, project_name: "Document race project" } });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json();
  const firstResponse = await page.request.post(`/project-manager/api/projects/${project.project_id}/solutions`, { data: { solution_name: "First solution", version: "1.0" } });
  const secondResponse = await page.request.post(`/project-manager/api/projects/${project.project_id}/solutions`, { data: { solution_name: "Second solution", version: "1.0" } });
  expect(firstResponse.ok()).toBeTruthy();
  expect(secondResponse.ok()).toBeTruthy();
  const first = await firstResponse.json();
  const second = await secondResponse.json();
  let releaseFirst;
  let firstStarted;
  const started = new Promise((resolve) => { firstStarted = resolve; });
  const held = new Promise((resolve) => { releaseFirst = resolve; });
  await page.route(`**/api/solutions/${first.solution_id}/documents`, async (route) => {
    firstStarted();
    await held;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ document_id: "old", filename: "old-private.txt", size_bytes: 1 }]) });
  });
  await page.route(`**/api/solutions/${second.solution_id}/documents`, (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify([{ document_id: "new", filename: "current.txt", size_bytes: 1 }]),
  }));
  await page.goto("/project-manager/");
  await page.locator(`[data-action="edit"][data-type="solution"][data-id="${first.solution_id}"]`).first().click();
  await started;
  await page.locator("#solution-modal-close").click();
  await page.locator(`[data-action="edit"][data-type="solution"][data-id="${second.solution_id}"]`).first().click();
  await page.locator('#solution-modal [data-tab="documents"]').click();
  await expect(page.locator("#solution-documents-list")).toContainText("current.txt");
  releaseFirst();
  await page.waitForTimeout(300);
  await expect(page.locator("#solution-documents-list")).toContainText("current.txt");
  await expect(page.locator("#solution-documents-list")).not.toContainText("old-private.txt");
});

test("late solution documents are discarded after sign-out", async ({ page }) => {
  const { programId } = await loadLocalAuthedApp(page);
  const projectResponse = await page.request.post("/project-manager/api/projects", { data: { program_id: programId, project_name: "Document sign-out project" } });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json();
  const solutionResponse = await page.request.post(`/project-manager/api/projects/${project.project_id}/solutions`, { data: { solution_name: "Private solution", version: "1.0" } });
  expect(solutionResponse.ok()).toBeTruthy();
  const solution = await solutionResponse.json();
  let release;
  let markStarted;
  const started = new Promise((resolve) => { markStarted = resolve; });
  const held = new Promise((resolve) => { release = resolve; });
  await page.route(`**/api/solutions/${solution.solution_id}/documents`, async (route) => {
    markStarted();
    await held;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ document_id: "old", filename: "private.txt", size_bytes: 1 }]) });
  });
  await page.goto("/project-manager/");
  await page.locator(`[data-action="edit"][data-type="solution"][data-id="${solution.solution_id}"]`).first().click();
  await started;
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  release();
  await page.waitForTimeout(300);
  await expect(page.locator("#solution-documents-list")).toBeEmpty();
});

test("a delayed unauthorized write is not replayed in a new login", async ({ page }) => {
  await loadLocalAuthedApp(page);
  let releaseOld;
  let oldFinished;
  let writes = 0;
  let refreshes = 0;
  const held = new Promise((resolve) => { releaseOld = resolve; });
  const finished = new Promise((resolve) => { oldFinished = resolve; });
  await page.route("**/project-manager/api/auth/refresh", async (route) => {
    refreshes += 1;
    await route.continue();
  });
  await page.route("**/project-manager/api/programs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    writes += 1;
    if (writes === 1) {
      await held;
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Old session expired" }) });
      oldFinished();
    } else {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ program_id: "unexpected", program_name: "Old" }) });
    }
  });
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-program").click();
  await page.locator('#program-form [name="program_name"]').fill("Old session write");
  await page.locator("#program-submit-btn").click();
  await expect.poll(() => writes).toBe(1);
  await page.locator("#logout-btn").dispatchEvent("click");
  await expect(page.locator("#auth-screen")).toBeVisible();
  const soeid = `retry${Date.now()}`.slice(0, 20);
  expect((await page.request.post("/project-manager/api/auth/register", { data: { soeid, display_name: "New user", password: "Password123" } })).ok()).toBeTruthy();
  const personal = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post("/project-manager/api/auth/active-space", { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.locator('#login-form [name="soeid"]').fill(soeid);
  await page.locator('#login-form [name="password"]').fill("Password123");
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page.locator("#app-shell")).toBeVisible();
  refreshes = 0;
  releaseOld();
  await finished;
  await page.waitForTimeout(300);
  expect(refreshes).toBe(0);
  expect(writes).toBe(1);
});
