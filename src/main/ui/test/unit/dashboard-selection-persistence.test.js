import { beforeEach, describe, expect, it } from 'vitest';
import { createDashboardState, renderDashboardView } from '../../js/routes/dashboard/render.js';
import { updateSectionPrefs, updatePrefs } from '../../js/routes/dashboard/prefs.js';

function harness() {
  document.body.innerHTML = '<section id="view-dashboard"><div id="main"></div><div id="completed"></div></section>';
  const dashboard = createDashboardState();
  const completed = new Date();
  completed.setDate(completed.getDate() - 20);
  const completedDate = `${completed.getFullYear()}-${String(completed.getMonth() + 1).padStart(2, '0')}-${String(completed.getDate()).padStart(2, '0')}`;
  const state = { activeSpace: { space_id: 'space' }, projects: [], tasks: [], users: [], solutions: [
    { solution_id: 'active', solution_name: 'Active solution', status: 'in_progress' },
    { solution_id: 'done', solution_name: 'Done solution', status: 'complete', completed_at: completedDate },
  ] };
  const ctx = { state, els: { dashboardTopProjects: document.querySelector('#main'), dashboardCompletedQuarter: document.querySelector('#completed') }, formatStatus: String };
  const render = () => renderDashboardView(dashboard, ctx);
  render();
  return { dashboard, state, render };
}

beforeEach(() => localStorage.clear());
describe('dashboard inclusion preferences', () => {
  it('preserves selected IDs across scope, horizon and temporary empty data', () => {
    const { dashboard, state, render } = harness();
    updatePrefs(dashboard, { scope: 'all', horizon_days: 90 });
    updateSectionPrefs(dashboard, 'main', { solution_ids: ['done'] });
    updateSectionPrefs(dashboard, 'completed', { solution_ids: ['done'] });
    render();
    updatePrefs(dashboard, { scope: 'active', horizon_days: 14 });
    render();
    expect(dashboard.prefs.sections.main.solution_ids).toEqual(['done']);
    expect(dashboard.prefs.sections.completed.solution_ids).toEqual(['done']);
    const solutions = state.solutions;
    state.solutions = [];
    render();
    state.solutions = solutions;
    updatePrefs(dashboard, { scope: 'all', horizon_days: 90 });
    render();
    expect(document.querySelector('#main').textContent).toContain('Done solution');
    expect(document.querySelector('#main').textContent).not.toContain('Active solution');
    expect(JSON.parse(localStorage.getItem('sipm-dashboard-view-prefs-v4:space')).sections.completed.solution_ids).toEqual(['done']);
  });
});

it('keeps selections outside the current window when applying visible changes', async () => {
  const { openDashboardConfigModal, renderDashboardConfigModal, applyModalConfig } = await import('../../js/routes/dashboard/modal.js');
  const { dashboard, render } = harness();
  updatePrefs(dashboard, { scope: 'all' });
  updateSectionPrefs(dashboard, 'main', { solution_ids: ['done'] });
  render();
  updatePrefs(dashboard, { scope: 'active' });
  render();
  openDashboardConfigModal(dashboard, 'main');
  renderDashboardConfigModal(dashboard, 'main', { columnDefsBySection: dashboard.columnDefsBySection });
  document.querySelector("input[name='dashboard-config-solution'][value='active']").checked = true;
  applyModalConfig(dashboard, render);
  expect(dashboard.prefs.sections.main.solution_ids).toEqual(['done', 'active']);
});

it('preserves legacy preferences when scoped storage writes fail', async () => {
  const { loadPrefs } = await import('../../js/routes/dashboard/prefs.js');
  localStorage.setItem('sipm-dashboard-view-prefs-v3', JSON.stringify({ scope: 'mine' }));
  const originalSet = Storage.prototype.setItem;
  Storage.prototype.setItem = function (key, value) {
    if (key.startsWith('sipm-dashboard-view-prefs-v4:')) throw new Error('quota');
    return originalSet.call(this, key, value);
  };
  try {
    expect(loadPrefs('space').scope).toBe('mine');
    expect(localStorage.getItem('sipm-dashboard-view-prefs-v3')).not.toBeNull();
  } finally {
    Storage.prototype.setItem = originalSet;
  }
});

it('keeps completed items with ISO timestamp dates while rejecting malformed timestamps', () => {
  const { state, render } = harness();
  const date = state.solutions[1].completed_at;
  state.solutions[1].completed_at = `${date}T23:59:59.123456Z`;
  render();
  expect(document.querySelector('#completed').textContent).toContain('Done solution');
  state.solutions[1].completed_at = `${date}invalid`;
  render();
  expect(document.querySelector('#completed').textContent).not.toContain('Done solution');
});
