import { expect, it } from 'vitest';
import { saveTasksWorkbenchForm, deleteActiveTasksWorkbenchItem, handleTasksWorkbenchShortcut } from '../../js/routes/tasks-workbench/drawer.js';
import { applyTasksWorkbenchBulkAction } from '../../js/routes/tasks-workbench/bulk-actions.js';

function setup() {
  document.body.innerHTML = '<form id="task"><input name="task_id" value="a"><input name="task_name" value="Task"><input name="status" value="to_do"><input name="priority" value="3"><input name="assignee_user_soeid"></form>';
  const state = { user: {user_id:'u'}, activeSpace: {space_id:'s'}, tasks: [], currentView:'tasks-workbench', tasksWorkbench: {activeTaskId:'a', selected:new Set(['a'])} };
  const row = {task_id:'a', task_name:'Task', status:'to_do', priority:3, project_id:'p', solution_id:'s'};
  const requests = [], notices = [];
  const ctx = {state, els:{ tasksWorkbenchForm:document.querySelector('#task'), tasksWorkbenchBulkAction:{value:'status'}, tasksWorkbenchBulkStatus:{value:'on_hold'} }, api:(path) => new Promise(resolve => requests.push({path, resolve})), upsertById:()=>{}, findUserBySoeid:()=>null, renderTasksWorkbench:()=>{}, renderDashboard:()=>{}, setTasksWorkbenchBulkFeedback:(message)=>notices.push(message), setDeliverableFormNotice:(_el,message)=>notices.push(message), persistTasksWorkbenchUiState:()=>{}, resolveAssigneeSelectValue:()=>'', timestampLabel:()=>'', deleteTasksById: () => new Promise(resolve => requests.push({path:'delete', resolve})) };
  return { ctx, state, row, requests, notices };
}

it('blocks overlapping bulk during a save and releases after completion', async () => {
  const {ctx, row, requests, notices} = setup();
  const first = saveTasksWorkbenchForm(ctx);
  await applyTasksWorkbenchBulkAction(ctx);
  expect(requests).toHaveLength(1);
  expect(notices.at(-1)).toMatch(/wait/i);
  requests[0].resolve(row); await first;
  const next = applyTasksWorkbenchBulkAction(ctx);
  expect(requests).toHaveLength(2);
  requests[1].resolve([row]); await next;
});

it('blocks overlapping save during bulk and permits it after completion', async () => {
  const {ctx, row, requests, notices} = setup();
  const first = applyTasksWorkbenchBulkAction(ctx);
  await saveTasksWorkbenchForm(ctx);
  expect(requests).toHaveLength(1);
  expect(notices.at(-1)).toMatch(/wait/i);
  requests[0].resolve([row]); await first;
  const next = saveTasksWorkbenchForm(ctx);
  expect(requests).toHaveLength(2);
  requests[1].resolve(row); await next;
});

it('permits disjoint task mutations and a replacement context', async () => {
  const {ctx, state, row, requests} = setup();
  const first = saveTasksWorkbenchForm(ctx);
  state.tasksWorkbench.selected = new Set(['b']);
  const second = applyTasksWorkbenchBulkAction(ctx);
  expect(requests).toHaveLength(2);
  state.activeSpace = {space_id:'new'};
  state.tasksWorkbench.selected = new Set(['a']);
  const third = applyTasksWorkbenchBulkAction(ctx);
  expect(requests).toHaveLength(3);
  requests[0].resolve(row); requests[1].resolve([{...row, task_id:'b'}]); requests[2].resolve([row]);
  await Promise.all([first, second, third]);
});

it('blocks drawer and keyboard deletes while the selected task is saving', async () => {
  const {ctx, row, requests, notices} = setup();
  const save = saveTasksWorkbenchForm(ctx);
  await deleteActiveTasksWorkbenchItem(ctx);
  await handleTasksWorkbenchShortcut(ctx, { key:'Delete', target:document.body, preventDefault:()=>{} });
  expect(requests).toHaveLength(1);
  expect(notices.at(-1)).toMatch(/wait/i);
  requests[0].resolve(row); await save;
});

it('holds the task during delete confirmation and releases it after cancellation', async () => {
  const {ctx, row, requests, notices} = setup();
  const pendingDelete = deleteActiveTasksWorkbenchItem(ctx);
  await saveTasksWorkbenchForm(ctx);
  expect(requests).toHaveLength(1);
  expect(notices.at(-1)).toMatch(/wait/i);
  requests[0].resolve({cancelled:true, deletedIds:[], failed:[]});
  await pendingDelete;
  const save = saveTasksWorkbenchForm(ctx);
  expect(requests).toHaveLength(2);
  requests[1].resolve(row); await save;
});

it('does not let a stale release unlock an overlapping replacement request', async () => {
  const {ctx, state, row, requests, notices} = setup();
  const old = applyTasksWorkbenchBulkAction(ctx);
  state.activeSpace = {space_id:'new'};
  const current = applyTasksWorkbenchBulkAction(ctx);
  expect(requests).toHaveLength(2);
  requests[0].resolve([row]); await old;
  await saveTasksWorkbenchForm(ctx);
  expect(requests).toHaveLength(2);
  expect(notices.at(-1)).toMatch(/wait/i);
  requests[1].resolve([row]); await current;
});
