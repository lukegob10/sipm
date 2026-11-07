import { expect, test } from '@playwright/test';

test('failed reviewable requests wait for an explicit retry', async ({ page }) => {
  const soeid = `review${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Review admin', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  await page.route('**/api/auth/bootstrap', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, space_kind: 'collaboration', is_global_admin: true } } });
  });
  await page.route('**/api/spaces/*/members', (route) => route.fulfill({ json: [] }));
  let requests = 0;
  await page.route('**/api/spaces/access-requests/reviewable', (route) => {
    requests += 1;
    return requests === 1 ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) : route.fulfill({ json: [] });
  });
  await page.goto('/project-manager/spaces');
  const retry = page.locator('[data-space-action="retry-reviewable-access-requests"]');
  await expect(retry).toBeVisible();
  // Rerenders must not repeatedly ask the server for a failing list.
  await page.locator('[data-space-action="select-section"][data-section="space-directory"]').click();
  await page.locator('[data-space-action="select-section"][data-section="current-space"]').click();
  await expect(retry).toBeVisible();
  expect(requests).toBe(1);
  await retry.click();
  await expect(page.getByText('No pending access requests.')).toBeVisible();
  expect(requests).toBe(2);
});
