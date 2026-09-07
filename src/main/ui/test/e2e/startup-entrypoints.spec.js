import { expect, test } from "@playwright/test";

const deferredAssets = /\/js\/routes\/(?:spaces\/(?:interactions|render)|master\/(?:interactions|quickstart))\.js/;

async function registerMember(page, { personal = true } = {}) {
  const soeid = `entry${Date.now()}${Math.random().toString(16).slice(2, 6)}`.slice(0, 24);
  const response = await page.request.post("/project-manager/api/auth/register", {
    data: { soeid, display_name: "Entrypoint User", password: "Password123" },
  });
  expect(response.ok()).toBeTruthy();
  if (personal) {
    const space = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
    expect(space.ok()).toBeTruthy();
    const active = await page.request.post("/project-manager/api/auth/active-space", {
      data: { space_id: (await space.json()).space_id },
    });
    expect(active.ok()).toBeTruthy();
  }
  return soeid;
}

async function recordBindings(page) {
  await page.addInitScript(() => {
    window.startupBindings = {};
    const original = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, ...args) {
      if (this.id) {
        const key = `${this.id}:${type}`;
        window.startupBindings[key] = (window.startupBindings[key] || 0) + 1;
      }
      return original.call(this, type, ...args);
    };
  });
}

for (const path of ["/project-manager/", "/project-manager/tasks-workbench", "/project-manager/reset-password"]) {
  test(`signed-out entrypoint ${path} does not load hidden route assets`, async ({ page }) => {
    const routeRequests = [];
    page.on("request", (request) => {
      if (request.url().includes("/js/routes/")) routeRequests.push(request.url());
    });
    await recordBindings(page);
    await page.goto(path);
    await expect(page.locator(path.endsWith("reset-password") ? "#reset-screen" : "#auth-screen")).toBeVisible();
    expect(routeRequests.filter((url) => deferredAssets.test(url))).toEqual([]);
    expect(routeRequests.filter((url) => /\/routes\/[^/]+\.js/.test(url))).toEqual([]);
    const bindings = await page.evaluate(() => window.startupBindings);
    expect(bindings["login-form:submit"]).toBe(1);
    expect(bindings["reset-form:submit"]).toBe(1);
    expect(bindings["capacity-user-form:submit"]).toBe(1);
    expect(bindings["space-create-modal-form:submit"]).toBeUndefined();
    expect(bindings["tasks-workbench-search:input"]).toBe(1);
  });
}

test("login warms its requested screen while credentials are pending without private data reads", async ({ page }) => {
  const soeid = await registerMember(page);
  const program = await page.request.post("/project-manager/api/programs", { data: { program_name: "Preload Program" } });
  expect(program.ok()).toBeTruthy();
  const logout = await page.request.post("/project-manager/api/auth/logout");
  expect(logout.ok()).toBeTruthy();
  let releaseLogin;
  const loginHeld = new Promise((resolve) => { releaseLogin = resolve; });
  await page.route("**/api/auth/login", async (route) => {
    await loginHeld;
    await route.continue();
  });
  const privateRequests = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.includes("/api/") && !path.includes("/api/auth/")) privateRequests.push(path);
  });
  try {
    await page.goto("/project-manager/");
    await expect(page.locator("#auth-screen")).toBeVisible();
    const moduleResponses = Promise.all([
      page.waitForResponse("**/js/routes/master.js"),
      page.waitForResponse("**/js/routes/spaces/interactions.js"),
      page.waitForResponse("**/js/routes/spaces/render.js"),
    ]);
    await page.locator('#login-form [name="soeid"]').fill(soeid);
    await page.locator('#login-form [name="password"]').fill("Password123");
    await page.locator('#login-form button[type="submit"]').click();
    expect((await moduleResponses).every((response) => response.ok())).toBeTruthy();
    await expect(page.locator('#login-form button[type="submit"]')).toBeDisabled();
    await expect(page.locator("#auth-screen")).toBeVisible();
    expect(privateRequests).toEqual([]);
    releaseLogin();
    await expect(page.locator("#master-table")).toContainText("Preload Program");
    await page.locator("#filter-query").fill("Preload Program");
    await expect(page.locator("#filter-query")).toHaveValue("Preload Program");
    await expect(page.locator("#master-table")).toContainText("Preload Program");
  } finally {
    releaseLogin();
  }
});

