import { expect, test } from '@playwright/test';

test('collapsing a Roadmap row preserves timeline scroll and focus', async ({ page }) => {
  const soeid = `road${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Roadmap user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Roadmap program' } });
  expect(program.ok()).toBeTruthy();
  const programId = (await program.json()).program_id;
  const project = await page.request.post('/project-manager/api/projects', { data: { program_id: programId, project_name: 'Roadmap project' } });
  expect(project.ok()).toBeTruthy();
  const solution = await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: 'Roadmap solution', version: '1', due_date: '2026-05-14' } });
  expect(solution.ok()).toBeTruthy();
  await page.goto('/project-manager/');
  await page.locator('.nav-btn[data-view="gantt"]').click();
  await expect.poll(() => page.locator('#gantt-from').evaluate((el) => !!el._bound)).toBe(true);
  await page.locator('#gantt-from').fill('2026-01-01');
  await page.locator('#gantt-to').fill('2028-12-31');
  await expect(page.locator('.gantt-summary-window')).toHaveText('2026-01-01 - 2028-12-31');
  const scroll = page.locator('.gantt-scroll');
  const toggle = page.locator(`[data-gantt-action="toggle-collapse"][data-gantt-key="program:${programId}"]`);
  await expect(toggle).toBeVisible();
  // A data refresh can replace the chart after the locator resolves. Set the
  // initial position on a connected scroll container before testing collapse.
  await expect.poll(() => scroll.evaluate((el) => {
    if (!el.isConnected) return 0;
    el.scrollLeft = 300;
    return el.scrollLeft;
  })).toBeGreaterThan(200);
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(toggle).toHaveAttribute('aria-label', /Expand/);
  await expect(toggle).toBeFocused();
  expect(await scroll.evaluate((el) => el.scrollLeft)).toBeGreaterThan(200);
  await page.locator('#gantt-from').fill('0001-01-01');
  await page.locator('#gantt-to').fill('9999-12-31');
  await expect(page.locator('.gantt-month-tick').first()).toBeVisible();
  expect(await page.locator('.gantt-month-tick').count()).toBeLessThanOrEqual(240);
  expect(await scroll.evaluate((el) => parseFloat(el.style.getPropertyValue('--gantt-track-width')))).toBe(262144);
  expect(await page.locator('.gantt-row-program .gantt-track').evaluate((el) => getComputedStyle(el).backgroundImage)).toBe('none');
});

test('milestone markers stay within timeline edges', async ({ page }) => {
  const soeid = `edge${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post('/project-manager/api/auth/register', { data: { soeid, display_name: 'Roadmap user', password: 'Password123' } })).ok()).toBeTruthy();
  const personal = await page.request.post('/project-manager/api/spaces/personal', { data: {} });
  expect(personal.ok()).toBeTruthy();
  expect((await page.request.post('/project-manager/api/auth/active-space', { data: { space_id: (await personal.json()).space_id } })).ok()).toBeTruthy();
  const program = await page.request.post('/project-manager/api/programs', { data: { program_name: 'Edge program' } });
  const project = await page.request.post('/project-manager/api/projects', { data: { program_id: (await program.json()).program_id, project_name: 'Edge project' } });
  expect((await page.request.post(`/project-manager/api/projects/${(await project.json()).project_id}/solutions`, { data: { solution_name: 'Edge milestone', version: '1', due_date: '2026-05-14' } })).ok()).toBeTruthy();
  await page.goto('/project-manager/gantt');
  const marker = page.locator('.gantt-row-solution .gantt-milestone');
  await expect.poll(() => page.locator('#gantt-from').evaluate((el) => !!el._bound)).toBe(true);
  for (const [from, to] of [['2026-01-01', '2026-05-14'], ['2026-05-14', '2026-12-31']]) {
    await page.locator('#gantt-from').fill(from);
    await page.locator('#gantt-to').fill(to);
    await expect(page.locator('.gantt-summary-window')).toHaveText(`${from} - ${to}`);
    await expect(marker).toBeVisible();
    const bounds = await marker.evaluate((node) => {
      const markerBox = node.getBoundingClientRect();
      const trackBox = node.closest('.gantt-track').getBoundingClientRect();
      return { left: markerBox.left - trackBox.left, right: markerBox.right - trackBox.right };
    });
    expect(bounds.left).toBeGreaterThanOrEqual(-0.1);
    expect(bounds.right).toBeLessThanOrEqual(0.1);
  }
});
