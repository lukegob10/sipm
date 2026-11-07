import { describe, expect, it } from 'vitest';
import { renderGantt } from '../../js/routes/gantt.js';
import { registerMutationContextLifetime } from '../../js/utils/form-state.js';

function createChart() {
  document.body.innerHTML = '<div id="chart"></div>';
  const chart = document.querySelector('#chart');
  const state = {
    authed: true, user: { user_id: 'u1' }, activeSpace: { space_id: 's1' }, currentView: 'gantt',
    ganttWindow: { from: '2026-01-01', to: '2027-12-31' }, ganttCollapsed: new Set(),
    programs: [{ program_id: 'p1', program_name: 'Program' }],
    projects: [{ project_id: 'j1', program_id: 'p1', project_name: 'Project' }],
    solutions: [{ solution_id: 's1', project_id: 'j1', solution_name: 'Solution', due_date: '2026-05-14' }], tasks: [],
  };
  let session = 1;
  let space = 1;
  registerMutationContextLifetime(state, () => ({ session, space }));
  const ctx = { state, els: { ganttChart: chart } };
  renderGantt(ctx);
  chart.querySelector('.gantt-scroll').scrollLeft = 300;
  chart.querySelector('[data-gantt-key="program:p1"]').focus();
  return { chart, state, ctx, newSession: () => { session += 1; }, newSpace: () => { space += 1; } };
}

describe('Gantt viewport preservation', () => {
  it('preserves scroll and toggle focus during same-session rerender and token refresh', () => {
    const h = createChart();
    h.state.user = { user_id: 'u1' };
    h.state.activeSpace = { space_id: 's1' };
    h.state.ganttCollapsed.add('program:p1');
    renderGantt(h.ctx);
    expect(h.chart.querySelector('.gantt-scroll').scrollLeft).toBe(300);
    expect(document.activeElement.getAttribute('data-gantt-key')).toBe('program:p1');
    expect(document.activeElement.getAttribute('aria-label')).toContain('Expand');
  });

  it.each(['session', 'space', 'window', 'view'])('does not restore the prior viewport after %s changes', (change) => {
    const h = createChart();
    if (change === 'session') h.newSession();
    if (change === 'space') h.newSpace();
    if (change === 'window') h.state.ganttWindow.to = '2028-12-31';
    if (change === 'view') h.state.currentView = 'calendar';
    renderGantt(h.ctx);
    expect(h.chart.querySelector('.gantt-scroll').scrollLeft).toBe(0);
    expect(h.chart.contains(document.activeElement)).toBe(false);
  });
});
