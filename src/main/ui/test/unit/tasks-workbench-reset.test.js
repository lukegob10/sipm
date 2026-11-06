import { expect, it, vi } from "vitest";
import { fillTasksWorkbenchForm, resetTasksWorkbenchEditor } from "../../js/routes/tasks-workbench/drawer.js";
it("resets the current task without switching selection", () => {
  document.body.innerHTML = '<form><input name="task_id"><input name="task_name"><textarea name="description"></textarea></form>';
  const form = document.querySelector('form');
  const task = { task_id: 'a', task_name: 'Saved', status: 'to_do' };
  const state = { tasks: [task], projects: [], solutions: [], tasksWorkbench: { activeTaskId: 'a', drawerOpen: true } };
  const ctx = { state, els: { tasksWorkbenchForm: form }, resolveAssigneeSelectValue: () => '', clearDeliverableFormNotice: vi.fn(), persistTasksWorkbenchUiState: vi.fn() };
  ctx.renderTasksWorkbench = () => { if (!state.tasksWorkbench.activeTaskId) state.tasksWorkbench.activeTaskId = 'a'; fillTasksWorkbenchForm(ctx, task); };
  fillTasksWorkbenchForm(ctx, task);
  form.querySelector('[name="task_name"]').value = 'Unsaved';
  resetTasksWorkbenchEditor(ctx);
  expect(state.tasksWorkbench.activeTaskId).toBe('a');
  expect(form.querySelector('[name="task_name"]').value).toBe('Saved');
});
