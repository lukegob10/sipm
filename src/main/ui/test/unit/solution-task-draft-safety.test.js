import { expect, it, vi } from "vitest";

import { createTaskEntityController } from "../../js/entities/tasks.js";

function taskController(api) {
  document.body.innerHTML = `
    <form id="task-form" class="hidden">
      <input name="task_id" />
      <input name="project_id" />
      <input name="solution_id" />
      <input name="task_name" />
      <textarea name="description"></textarea>
      <input name="github_repo_url" />
      <input name="priority" />
      <input name="due_date" />
      <select name="status"><option value="to_do">To do</option></select>
      <select name="assignee"><option value="">Unassigned</option></select>
      <input name="assignee_user_soeid" />
      <input name="estimate_hours" />
      <input name="blocked" type="checkbox" />
      <input name="blocker_note" />
      <textarea name="acceptance_criteria"></textarea>
      <input name="capacity_hours" />
      <button id="task-submit" type="submit">Create Task</button>
      <button id="task-delete" type="button">Delete Task</button>
    </form>
    <div id="task-form-footer" class="hidden"></div>
    <p id="task-status"></p>
    <form id="solution-form"><input name="solution_id" value="solution-1" /></form>
    <button id="show-task-form" type="button"></button>
    <div id="solution-task-table"></div>
  `;
  const state = {
    activeSpace: { space_id: "space-1" },
    user: { user_id: "user-1" },
    authed: true,
    solutions: [{ solution_id: "solution-1", project_id: "project-1" }],
    tasks: [],
    myWork: { records: [], loading: true, loadRequestId: 7 },
  };
  const els = {
    taskForm: document.getElementById("task-form"),
    taskFormFooter: document.getElementById("task-form-footer"),
    taskSubmitBtn: document.getElementById("task-submit"),
    deleteTaskBtn: document.getElementById("task-delete"),
    taskFormStatus: document.getElementById("task-status"),
    solutionForm: document.getElementById("solution-form"),
    showTaskFormBtn: document.getElementById("show-task-form"),
    solutionTaskTable: document.getElementById("solution-task-table"),
  };
  const deps = {
    state,
    els,
    api,
    findUserBySoeid: () => null,
    resolveAssigneeSelectValue: (soeid) => soeid || "",
    hoursFromFteInput: (value) => Number(value || 0) * 160,
    hoursFromNullableFteInput: (value) => value ? Number(value) * 160 : null,
    fteFromHoursForInput: (hours) => String(Number(hours || 0) / 160),
    updateTaskRepoPreview: vi.fn(),
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    upsertById: vi.fn((rows, saved, idKey) => {
      const index = rows.findIndex((row) => row[idKey] === saved[idKey]);
      if (index === -1) rows.push(saved);
      else rows[index] = saved;
    }),
    deleteTasksById: vi.fn(),
    renderSolutionTasks: vi.fn(),
    renderDashboard: vi.fn(),
    renderGantt: vi.fn(),
    timestampLabel: () => "12:00",
  };
  return { controller: createTaskEntityController(deps), deps };
}


it("asks before replacing a dirty task and preserves it on cancel", async () => {
 const {deps}=taskController(vi.fn()); let finish; deps.showConfirmModal=()=>new Promise(r=>{finish=r;});
 // The controller captures dependencies when constructed.
 const replacement=createTaskEntityController(deps); replacement.bindTaskForm();
 const first={task_id:'a',task_name:'First',project_id:'p',solution_id:'s',status:'to_do',priority:3};
 replacement.fillTaskForm(first);
 const name=deps.els.taskForm.querySelector('[name="task_name"]');name.value='Draft';name.dispatchEvent(new Event('input',{bubbles:true}));
 const switchTask=replacement.requestFillTaskForm({...first,task_id:'b',task_name:'Second'});
 expect(name.value).toBe('Draft');finish(false);expect(await switchTask).toBe(false);expect(name.value).toBe('Draft');
});

it("does not discard a newer draft after an old confirmation", async () => {
 const {deps}=taskController(vi.fn()); let finish; deps.showConfirmModal=()=>new Promise(r=>{finish=r;});
 const controller=createTaskEntityController(deps); controller.bindTaskForm();
 const first={task_id:'a',task_name:'First',project_id:'p',solution_id:'s',status:'to_do',priority:3};
 controller.fillTaskForm(first); const name=deps.els.taskForm.querySelector('[name="task_name"]');name.value='Draft';name.dispatchEvent(new Event('input',{bubbles:true}));
 const pending=controller.hideTaskForm();name.value='Newer';name.dispatchEvent(new Event('input',{bubbles:true}));
 finish(true);expect(await pending).toBe(false);expect(name.value).toBe('Newer');expect(deps.els.taskForm.classList.contains('hidden')).toBe(false);
});
