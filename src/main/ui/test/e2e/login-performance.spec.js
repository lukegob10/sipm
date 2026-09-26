import { expect, test } from "@playwright/test";

const LOGIN_PATH = "/project-manager/api/auth/login";
const PASSWORD = "Password123";

async function createSignedOutMember(page) {
  const suffix = `${Date.now()}${Math.random().toString(16).slice(2, 8)}`;
  const soeid = `login${suffix}`.replace(/[^a-z0-9]/g, "").slice(0, 20);
  const register = await page.request.post("/project-manager/api/auth/register", {
    data: { soeid, display_name: "Login Browser User", password: PASSWORD },
  });
  expect(register.ok()).toBeTruthy();

  const personalSpace = await page.request.post("/project-manager/api/spaces/personal", { data: {} });
  expect(personalSpace.ok()).toBeTruthy();
  const activate = await page.request.post("/project-manager/api/auth/active-space", {
    data: { space_id: (await personalSpace.json()).space_id },
  });
  expect(activate.ok()).toBeTruthy();
  const programName = `Login Browser Program ${suffix}`;
  const program = await page.request.post("/project-manager/api/programs", {
    data: { program_name: programName },
  });
  expect(program.ok()).toBeTruthy();
  const logout = await page.request.post("/project-manager/api/auth/logout");
  expect(logout.ok()).toBeTruthy();
  return { soeid, programName };
}

async function recordLoginMetrics(page, programName) {
  await page.addInitScript(({ loginPath, seededProgramName }) => {
    const metrics = {
      submitAt: null,
      feedbackFrameAt: null,
      usableUiAt: null,
      loginFetchCount: 0,
    };
    window.__loginMetrics = metrics;

    document.addEventListener("submit", (event) => {
      if (event.target?.id === "login-form" && metrics.submitAt === null) {
        metrics.submitAt = performance.now();
      }
    }, true);

    const busyObserver = new MutationObserver((records) => {
      for (const record of records) {
        if (
          record.target.matches?.('#login-form button[type="submit"]')
          && record.target.getAttribute("aria-busy") === "true"
          && metrics.feedbackFrameAt === null
        ) {
          requestAnimationFrame(() => {
            if (metrics.feedbackFrameAt === null && record.target.getAttribute("aria-busy") === "true") {
              metrics.feedbackFrameAt = performance.now();
            }
          });
        }
      }
    });
    busyObserver.observe(document, { attributes: true, attributeFilter: ["aria-busy"], subtree: true });

    function isUsableMasterView() {
      const view = document.querySelector("#view-master");
      const search = document.querySelector("#filter-query");
      const table = document.querySelector("#master-table table");
      return metrics.submitAt !== null
        && view?.classList.contains("active")
        && view.getClientRects().length > 0
        && search
        && !search.disabled
        && table?.getClientRects().length > 0
        && table.textContent.includes(seededProgramName);
    }

    let readinessFrameScheduled = false;
    const readinessObserver = new MutationObserver(() => {
      if (metrics.usableUiAt !== null || readinessFrameScheduled || !isUsableMasterView()) return;
      readinessFrameScheduled = true;
      requestAnimationFrame(() => {
        readinessFrameScheduled = false;
        if (metrics.usableUiAt === null && isUsableMasterView()) metrics.usableUiAt = performance.now();
      });
    });
    readinessObserver.observe(document, {
      attributes: true,
      attributeFilter: ["class", "disabled"],
      childList: true,
      subtree: true,
    });

    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : input?.url;
      if (url && new URL(url, window.location.href).pathname === loginPath) metrics.loginFetchCount += 1;
      return originalFetch(input, init);
    };
  }, { loginPath: LOGIN_PATH, seededProgramName: programName });
}

async function openSignIn(page, soeid) {
  await page.goto("/project-manager/");
  await expect(page.locator("#auth-screen")).toBeVisible();
  await page.locator('#login-form input[name="soeid"]').fill(soeid);
  await page.locator('#login-form input[name="password"]').fill(PASSWORD);
}

async function waitForUsableMasterView(page, programName) {
  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.locator("#view-master")).toHaveClass(/active/);
  await expect(page.locator("#master-table table")).toBeVisible();
  await expect(page.locator("#master-table")).toContainText(programName);
  await expect(page.locator("#filter-query")).toBeEnabled();
  await expect.poll(() => page.evaluate(() => window.__loginMetrics.usableUiAt)).not.toBeNull();
}

async function collectLoginMetrics(page) {
  return page.evaluate(() => {
    const { submitAt, feedbackFrameAt, usableUiAt, loginFetchCount } = window.__loginMetrics;
    const response = performance.getEntriesByType("resource").find((entry) => {
      try {
        return new URL(entry.name).pathname === "/project-manager/api/auth/login" && entry.responseEnd > 0;
      } catch {
        return false;
      }
    });
    if (submitAt === null || feedbackFrameAt === null || usableUiAt === null || !response) {
      throw new Error("Login timing instrumentation did not capture submit, feedback, response, and usable UI.");
    }
    return {
      feedbackFrameMs: feedbackFrameAt - submitAt,
      authResponseMs: response.responseEnd - submitAt,
      authRequestMs: response.duration,
      usableUiMs: usableUiAt - submitAt,
      loginFetchCount,
    };
  });
}

