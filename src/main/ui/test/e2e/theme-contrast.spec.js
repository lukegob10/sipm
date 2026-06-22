import { expect, test } from "@playwright/test";

const MIN_TEXT_CONTRAST = 4.5;
const MIN_DISABLED_CONTRAST = 3;

async function loadLocalAuthedApp(page) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const soeid = `theme${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const programName = `Theme Program ${suffix}`;
  const projectName = `Theme Project ${suffix}`;

  const register = await page.request.post("/project-manager/api/auth/register", {
    data: {
      soeid,
      display_name: "Theme Audit User",
      password: "Password123",
    },
  });
  expect(register.ok()).toBeTruthy();

  const program = await page.request.post("/project-manager/api/programs", {
    data: {
      program_name: programName,
      description: "Program for theme audit coverage.",
    },
  });
  expect(program.ok()).toBeTruthy();
  const programBody = await program.json();

  const project = await page.request.post("/project-manager/api/projects", {
    data: {
      program_id: programBody.program_id,
      project_name: projectName,
      sponsor: "Theme Sponsor",
      status: "active",
    },
  });
  expect(project.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.locator("#app-shell")).toBeVisible();
}

async function setTheme(page, theme) {
  const isLight = await page.locator("body").evaluate((body) => body.classList.contains("theme-light"));
  if ((theme === "light") !== isLight) {
    await page.locator("#theme-toggle").click();
  }
  await expect(page.locator("body")).toHaveClass(theme === "light" ? /theme-light/ : /^(?!.*theme-light).*$/);
  await page.waitForTimeout(250);
}

async function openRoute(page, view, waitForSelector) {
  await page.locator(`.nav-btn[data-view="${view}"]`).click();
  const domView = view === "access" ? "spaces" : view;
  await expect(page.locator(`#view-${domView}`)).toHaveClass(/active/);
  if (waitForSelector) {
    await expect(page.locator(waitForSelector)).toBeVisible();
  }
  await page.waitForTimeout(250);
}

async function assertContrastForSelector(page, selector, label, options = {}) {
  const result = await page.locator(selector).first().evaluate((node, minContrast) => {
    function parseColor(value) {
      const raw = String(value || "").trim();
      const rgb = raw.match(/^rgba?\(([^)]+)\)$/i);
      if (rgb) {
        const parts = rgb[1].split(",").map((part) => part.trim());
        return {
          r: Number(parts[0]),
          g: Number(parts[1]),
          b: Number(parts[2]),
          a: parts[3] === undefined ? 1 : Number(parts[3]),
        };
      }
      const srgb = raw.match(/^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)$/i);
      if (srgb) {
        return {
          r: Number(srgb[1]) * 255,
          g: Number(srgb[2]) * 255,
          b: Number(srgb[3]) * 255,
          a: srgb[4] === undefined ? 1 : Number(srgb[4]),
        };
      }
      return { r: 0, g: 0, b: 0, a: 0 };
    }

    function composite(top, bottom) {
      const alpha = top.a + bottom.a * (1 - top.a);
      if (!alpha) return { r: 0, g: 0, b: 0, a: 0 };
      return {
        r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / alpha,
        g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / alpha,
        b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / alpha,
        a: alpha,
      };
    }

    function channel(value) {
      const normalized = value / 255;
      return normalized <= 0.03928
        ? normalized / 12.92
        : ((normalized + 0.055) / 1.055) ** 2.4;
    }

    function luminance(color) {
      return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
    }

    function contrastRatio(foreground, background) {
      const light = Math.max(luminance(foreground), luminance(background));
      const dark = Math.min(luminance(foreground), luminance(background));
      return (light + 0.05) / (dark + 0.05);
    }

    function effectiveBackground(element) {
      let background = { r: 255, g: 255, b: 255, a: 1 };
      const stack = [];
      for (let current = element; current; current = current.parentElement) {
        stack.push(current);
      }
      stack.reverse().forEach((current) => {
        const color = parseColor(getComputedStyle(current).backgroundColor);
        if (color.a > 0) background = composite(color, background);
      });
      return background;
    }

    const style = getComputedStyle(node);
    const foreground = parseColor(style.color);
    const background = effectiveBackground(node);
    const ratio = contrastRatio(foreground, background);
    return {
      ratio,
      minContrast,
      color: style.color,
      background: `rgb(${Math.round(background.r)}, ${Math.round(background.g)}, ${Math.round(background.b)})`,
      text: node.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
    };
  }, options.minContrast || MIN_TEXT_CONTRAST);

  expect(
    result.ratio,
    `${label} contrast ${result.ratio.toFixed(2)} below ${result.minContrast}; fg ${result.color}; bg ${result.background}; text "${result.text}"`,
  ).toBeGreaterThanOrEqual(result.minContrast);
}

