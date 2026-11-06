import { expect, test } from '@playwright/test';

test('approval queue failure waits for an explicit retry', async ({ page }) => {
  const soeid = `ap${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Approval user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  let requests = 0;
  await page.route('**/api/agent/change-requests?status=pending*', (route) => {
    requests += 1;
    return requests === 1 ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } })
      : route.fulfill({ json: { records: [], pending_count: 0, failed_count: 0, has_more: false } });
  });
  await page.goto('/project-manager/spaces');
  await page.getByRole('button', { name: /Agent Approvals/ }).click();
  await expect(page.getByText('Could not load the approval queue. Retry to see current proposals.')).toBeVisible();
  await expect(page.getByText('Nothing waiting')).toHaveCount(0);
  await page.getByRole('button', { name: /Current Space/ }).click();
  await page.getByRole('button', { name: /Agent Approvals/ }).click();
  expect(requests).toBe(1);
  await page.getByRole('button', { name: 'Retry loading approval queue' }).click();
  await expect(page.getByText('Nothing waiting')).toBeVisible();
  expect(requests).toBe(2);
});
