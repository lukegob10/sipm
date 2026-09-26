import { describe, expect, it, vi } from "vitest";

import { renderTasksWorkbench } from "../../js/routes/tasks-workbench.js";
import {
  deleteActiveTasksWorkbenchItem,
  fillTasksWorkbenchForm,
  saveTasksWorkbenchForm,
} from "../../js/routes/tasks-workbench/drawer.js";
import { updateTasksWorkbenchSolutionOptions } from "../../js/routes/tasks-workbench/interactions.js";
import { populateTasksWorkbenchOptions } from "../../js/routes/tasks-workbench/options.js";

function taskRecord(taskId = "task-1", overrides = {}) {
  return {
    task_id: taskId,
    task_name: `Title ${taskId}`,
    description: `Description ${taskId}`,
    acceptance_criteria: `Criteria ${taskId}`,
    status: "to_do",
    priority: 2,
    due_date: "2026-10-01",
    blocker_note: "",
    blocked: false,
    assignee_user_soeid: "tu12345",
    assignee: "Test User",
    project_id: "project-1",
    solution_id: "solution-1",
    ...overrides,
  };
}

function createWorkbenchEditor() {
  document.body.innerHTML = `
    <form id="tasks-workbench-form">
      <input name="task_id" />
      <input name="task_name" />
      <textarea name="description"></textarea>
      <textarea name="acceptance_criteria"></textarea>
      <select name="status"><option value="to_do">To do</option><option value="active">Active</option></select>
      <input name="priority" />
      <input name="due_date" />
      <textarea name="blocker_note"></textarea>
      <input type="checkbox" name="blocked" />
      <select name="assignee"><option value="">Unassigned</option><option value="tu12345">Test User</option></select>
      <input name="assignee_user_soeid" />
    </form>
    <button id="tasks-workbench-save" form="tasks-workbench-form" type="submit"></button>
    <div id="tasks-workbench-context"></div>
    <p id="tasks-workbench-form-status"></p>
    <button id="tasks-workbench-delete"></button>
  `;
  const form = document.getElementById("tasks-workbench-form");
  const ctx = {
    state: {
      tasks: [taskRecord()],
      tasksWorkbench: { activeTaskId: "task-1", selected: new Set() },
      projects: [{ project_id: "project-1", project_name: "Project" }],
      solutions: [{ solution_id: "solution-1", solution_name: "Solution" }],
    },
    els: {
      tasksWorkbenchForm: form,
      tasksWorkbenchContext: document.getElementById("tasks-workbench-context"),
      tasksWorkbenchFormStatus: document.getElementById("tasks-workbench-form-status"),
      tasksWorkbenchDelete: document.getElementById("tasks-workbench-delete"),
      tasksWorkbenchActivity: null,
    },
    escapeHtml: (value) => String(value || ""),
    effectiveTaskRepoInfo: () => ({ url: "", source: "" }),
    renderExternalRepoLink: () => "",
    clearDeliverableFormNotice: vi.fn(),
    resolveAssigneeSelectValue: (soeid) => soeid || "",
    findUserBySoeid: (soeid) => soeid === "tu12345" ? { display_name: "Test User" } : null,
    setDeliverableFormNotice: vi.fn(),
    timestampLabel: () => "now",
    api: vi.fn(),
    upsertById: vi.fn((rows, updated, key) => {
      const index = rows.findIndex((row) => row[key] === updated[key]);
      if (index === -1) rows.push(updated);
      else rows[index] = updated;
    }),
    persistTasksWorkbenchUiState: vi.fn(),
    renderTasksWorkbench: vi.fn(() => {
      let activeTaskId = ctx.state.tasksWorkbench.activeTaskId;
      if (!ctx.state.tasks.some((task) => task.task_id === activeTaskId)) activeTaskId = "";
      if (ctx.state.tasksWorkbench.drawerOpen !== false && !activeTaskId && ctx.state.tasks.length) {
        activeTaskId = ctx.state.tasks[0].task_id;
      }
      ctx.state.tasksWorkbench.activeTaskId = activeTaskId;
      const activeTask = ctx.state.tasks.find((task) => task.task_id === activeTaskId) || null;
      fillTasksWorkbenchForm(ctx, activeTask);
    }),
    renderSolutionTasks: vi.fn(),
    renderDashboard: vi.fn(),
    ignoreNextRefresh: new Set(),
    deleteTasksById: vi.fn(),
  };
  return { ctx, form };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function formValue(form, name) {
  return form.querySelector(`[name="${name}"]`);
}

describe("tasks workbench route", () => {
  it.each([
    [{ acceptance_criteria: "Current criteria", done_criteria: "Legacy criteria" }, "Current criteria"],
    [{ acceptance_criteria: null, done_criteria: "Legacy criteria" }, "Legacy criteria"],
  ])("fills task descriptions and acceptance criteria in the editor", (criteria, expected) => {
    const { ctx, form } = createWorkbenchEditor();

    fillTasksWorkbenchForm(ctx, taskRecord("task-a", { description: "Task details", ...criteria }));

    expect(formValue(form, "description").value).toBe("Task details");
    expect(formValue(form, "acceptance_criteria").value).toBe(expected);
  });

  it("preserves dirty same-task fields on refresh and resets them on an intentional task switch", () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    fillTasksWorkbenchForm(ctx, taskA);
    const saveButton = document.getElementById("tasks-workbench-save");
    expect(saveButton.disabled).toBe(false);

    formValue(form, "task_name").value = "Task A draft";
    fillTasksWorkbenchForm(ctx, { ...taskA, task_name: "Task A remote update", description: "Fresh description" });

    expect(formValue(form, "task_name").value).toBe("Task A draft");
    expect(formValue(form, "description").value).toBe("Fresh description");

    fillTasksWorkbenchForm(ctx, taskRecord("task-b", { task_name: "Task B" }));

    expect(form.dataset.activeTaskId).toBe("task-b");
    expect(formValue(form, "task_name").value).toBe("Task B");
    fillTasksWorkbenchForm(ctx, null);
    expect(formValue(form, "task_id").value).toBe("");
    expect(saveButton.disabled).toBe(true);
  });

  it("renders task identity and project/solution context in separate columns", () => {
    document.body.innerHTML = '<div id="tasks-workbench-table"></div>';
    const table = document.getElementById("tasks-workbench-table");

    renderTasksWorkbench({
      els: { tasksWorkbenchTable: table },
      rows: [{
        task_id: "task-1",
        task_name: "Prepare release notes",
        project_id: "project-1",
        project_name: "Platform Renewal",
        solution_id: "solution-1",
        solution_name: "Case Management",
        status: "active",
        assignee: "Engineer One",
        due_date: "2026-07-31",
        priority: 2,
        urgency_score: 42,
      }],
      activeTaskId: "",
      selectedIds: new Set(),
      sort: "default",
      formatStatus: (status) => status,
      summary: { total: 1, visible: 1 },
    });

    const headers = [...table.querySelectorAll("thead th")]
      .map((cell) => cell.querySelector("button span")?.textContent.trim() || cell.textContent.trim());
    expect(headers).toEqual(["", "Task", "Project / Solution", "Status", "Assignee", "Due", "Priority", "Urgency"]);

    const cells = table.querySelectorAll("tbody td");
    expect(cells).toHaveLength(8);
    expect(cells[1].textContent.trim()).toBe("Prepare release notes");
    expect(cells[1].querySelector(".task-workbench-context")).toBeNull();
    expect(cells[2].textContent).toContain("Platform Renewal");
    expect(cells[2].textContent).toContain("Case Management");
    expect(cells[2].querySelectorAll(".task-workbench-context-link")).toHaveLength(2);
  });

  it("renders solution options as text and keeps untrusted IDs inside the value attribute", () => {
    document.body.innerHTML = '<select id="tasks-workbench-solution"><option value="">All Solutions</option></select>';
    const solutionId = 'solution-1" data-injected="yes';
    const solutionName = '</option><option value="injected">Injected</option><option>';
    const select = document.getElementById("tasks-workbench-solution");

    updateTasksWorkbenchSolutionOptions({
      state: {
        solutions: [{ solution_id: solutionId, solution_name: solutionName }],
      },
      els: { tasksWorkbenchSolution: select },
    }, "");

    expect(select.options).toHaveLength(2);
    expect(select.options[1].value).toBe(solutionId);
    expect(select.options[1].textContent).toBe(solutionName);
    expect(select.options[1].hasAttribute("data-injected")).toBe(false);
  });

  it("saves a manually entered assignee SOEID for My Work assignment", async () => {
    document.body.innerHTML = `
      <form id="tasks-workbench-form">
        <input name="task_id" value="task-1" />
        <input name="task_name" value="Prepare release notes" />
        <textarea name="description"></textarea>
        <textarea name="acceptance_criteria"></textarea>
        <select name="status"><option value="to_do" selected>To do</option></select>
        <input name="priority" value="2" />
        <input name="due_date" value="" />
        <select name="assignee"><option value="">Unassigned</option></select>
        <input name="assignee_user_soeid" value=" tu12345 " />
        <input type="checkbox" name="blocked" />
        <textarea name="blocker_note"></textarea>
      </form>
      <p id="tasks-workbench-form-status"></p>
    `;
    const api = vi.fn().mockResolvedValue({
      task_id: "task-1",
      assignee: "Test User",
      assignee_user_soeid: "tu12345",
    });
    const ctx = {
      state: { tasks: [], tasksWorkbench: {} },
      els: {
        tasksWorkbenchForm: document.getElementById("tasks-workbench-form"),
        tasksWorkbenchFormStatus: document.getElementById("tasks-workbench-form-status"),
      },
      api,
      upsertById: vi.fn(),
      resolveAssigneeSelectValue: (soeid) => soeid || "",
      findUserBySoeid: (soeid) => soeid === "tu12345"
        ? { soeid: "tu12345", display_name: "Test User" }
        : null,
      renderTasksWorkbench: vi.fn(),
      renderSolutionTasks: vi.fn(),
      setDeliverableFormNotice: vi.fn(),
      timestampLabel: () => "now",
      persistTasksWorkbenchUiState: vi.fn(),
    };

    await saveTasksWorkbenchForm(ctx);

    expect(api).toHaveBeenCalledWith("/tasks/task-1", expect.objectContaining({ method: "PATCH" }));
    const payload = JSON.parse(api.mock.calls[0][1].body);
    expect(payload.assignee).toBe("Test User");
    expect(payload.assignee_user_soeid).toBe("tu12345");
  });

  it("keeps the selected task and its draft when a slower save completes after switching", async () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    ctx.state.tasks = [taskA, taskRecord("task-b")];
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskA);
    formValue(form, "task_name").value = "Submitted Task A";
    const response = deferred();
    ctx.api.mockReturnValueOnce(response.promise);

    const saving = saveTasksWorkbenchForm(ctx);
    ctx.state.tasksWorkbench.activeTaskId = "task-b";
    fillTasksWorkbenchForm(ctx, taskRecord("task-b", { task_name: "Task B" }));
    formValue(form, "task_name").value = "Task B unsaved draft";

    response.resolve(taskRecord("task-a", { task_name: "Submitted Task A" }));
    await saving;

    expect(ctx.state.tasksWorkbench.activeTaskId).toBe("task-b");
    expect(formValue(form, "task_id").value).toBe("task-b");
    expect(formValue(form, "task_name").value).toBe("Task B unsaved draft");
    expect(ctx.setDeliverableFormNotice).not.toHaveBeenCalledWith(
      ctx.els.tasksWorkbenchFormStatus,
      "Saved task at now.",
      "success",
      3200
    );
    expect(ctx.renderTasksWorkbench).toHaveBeenCalledOnce();
  });

  it("preserves newer edits made to the same task while a save is pending", async () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    ctx.state.tasks = [taskA];
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskA);
    formValue(form, "task_name").value = "Submitted title";
    const response = deferred();
    ctx.api.mockReturnValueOnce(response.promise);

    const saving = saveTasksWorkbenchForm(ctx);
    formValue(form, "task_name").value = "Newer draft";
    response.resolve(taskRecord("task-a", { task_name: "Submitted title" }));
    await saving;

    expect(formValue(form, "task_name").value).toBe("Newer draft");
    expect(ctx.state.tasksWorkbench.activeTaskId).toBe("task-a");
    expect(ctx.renderTasksWorkbench).toHaveBeenCalledOnce();
  });

  it("keeps a reopened same-task draft after switching away and back during a pending save", async () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    const taskB = taskRecord("task-b");
    ctx.state.tasks = [taskA, taskB];
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskA);
    formValue(form, "task_name").value = "Submitted Task A";
    const response = deferred();
    ctx.api.mockReturnValueOnce(response.promise);

    const saving = saveTasksWorkbenchForm(ctx);
    ctx.state.tasksWorkbench.activeTaskId = "task-b";
    fillTasksWorkbenchForm(ctx, taskB);
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskA);
    formValue(form, "task_name").value = "Reopened Task A draft";

    response.resolve(taskRecord("task-a", { task_name: "Submitted Task A" }));
    await saving;

    expect(ctx.state.tasksWorkbench.activeTaskId).toBe("task-a");
    expect(formValue(form, "task_id").value).toBe("task-a");
    expect(formValue(form, "task_name").value).toBe("Reopened Task A draft");
    const noticeMessages = ctx.setDeliverableFormNotice.mock.calls.map(([, message]) => message);
    expect(noticeMessages).not.toContain("Saved task at now.");
  });

  it("resets a clean draft baseline after an unchanged save", async () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    ctx.state.tasks = [taskA];
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskA);
    formValue(form, "task_name").value = "Saved title";
    ctx.api.mockResolvedValueOnce(taskRecord("task-a", { task_name: "Saved title" }));

    await saveTasksWorkbenchForm(ctx);
    fillTasksWorkbenchForm(ctx, taskRecord("task-a", { task_name: "Later server title" }));

    expect(formValue(form, "task_name").value).toBe("Later server title");
  });

  it("ignores a save response after the session or active space changes", async () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    ctx.state.tasks = [taskA];
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    ctx.state.user = { user_id: "user-a" };
    ctx.state.activeSpace = { space_id: "space-a" };
    fillTasksWorkbenchForm(ctx, taskA);
    const response = deferred();
    ctx.api.mockReturnValueOnce(response.promise);

    const saving = saveTasksWorkbenchForm(ctx);
    ctx.state.user = { user_id: "user-a" };
    ctx.state.activeSpace = { space_id: "space-a" };
    response.resolve(taskRecord("task-a", { task_name: "Should be ignored" }));
    await saving;

    expect(ctx.upsertById).not.toHaveBeenCalled();
    expect(ctx.renderTasksWorkbench).not.toHaveBeenCalled();
    expect(formValue(form, "task_name").value).toBe("Title task-a");
    expect(ctx.setDeliverableFormNotice).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["success", { cancelled: false, deletedIds: ["task-a"], failed: [] }],
    ["failure", { cancelled: false, deletedIds: [], failed: [{ id: "task-a", error: new Error("failed") }] }],
  ])("does not show a late delete %s notice in another task editor", async (_label, result) => {
    const { ctx, form } = createWorkbenchEditor();
    ctx.state.tasks.push(taskRecord("task-b"));
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskRecord("task-a"));
    const response = deferred();
    ctx.deleteTasksById.mockReturnValueOnce(response.promise);

    const deleting = deleteActiveTasksWorkbenchItem(ctx);
    ctx.state.tasksWorkbench.activeTaskId = "task-b";
    fillTasksWorkbenchForm(ctx, taskRecord("task-b"));
    response.resolve(result);
    await deleting;

    expect(formValue(form, "task_id").value).toBe("task-b");
    expect(ctx.renderTasksWorkbench).toHaveBeenCalledOnce();
    const noticeMessages = ctx.setDeliverableFormNotice.mock.calls.map(([, message]) => message);
    expect(noticeMessages.some((message) => /^(Deleted task at|Delete failed for)/.test(message))).toBe(false);
  });

  it("does not show delete success in the next row auto-selected by the refresh", async () => {
    const { ctx, form } = createWorkbenchEditor();
    const taskA = taskRecord("task-a");
    const taskB = taskRecord("task-b");
    ctx.state.tasks = [taskA, taskB];
    ctx.state.tasksWorkbench.activeTaskId = "task-a";
    fillTasksWorkbenchForm(ctx, taskA);
    ctx.deleteTasksById.mockImplementation(async () => {
      ctx.state.tasks.splice(0, 1);
      ctx.state.tasksWorkbench.activeTaskId = "";
      return { cancelled: false, deletedIds: ["task-a"], failed: [] };
    });

    await deleteActiveTasksWorkbenchItem(ctx);

    expect(ctx.renderTasksWorkbench).toHaveBeenCalledOnce();
    expect(ctx.state.tasksWorkbench.activeTaskId).toBe("task-b");
    expect(formValue(form, "task_id").value).toBe("task-b");
    const noticeMessages = ctx.setDeliverableFormNotice.mock.calls.map(([, message]) => message);
    expect(noticeMessages).not.toContain("Deleted task at now.");
  });

  it("keeps the assignee picker and editable SOEID synchronized", () => {
    document.body.innerHTML = `
      <form id="tasks-workbench-form">
        <select name="assignee"></select>
        <input name="assignee_user_soeid" />
      </form>
    `;
    const form = document.getElementById("tasks-workbench-form");
    const select = form.querySelector('[name="assignee"]');
    const soeidInput = form.querySelector('[name="assignee_user_soeid"]');
    populateTasksWorkbenchOptions({
      state: {
        users: [{ soeid: "tu12345", display_name: "Test User" }],
      },
      els: { tasksWorkbenchForm: form },
      normalizeTasksWorkbenchUiState: vi.fn(),
    });

    select.value = "tu12345";
    select.dispatchEvent(new Event("change"));
    expect(soeidInput.value).toBe("tu12345");

    soeidInput.value = "TU12345";
    soeidInput.dispatchEvent(new Event("input"));
    expect(select.value).toBe("tu12345");

    soeidInput.value = "external-user";
    soeidInput.dispatchEvent(new Event("input"));
    expect(select.value).toBe("");
  });

  it("renders hostile assignee labels as text instead of creating extra options", () => {
    document.body.innerHTML = `
      <select id="assignee-filter"></select>
      <select id="assignee-bulk"></select>
    `;
    const displayName = 'Good</option><option value="spoof" data-pwned="yes">Choose this fake account</option><option>';
    const soeid = 'developer"><option value="spoof-id" data-pwned="yes">';
    const ctx = {
      state: { users: [{ soeid, display_name: displayName }] },
      els: {
        tasksWorkbenchAssignee: document.getElementById("assignee-filter"),
        tasksWorkbenchBulkAssignee: document.getElementById("assignee-bulk"),
      },
      normalizeTasksWorkbenchUiState: vi.fn(),
    };

    populateTasksWorkbenchOptions(ctx);

    const options = ctx.els.tasksWorkbenchAssignee.options;
    expect(options).toHaveLength(3);
    expect(options[2].value).toBe(soeid);
    expect(options[2].textContent).toBe(displayName);
    expect(ctx.els.tasksWorkbenchAssignee.querySelector("[data-pwned]")).toBeNull();
  });
});
