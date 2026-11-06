import { expect, it } from 'vitest';
import { applyTasksWorkbenchBulkAction } from '../../js/routes/tasks-workbench/bulk-actions.js';

it('rejects fractional shifts', async () => {
  let calls = 0;
  const ctx = { state: { tasksWorkbench: { selected: new Set(['a']) } }, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '1.9' } }, api: async () => { calls++; return []; }, upsertById: () => {}, renderTasksWorkbench: () => {}, setTasksWorkbenchBulkFeedback: () => {} };
  await applyTasksWorkbenchBulkAction(ctx);
  expect(calls).toBe(0);
});

it('does not duplicate an in-flight bulk shift', async () => {
  let calls = 0, finish;
  const ctx = { state: { tasks: [], tasksWorkbench: { selected: new Set(['a']) } }, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '1' } }, api: () => { calls++; return new Promise(r => { finish = r; }); }, upsertById: () => {}, renderTasksWorkbench: () => {}, setTasksWorkbenchBulkFeedback: () => {} };
  const first = applyTasksWorkbenchBulkAction(ctx);
  void applyTasksWorkbenchBulkAction(ctx);
  expect(calls).toBe(1);
  finish([]);
  await first;
});


it('ignores a delete result after the space changes', async () => {
  let finish, rendered = 0;
  const state = { user: { user_id: 'u' }, activeSpace: { space_id: 'one' }, tasksWorkbench: { selected: new Set(['a']) } };
  const ctx = { state, els: { tasksWorkbenchBulkAction: { value: 'delete' } }, deleteTasksById: () => new Promise(r => { finish = r; }), renderTasksWorkbench: () => { rendered++; }, setTasksWorkbenchBulkFeedback: () => {} };
  const request = applyTasksWorkbenchBulkAction(ctx);
  state.activeSpace = { space_id: 'two' };
  finish({ cancelled: false, failed: [], deletedIds: ['a'] });
  await request;
  expect(rendered).toBe(0);
});

it('reports incomplete server responses without claiming success or replacing tasks', async () => {
  const messages = [];
  const state = { tasks: [{ task_id: 'a', task_name: 'Old' }], tasksWorkbench: { selected: new Set(['a']) } };
  const ctx = { state, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '1' } }, api: async () => [{ task_id: 'a' }], upsertById: () => { throw new Error('must not replace data'); }, setTasksWorkbenchBulkFeedback: (message) => messages.push(message) };
  await applyTasksWorkbenchBulkAction(ctx);
  expect(messages.at(-1)).toMatch(/may have succeeded; refresh before retrying/i);
  expect(state.tasks[0].task_name).toBe('Old');
});

it('accepts a complete response and allows another action after completion', async () => {
  const row = { task_id: 'a', task_name: 'Task', status: 'to_do', priority: 3, project_id: 'p', solution_id: 's' };
  let calls = 0;
  const messages = [];
  const state = { tasks: [], tasksWorkbench: { selected: new Set(['a']) } };
  const ctx = { state, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '-2' } }, api: async (_path, options) => { calls++; expect(JSON.parse(options.body).due_date_shift_days).toBe(-2); return [row]; }, upsertById: (list, item) => list.push(item), renderTasksWorkbench: () => {}, setTasksWorkbenchBulkFeedback: (message) => messages.push(message) };
  await applyTasksWorkbenchBulkAction(ctx);
  await applyTasksWorkbenchBulkAction(ctx);
  expect(calls).toBe(2);
  expect(messages.at(-1)).toBe('Updated 1 task.');
});

it('does not let an old in-flight action block a replacement space', async () => {
  let firstResolve, calls = 0;
  const row = { task_id: 'a', task_name: 'Task', status: 'to_do', priority: 3, project_id: 'p', solution_id: 's' };
  const state = { user: { user_id: 'u' }, activeSpace: { space_id: 'one' }, tasks: [], tasksWorkbench: { selected: new Set(['a']) } };
  const ctx = { state, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '1' } }, api: () => { calls++; return calls === 1 ? new Promise(r => { firstResolve = r; }) : Promise.resolve([row]); }, upsertById: () => {}, renderTasksWorkbench: () => {}, setTasksWorkbenchBulkFeedback: () => {} };
  const first = applyTasksWorkbenchBulkAction(ctx);
  state.activeSpace = { space_id: 'two' };
  await applyTasksWorkbenchBulkAction(ctx);
  expect(calls).toBe(2);
  firstResolve([row]);
  await first;
});

it.each([
  { code: 'NETWORK_UNAVAILABLE', status: 0 },
  { status: 408 },
  { status: 503 },
])('warns about uncertain mutation outcome for %o', async (error) => {
  const messages = [];
  const state = { tasks: [], tasksWorkbench: { selected: new Set(['a']) } };
  const ctx = { state, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '1' } }, api: async () => { throw error; }, setTasksWorkbenchBulkFeedback: (message) => messages.push(message) };
  await applyTasksWorkbenchBulkAction(ctx);
  expect(messages.at(-1)).toMatch(/may have succeeded.*refresh before retrying/i);
});

it('reports a definite validation rejection as a failure', async () => {
  const messages = [];
  const state = { tasks: [], tasksWorkbench: { selected: new Set(['a']) } };
  const ctx = { state, els: { tasksWorkbenchBulkAction: { value: 'shift_due' }, tasksWorkbenchBulkShift: { value: '1' } }, api: async () => { throw { status: 400, message: 'Bad shift' }; }, setTasksWorkbenchBulkFeedback: (message) => messages.push(message) };
  await applyTasksWorkbenchBulkAction(ctx);
  expect(messages.at(-1)).toBe('Bulk update failed: Bad shift');
});