async function assertVisibleContrast(page, selectors, theme) {
  for (const item of selectors) {
    const locator = page.locator(item.selector);
    const count = await locator.count();
    if (!count) continue;
    const visible = await locator.first().isVisible().catch(() => false);
    if (!visible) continue;
    await assertContrastForSelector(page, item.selector, `${theme} ${item.label}`, {
      minContrast: item.disabled ? MIN_DISABLED_CONTRAST : MIN_TEXT_CONTRAST,
    });
  }
}

test("shared controls keep readable contrast in light and dark themes", async ({ page }) => {
  await loadLocalAuthedApp(page);

  const routeSamples = [
    {
      view: "master",
      waitFor: "#master-table",
      selectors: [
        { selector: ".nav-btn.active", label: "active nav" },
        { selector: "#topbar-create-toggle", label: "primary topbar button" },
        { selector: "[data-master-outline-action='expand-all']", label: "secondary toolbar button" },
        { selector: "#master-table th", label: "deliverables table header" },
        { selector: "#filter-query", label: "deliverables query control" },
        { selector: "#connection-status", label: "status pill" },
      ],
    },
    {
      view: "dashboard",
      waitFor: "#dashboard-space-capacity",
      selectors: [
        { selector: "#dashboard-space-capacity", label: "dashboard card" },
        { selector: "#view-dashboard .pill", label: "dashboard pill" },
        { selector: "#view-dashboard .dashboard-risk-badge", label: "dashboard risk badge" },
        { selector: "#view-dashboard th", label: "dashboard table header" },
      ],
    },
    {
      view: "program-dashboard",
      waitFor: "#program-dashboard-root",
      selectors: [
        { selector: "#program-dashboard-root .program-dashboard-empty", label: "program empty state" },
        { selector: "#program-dashboard-root .program-dashboard-table-action", label: "program table action" },
        { selector: "#program-dashboard-root .program-dashboard-status", label: "program status pill" },
        { selector: "#program-dashboard-root .program-dashboard-grid-header .program-dashboard-grid-cell", label: "program table header" },
      ],
    },
    {
      view: "planning",
      waitFor: "#planning-board",
      selectors: [
        { selector: "#view-planning button", label: "planning button" },
        { selector: "#view-planning .table", label: "planning table shell" },
        { selector: "#view-planning .pill", label: "planning pill" },
      ],
    },
    {
      view: "team-capacity",
      waitFor: "#capacity-user-form",
      selectors: [
        { selector: "#capacity-user-form button", label: "team capacity button" },
        { selector: "#capacity-user-list th", label: "team capacity table header" },
        { selector: "#view-team-capacity .capacity-badge", label: "capacity badge" },
      ],
    },
    {
      view: "spaces",
      waitFor: "#view-spaces .panel-header",
      selectors: [
        { selector: "#view-spaces h2", label: "spaces route title" },
        { selector: "#space-governance-shell .space-empty-card", label: "admin boundary message" },
        { selector: "#space-governance-shell .pill", label: "space badge" },
        { selector: "#space-governance-shell button:disabled", label: "space disabled button", disabled: true },
      ],
    },
  ];

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    for (const route of routeSamples) {
      await openRoute(page, route.view, route.waitFor);
      await assertVisibleContrast(page, route.selectors, theme);
    }

    await openRoute(page, "master", "#master-table");
    await page.locator("#topbar-create-toggle").click();
    await page.locator("#topbar-create-project").click();
    await expect(page.locator("#project-modal:not(.hidden) .modal-content")).toBeVisible();
    await assertVisibleContrast(page, [
      { selector: "#project-modal .modal-header h3", label: "project modal title" },
      { selector: "#project-modal input", label: "project modal input" },
      { selector: "#delete-project", label: "project modal disabled delete", disabled: true },
      { selector: "#project-submit-btn", label: "project modal primary action" },
    ], theme);
    await page.locator("#project-modal-close").click();
  }
});
