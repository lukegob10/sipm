import { describe, expect, it } from 'vitest';
import { buildGanttRows } from '../../js/routes/gantt.js';
import { parseDateOnly } from '../../js/utils/date-only.js';

function rowsFor(solution, tasks = []) {
  return buildGanttRows({
    ganttWindow: { from: '2026-01-01', to: '2026-12-31' },
    todayDay: parseDateOnly('2026-04-01').dayNumber,
    programs: [{ program_id: 'p1', program_name: 'Program' }],
    projects: [{ project_id: 'j1', program_id: 'p1', project_name: 'Project', status: 'active' }],
    solutions: [{ solution_id: 's1', project_id: 'j1', solution_name: 'Solution', status: 'active', ...solution }],
    tasks,
  }).rows;
}

describe('Gantt deadlines', () => {
  it('does not treat an active solution planned start as a due date', () => {
    const rows = rowsFor({ planned_start_date: '2026-03-01', due_date: null });
    expect(rows.find((row) => row.type === 'solution')).toMatchObject({ health: 'green', healthLabel: 'On time' });
    expect(rows.find((row) => row.type === 'project')).not.toMatchObject({ health: 'red' });
    expect(rows.find((row) => row.type === 'program')).not.toMatchObject({ health: 'red' });
  });

  it('describes an approaching or missed planned start when no deadline exists', () => {
    expect(rowsFor({ status: 'not_started', planned_start_date: '2026-04-05', due_date: null }).find((row) => row.type === 'solution'))
      .toMatchObject({ health: 'yellow', healthLabel: 'Starting soon' });
    expect(rowsFor({ status: 'not_started', planned_start_date: '2026-03-05', due_date: null }).find((row) => row.type === 'solution'))
      .toMatchObject({ health: 'yellow', healthLabel: 'Start passed' });
  });

  it('uses the actual due date even if the planned start is later', () => {
    const rows = rowsFor({ planned_start_date: '2026-05-01', due_date: '2026-03-01' });
    expect(rows.find((row) => row.type === 'solution')).toMatchObject({ health: 'red', healthLabel: 'Overdue' });
    expect(rows.find((row) => row.type === 'project')).toMatchObject({ health: 'red', healthLabel: 'Overdue' });
    expect(rows.find((row) => row.type === 'program')).toMatchObject({ health: 'red', healthLabel: 'Overdue' });
  });

  it('rolls up a child due date without using its later parent planned start', () => {
    const rows = rowsFor({ planned_start_date: '2026-05-01', due_date: null }, [
      { task_id: 't1', project_id: 'j1', solution_id: 's1', task_name: 'Late task', status: 'to_do', due_date: '2026-03-20' },
    ]);
    expect(rows.find((row) => row.type === 'solution')).toMatchObject({ health: 'yellow', healthLabel: 'Child overdue' });
    expect(rows.find((row) => row.type === 'project')).toMatchObject({ health: 'red', healthLabel: 'Overdue' });
    expect(rows.find((row) => row.type === 'program')).toMatchObject({ health: 'red', healthLabel: 'Overdue' });
  });

  it('still propagates overdue child work when the parent has no due date', () => {
    const rows = rowsFor({ planned_start_date: '2026-03-01', due_date: null }, [
      { task_id: 't1', project_id: 'j1', solution_id: 's1', task_name: 'Late task', status: 'to_do', due_date: '2026-03-20' },
      { task_id: 't2', project_id: 'j1', solution_id: 's1', task_name: 'Current task', status: 'to_do', due_date: '2026-04-20' },
    ]);
    expect(rows.find((row) => row.type === 'solution')).toMatchObject({ health: 'yellow', healthLabel: 'Child overdue' });
    expect(rows.find((row) => row.type === 'project')).toMatchObject({ health: 'yellow', healthLabel: 'Child overdue' });
  });
});
