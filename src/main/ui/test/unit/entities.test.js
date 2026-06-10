import { describe, expect, it, vi } from "vitest";

import { buildProgramPayload } from "../../js/entities/programs.js";
import { buildProjectPayload, createProjectEntityController } from "../../js/entities/projects.js";
import { buildSolutionPayload } from "../../js/entities/solutions.js";
import { buildTaskPayload, createTaskEntityController } from "../../js/entities/tasks.js";

function formData(values) {
  const data = new FormData();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) data.set(key, value);
  });
  return data;
}

function projectEls() {
  document.body.innerHTML = `
    <section id="project-modal" class="hidden">
      <div class="modal-backdrop"></div>
      <button id="close" type="button"></button>
      <h2 id="title"></h2>
      <form id="project-form">
        <input name="project_id" />
        <select name="program_id"><option value="program-1"></option></select>
        <input name="project_name" />
        <select name="status"><option value="not_started"></option><option value="active"></option></select>
        <textarea name="description"></textarea>
        <textarea name="success_criteria"></textarea>
        <input name="sponsor" />
        <input name="sponsor_user_soeid" />
        <input name="strategic_objective" />
        <input name="priority" />
        <button id="submit" type="submit"></button>
        <button id="delete" type="button"></button>
      </form>
      <p id="status"></p>
    </section>
  `;
  return {
    projectModal: document.querySelector("#project-modal"),
    projectModalClose: document.querySelector("#close"),
    projectModalTitle: document.querySelector("#title"),
    projectForm: document.querySelector("#project-form"),
    projectSubmitBtn: document.querySelector("#submit"),
    deleteProjectBtn: document.querySelector("#delete"),
    projectFormStatus: document.querySelector("#status"),
  };
}

function buildProjectController(overrides = {}) {
  const state = { programs: [{ program_id: "program-1", program_name: "Default Program" }], projects: [] };
  const ignoreNextRefresh = new Set();
  const deps = {
    state,
    els: projectEls(),
    api: vi.fn(),
    markIgnoreRefresh: vi.fn(),
    ignoreNextRefresh,
    upsertById: vi.fn((rows, saved) => rows.push(saved)),
    removeById: vi.fn((rows, id) => {
      const index = rows.findIndex((row) => row.project_id === id);
      if (index >= 0) rows.splice(index, 1);
    }),
    populateSelects: vi.fn(),
    renderMasterTable: vi.fn(),
    renderDashboard: vi.fn(),
    renderKanban: vi.fn(),
    renderCalendar: vi.fn(),
    renderGantt: vi.fn(),
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    timestampLabel: vi.fn(() => "12:00"),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    trackWorkflow: vi.fn(),
    ...overrides,
  };
  return { controller: createProjectEntityController(deps), deps };
}

function taskEls() {
  document.body.innerHTML = `
    <form id="task-form" class="hidden">
      <input name="task_id" />
      <input name="project_id" />
      <input name="solution_id" />
      <input name="task_name" />
      <input name="github_repo_url" />
      <input name="priority" />
      <input name="due_date" />
      <select name="status"><option value="to_do"></option><option value="in_progress"></option></select>
      <select name="assignee"><option value=""></option><option value="eng123"></option></select>
      <input name="assignee_user_soeid" />
      <input name="estimate_hours" />
      <input name="blocked" type="checkbox" />
      <input name="blocker_note" />
      <input name="done_criteria" />
      <input name="capacity_hours" />
    </form>
    <div id="task-form-footer" class="hidden"></div>
    <button id="task-submit-btn" type="submit"></button>
    <button id="delete-task" type="button"></button>
    <p id="task-form-status"></p>
    <form id="solution-form"><input name="solution_id" /></form>
    <button id="show-task-form" type="button"></button>
  `;
  return {
    taskForm: document.querySelector("#task-form"),
    taskFormFooter: document.querySelector("#task-form-footer"),
    taskSubmitBtn: document.querySelector("#task-submit-btn"),
    deleteTaskBtn: document.querySelector("#delete-task"),
    taskFormStatus: document.querySelector("#task-form-status"),
    solutionForm: document.querySelector("#solution-form"),
    showTaskFormBtn: document.querySelector("#show-task-form"),
  };
}

