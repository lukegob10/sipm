import { expect, test } from '@playwright/test';

test('failed membership load waits for a retry and does not claim an empty roster', async ({ page }) => {
  const soeid = `mem${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Members user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  const { space_id: id } = await personal.json();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: id } })).ok()).toBeTruthy();
  await page.route('**/api/auth/bootstrap', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, is_global_admin: true } } });
  });
  let requests = 0;
  await page.route(`**/api/spaces/${id}/members`, (route) => {
    requests += 1;
    return requests === 1 ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) : route.fulfill({ json: [] });
  });
  await page.goto('/project-manager/spaces');
  await page.locator('[data-space-action="select-section"][data-section="current-space"]').click();
  const retry = page.locator(`[data-space-action="retry-space-members"][data-space-id="${id}"]`);
  await expect(retry).toBeVisible();
  await expect(page.getByText('No memberships found')).toHaveCount(0);
  await page.locator('[data-space-action="select-section"][data-section="agent-approvals"]').click();
  await page.locator('[data-space-action="select-section"][data-section="current-space"]').click();
  await expect(retry).toBeVisible();
  expect(requests).toBe(1);
  await retry.click();
  await expect(retry).toHaveCount(0);
  expect(requests).toBe(2);
});

test('directory details expose a retry for failed membership counts', async ({ page }) => {
  const soeid = `dir${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Directory user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  const { space_id: id } = await personal.json();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: id } })).ok()).toBeTruthy();
  await page.route('**/api/auth/bootstrap', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, active_space: { ...payload.active_space, is_global_admin: true } } });
  });
  let requests = 0;
  await page.route(`**/api/spaces/${id}/members`, (route) => {
    requests += 1;
    return requests === 1 ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) : route.fulfill({ json: [] });
  });
  await page.goto('/project-manager/spaces');
  await page.locator('[data-space-action="select-section"][data-section="space-directory"]').click();
  await page.locator(`[data-space-action="open-directory-space"][data-space-id="${id}"]`).click();
  const modal = page.locator('#space-directory-modal');
  const retry = modal.locator(`[data-space-action="retry-space-members"][data-space-id="${id}"]`);
  await expect(retry).toBeVisible();
  expect(requests).toBe(1);
  await retry.click();
  await expect(retry).toHaveCount(0);
  await expect(modal.locator('.space-summary-card').filter({ hasText: 'Members' }).locator('strong')).toHaveText('0');
  expect(requests).toBe(2);
});
