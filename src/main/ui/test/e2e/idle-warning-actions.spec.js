import { expect, test } from '@playwright/test';

async function openWithShortIdlePolicy(page) {
  const soeid = `idle${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Idle user', password: 'Password123' } })).ok()).toBeTruthy();
  const space = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(space.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await space.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Idle program' } });
  expect(program.ok()).toBeTruthy();
  const programId = (await program.json()).program_id;
  await page.route('**/auth/session-policy', (route) => route.fulfill({ json: {
    idle_timeout_seconds: 12, warning_seconds: 9, activity_heartbeat_seconds: 1,
  } }));
  await page.goto('/project-manager/');
  await expect(page.locator('#app-shell')).toBeVisible();
  return programId;
}

test('idle warning is above open preferences and keeps keyboard focus until Stay', async ({ page }) => {
  await openWithShortIdlePolicy(page);
  await page.locator('#preferences-open').click();
  const preferences = page.locator('#preferences-modal');
  const warning = page.locator('#idle-modal');
  await expect(preferences).toBeVisible();
  await expect(warning).toBeVisible({ timeout: 10000 });
  await expect(page.locator('#idle-stay')).toBeFocused();
  expect(await warning.locator('.modal-content').evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)?.closest('.modal')?.id;
  })).toBe('idle-modal');
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#idle-logout')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#idle-stay')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(warning).toBeVisible();
  await expect(preferences).toBeVisible();
  await page.locator('#idle-stay').click();
  await expect(warning).toBeHidden();
  await expect(preferences).toBeVisible();
  await expect(preferences.locator('[name="developer_mode_enabled"]')).toBeFocused();
});

test('idle Sign out remains clickable after moving the pointer to it', async ({ page }) => {
  await openWithShortIdlePolicy(page);
  const warning = page.locator('#idle-modal');
  await expect(warning).toBeVisible({ timeout: 10000 });
  await page.locator('#idle-logout').click();
  await expect(warning).toBeHidden();
  await expect(page.locator('#auth-screen')).toBeVisible();
});


test('idle warning takes keyboard priority over a pending confirmation', async ({ page }) => {
  const programId = await openWithShortIdlePolicy(page);
  await page.locator(`[data-action="edit"][data-type="program"][data-id="${programId}"]`).first().click();
  await page.locator('#program-form [name="program_name"]').fill('Unsaved edit');
  await page.locator('#program-modal-close').click();
  await expect(page.locator('#confirm-modal')).toBeVisible();
  await expect(page.locator('#idle-modal')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('#idle-stay')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#confirm-modal')).toBeVisible();
  await expect(page.locator('#idle-modal')).toBeVisible();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#idle-logout')).toBeFocused();
  await page.locator('#idle-stay').click();
  await expect(page.locator('#idle-modal')).toBeHidden();
  await expect(page.locator('#confirm-modal-confirm')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#confirm-modal')).toBeHidden();
  await expect(page.locator('#program-modal')).toBeVisible();
});
