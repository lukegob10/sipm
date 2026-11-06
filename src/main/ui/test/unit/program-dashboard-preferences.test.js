import { afterEach, expect, it } from 'vitest';
import { createProgramDashboardState, renderProgramDashboardView } from '../../js/routes/program-dashboard/render.js';

afterEach(() => { localStorage.clear(); document.body.innerHTML = ''; });

it('keeps private and separate public dashboard selections distinct for the same space', () => {
  document.body.innerHTML = '<section id="view-program-dashboard"><div id="program-dashboard-root"></div></section>';
  const state = { activeSpace: { space_id: 'space-1' }, programs: [{ program_id: 'a', program_name: 'A' }, { program_id: 'b', program_name: 'B' }], projects: [], solutions: [] };
  const els = { programDashboardRoot: document.querySelector('#program-dashboard-root') };
  const dashboard = createProgramDashboardState();
  const prefs = (id) => JSON.stringify({ selectedProgramIds: [id], collapsedProgramIds: [], collapsedProjectIds: [] });
  localStorage.setItem('sipm-program-dashboard-v1:space-1', prefs('b'));
  localStorage.setItem('sipm-program-dashboard-v1:public:one:space-1', prefs('a'));
  localStorage.setItem('sipm-program-dashboard-v1:public:two:space-1', prefs('b'));
  const render = (publicSlug = '') => {
    renderProgramDashboardView(dashboard, { state, els, formatStatus: String, publicMode: !!publicSlug, publicSlug });
    return [...els.programDashboardRoot.querySelectorAll('[data-program-dashboard-control="program"]')].filter((input) => input.checked).map((input) => input.value);
  };
  expect(render()).toEqual(['b']);
  expect(render('one')).toEqual(['a']);
  expect(render('two')).toEqual(['b']);
  expect(render()).toEqual(['b']);
  expect(localStorage.getItem('sipm-program-dashboard-v1:space-1')).toBe(prefs('b'));
});

it('does not overwrite private selection when a public dashboard shows a different program set', () => {
  document.body.innerHTML = '<section id="view-program-dashboard"><div id="program-dashboard-root"></div></section>';
  const privateKey = 'sipm-program-dashboard-v1:space-1';
  const original = { selectedProgramIds: ['private-b'], collapsedProgramIds: ['private-b'], collapsedProjectIds: [] };
  localStorage.setItem(privateKey, JSON.stringify(original));
  renderProgramDashboardView(createProgramDashboardState(), {
    publicMode: true, publicSlug: 'published',
    state: { activeSpace: { space_id: 'space-1' }, programs: [{ program_id: 'public-a', program_name: 'Public A' }], projects: [], solutions: [] },
    els: { programDashboardRoot: document.querySelector('#program-dashboard-root') }, formatStatus: String,
  });
  expect(JSON.parse(localStorage.getItem(privateKey))).toEqual(original);
});
