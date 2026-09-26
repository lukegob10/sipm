import { describe, expect, it, vi } from "vitest";

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
    markIgnoreRefresh: vi.fn(),
    ignoreNextRefresh: new Set(),
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

function submit(form) {
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("task workbench form request races", () => {
  it("sends one create and preserves a newer draft without leaving it in create mode", async () => {
    let resolveRequest;
    const api = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const { controller, deps } = taskController(api);
    controller.bindTaskForm();
    controller.showTaskForm(deps.state.solutions[0]);
    const form = deps.els.taskForm;
    const taskName = form.querySelector('[name="task_name"]');
    taskName.value = "First draft";
    submit(form);
    submit(form);

    expect(api).toHaveBeenCalledTimes(1);
    expect(deps.els.taskSubmitBtn.disabled).toBe(true);

    taskName.value = "Next draft";
    taskName.dispatchEvent(new Event("input", { bubbles: true }));
    resolveRequest({
      task_id: "created-task",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "First draft",
      status: "to_do",
      priority: 3,
      capacity_hours: 0,
    });

    await vi.waitFor(() => expect(deps.upsertById).toHaveBeenCalledTimes(1));
    expect(form.querySelector('[name="task_id"]').value).toBe("created-task");
    expect(taskName.value).toBe("Next draft");
    expect(deps.els.taskSubmitBtn.textContent).toBe("Save Changes");
    expect(deps.els.taskSubmitBtn.disabled).toBe(false);
  });

  it("ignores a task response after the active space changes", async () => {
    let resolveRequest;
    const api = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const { controller, deps } = taskController(api);
    controller.bindTaskForm();
    controller.showTaskForm(deps.state.solutions[0]);
    deps.els.taskForm.querySelector('[name="task_name"]').value = "Old space task";
    submit(deps.els.taskForm);
    deps.state.activeSpace.space_id = "space-2";
    resolveRequest({
      task_id: "old-space-task",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Old space task",
      status: "to_do",
      priority: 3,
      capacity_hours: 0,
    });

    await vi.waitFor(() => expect(deps.els.taskSubmitBtn.disabled).toBe(false));
    expect(deps.upsertById).not.toHaveBeenCalled();
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
  });

  it("does not mark a task refresh when deletion is cancelled", async () => {
    const { controller, deps } = taskController(vi.fn());
    deps.deleteTasksById.mockResolvedValue({ cancelled: true, deletedIds: [], failed: [] });
    controller.bindTaskForm();
    controller.fillTaskForm({
      task_id: "task-1",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Task one",
    });

    deps.els.deleteTaskBtn.click();

    await vi.waitFor(() => expect(deps.deleteTasksById).toHaveBeenCalledOnce());
    expect(deps.markIgnoreRefresh).not.toHaveBeenCalled();
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
  });

  it("keeps the newly opened task editor when an earlier delete succeeds", async () => {
    const pendingDelete = deferred();
    const { controller, deps } = taskController(vi.fn());
    deps.deleteTasksById.mockReturnValue(pendingDelete.promise);
    controller.bindTaskForm();
    controller.fillTaskForm({
      task_id: "task-a",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Task A",
    });

    deps.els.deleteTaskBtn.click();
    await vi.waitFor(() => expect(deps.deleteTasksById).toHaveBeenCalledOnce());
    deps.els.solutionForm.querySelector('[name="solution_id"]').value = "solution-2";
    controller.fillTaskForm({
      task_id: "task-b",
      project_id: "project-2",
      solution_id: "solution-2",
      task_name: "Task B",
    });
    pendingDelete.resolve({ cancelled: false, deletedIds: ["task-a"], failed: [] });

    await vi.waitFor(() => expect(deps.renderDashboard).toHaveBeenCalledOnce());
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("task-b");
    expect(deps.els.taskForm.querySelector('[name="task_name"]').value).toBe("Task B");
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
    expect(deps.setDeliverableFormNotice).not.toHaveBeenCalled();
  });

  it("refreshes the deleted task's solution list without replacing another task editor", async () => {
    const pendingDelete = deferred();
    const { controller, deps } = taskController(vi.fn());
    deps.deleteTasksById.mockReturnValue(pendingDelete.promise);
    controller.bindTaskForm();
    controller.fillTaskForm({
      task_id: "task-a",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Task A",
    });

    deps.els.deleteTaskBtn.click();
    await vi.waitFor(() => expect(deps.deleteTasksById).toHaveBeenCalledOnce());
    controller.fillTaskForm({
      task_id: "task-b",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Task B",
    });
    pendingDelete.resolve({ cancelled: false, deletedIds: ["task-a"], failed: [] });

    await vi.waitFor(() => expect(deps.renderSolutionTasks).toHaveBeenCalledWith("solution-1"));
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("task-b");
    expect(deps.els.taskForm.querySelector('[name="task_name"]').value).toBe("Task B");
    expect(deps.setDeliverableFormNotice).not.toHaveBeenCalled();
  });

  it("keeps the task editor open and reports a failed deletion", async () => {
    const { controller, deps } = taskController(vi.fn());
    deps.deleteTasksById.mockResolvedValue({
      cancelled: false,
      deletedIds: [],
      failed: [{ error: { message: "Still in use" } }],
    });
    controller.bindTaskForm();
    controller.fillTaskForm({
      task_id: "task-a",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Task A",
    });

    deps.els.deleteTaskBtn.click();

    await vi.waitFor(() => expect(deps.setDeliverableFormNotice).toHaveBeenCalledWith(
      deps.els.taskFormStatus,
      "Delete failed: Still in use",
      "error"
    ));
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("task-a");
    expect(deps.els.taskForm.querySelector('[name="task_name"]').value).toBe("Task A");
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
    expect(deps.renderDashboard).not.toHaveBeenCalled();
  });

  it("does not clear a new space's refresh marker when an old delete rejects", async () => {
    const pendingDelete = deferred();
    const { controller, deps } = taskController(vi.fn());
    deps.deleteTasksById.mockReturnValue(pendingDelete.promise);
    controller.bindTaskForm();
    controller.fillTaskForm({
      task_id: "task-a",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Task A",
    });

    deps.els.deleteTaskBtn.click();
    deps.state.activeSpace = { space_id: "space-2" };
    deps.ignoreNextRefresh.add("tasks");
    pendingDelete.reject(new Error("Old request failed"));
    await Promise.resolve();

    expect(deps.ignoreNextRefresh.has("tasks")).toBe(true);
    expect(deps.setDeliverableFormNotice).not.toHaveBeenCalled();
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
  });

  it("does not render an old solution task list after the editor switches", async () => {
    let resolveRequest;
    const api = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const { controller, deps } = taskController(api);
    controller.bindTaskForm();
    controller.showTaskForm(deps.state.solutions[0]);
    deps.els.taskForm.querySelector('[name="task_name"]').value = "Old solution task";
    submit(deps.els.taskForm);

    deps.els.solutionForm.querySelector('[name="solution_id"]').value = "solution-2";
    controller.fillTaskForm({
      task_id: "current-task",
      project_id: "project-2",
      solution_id: "solution-2",
      task_name: "Current solution task",
    });
    resolveRequest({
      task_id: "old-solution-task",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Old solution task",
      status: "to_do",
      priority: 3,
      capacity_hours: 0,
    });

    await vi.waitFor(() => expect(deps.els.taskSubmitBtn.disabled).toBe(false));
    expect(deps.upsertById).toHaveBeenCalledOnce();
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("current-task");
    expect(deps.els.taskForm.querySelector('[name="task_name"]').value).toBe("Current solution task");
  });

  it("ignores responses after the user or active-space object is replaced", async () => {
    let resolveRequest;
    const api = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const { controller, deps } = taskController(api);
    controller.bindTaskForm();
    controller.showTaskForm(deps.state.solutions[0]);
    deps.els.taskForm.querySelector('[name="task_name"]').value = "Old context task";
    submit(deps.els.taskForm);
    deps.state.user = { ...deps.state.user };
    deps.state.activeSpace = { ...deps.state.activeSpace };
    resolveRequest({
      task_id: "old-context-task",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Old context task",
      status: "to_do",
      priority: 3,
      capacity_hours: 0,
    });

    await vi.waitFor(() => expect(deps.els.taskSubmitBtn.disabled).toBe(false));
    expect(deps.upsertById).not.toHaveBeenCalled();
    expect(deps.renderSolutionTasks).not.toHaveBeenCalled();
  });
});
