import { expect, test } from '@playwright/test';

async function setup(page) {
  const soeid = `focus${Date.now()}${Math.random().toString(36).slice(2, 5)}`.slice(0, 20);
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Focus User', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
}

test('Preferences contains forward and reverse tab navigation', async ({ page }) => {
  await setup(page);
  await page.goto('/project-manager/');
  await page.locator('#preferences-open').click();
  await expect(page.locator('#preferences-modal')).toBeVisible();
  await page.locator('#preferences-cancel').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#preferences-close')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#preferences-cancel')).toBeFocused();
});

test('dynamic Dashboard dialog contains keyboard focus', async ({ page }) => {
  await setup(page);
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Focus program' } });
  expect(program.ok()).toBeTruthy();
  const project = await page.request.post('/project-manager/api/projects', { data: { program_id: (await program.json()).program_id, project_name: 'Focus project' } });
  expect(project.ok()).toBeTruthy();
  expect((await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: 'Focus solution', version: '1' } })).ok()).toBeTruthy();
  await page.goto('/project-manager/dashboard');
  await page.locator('[data-dashboard-action="open-config"]').first().click();
  const modal = page.locator('#dashboard-config-modal');
  await expect(modal).toBeVisible();
  await modal.locator('[data-dashboard-action="apply-table-config"]').focus();
  await page.keyboard.press('Tab');
  await expect(modal.locator('button[data-dashboard-action="close-config"]').first()).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(modal.locator('[data-dashboard-action="apply-table-config"]')).toBeFocused();
});

test('editor opens with focus and returns focus to its trigger', async ({ page }) => {
  await setup(page);
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Editor focus' } });
  expect(program.ok()).toBeTruthy();
  const id = (await program.json()).program_id;
  await page.goto('/project-manager/');
  const trigger = page.locator(`[data-action="edit"][data-type="program"][data-id="${id}"]`).first();
  await trigger.click();
  await expect(page.locator('#program-modal-close')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#program-modal')).toBeHidden();
  await expect(trigger).toBeFocused();
  // A live collection refresh replaces the table after the dialog closes.
  expect((await page.request.post('/project-manager/api/programs', { data: { program_name: 'Refresh focus proof' } })).ok()).toBeTruthy();
  await expect(page.getByRole('button', { name: 'Refresh focus proof', exact: true })).toBeVisible();
  await expect(trigger).toBeFocused();
});