function buildTaskController(overrides = {}) {
  const state = {
    solutions: [{ solution_id: "solution-1", project_id: "project-1" }],
    tasks: [],
  };
  const ignoreNextRefresh = new Set();
  const deps = {
    state,
    els: taskEls(),
    api: vi.fn(),
    findUserBySoeid: vi.fn(),
    resolveAssigneeSelectValue: vi.fn((soeid) => soeid || ""),
    hoursFromFteInput: vi.fn((value) => Number(value || 0) * 160),
    hoursFromNullableFteInput: vi.fn((value) => (value ? Number(value) * 160 : null)),
    fteFromHoursForInput: vi.fn((hours) => String(Number(hours || 0) / 160)),
    updateTaskRepoPreview: vi.fn(),
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    markIgnoreRefresh: vi.fn(),
    ignoreNextRefresh,
    upsertById: vi.fn(),
    deleteTasksById: vi.fn(),
    renderSolutionTasks: vi.fn(),
    renderDashboard: vi.fn(),
    renderGantt: vi.fn(),
    timestampLabel: vi.fn(() => "12:00"),
    trackWorkflow: vi.fn(),
    ...overrides,
  };
  return { controller: createTaskEntityController(deps), deps };
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

describe("entity payload builders", () => {
  it("normalizes project identifiers and nullable text fields", () => {
    const payload = buildProjectPayload(formData({
      program_id: " program-1 ",
      project_name: "  Project Alpha  ",
      status: "active",
      description: " Keep spacing in long text ",
      success_criteria: "   ",
      sponsor: "  Sponsor Name  ",
      sponsor_user_soeid: " tu12345 ",
      strategic_objective: "",
      priority: "2",
    }));

    expect(payload).toEqual({
      program_id: "program-1",
      project_name: "Project Alpha",
      status: "active",
      description: " Keep spacing in long text ",
      success_criteria: null,
      sponsor: "Sponsor Name",
      sponsor_user_soeid: "tu12345",
      strategic_objective: null,
      priority: 2,
    });
  });

  it("normalizes program payload fields", () => {
    const payload = buildProgramPayload(formData({
      program_name: "  Enterprise Change  ",
      description: "   ",
    }));

    expect(payload).toEqual({
      program_name: "Enterprise Change",
      description: null,
    });
  });

  it("builds solution payloads without unsupported FTE aliases or display-name SOEID fallback", () => {
    const payload = buildSolutionPayload(
      formData({
        solution_name: "  Solution One  ",
        github_repo_url: " https://github.com/org/repo ",
        version: " 1.0.0 ",
        status: "active",
        priority: "1",
        owner: "  Owner Name  ",
        owner_user_soeid: " on12345 ",
        assignee: "Assignee Display",
        assignee_user_soeid: "",
        capacity_hours: "0.5",
        rag_status: "amber",
      }),
      { hoursFromFteInput: (value) => Number(value) * 160 }
    );

    expect(payload.solution_name).toBe("Solution One");
    expect(payload.github_repo_url).toBe("https://github.com/org/repo");
    expect(payload.version).toBe("1.0.0");
    expect(payload.owner).toBe("Owner Name");
    expect(payload.owner_user_soeid).toBe("on12345");
    expect(payload.assignee).toBe("Assignee Display");
    expect(payload.assignee_user_soeid).toBeNull();
    expect(payload.capacity_hours).toBe(80);
    expect(payload).not.toHaveProperty("capacity_fte_months");
  });

  it("builds task payloads with repo trimming and blocked-note consistency", () => {
    const users = new Map([["eng123", { display_name: "Engineer One" }]]);
    const commonDeps = {
      findUserBySoeid: (soeid) => users.get(soeid),
      hoursFromFteInput: (value) => Number(value || 0) * 160,
      hoursFromNullableFteInput: (value) => (value ? Number(value) * 160 : null),
    };

    const blocked = buildTaskPayload(
      formData({
        task_name: "  Task One  ",
        github_repo_url: " https://github.com/org/task ",
        status: "in_progress",
        priority: "2",
        assignee: " eng123 ",
        estimate_hours: "0.25",
        blocked: "on",
        blocker_note: " Waiting on access ",
        done_criteria: " Ship it ",
        capacity_hours: "0.5",
      }),
      commonDeps
    );

    expect(blocked.task_name).toBe("Task One");
    expect(blocked.github_repo_url).toBe("https://github.com/org/task");
    expect(blocked.assignee).toBe("Engineer One");
    expect(blocked.assignee_user_soeid).toBe("eng123");
    expect(blocked.blocker_note).toBe("Waiting on access");
    expect(blocked.estimate_hours).toBe(40);
    expect(blocked.capacity_hours).toBe(80);
    expect(blocked).not.toHaveProperty("estimate_fte_months");
    expect(blocked).not.toHaveProperty("capacity_fte_months");

    const unblocked = buildTaskPayload(
      formData({
        task_name: "Task One",
        status: "in_progress",
        blocker_note: "Should not persist",
      }),
      commonDeps
    );
    expect(unblocked.blocked).toBe(false);
    expect(unblocked.blocker_note).toBeNull();
  });
});

describe("task entity controller", () => {
  it("prepares create state and fills edit state with task fields", () => {
    const { controller, deps } = buildTaskController();

    controller.showTaskForm({ solution_id: "solution-1", project_id: "project-1" });

    expect(deps.els.taskForm.classList.contains("hidden")).toBe(false);
    expect(deps.els.taskFormFooter.classList.contains("hidden")).toBe(false);
    expect(deps.els.taskForm.querySelector("[name='task_id']").value).toBe("");
    expect(deps.els.taskForm.querySelector("[name='project_id']").value).toBe("project-1");
    expect(deps.els.taskForm.querySelector("[name='solution_id']").value).toBe("solution-1");
    expect(deps.els.taskForm.querySelector("[name='priority']").value).toBe("3");
    expect(deps.els.taskForm.querySelector("[name='status']").value).toBe("to_do");
    expect(deps.els.deleteTaskBtn.disabled).toBe(true);
    expect(deps.els.taskSubmitBtn.textContent).toBe("Create Task");
    expect(deps.updateTaskRepoPreview).toHaveBeenLastCalledWith("solution-1", "");

    controller.fillTaskForm({
      task_id: "task-1",
      project_id: "project-1",
      solution_id: "solution-1",
      task_name: "Draft Task",
      github_repo_url: "https://github.com/org/repo",
      priority: 2,
      due_date: "2026-04-01",
      status: "in_progress",
      assignee: "Engineer One",
      assignee_user_soeid: "eng123",
      estimate_hours: 40,
      blocked: true,
      blocker_note: "Waiting",
      done_criteria: "Complete",
      capacity_hours: 80,
    });

    expect(deps.els.taskForm.querySelector("[name='task_id']").value).toBe("task-1");
    expect(deps.els.taskForm.querySelector("[name='task_name']").value).toBe("Draft Task");
    expect(deps.els.taskForm.querySelector("[name='github_repo_url']").value).toBe("https://github.com/org/repo");
    expect(deps.els.taskForm.querySelector("[name='priority']").value).toBe("2");
    expect(deps.els.taskForm.querySelector("[name='due_date']").value).toBe("2026-04-01");
    expect(deps.els.taskForm.querySelector("[name='status']").value).toBe("in_progress");
    expect(deps.els.taskForm.querySelector("[name='assignee']").value).toBe("eng123");
    expect(deps.els.taskForm.querySelector("[name='estimate_hours']").value).toBe("0.25");
    expect(deps.els.taskForm.querySelector("[name='blocked']").checked).toBe(true);
    expect(deps.els.taskForm.querySelector("[name='blocker_note']").value).toBe("Waiting");
    expect(deps.els.taskForm.querySelector("[name='done_criteria']").value).toBe("Complete");
    expect(deps.els.taskForm.querySelector("[name='capacity_hours']").value).toBe("0.5");
    expect(deps.els.deleteTaskBtn.disabled).toBe(false);
    expect(deps.els.taskSubmitBtn.textContent).toBe("Save Changes");
    expect(deps.resolveAssigneeSelectValue).toHaveBeenCalledWith("eng123", "Engineer One");
    expect(deps.updateTaskRepoPreview).toHaveBeenLastCalledWith("solution-1", "https://github.com/org/repo");
  });
});

describe("project entity controller", () => {
  it("opens and closes the project form with edit state", () => {
    const { controller, deps } = buildProjectController();

    controller.openProjectForm({
      project_id: "proj-1",
      project_name: "Project One",
      status: "active",
      description: "Description",
      success_criteria: "Criteria",
      sponsor: "Sponsor",
      sponsor_user_soeid: "sp123",
      strategic_objective: "Objective",
      priority: 1,
    });

    expect(deps.els.projectModal.classList.contains("hidden")).toBe(false);
    expect(deps.els.projectModalTitle.textContent).toBe("Edit Project");
    expect(deps.els.projectSubmitBtn.textContent).toBe("Save Changes");
    expect(deps.els.deleteProjectBtn.disabled).toBe(false);
    expect(deps.els.projectForm.querySelector("[name='project_name']").value).toBe("Project One");

    controller.closeProjectForm();

    expect(deps.els.projectModal.classList.contains("hidden")).toBe(true);
    expect(deps.els.projectModalTitle.textContent).toBe("Create Project");
    expect(deps.els.projectSubmitBtn.textContent).toBe("Create Project");
    expect(deps.els.deleteProjectBtn.disabled).toBe(true);
  });

  it("creates a project and refreshes dependent views", async () => {
    const saved = { project_id: "proj-1", project_name: "Created" };
    const { controller, deps } = buildProjectController({
      api: vi.fn().mockResolvedValue(saved),
    });
    controller.bindProjectForm();
    deps.els.projectForm.querySelector("[name='project_name']").value = " Created ";
    deps.els.projectForm.querySelector("[name='status']").value = "active";
    deps.els.projectForm.querySelector("[name='priority']").value = "2";

    deps.els.projectForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await flushPromises();

    expect(deps.markIgnoreRefresh).toHaveBeenCalledWith("projects");
    expect(deps.api).toHaveBeenCalledWith("/projects", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(deps.api.mock.calls[0][1].body)).toMatchObject({ project_name: "Created", priority: 2 });
    expect(deps.upsertById).toHaveBeenCalledWith(deps.state.projects, saved, "project_id");
    expect(deps.populateSelects).toHaveBeenCalledTimes(1);
    expect(deps.renderMasterTable).toHaveBeenCalledTimes(1);
    expect(deps.renderDashboard).toHaveBeenCalledTimes(1);
    expect(deps.renderKanban).toHaveBeenCalledTimes(1);
    expect(deps.renderCalendar).toHaveBeenCalledTimes(1);
    expect(deps.renderGantt).toHaveBeenCalledTimes(1);
    expect(deps.trackWorkflow).toHaveBeenCalledWith("projects", "create", "success", { source: "project_form" });
    expect(deps.setDeliverableFormNotice).toHaveBeenLastCalledWith(
      deps.els.projectFormStatus,
      "Created project at 12:00.",
      "success",
      3200
    );
  });

  it("updates a project through the edit path", async () => {
    const saved = { project_id: "proj-1", project_name: "Updated" };
    const { controller, deps } = buildProjectController({
      api: vi.fn().mockResolvedValue(saved),
    });
    controller.openProjectForm(saved);
    controller.bindProjectForm();

    deps.els.projectForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await flushPromises();

    expect(deps.api).toHaveBeenCalledWith("/projects/proj-1", expect.objectContaining({ method: "PATCH" }));
    expect(deps.trackWorkflow).toHaveBeenCalledWith("projects", "update", "success", { source: "project_form" });
    expect(deps.setDeliverableFormNotice).toHaveBeenLastCalledWith(
      deps.els.projectFormStatus,
      "Saved project at 12:00.",
      "success",
      3200
    );
  });

  it("reports create failures and clears the ignored refresh marker", async () => {
    const ignoreNextRefresh = new Set(["projects"]);
    const { controller, deps } = buildProjectController({
      api: vi.fn().mockRejectedValue(new Error("backend down")),
      ignoreNextRefresh,
    });
    controller.bindProjectForm();
    deps.els.projectForm.querySelector("[name='project_name']").value = "Created";

    deps.els.projectForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await flushPromises();

    expect(ignoreNextRefresh.has("projects")).toBe(false);
    expect(deps.trackWorkflow).toHaveBeenCalledWith("projects", "create", "failure", { source: "project_form" });
    expect(deps.setDeliverableFormNotice).toHaveBeenLastCalledWith(
      deps.els.projectFormStatus,
      "Create failed: backend down",
      "error"
    );
  });

  it("deletes a confirmed project and closes the form", async () => {
    const { controller, deps } = buildProjectController({
      api: vi.fn().mockResolvedValue({ ok: true }),
    });
    deps.state.projects.push({ project_id: "proj-1", project_name: "Project One" });
    controller.openProjectForm({ project_id: "proj-1", project_name: "Project One" });
    controller.bindProjectForm();

    deps.els.deleteProjectBtn.click();
    await flushPromises();

    expect(deps.showConfirmModal).toHaveBeenCalledWith(expect.objectContaining({
      title: "Delete Project?",
      confirmLabel: "Delete Project",
    }));
    expect(deps.api).toHaveBeenCalledWith("/projects/proj-1", { method: "DELETE" });
    expect(deps.removeById).toHaveBeenCalledWith(deps.state.projects, "proj-1", "project_id");
    expect(deps.els.projectModal.classList.contains("hidden")).toBe(true);
    expect(deps.trackWorkflow).toHaveBeenCalledWith("projects", "delete", "success", { source: "project_form" });
  });
});