test("direct capacity entry binds once, preserves a draft on repeat navigation, and submits once", async ({ page }) => {
  await registerMember(page);
  await recordBindings(page);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/project-manager/team-capacity");
  await expect(page.locator("#capacity-user-list tr[data-soeid]").first()).toBeVisible();
  const name = page.locator('#capacity-user-form [name="display_name"]');
  await name.fill("Unsaved capacity draft");
  for (let i = 0; i < 2; i += 1) {
    await page.locator('.nav-btn[data-view="master"]').click();
    await expect(page.locator("#master-table table")).toBeVisible();
    await page.locator('.nav-btn[data-view="team-capacity"]').click();
    await expect(page.locator("#capacity-user-list tr[data-soeid]").first()).toBeVisible();
  }
  await expect(name).toHaveValue("Unsaved capacity draft");
  await page.locator("#capacity-user-list tr[data-soeid]").first().click();
  let saves = 0;
  await page.route("**/api/users/**", async (route) => {
    if (route.request().method() === "PATCH") saves += 1;
    await route.continue();
  });
  await page.locator('#capacity-user-form [name="capacity_fte_month"]').fill("0.75");
  await page.locator('#capacity-user-form button[type="submit"]').click();
  await expect(page.locator("#capacity-user-form-status")).toContainText("Saved member");
  expect(saves).toBe(1);
  const bindings = await page.evaluate(() => window.startupBindings);
  expect(bindings["capacity-user-form:submit"]).toBe(1);
  expect(bindings["capacity-reload:click"]).toBe(1);
  expect(errors).toEqual([]);
});

test("direct Tasks entry keeps filters and one binding across back and forward", async ({ page }) => {
  await registerMember(page);
  await recordBindings(page);
  await page.goto("/project-manager/tasks-workbench");
  const search = page.locator("#tasks-workbench-search");
  await expect(search).toBeVisible();
  await expect(page.locator("#tasks-workbench-table")).toContainText("No tasks match");
  await expect.poll(() => page.evaluate(() => window.startupBindings["tasks-workbench-search:input"])).toBe(1);
  await search.fill("preserved query");
  await expect.poll(() => page.evaluate(() => Object.values(localStorage).some((value) => value.includes("preserved query")))).toBe(true);
  await page.locator('.nav-btn[data-view="master"]').click();
  await expect(page.locator("#master-table table")).toBeVisible();
  await page.goBack();
  await expect(search).toBeVisible();
  await expect(search).toHaveValue("preserved query");
  await page.goForward();
  await page.locator('.nav-btn[data-view="tasks-workbench"]').click();
  await expect(search).toHaveValue("preserved query");
  expect(await page.evaluate(() => window.startupBindings["tasks-workbench-search:input"])).toBe(1);
});

test("Tasks accepts a query while its first renderer import is still pending", async ({ page }) => {
  await registerMember(page);
  let releaseModule;
  const heldModule = new Promise((resolve) => { releaseModule = resolve; });
  await page.route("**/js/routes/tasks-workbench.js", async (route) => {
    await heldModule;
    await route.continue();
  });
  await page.goto("/project-manager/");
  await expect(page.locator("#master-table table")).toBeVisible();
  await page.locator('.nav-btn[data-view="tasks-workbench"]').click();
  const search = page.locator("#tasks-workbench-search");
  await search.fill("query entered before renderer");
  await expect.poll(() => page.evaluate(() => Object.values(localStorage).some((value) => value.includes("query entered before renderer")))).toBe(true);
  releaseModule();
  await expect(page.locator("#tasks-workbench-table")).toContainText("No tasks match");
  await expect(search).toHaveValue("query entered before renderer");
});

