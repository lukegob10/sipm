import { afterEach, expect, it, vi } from 'vitest';
import { filteredSolutions } from '../../js/routes/master/filters.js';

afterEach(() => vi.useRealTimers());
function filter(query, solutions, extra = {}) {
  const state = { filters: { query }, solutions, projects: [], programs: [], tasks: [], ...extra };
  return filteredSolutions({ state, hideClosedDeliverables: () => false, isClosedSolutionStatus: () => false });
}

it('treats today as not overdue and ignores closed or malformed dates', () => {
  vi.useFakeTimers(); vi.setSystemTime(new Date(2026, 9, 29, 16));
  const solutions = [
    { solution_id: 'today', status: 'active', due_date: '2026-10-29' },
    { solution_id: 'past', status: 'active', due_date: '2026-10-28' },
    { solution_id: 'closed', status: 'complete', due_date: '2026-10-28' },
    { solution_id: 'invalid', status: 'active', due_date: '2026-02-30' },
  ];
  expect(filter('overdue', solutions).map((row) => row.solution_id)).toEqual(['past']);
});

it('matches current user IDs on solutions and projects without prefix collisions', () => {
  const solutions = [
    { solution_id: 'a', owner_user_soeid: 'AX1' },
    { solution_id: 'b', project_id: 'p' },
    { solution_id: 'c', owner_user_soeid: 'ax12' },
  ];
  const extra = { user: { display_name: 'Alex', soeid: 'ax1' }, projects: [{ project_id: 'p', owner_user_soeid: 'ax1' }] };
  expect(filter('my', solutions, extra).map((row) => row.solution_id)).toEqual(['a', 'b']);
  expect(filter('owner:ax1', solutions, extra).map((row) => row.solution_id)).toEqual(['a', 'b', 'c']);
});

it('uses linked IDs before names, with exact legacy name fallback', () => {
  const solutions = [
    { solution_id: 'linked-other', owner: 'Alex', owner_user_soeid: 'other' },
    { solution_id: 'similar-name', owner: 'Alexandra' },
    { solution_id: 'legacy', owner: ' alex ' },
    { solution_id: 'assignee', assignee_user_soeid: 'AX1' },
    { solution_id: 'sponsor', project_id: 'sponsored' },
  ];
  const extra = { user: { display_name: 'Alex', soeid: 'ax1' }, projects: [{ project_id: 'sponsored', sponsor_user_soeid: 'ax1' }] };
  expect(filter('my', solutions, extra).map((row) => row.solution_id)).toEqual(['legacy', 'assignee', 'sponsor']);
  expect(filter('owner:ax1', solutions, extra).map((row) => row.solution_id)).toEqual(['assignee']);
  expect(filter('sponsor:ax1', solutions, extra).map((row) => row.solution_id)).toEqual(['sponsor']);
});

it('shows an active solution under its closed project while closed work is hidden', async () => {
  const { filteredDeliverables } = await import('../../js/routes/master/filters.js');
  const state = { filters: {query:''}, programs:[], tasks:[], projects:[{project_id:'p', project_name:'Closed parent', status:'complete'}], solutions:[{solution_id:'active', solution_name:'Active child', project_id:'p', status:'active'}, {solution_id:'closed', project_id:'p', status:'complete'}] };
  const ctx = {state, hideClosedDeliverables:()=>true, isClosedProjectStatus:(status)=>status==='complete', isClosedSolutionStatus:(status)=>status==='complete', solutionProgress:()=>0};
  const rows = filteredDeliverables(ctx);
  expect(rows.find((row) => row.type === 'project-header').project.project_name).toBe('Closed parent');
  expect(rows.filter((row) => row.type === 'solution').map((row) => row.solution.solution_id)).toEqual(['active']);
});

it('uses strict civil dates for due-soon summaries', async () => {
  const { filteredDeliverables } = await import('../../js/routes/master/filters.js');
  vi.useFakeTimers(); vi.setSystemTime(new Date(2026, 1, 25, 12));
  const state = {filters:{query:''}, programs:[], tasks:[], projects:[{project_id:'p'}], solutions:[
    {solution_id:'invalid',project_id:'p',due_date:'2026-02-30',status:'active'},
    {solution_id:'valid',project_id:'p',due_date:'2026-03-01',status:'active'},
  ]};
  const rows = filteredDeliverables({state,hideClosedDeliverables:()=>false,isClosedProjectStatus:()=>false,isClosedSolutionStatus:()=>false,solutionProgress:()=>0});
  expect(rows.find((row) => row.type === 'project-header').dueSoonCount).toBe(1);
});
