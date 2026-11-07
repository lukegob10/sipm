import { expect, test } from '@playwright/test';

test('token issuance exposes the one-time secret before a failing list refresh and preserves focus', async ({ page }) => {
  const soeid = `tok${Date.now()}${Math.random().toString(36).slice(2, 5)}`.slice(0, 20);
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Token admin', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.route('**/api/auth/bootstrap', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, is_global_admin: true } } });
  });
  let releaseAdmins;
  await page.route('**/api/users/global-admins?*', async (route) => {
    await new Promise((resolve) => { releaseAdmins = resolve; });
    await route.fulfill({ json: [] });
  });
  let issueCount = 0;
  await page.route('**/api/users/by-soeid/target/api-tokens', async (route) => {
    issueCount += 1;
    await route.fulfill({ json: { token: 'one-time-token', user_id: 'target-id' } });
  });
  let release;
  await page.route('**/api/users/target-id/api-tokens', async (route) => {
    await new Promise((resolve) => { release = resolve; });
    await route.fulfill({ status: 503, json: { detail: 'unavailable' } });
  });
  await page.goto('/project-manager/access');
  await page.getByRole('tab', { name: /API Tokens/ }).click();
  const form = page.locator('#user-api-token-form');
  await form.locator('[name="soeid"]').fill('target');
  await form.locator('[name="name"]').fill('Automation');
  await expect.poll(() => typeof releaseAdmins).toBe('function');
  releaseAdmins();
  await expect(page.getByRole('tab', { name: /Administrators/ })).toContainText('0');
  await expect(form.locator('[name="soeid"]')).toHaveValue('target');
  await expect(form.locator('[name="name"]')).toHaveValue('Automation');
  await form.locator('button[type="submit"]').click();
  const dialog = page.getByRole('dialog', { name: 'Copy this token now' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Copy token' })).toBeFocused();
  await expect(dialog.locator('input')).toHaveValue('one-time-token');
  await expect.poll(() => typeof release).toBe('function');
  await form.evaluate((node) => node.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(issueCount).toBe(1);
  release();
  await expect(page.getByText('Token issued. Copy it now; the token list could not be refreshed.')).toBeVisible();
  await expect(dialog.locator('input')).toHaveValue('one-time-token');
  await expect(dialog.getByRole('button', { name: 'Copy token' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(page.locator('#user-api-token-form button[type="submit"]')).toBeFocused();
});
