import { expect, it } from 'vitest';
import { loadTasksWorkbenchSavedViews, updateTasksWorkbenchSavedViewsUI, bindTasksWorkbenchSavedViewControls } from '../../js/routes/tasks-workbench/saved-views.js';

it('preserves the restored selected view when its list loads', () => {
  localStorage.clear();
  localStorage.setItem('saved:user:space', JSON.stringify([{ view_id: 'v1', name: 'One' }]));
  const state = { authed: true, user: { soeid: 'user' }, tasksWorkbench: { selectedSavedViewId: 'v1' } };
  loadTasksWorkbenchSavedViews({ state, normalize: s => s.toLowerCase(), activeSpaceId: () => 'space', tasksWorkbenchSavedViewsKeyPrefix: 'saved' });
  expect(state.tasksWorkbench.savedViews).toHaveLength(1);
  expect(state.tasksWorkbench.selectedSavedViewId).toBe('v1');
});

it('does not reorder the shared solution list when building filter options', async () => {
  const { updateTasksWorkbenchSolutionOptions } = await import('../../js/routes/tasks-workbench/interactions.js');
  document.body.innerHTML = '<select id="solutions"></select>';
  const solutions = [ { solution_id: 'b', solution_name: 'Beta' }, { solution_id: 'a', solution_name: 'Alpha' } ];
  const select = document.querySelector('#solutions');
  updateTasksWorkbenchSolutionOptions({ state: { solutions }, els: { tasksWorkbenchSolution: select } }, '');
  expect(solutions.map((row) => row.solution_id)).toEqual(['b', 'a']);
  expect(Array.from(select.options).map((option) => option.value)).toEqual(['', 'a', 'b']);
});

it('renders a stored view ID as text within its option value', async () => {
  const { updateTasksWorkbenchSavedViewsUI } = await import('../../js/routes/tasks-workbench/saved-views.js');
  document.body.innerHTML = '<select id="saved"></select>';
  const id = 'x"/><img src=x onerror="alert(1)';
  const select = document.querySelector('#saved');
  updateTasksWorkbenchSavedViewsUI({
    state: { tasksWorkbench: { savedViews: [{ view_id: id, name: 'View' }], selectedSavedViewId: id } },
    els: { tasksWorkbenchSavedSelect: select },
    escapeHtml: (value) => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'),
    persistTasksWorkbenchUiState: () => {},
  });
  expect(select.options).toHaveLength(2);
  expect(select.options[1].value).toBe(id);
  expect(document.querySelector('img')).toBeNull();
});

it('reports storage failures for saving and deleting views', async () => {
  document.body.innerHTML = '<input id="name" value="View"><button id="save"></button><button id="delete"></button><select id="saved"></select><span id="status"></span>';
  const wb = { savedViews: [], selectedSavedViewId: '', preset: 'all', filters: {} };
  const state = { authed: true, user: { soeid: 'user' }, activeSpace: { space_id: 'space' }, tasksWorkbench: wb };
  const els = { tasksWorkbenchSavedName: document.querySelector('#name'), tasksWorkbenchSavedSave: document.querySelector('#save'), tasksWorkbenchSavedDelete: document.querySelector('#delete'), tasksWorkbenchSavedSelect: document.querySelector('#saved'), tasksWorkbenchSavedStatus: document.querySelector('#status') };
  const ctx = { state, els, normalize: (value) => value.toLowerCase(), escapeHtml: String, activeSpaceId: () => 'space', tasksWorkbenchSavedViewsKeyPrefix: 'saved', persistTasksWorkbenchUiState: () => {}, showConfirmModal: async () => true };
  bindTasksWorkbenchSavedViewControls(ctx);
  const originalSet = Storage.prototype.setItem;
  const originalWarn = console.warn;
  Storage.prototype.setItem = () => { throw new Error('quota'); };
  console.warn = () => {};
  try {
    els.tasksWorkbenchSavedSave.click();
    expect(els.tasksWorkbenchSavedStatus.textContent).toMatch(/could not save.*browser storage/i);
    els.tasksWorkbenchSavedDelete.click();
    await Promise.resolve();
    expect(els.tasksWorkbenchSavedStatus.textContent).toMatch(/could not save this deletion/i);
  } finally {
    Storage.prototype.setItem = originalSet;
    console.warn = originalWarn;
  }
});

it('does not overwrite saved views after a transient storage read failure', () => {
  localStorage.clear();
  const key = 'saved:user:space';
  const original = JSON.stringify([{ view_id: 'v1', name: 'Keep' }]);
  localStorage.setItem(key, original);
  document.body.innerHTML = '<select id="saved"></select><input id="name" value="New"><button id="save"></button><span id="status"></span>';
  const state = { authed: true, user: { soeid: 'user' }, tasksWorkbench: { selectedSavedViewId: 'v1', savedViews: [{ view_id: 'old', name: 'Previous space' }], filters: {} } };
  let uiWrites = 0;
  const els = { tasksWorkbenchSavedSelect: document.querySelector('#saved'), tasksWorkbenchSavedName: document.querySelector('#name'), tasksWorkbenchSavedSave: document.querySelector('#save'), tasksWorkbenchSavedStatus: document.querySelector('#status') };
  const ctx = { state, els, normalize: s => s.toLowerCase(), escapeHtml: String, activeSpaceId: () => 'space', tasksWorkbenchSavedViewsKeyPrefix: 'saved', persistTasksWorkbenchUiState: () => { uiWrites++; } };
  const originalGet = Storage.prototype.getItem;
  const originalWarn = console.warn;
  Storage.prototype.getItem = function (name) { if (name === key) throw new Error('read failed'); return originalGet.call(this, name); };
  console.warn = () => {};
  try {
    loadTasksWorkbenchSavedViews(ctx);
    updateTasksWorkbenchSavedViewsUI(ctx);
    bindTasksWorkbenchSavedViewControls(ctx);
    els.tasksWorkbenchSavedSave.click();
    expect(els.tasksWorkbenchSavedStatus.textContent).toMatch(/could not load/i);
    expect(els.tasksWorkbenchSavedSelect.options).toHaveLength(1);
    expect(state.tasksWorkbench.selectedSavedViewId).toBe('v1');
    expect(uiWrites).toBe(0);
  } finally {
    Storage.prototype.getItem = originalGet;
    console.warn = originalWarn;
  }
  expect(localStorage.getItem(key)).toBe(original);
});

it('still resets malformed saved view data', () => {
  localStorage.clear();
  const key = 'saved:user:space';
  localStorage.setItem(key, '{invalid');
  const state = { authed: true, user: { soeid: 'user' }, tasksWorkbench: {} };
  const originalWarn = console.warn;
  console.warn = () => {};
  try {
    loadTasksWorkbenchSavedViews({ state, normalize: s => s.toLowerCase(), activeSpaceId: () => 'space', tasksWorkbenchSavedViewsKeyPrefix: 'saved' });
  } finally {
    console.warn = originalWarn;
  }
  expect(localStorage.getItem(key)).toBe('[]');
});
