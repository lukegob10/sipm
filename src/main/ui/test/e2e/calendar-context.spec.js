import { test, expect } from '@playwright/test';

test('calendar modal clears on sign out', async ({ page }) => {
  const soeid = `cal${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Calendar user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Calendar program' } });
  expect(program.ok()).toBeTruthy();
  const project = await page.request.post('/project-manager/api/projects', { data: { program_id: (await program.json()).program_id, project_name: 'Calendar project' } });
  expect(project.ok()).toBeTruthy();
  const solution = await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: 'Private calendar solution', version: '1', due_date: '2026-05-14' } });
  expect(solution.ok()).toBeTruthy();
  await page.goto('/project-manager/calendar');
  const month = page.locator('#calendar-month');
  await month.fill('2026-05');
  await month.dispatchEvent('change');
  await page.locator('.calendar-cell[data-day="14"] .calendar-open-day').click();
  await expect(page.locator('#calendar-modal')).toBeVisible();
  await expect(page.locator('#calendar-modal-list')).toContainText('Private calendar solution');
  await expect(page.getByRole('dialog', { name: 'May 14, 2026' })).toBeVisible();
  await expect(page.locator('#calendar-modal-close')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#calendar-modal')).toBeHidden();
  await expect(page.locator('.calendar-cell[data-day="14"] .calendar-open-day')).toBeFocused();
  await page.locator('.calendar-cell[data-day="14"] .calendar-open-day').click();
  await page.locator('#logout-btn').dispatchEvent('click');
  await expect(page.locator('#auth-screen')).toBeVisible();
  await expect(page.locator('#calendar-modal')).toBeHidden();
  await expect(page.locator('#calendar-modal-list')).toBeEmpty();
});


test('calendar modal clears when the active space changes', async ({ page }) => {
  const soeid = `cals${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Calendar user', password: 'Password123' } })).ok()).toBeTruthy();
  const spaces = await page.request.get('/project-manager/api/spaces');
  expect(spaces.ok()).toBeTruthy();
  const home = (await spaces.json())[0];
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Private program' } });
  expect(program.ok()).toBeTruthy();
  const project = await page.request.post('/project-manager/api/projects', { data: { program_id: (await program.json()).program_id, project_name: 'Private project' } });
  expect(project.ok()).toBeTruthy();
  const solution = await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: 'Private calendar item', version: '1', due_date: '2026-05-14' } });
  expect(solution.ok()).toBeTruthy();
  await page.goto('/project-manager/calendar');
  await page.locator('#calendar-month').fill('2026-05');
  await page.locator('#calendar-month').dispatchEvent('change');
  await page.locator('.calendar-cell[data-day="14"] .calendar-open-day').click();
  await expect(page.locator('#calendar-modal-list')).toContainText('Private calendar item');
  await page.locator('#space-switcher-trigger').dispatchEvent('click');
  const switched = page.waitForResponse((response) => response.url().endsWith('/api/auth/active-space') && response.request().method() === 'POST');
  await page.locator(`#space-switcher-all-list [data-space-switch="${home.space_id}"]`).dispatchEvent('click');
  const response = await switched;
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).space_id).toBe(home.space_id);
  await expect(page.locator('#calendar-modal')).toBeHidden();
  await expect(page.locator('#calendar-modal-list')).toBeEmpty();
});


test('space switch restores Calendar and Deliverables preferences for the destination', async ({ page }) => {
  const soeid = `calm${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Calendar user', password: 'Password123' } })).ok()).toBeTruthy();
  const spaces = await page.request.get('/project-manager/api/spaces');
  expect(spaces.ok()).toBeTruthy();
  const home = (await spaces.json())[0];
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  const personalId = (await personal.json()).space_id;
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: personalId } })).ok()).toBeTruthy();
  await page.goto('/project-manager/calendar');
  await expect(page.locator('#app-shell')).toBeVisible();
  const month = page.locator('#calendar-month');
  await expect(month).toBeVisible();
  await month.fill('2026-05');
  await month.dispatchEvent('change');
  await page.evaluate(({ user, space }) => {
    const saved = [{ view_id: 'home-view', name: 'Home saved view', preset: 'all', filters: {}, updated_at: '' }];
    localStorage.setItem(`sipm-tasks-workbench-views:${user}:${space}`, JSON.stringify(saved));
    localStorage.setItem(`sipm-tasks-workbench-views:another-user:${space}`, JSON.stringify([{ view_id: 'other', name: 'Other user view', preset: 'all', filters: {} }]));
  }, { user: soeid, space: home.space_id });
  const switchTo = async (id) => {
    await page.locator('#space-switcher-trigger').click();
    const response = page.waitForResponse((r) => r.url().endsWith('/api/auth/active-space') && r.request().method() === 'POST');
    await page.locator(`#space-switcher-all-list [data-space-switch="${id}"]`).click();
    expect((await response).ok()).toBeTruthy();
    await expect(page.locator('#space-switcher-panel')).toHaveClass(/hidden/);
  };
  await switchTo(home.space_id);
  await expect(page.locator('#tasks-workbench-saved-select')).toContainText('Home saved view');
  await expect(page.locator('#tasks-workbench-saved-select')).not.toContainText('Other user view');
  await page.evaluate(({ user, space }) => {
    localStorage.setItem(`sipm-calendar-view-state-v1:${space}`, JSON.stringify({ month: '2026-07', filters: { project: '', owner: '' } }));
    localStorage.setItem(`sipm-master-filters-v1:${space}`, JSON.stringify({ filters: { query: 'destination-query' }, collapsed: [] }));
    localStorage.setItem(`sipm-tasks-workbench-views:${user}:${space}`, JSON.stringify([{ view_id: 'personal-view', name: 'Personal saved view', preset: 'all', filters: {}, updated_at: '' }]));
  }, { user: soeid, space: personalId });
  await switchTo(personalId);
  await expect(page.locator('#tasks-workbench-saved-select')).toContainText('Personal saved view');
  await expect(page.locator('#tasks-workbench-saved-select')).not.toContainText('Home saved view');
  await page.locator('.nav-btn[data-view="calendar"]').click();
  await expect(month).toHaveValue('2026-07');
  await expect(page.locator('.calendar-month-label')).toContainText('July 2026');
  await page.locator('.nav-btn[data-view="master"]').click();
  await expect(page.locator('#filter-query')).toHaveValue('destination-query');
});
