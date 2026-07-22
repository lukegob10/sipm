import { expect, test } from "@playwright/test";

async function loadLocalAuthedApp(page) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const soeid = `responsive${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: {
      soeid,
      display_name: "Responsive Framework User",
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

  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}

async function expectNoDocumentOverflow(page) {
  await expect.poll(() => page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
  }))).toEqual(expect.objectContaining({
    viewport: await page.evaluate(() => window.innerWidth),
    documentWidth: await page.evaluate(() => window.innerWidth),
  }));
}

test("compact shell keeps every member route and session action reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loadLocalAuthedApp(page);
  await expect(page.locator(".view > .product-route-panel")).toHaveCount(14);
  await expect(page.locator(".view .route-title")).toHaveCount(14);

  const routes = [
    ["master", "Deliverables"],
    ["tasks-workbench", "Tasks"],
    ["pm-dashboard", "PM Command Center"],
    ["dashboard", "Dashboard"],
    ["program-dashboard", "Program Dashboard"],
    ["kanban", "Kanban"],
    ["calendar", "Calendar"],
    ["gantt", "Roadmap"],
    ["team-capacity", "Team Capacity"],
    ["spaces", "Space Governance"],
  ];

  for (const [view, title] of routes) {
    await page.locator("#shell-nav-toggle").click();
    await expect(page.locator("#app-navigation")).toBeInViewport();
    await page.locator(`.nav-btn[data-view="${view}"]`).click();
    await expect(page.locator(`#view-${view === "spaces" ? "spaces" : view}`)).toHaveClass(/active/);
    await expect(page.locator(`#view-${view === "spaces" ? "spaces" : view} .route-title`)).toHaveText(title);
    await expect(page.locator("#shell-nav-toggle")).toHaveAttribute("aria-expanded", "false");
    if (view === "tasks-workbench") {
      await expect(page.locator("#tasks-workbench-drawer")).toBeHidden();
    }
    await expectNoDocumentOverflow(page);
  }

  await page.goto("/project-manager/calendar");
  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.locator("#calendar-agenda")).toBeVisible();
  await expect(page.locator("#calendar-grid")).toBeHidden();

  await page.locator("#account-menu-toggle").click();
  await expect(page.locator("#account-menu-panel")).toBeVisible();
  await expect(page.locator("#preferences-open")).toBeVisible();
  await expect(page.locator("#completed-visibility-toggle")).toHaveCount(0);
  await expect(page.locator("#theme-toggle")).toHaveCount(0);
  await expect(page.locator("#logout-btn")).toBeVisible();
});

test("tablet shell uses the same deliberate drawer contract", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await loadLocalAuthedApp(page);

  await expect(page.locator("#shell-nav-toggle")).toBeVisible();
  await page.locator("#shell-nav-toggle").click();
  await expect(page.locator("#app-navigation")).toBeInViewport();
  await page.locator('.nav-btn[data-view="program-dashboard"]').click();
  await expect(page.locator("#view-program-dashboard")).toHaveClass(/active/);
  await expectNoDocumentOverflow(page);
});

test("desktop route frames remain aligned at compact and wide widths", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await loadLocalAuthedApp(page);

  const routes = [
    ["master", "Deliverables"],
    ["tasks-workbench", "Tasks"],
    ["pm-dashboard", "PM Command Center"],
    ["dashboard", "Dashboard"],
    ["program-dashboard", "Program Dashboard"],
    ["kanban", "Kanban"],
    ["calendar", "Calendar"],
    ["gantt", "Roadmap"],
    ["team-capacity", "Team Capacity"],
    ["spaces", "Space Governance"],
  ];

  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const mainPadding = await page.locator("main").evaluate((element) => {
      const styles = getComputedStyle(element);
      return {
        left: styles.paddingLeft,
        right: styles.paddingRight,
      };
    });
    expect(mainPadding).toEqual({ left: "12px", right: "20px" });

    for (const [view, title] of routes) {
      await page.locator(`.nav-btn[data-view="${view}"]`).click();
      await expect(page.locator(`#view-${view} .route-title`)).toHaveText(title);
      await expect(page.locator(`.nav-btn[data-view="${view}"]`)).toHaveAttribute("aria-current", "page");
      await expectNoDocumentOverflow(page);
    }
  }
});

test("ultrawide shell and dashboard use the full workspace width", async ({ page }) => {
  await page.setViewportSize({ width: 2560, height: 900 });
  await loadLocalAuthedApp(page);

  const layout = await page.evaluate(() => {
    const sidebarRect = document.querySelector("#app-navigation").getBoundingClientRect();
    const mainRect = document.querySelector("main").getBoundingClientRect();
    const routePanelRect = document.querySelector(".view.active > .product-route-panel").getBoundingClientRect();
    return {
      leftGutter: mainRect.left - sidebarRect.right,
      rightGutter: window.innerWidth - mainRect.right,
      mainWidth: mainRect.width,
      routePanelWidth: routePanelRect.width,
    };
  });

  expect(layout.leftGutter).toBeCloseTo(0, 0);
  expect(layout.rightGutter).toBeCloseTo(0, 0);
  expect(layout.mainWidth).toBeCloseTo(2560 - 240, 0);
  expect(layout.routePanelWidth).toBeCloseTo(2560 - 240 - 32, 0);

  await page.locator('.nav-btn[data-view="dashboard"]').click();
  const dashboardWidth = await page.locator("#view-dashboard > .panel").evaluate((element) => (
    element.getBoundingClientRect().width
  ));
  expect(dashboardWidth).toBeCloseTo(layout.routePanelWidth, 0);
  await expectNoDocumentOverflow(page);
});

test("desktop dashboard fills the viewport with a 55/45 priority split", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await loadLocalAuthedApp(page);
  await page.locator('.nav-btn[data-view="dashboard"]').click();

  const dashboard = page.locator("#view-dashboard");
  const primarySection = page.locator("#dashboard-top-projects");
  const supportingSection = page.locator("#view-dashboard .dashboard-grid");
  await expect(dashboard).toHaveClass(/active/);
  await expect(primarySection).toBeVisible();
  await expect(supportingSection).toBeVisible();

  const layout = await page.evaluate(() => {
    const dashboardRect = document.querySelector("#view-dashboard").getBoundingClientRect();
    const primaryRect = document.querySelector("#dashboard-top-projects").getBoundingClientRect();
    const supportingRect = document.querySelector("#view-dashboard .dashboard-grid").getBoundingClientRect();
    return {
      dashboardBottom: dashboardRect.bottom,
      viewportHeight: window.innerHeight,
      primaryShare: primaryRect.height / (primaryRect.height + supportingRect.height),
      supportingColumns: getComputedStyle(document.querySelector("#view-dashboard .dashboard-grid")).gridTemplateColumns
        .split(" ")
        .length,
    };
  });

  expect(layout.dashboardBottom).toBeLessThanOrEqual(layout.viewportHeight);
  expect(layout.dashboardBottom).toBeGreaterThan(layout.viewportHeight - 30);
  expect(layout.primaryShare).toBeGreaterThanOrEqual(0.54);
  expect(layout.primaryShare).toBeLessThanOrEqual(0.56);
  expect(layout.supportingColumns).toBe(3);
  await expectNoDocumentOverflow(page);
});
