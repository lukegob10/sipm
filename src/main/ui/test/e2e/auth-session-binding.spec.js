import { expect, test } from '@playwright/test';

async function openFirstSession(page, { isolateBackground = false } = {}) {
  const soeid = `binding${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`.slice(0, 20);
  const register = await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'First user', password: 'Password123' } });
  expect(register.ok()).toBeTruthy();
  const user = await register.json();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  if (isolateBackground) await page.routeWebSocket('**/ws**', () => {});
  await page.goto('/project-manager/');
  await expect(page.locator('#app-shell')).toBeVisible();
  if (isolateBackground) await page.waitForLoadState('networkidle');
  return { soeid, user };
}

async function replaceCookieSession(page, first, sameUser) {
  const other = await page.context().newPage();
  let response;
  if (sameUser) {
    response = await other.request.post('/project-manager/api/auth/login', { data: { soeid: first.soeid, password: 'Password123' } });
  } else {
    const soeid = `other${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`.slice(0, 20);
    response = await other.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Other user', password: 'Password123' } });
  }
  expect(response.ok()).toBeTruthy();
  const user = await response.json();
  expect(response.headers()['x-sipm-session']).toBeTruthy();
  return { other, user };
}

for (const sameUser of [false, true]) {
  const label = sameUser ? 'same-user new session' : 'replacement user';
  test(`old tab cannot write with ${label} cookies`, async ({ page }) => {
    const first = await openFirstSession(page, { isolateBackground: true });
    await page.locator('#topbar-create-toggle').click();
    await page.locator('#topbar-create-program').click();
    await page.locator('#program-form [name="program_name"]').fill('Stale tab program');
    await page.route('**/project-manager/api/**', async (route) => {
      if (route.request().url().endsWith('/api/programs') && route.request().method() === 'POST') return route.continue();
      return route.abort();
    });
    const { other, user } = await replaceCookieSession(page, first, sameUser);
    const rejected = page.waitForResponse((response) => response.url().endsWith('/api/programs') && response.request().method() === 'POST');
    await page.locator('#program-submit-btn').click();
    const response = await rejected;
    expect(response.status()).toBe(409);
    expect(response.headers()['x-error-code']).toBe('SESSION_CONTEXT_CHANGED');
    await expect(page.locator('#auth-screen')).toBeVisible();
    const me = await other.request.get('/project-manager/api/auth/me');
    expect(me.ok()).toBeTruthy();
    expect((await me.json()).user_id).toBe(user.user_id);
    const programs = await other.request.get('/project-manager/api/programs');
    expect(programs.ok()).toBeTruthy();
    expect((await programs.json()).map((item) => item.program_name)).not.toContain('Stale tab program');
  });

  test(`old tab logout preserves ${label} cookies`, async ({ page }) => {
    const first = await openFirstSession(page, { isolateBackground: true });
    await page.route('**/project-manager/api/**', async (route) => {
      if (route.request().url().endsWith('/auth/logout')) return route.continue();
      return route.abort();
    });
    const { other, user } = await replaceCookieSession(page, first, sameUser);
    const rejected = page.waitForResponse((response) => response.url().endsWith('/api/auth/logout') && response.request().method() === 'POST');
    await page.locator('#logout-btn').dispatchEvent('click');
    expect((await rejected).status()).toBe(409);
    const me = await other.request.get('/project-manager/api/auth/me');
    expect(me.ok()).toBeTruthy();
    expect((await me.json()).user_id).toBe(user.user_id);
  });
}

test('a delayed refresh finishes before another tab signs in', async ({ page }) => {
  const otherSoeid = `lock${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`.slice(0, 20);
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid: otherSoeid, display_name: 'Other user', password: 'Password123' } })).ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/logout')).ok()).toBeTruthy();
  const other = await page.context().newPage();
  await other.goto('/project-manager/');
  await expect(other.locator('#auth-screen')).toBeVisible();
  await other.locator('#login-form [name="soeid"]').fill(otherSoeid);
  await other.locator('#login-form [name="password"]').fill('Password123');
  await openFirstSession(page);
  let markRefresh;
  let releaseRefresh;
  const refreshStarted = new Promise((resolve) => { markRefresh = resolve; });
  const refreshHeld = new Promise((resolve) => { releaseRefresh = resolve; });
  await page.route('**/api/auth/refresh', async (route) => {
    const response = await route.fetch();
    markRefresh();
    await refreshHeld;
    await route.fulfill({ response });
  });
  let originalWrite = true;
  await page.route('**/api/programs', async (route) => {
    if (route.request().method() === 'POST' && originalWrite) {
      originalWrite = false;
      await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'expired' }) });
    } else {
      await route.continue();
    }
  });
  await page.locator('#topbar-create-toggle').click();
  await page.locator('#topbar-create-program').click();
  await page.locator('#program-form [name="program_name"]').fill('Refresh held program');
  await page.locator('#program-submit-btn').click();
  await refreshStarted;
  let logins = 0;
  await other.route('**/api/auth/login', async (route) => { logins += 1; await route.continue(); });
  await other.locator('#login-form button[type="submit"]').click();
  await other.waitForTimeout(300);
  expect(logins).toBe(0);
  releaseRefresh();
  await expect(other.locator('#app-shell')).toBeVisible();
  expect(logins).toBe(1);
  const me = await other.request.get('/project-manager/api/auth/me');
  expect(me.ok()).toBeTruthy();
  expect((await me.json()).soeid).toBe(otherSoeid);
});

test('a late logout after session mismatch cannot revoke the replacement account', async ({ page }) => {
  const first = await openFirstSession(page, { isolateBackground: true });
  await page.locator('#preferences-open').dispatchEvent('click');
  await expect(page.locator('#preferences-modal')).toBeVisible();
  await page.locator('#preferences-form [name="theme"]').selectOption('light');
  let logoutRequests = 0;
  await page.route('**/project-manager/api/**', async (route) => {
    const url = route.request().url();
    if (url.endsWith('/auth/logout')) { logoutRequests += 1; return route.continue(); }
    if (url.endsWith('/users/me/preferences') && route.request().method() === 'PATCH') return route.continue();
    return route.abort();
  });
  const { other, user } = await replaceCookieSession(page, first, false);
  const rejected = page.waitForResponse((response) => response.url().endsWith('/users/me/preferences') && response.request().method() === 'PATCH');
  await page.locator('#preferences-form button[type="submit"]').click();
  expect((await rejected).status()).toBe(409);
  await expect(page.locator('#auth-screen')).toBeVisible();
  await page.locator('#logout-btn').dispatchEvent('click');
  const me = await other.request.get('/project-manager/api/auth/me');
  expect(me.ok()).toBeTruthy();
  expect((await me.json()).user_id).toBe(user.user_id);
  expect(logoutRequests).toBe(0);
});
