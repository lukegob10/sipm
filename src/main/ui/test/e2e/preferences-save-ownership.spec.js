import {test,expect} from '@playwright/test';
test('old preference save does not close a newly reopened modal',async({page})=>{
 const id=`pref${Date.now()}`; expect((await page.request.post('/project-manager/api/auth/register',{data:{soeid:id,display_name:'User',password:'Password123'}})).ok()).toBeTruthy();
 expect((await page.request.post('/project-manager/api/spaces/personal',{data:{}})).ok()).toBeTruthy();
 await page.goto('/project-manager/'); await page.locator('#preferences-open').click();
 let release; const wait=new Promise(r=>{release=r}); let started; const start=new Promise(r=>{started=r});
 await page.route('**/api/users/me/preferences',async route=>{if(route.request().method()==='PATCH'){started();await wait;} await route.continue();});
 await page.locator('#preferences-form select[name="theme"]').selectOption('light');
 await page.locator('#preferences-form button[type="submit"]').click(); await start;
 await page.locator('#preferences-cancel').click(); await page.locator('#preferences-open').click();
 release(); await page.waitForTimeout(500);
 await expect(page.locator('#preferences-modal')).toBeVisible();
});

test('duplicate submits are gated and edits during save remain open', async ({ page }) => {
  const id = `pref${Date.now()}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid: id, display_name: 'User', password: 'Password123' } })).ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/spaces/personal', { data: {} })).ok()).toBeTruthy();
  await page.goto('/project-manager/');
  await page.locator('#preferences-open').click();
  let release, started;
  const held = new Promise((resolve) => { release = resolve; });
  const ready = new Promise((resolve) => { started = resolve; });
  let writes = 0;
  await page.route('**/api/users/me/preferences', async (route) => {
    if (route.request().method() === 'PATCH') { writes++; started(); await held; }
    await route.continue();
  });
  const form = page.locator('#preferences-form');
  await form.locator('[name="theme"]').selectOption('light');
  await form.locator('button[type="submit"]').click();
  await ready;
  await form.evaluate((element) => element.requestSubmit());
  await form.locator('[name="theme"]').selectOption('slate');
  expect(writes).toBe(1);
  release();
  await expect(page.locator('#preferences-status')).toContainText('Newer edits are not saved');
  await expect(page.locator('#preferences-modal')).toBeVisible();
  await expect(form.locator('[name="theme"]')).toHaveValue('slate');
});

test('theme migration finishes before a user preference save', async ({ page }) => {
  const id = `pref${Date.now()}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid: id, display_name: 'User', password: 'Password123' } })).ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/spaces/personal', { data: {} })).ok()).toBeTruthy();
  await page.addInitScript(() => localStorage.setItem('sipm-theme', 'light'));
  let release, started;
  const held = new Promise((resolve) => { release = resolve; });
  const ready = new Promise((resolve) => { started = resolve; });
  const themes = [];
  await page.route('**/api/users/me/preferences', async (route) => {
    if (route.request().method() === 'PATCH') {
      themes.push(route.request().postDataJSON().theme);
      if (themes.length === 1) { started(); await held; }
    }
    await route.continue();
  });
  await page.goto('/project-manager/');
  await ready;
  await page.locator('#preferences-open').click();
  await page.locator('#preferences-form [name="theme"]').selectOption('slate');
  await page.locator('#preferences-form button[type="submit"]').click();
  expect(themes).toEqual(['light']);
  release();
  await expect(page.locator('#preferences-modal')).toHaveClass(/hidden/);
  expect(themes).toEqual(['light', 'slate']);
  const response = await page.request.get('/project-manager/api/users/me/preferences');
  expect((await response.json()).theme).toBe('slate');
});

test('a pending preference save cannot update a replacement session', async ({ page }) => {
  const id = `pref${Date.now()}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid: id, display_name: 'User', password: 'Password123' } })).ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/spaces/personal', { data: {} })).ok()).toBeTruthy();
  await page.goto('/project-manager/');
  await page.locator('#preferences-open').click();
  let release, started;
  const held = new Promise((resolve) => { release = resolve; });
  const ready = new Promise((resolve) => { started = resolve; });
  await page.route('**/api/users/me/preferences', async (route) => {
    if (route.request().method() === 'PATCH') { started(); await held; }
    await route.continue();
  });
  await page.locator('#preferences-form [name="theme"]').selectOption('light');
  await page.locator('#preferences-form button[type="submit"]').click();
  await ready;
  await page.locator('#logout-btn').dispatchEvent('click');
  await expect(page.locator('#auth-screen')).toBeVisible();
  release();
  await expect(page.locator('#auth-screen')).toBeVisible();
  await expect(page.locator('#preferences-modal')).toHaveClass(/hidden/);
});

test('preference writes remain ordered across a space switch', async ({ page }) => {
  const id = `pref${Date.now()}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid: id, display_name: 'User', password: 'Password123' } })).ok()).toBeTruthy();
  const spaces = await page.request.get('/project-manager/api/spaces');
  const home = (await spaces.json())[0];
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.goto('/project-manager/');
  await page.locator('#preferences-open').click();
  let release, started;
  const held = new Promise((resolve) => { release = resolve; });
  const ready = new Promise((resolve) => { started = resolve; });
  const themes = [];
  await page.route('**/api/users/me/preferences', async (route) => {
    if (route.request().method() === 'PATCH') {
      themes.push(route.request().postDataJSON().theme);
      if (themes.length === 1) { started(); await held; }
    }
    await route.continue();
  });
  await page.locator('#preferences-form [name="theme"]').selectOption('light');
  await page.locator('#preferences-form button[type="submit"]').click();
  await ready;
  await page.locator('#preferences-cancel').click();
  await page.locator('#space-switcher-trigger').click();
  const switched = page.waitForResponse((response) => response.url().endsWith('/api/auth/active-space') && response.request().method() === 'POST');
  await page.locator(`#space-switcher-all-list [data-space-switch="${home.space_id}"]`).click();
  expect((await switched).ok()).toBeTruthy();
  await expect(page.locator('#space-switcher-panel')).toHaveClass(/hidden/);
  await page.locator('#preferences-open').click();
  await page.locator('#preferences-form [name="theme"]').selectOption('slate');
  await page.locator('#preferences-form button[type="submit"]').click();
  expect(themes).toEqual(['light']);
  release();
  await expect(page.locator('#preferences-modal')).toHaveClass(/hidden/);
  expect(themes).toEqual(['light', 'slate']);
  const response = await page.request.get('/project-manager/api/users/me/preferences');
  expect((await response.json()).theme).toBe('slate');
});