test("Deliverables creates and binds its query control only after its renderer is ready", async ({ page }) => {
  await registerMember(page);
  let releaseModule;
  const heldModule = new Promise((resolve) => { releaseModule = resolve; });
  await page.route("**/js/routes/master.js", async (route) => {
    await heldModule;
    await route.continue();
  });
  await page.goto("/project-manager/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.locator("#filter-query")).toHaveCount(0);
  await expect(page.locator("#master-quickstart")).toBeHidden();
  await expect(page.locator("#master-table tr")).toHaveCount(0);
  releaseModule();
  const search = page.locator("#filter-query");
  await expect(search).toBeVisible();
  await search.fill("project:unmatched");
  await search.press("Enter");
  await expect(search).toHaveValue("project:unmatched");
  expect(await page.evaluate(() => Object.values(localStorage).some((value) => value.includes("project:unmatched")))).toBe(true);
});

test("Team Capacity preserves draft input while its first renderer import is pending", async ({ page }) => {
  await registerMember(page);
  let releaseModule;
  const heldModule = new Promise((resolve) => { releaseModule = resolve; });
  await page.route("**/js/routes/team-capacity.js", async (route) => {
    await heldModule;
    await route.continue();
  });
  await page.goto("/project-manager/");
  await expect(page.locator("#master-table table")).toBeVisible();
  await page.locator('.nav-btn[data-view="team-capacity"]').click();
  const name = page.locator('#capacity-user-form [name="display_name"]');
  await name.fill("Draft entered before renderer");
  const filter = page.locator("#capacity-name-filter");
  await filter.fill("Entrypoint");
  await expect.poll(() => page.evaluate(() => Object.values(localStorage).some((value) => value.includes('"name_filter":"Entrypoint"')))).toBe(true);
  releaseModule();
  await expect(page.locator("#capacity-user-list tr[data-soeid]").first()).toBeVisible();
  await expect(name).toHaveValue("Draft entered before renderer");
  await expect(filter).toHaveValue("Entrypoint");
  await page.locator("#capacity-clear-filters").click();
  await expect(filter).toHaveValue("");
  await expect(name).toHaveValue("Draft entered before renderer");
});

test("lobby direct entry binds governance before the first action and keeps shared forms ready", async ({ page }) => {
  await registerMember(page, { personal: false });
  await recordBindings(page);
  await page.goto("/project-manager/spaces");
  await expect(page.locator("#space-governance-shell")).toContainText("Space Access");
  await expect(page.locator('[data-space-action="refresh-lobby-data"]')).toBeVisible();
  await page.locator('[data-space-action="refresh-lobby-data"]').click();
  const bindings = await page.evaluate(() => window.startupBindings);
  expect(bindings["space-create-modal-form:submit"]).toBe(1);
  expect(bindings["space-member-modal-form:submit"]).toBe(1);
  expect(bindings["project-form:submit"]).toBe(1);
  expect(bindings["solution-form:submit"]).toBe(1);
  expect(bindings["task-form:submit"]).toBe(1);
});

test("public dashboard loads its renderer without private route controllers", async ({ page }) => {
  const requests = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.route("**/api/public/program-dashboard/startup-fixture", (route) => route.fulfill({
    json: { space: { space_id: "public-fixture", space_name: "Public startup fixture" }, programs: [], projects: [], solutions: [], phases: [] },
  }));
  await page.goto("/project-manager/public/program-dashboard/startup-fixture");
  await expect(page.locator("#program-dashboard-root")).not.toContainText("Loading dashboard...");
  await expect(page.locator("#program-dashboard-root")).toBeVisible();
  expect(requests.some((url) => url.includes("/routes/program-dashboard.js"))).toBe(true);
  expect(requests.filter((url) => deferredAssets.test(url))).toEqual([]);
  expect(requests.filter((url) => url.includes("/api/auth/"))).toEqual([]);
});

test("first Create from Calendar and task drawer shortcuts work without visiting Deliverables", async ({ page }) => {
  await registerMember(page);
  const programResponse = await page.request.post("/project-manager/api/programs", { data: { program_name: "Entrypoint Program" } });
  expect(programResponse.ok()).toBe(true);
  const program = await programResponse.json();
  const projectResponse = await page.request.post("/project-manager/api/projects", { data: { program_id: program.program_id, project_name: "Entrypoint Project" } });
  expect(projectResponse.ok()).toBe(true);
  const project = await projectResponse.json();
  const solutionResponse = await page.request.post(`/project-manager/api/projects/${project.project_id}/solutions`, { data: { solution_name: "Entrypoint Solution", version: "1.0" } });
  expect(solutionResponse.ok(), await solutionResponse.text()).toBe(true);
  const solution = await solutionResponse.json();
  const taskResponse = await page.request.post(`/project-manager/api/solutions/${solution.solution_id}/tasks`, { data: { task_name: "Entrypoint Task" } });
  expect(taskResponse.ok()).toBe(true);
  const task = await taskResponse.json();
  await page.goto("/project-manager/calendar");
  await expect(page.locator("#calendar-grid .calendar-cell[data-day]").first()).toBeVisible();
  await expect(page.locator(`#calendar-filter-project option[value="${project.project_id}"]`)).toHaveCount(1);
  await page.locator("#topbar-create-toggle").click();
  await page.locator("#topbar-create-project").click();
  await expect(page.locator("#project-modal")).toBeVisible();
  await page.locator('#project-form [name="program_id"]').selectOption(program.program_id);
  await page.locator('#project-form [name="project_name"]').fill("Created from Calendar");
  await page.locator('#project-form [name="sponsor"]').fill("Entrypoint Sponsor");
  expect(await page.locator("#project-form").evaluate((form) => form.checkValidity())).toBe(true);
  const created = page.waitForResponse((response) => response.url().endsWith("/api/projects") && response.request().method() === "POST");
  await page.locator("#project-submit-btn").click();
  expect((await created).ok()).toBe(true);
  await expect(page.locator("#project-form-status")).toContainText("Created project");
  await page.keyboard.press("Escape");
  await expect(page.locator("#project-modal")).toBeHidden();
  const month = page.locator("#calendar-month");
  const previous = await month.inputValue();
  await page.locator("#calendar-next").click();
  await expect(month).not.toHaveValue(previous);
  await page.locator("#calendar-prev").click();
  await expect(month).toHaveValue(previous);
  await page.locator('.nav-btn[data-view="tasks-workbench"]').click();
  const row = page.locator(`#tasks-workbench-table tr[data-id="${task.task_id}"]`);
  await expect(row).toBeVisible();
  await row.locator("strong").click();
  await expect(page.locator("#tasks-workbench-drawer")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#tasks-workbench-drawer")).toBeHidden();
  await expect(row).toBeFocused();
  await page.keyboard.press("e");
  await expect(page.locator('#tasks-workbench-form [name="task_name"]')).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(row).toBeFocused();
});

test("developer direct links load their routes with shared forms ready", async ({ page }) => {
  await registerMember(page);
  await recordBindings(page);
  const preferences = await page.request.patch("/project-manager/api/users/me/preferences", { data: { developer_mode_enabled: true } });
  expect(preferences.ok()).toBe(true);
  const requests = [];
  page.on("request", (request) => requests.push(request.url()));
  for (const route of ["my-work", "repositories"]) {
    await page.goto(`/project-manager/${route}`);
    await expect(page.locator(`#view-${route}`)).toHaveClass(/active/);
    await expect(page.locator("#app-shell")).toBeVisible();
    await expect.poll(() => requests.some((url) => url.includes(`/routes/${route}.js`))).toBe(true);
    expect(await page.evaluate(() => window.startupBindings["task-form:submit"])).toBe(1);
  }
});

test("a failed governance controller load recovers on reload without duplicate form bindings", async ({ page }) => {
  await registerMember(page, { personal: false });
  await recordBindings(page);
  const failed = page.waitForEvent("requestfailed", { predicate: (request) => request.url().endsWith("/js/routes/spaces/interactions.js") });
  await page.route("**/js/routes/spaces/interactions.js", (route) => route.abort(), { times: 1 });
  await page.goto("/project-manager/spaces");
  await failed;
  await expect(page.locator("#app-shell")).toBeVisible();
  expect(await page.evaluate(() => window.startupBindings["space-create-modal-form:submit"])).toBeUndefined();
  await page.reload();
  await expect(page.locator("#space-governance-shell")).toContainText("Space Access");
  expect(await page.evaluate(() => window.startupBindings["space-create-modal-form:submit"])).toBe(1);
});

test("Spaces and Platform Access reuse governance forms across route entries", async ({ page }) => {
  await registerMember(page);
  await recordBindings(page);
  // Exercise global-admin shell wiring with a local response fixture; the
  // actual permission enforcement remains covered by backend auth tests.
  await page.route("**/api/auth/bootstrap", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, is_global_admin: true } } });
  });
  await page.route("**/api/users/global-admins?*", (route) => route.fulfill({ json: [] }));
  await page.goto("/project-manager/");
  await expect(page.locator("#master-table table")).toBeVisible();
  await page.locator('.nav-btn[data-view="spaces"]').click();
  await expect(page.locator('[data-space-action="open-create-space-modal"]').first()).toBeVisible();
  await page.evaluate(() => {
    history.pushState(null, "", "/project-manager/access");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page.locator("#current-route-label")).toHaveText("Platform Access");
  await expect(page.locator('[data-space-action="open-create-space-modal"]').first()).toBeVisible();
  await page.locator('[data-space-action="open-create-space-modal"]').first().click();
  await expect(page.locator("#space-create-modal")).toBeVisible();
  await page.locator("#space-create-modal-close").click();
  await expect(page.locator("#space-create-modal")).toBeHidden();
  await page.goBack();
  await expect(page.locator("#current-route-label")).toHaveText("Space Governance");
  const bindings = await page.evaluate(() => window.startupBindings);
  expect(bindings["space-create-modal-form:submit"]).toBe(1);
  expect(bindings["space-member-modal-form:submit"]).toBe(1);
});
