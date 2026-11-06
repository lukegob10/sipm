import { describe, expect, it } from 'vitest';
import { renderGantt, resolveGanttTimelineScale } from '../../js/routes/gantt.js';

function renderWindow(from, to, dueDates) {
  document.body.innerHTML = '<div id="chart"></div>';
  const chart = document.querySelector('#chart');
  const state = {
    ganttWindow: { from, to }, ganttCollapsed: new Set(),
    programs: [{ program_id: 'p1', program_name: 'Program' }],
    projects: [{ project_id: 'j1', program_id: 'p1', project_name: 'Project' }],
    solutions: [{ solution_id: 's1', project_id: 'j1', solution_name: 'Solution' }],
    tasks: dueDates.map((due, index) => ({ task_id: `t${index}`, project_id: 'j1', solution_id: 's1', task_name: `Task ${index}`, due_date: due })),
  };
  renderGantt({ state, els: { ganttChart: chart } });
  return chart;
}

describe('Gantt long ranges', () => {
  it('keeps ordinary month boundaries and labels', () => {
    const chart = renderWindow('2026-01-15', '2026-03-05', ['2026-02-01']);
    const ticks = [...chart.querySelectorAll('.gantt-month-tick')];
    expect(ticks).toHaveLength(3);
    expect(ticks.map((tick) => tick.textContent)).toEqual(['Jan 2026', 'Feb 2026', 'Mar 2026']);
  });

  it('bounds labels and width across supported years while keeping endpoint positions', () => {
    const chart = renderWindow('0001-01-01', '9999-12-31', ['0001-01-01', '9999-12-31']);
    const ticks = chart.querySelectorAll('.gantt-month-tick');
    expect(ticks.length).toBeLessThanOrEqual(240);
    expect(ticks.length).toBeGreaterThan(1);
    const scroll = chart.querySelector('.gantt-scroll');
    expect(parseFloat(scroll.style.getPropertyValue('--gantt-track-width'))).toBe(262144);
    const first = chart.querySelector('.gantt-milestone[data-gantt-id="t0"]');
    const last = chart.querySelector('.gantt-milestone[data-gantt-id="t1"]');
    const overhang = (11 * Math.SQRT2 - 11) / 2;
    expect(parseFloat(first.style.left)).toBeCloseTo(overhang, 1);
    expect(parseFloat(last.style.left) + 11 + overhang).toBeCloseTo(262144, 1);
    expect(scroll.classList.contains('gantt-no-week-grid')).toBe(true);
  });

  it('limits wide timeline geometry proportionally', () => {
    const scale = resolveGanttTimelineScale({ totalDays: 3_652_059 }, 1200, 620);
    expect(scale.trackWidth).toBe(262144);
    expect(scale.dayWidth * 3_652_059).toBeCloseTo(scale.trackWidth);
  });
});