function roundedMetrics(metrics) {
  return Object.fromEntries(Object.entries(metrics).map(([key, value]) => [
    key,
    typeof value === "number" && key !== "loginFetchCount" ? Math.round(value * 10) / 10 : value,
  ]));
}

async function attachMetrics(testInfo, label, metrics) {
  const captured = {
    scenario: label,
    bcryptRounds: Number(process.env.SIPM_BCRYPT_ROUNDS || 12),
    ...roundedMetrics(metrics),
  };
  await testInfo.attach(`${label}-timings.json`, {
    body: Buffer.from(JSON.stringify(captured, null, 2)),
    contentType: "application/json",
  });
  console.info("SIPM login browser metrics", JSON.stringify(captured));
}

test("bcrypt 12 login reports busy feedback, auth response, and usable route timings", async ({ page }, testInfo) => {
  const { soeid, programName } = await createSignedOutMember(page);
  await recordLoginMetrics(page, programName);
  const requests = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === LOGIN_PATH) requests.push(request);
  });
  await openSignIn(page, soeid);

  const submit = page.locator('#login-form button[type="submit"]');
  await submit.click();
  await expect(submit).toBeDisabled();
  await expect(submit).toHaveAttribute("aria-busy", "true");
  await expect.poll(() => page.evaluate(() => window.__loginMetrics.feedbackFrameAt)).toBeGreaterThan(0);
  await waitForUsableMasterView(page, programName);

  const metrics = await collectLoginMetrics(page);
  expect(requests).toHaveLength(1);
  expect(metrics.loginFetchCount).toBe(1);
  expect(metrics.authResponseMs).toBeGreaterThan(metrics.feedbackFrameMs);
  expect(metrics.usableUiMs).toBeGreaterThanOrEqual(metrics.authResponseMs);
  await attachMetrics(testInfo, "bcrypt12-local", metrics);
});

test("held login gives prompt busy feedback and rejects duplicate submission", async ({ page }, testInfo) => {
  const syntheticDelayMs = 700;
  const { soeid, programName } = await createSignedOutMember(page);
  await recordLoginMetrics(page, programName);
  const requests = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === LOGIN_PATH) requests.push(request);
  });
  await page.route(`**${LOGIN_PATH}`, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, syntheticDelayMs));
    await route.continue();
  });
  await openSignIn(page, soeid);

  const responsePromise = page.waitForResponse((response) => (
    new URL(response.url()).pathname === LOGIN_PATH && response.request().method() === "POST"
  ));
  const submit = page.locator('#login-form button[type="submit"]');
  await submit.click();
  await expect(submit).toBeDisabled();
  await expect(submit).toHaveAttribute("aria-busy", "true");
  await expect.poll(() => page.evaluate(() => window.__loginMetrics.feedbackFrameAt)).toBeGreaterThan(0);
  await page.locator('#login-form input[name="password"]').press("Enter");
  await page.locator("#login-form").evaluate((form) => form.requestSubmit());
  expect(await page.evaluate(() => window.__loginMetrics.loginFetchCount)).toBe(1);
  expect(requests).toHaveLength(1);

  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  await waitForUsableMasterView(page, programName);
  const metrics = await collectLoginMetrics(page);
  expect(metrics.loginFetchCount).toBe(1);
  expect(requests).toHaveLength(1);
  expect(metrics.feedbackFrameMs).toBeLessThan(250);
  expect(metrics.authResponseMs).toBeGreaterThanOrEqual(syntheticDelayMs - 50);
  await attachMetrics(testInfo, `synthetic-delay-${syntheticDelayMs}ms`, metrics);
});

test("mobile sign-in keeps labeled controls, keyboard access, and the card in view", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto("/project-manager/");
  await expect(page.locator("#auth-screen")).toBeVisible();

  const loginForm = page.locator("#login-form");
  const soeid = loginForm.getByLabel("SOEID");
  const password = loginForm.getByLabel("Password");
  const submit = loginForm.getByRole("button", { name: "Sign in", exact: true });
  await expect(soeid).toHaveAttribute("autocomplete", "username");
  await expect(password).toHaveAttribute("autocomplete", "current-password");
  await expect(page.getByRole("heading", { name: "Sign in to SIPM" })).toBeVisible();

  const layout = await page.evaluate(() => {
    const card = document.querySelector("#auth-screen .auth-card").getBoundingClientRect();
    return {
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      cardLeft: card.left,
      cardRight: card.right,
    };
  });
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.cardLeft).toBeGreaterThanOrEqual(0);
  expect(layout.cardRight).toBeLessThanOrEqual(layout.viewportWidth);
  await expect(soeid).toBeInViewport();
  await expect(password).toBeInViewport();
  await expect(submit).toBeInViewport();

  await page.keyboard.press("Tab");
  await expect(page.locator(".skip-link")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#auth-tab-login")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#auth-tab-register")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(soeid).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(password).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(submit).toBeFocused();

  const describedBy = await page.locator("#login-form").getAttribute("aria-describedby");
  const hasAllDescriptionTargets = await page.evaluate((ids) => (
    ids.every((id) => document.getElementById(id))
  ), describedBy.split(/\s+/));
  expect(hasAllDescriptionTargets).toBeTruthy();
});
