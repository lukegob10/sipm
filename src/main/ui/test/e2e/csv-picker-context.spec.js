import { expect, test } from '@playwright/test';

async function register(page) {
  const soeid = `pick${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Picker user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  return soeid;
}

async function openCsv(page, kind) {
  await page.locator('#csv-actions-toggle').click();
  await page.locator(`#${kind}-upload`).click();
}

test('old CSV chooser does not populate a newly opened import modal', async ({ page }) => {
  await register(page);
  await page.goto('/project-manager/');
  await openCsv(page, 'projects');
  const pending = page.waitForEvent('filechooser');
  await page.locator('#csv-dropzone').click();
  const chooser = await pending;
  await page.locator('#csv-upload-close').click();
  await openCsv(page, 'solutions');
  await chooser.setFiles({ name: 'old.csv', mimeType: 'text/csv', buffer: Buffer.from('project_name\nOld') });
  await expect(page.locator('#csv-upload-file-name')).toHaveText('No file selected');
  const next = page.waitForEvent('filechooser');
  await page.locator('#csv-dropzone').click();
  await (await next).setFiles({ name: 'new.csv', mimeType: 'text/csv', buffer: Buffer.from('solution_name\nNew') });
  await expect(page.locator('#csv-upload-file-name')).toContainText('new.csv');
});

test('old roster chooser does not import after a new login', async ({ page }) => {
  await register(page);
  await page.goto('/project-manager/team-capacity');
  await expect(page.locator('#roster-upload')).toBeVisible();
  const pending = page.waitForEvent('filechooser');
  await page.locator('#roster-upload').click();
  const chooser = await pending;
  await page.locator('#logout-btn').dispatchEvent('click');
  await expect(page.locator('#auth-screen')).toBeVisible();
  const soeid = await register(page);
  await page.locator('#login-form [name="soeid"]').fill(soeid);
  await page.locator('#login-form [name="password"]').fill('Password123');
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page.locator('#app-shell')).toBeVisible();
  await page.locator('.nav-btn[data-view="team-capacity"]').dispatchEvent('click');
  await expect(page.locator('#roster-upload')).toBeVisible();
  let imports = 0;
  await page.route('**/api/users/import', async (route) => { imports += 1; await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ created: 1, updated: 0, errors: [] }) }); });
  await chooser.setFiles({ name: 'old.csv', mimeType: 'text/csv', buffer: Buffer.from('soeid,display_name\nold,Old') });
  await page.waitForTimeout(300);
  expect(imports).toBe(0);
  const next = page.waitForEvent('filechooser');
  await page.locator('#roster-upload').click();
  await (await next).setFiles({ name: 'new.csv', mimeType: 'text/csv', buffer: Buffer.from('soeid,display_name\nnew,New') });
  await expect.poll(() => imports).toBe(1);
});

test('old CSV chooser is discarded after a new login', async ({ page }) => {
  await register(page);
  await page.goto('/project-manager/');
  await openCsv(page, 'projects');
  const pending = page.waitForEvent('filechooser');
  await page.locator('#csv-dropzone').click();
  const chooser = await pending;
  await page.locator('#logout-btn').dispatchEvent('click');
  await expect(page.locator('#auth-screen')).toBeVisible();
  const soeid = await register(page);
  await page.locator('#login-form [name="soeid"]').fill(soeid);
  await page.locator('#login-form [name="password"]').fill('Password123');
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page.locator('#app-shell')).toBeVisible();
  await openCsv(page, 'projects');
  await chooser.setFiles({ name: 'old.csv', mimeType: 'text/csv', buffer: Buffer.from('project_name\nOld') });
  await expect(page.locator('#csv-upload-file-name')).toHaveText('No file selected');
});

test('CSV upload dialog receives focus and returns it on Escape', async ({ page }) => {
  await register(page);
  await page.goto('/project-manager/');
  await openCsv(page, 'projects');
  const dialog = page.getByRole('dialog', { name: 'Upload Projects CSV' });
  await expect(dialog).toBeVisible();
  await expect(page.locator('#csv-upload-close')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(page.locator('#csv-actions-toggle')).toBeFocused();
});
