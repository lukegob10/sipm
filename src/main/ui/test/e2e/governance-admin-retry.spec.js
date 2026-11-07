import { expect, test } from '@playwright/test';

test('failed administrator load waits for an explicit retry', async ({ page }) => {
  const soeid = `retry${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Retry user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.route('**/api/auth/bootstrap', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, is_global_admin: true } } });
  });
  let requests = 0;
  await page.route('**/api/users/global-admins?*', (route) => {
    requests += 1;
    return requests === 1 ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) : route.fulfill({ json: [] });
  });
  await page.goto('/project-manager/access');
  const retry = page.getByRole('button', { name: 'Retry', exact: true });
  await expect(retry).toBeVisible();
  // Other rerenders, including notice updates, must not retry a failed read.
  await page.locator('[data-space-action="select-platform-tool"][data-platform-tool="password-resets"]').click();
  await page.locator('[data-space-action="select-platform-tool"][data-platform-tool="administrators"]').click();
  await expect(retry).toBeVisible();
  expect(requests).toBe(1);
  await retry.click();
  await expect(page.getByText('No global admins found')).toBeVisible();
  expect(requests).toBe(2);
});
