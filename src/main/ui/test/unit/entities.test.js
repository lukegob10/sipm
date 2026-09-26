import { describe, expect, it, vi } from "vitest";

import { buildProgramPayload, createProgramEntityController } from "../../js/entities/programs.js";
import { buildProjectPayload, createProjectEntityController } from "../../js/entities/projects.js";
import { buildSolutionPayload, createSolutionEntityController } from "../../js/entities/solutions.js";
import { buildTaskPayload, createTaskEntityController } from "../../js/entities/tasks.js";

function formData(values) {
  const data = new FormData();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) data.set(key, value);
  });
  return data;
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

function programEls() {
  document.body.innerHTML = `
    <section id="program-modal" class="hidden">
      <div class="modal-backdrop"></div>
      <button id="program-close" type="button"></button>
      <h2 id="program-title"></h2>
      <form id="program-form">
        <input name="program_id" />
        <input name="program_name" />
        <textarea name="description"></textarea>
        <button id="program-delete" type="button"></button>
        <button id="program-reset" type="reset"></button>
        <button id="program-submit" type="submit"></button>
      </form>
      <p id="program-status"></p>
    </section>
  `;
  return {
    programModal: document.querySelector("#program-modal"),
    programModalClose: document.querySelector("#program-close"),
    programModalTitle: document.querySelector("#program-title"),
    programForm: document.querySelector("#program-form"),
    programSubmitBtn: document.querySelector("#program-submit"),
    deleteProgramBtn: document.querySelector("#program-delete"),
    programFormStatus: document.querySelector("#program-status"),
  };
}

function buildProgramController(overrides = {}) {
  const deps = {
    state: { programs: [], projects: [] },
    els: programEls(),
    api: vi.fn(),
    markIgnoreRefresh: vi.fn(),
    ignoreNextRefresh: new Set(),
    upsertById: vi.fn(),
    removeById: vi.fn(),
    populateSelects: vi.fn(),
    renderActiveView: vi.fn(),
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    timestampLabel: vi.fn(() => "12:00"),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    ...overrides,
  };
  return { controller: createProgramEntityController(deps), deps };
}

function solutionEls() {
  document.body.innerHTML = `
    <section id="solution-modal" class="hidden">
      <div class="modal-backdrop"></div>
      <button id="solution-close" type="button"></button>
      <h2 id="solution-title"></h2>
      <form id="solution-form">
        <input name="solution_id" />
        <input name="project_id" value="project-1" />
        <input name="solution_name" value="Solution One" />
        <input name="github_repo_url" />
        <input name="version" />
        <input name="capacity_hours" />
        <select name="status"><option value="not_started" selected></option></select>
        <select name="rag_status"><option value="green" selected></option></select>
        <textarea name="rag_reason"></textarea>
        <input name="priority" />
        <input name="due_date" />
        <input name="planned_start_date" />
        <textarea name="description"></textarea>
        <textarea name="problem_statement"></textarea>
        <textarea name="success_criteria"></textarea>
        <textarea name="escalation"></textarea>
        <input name="impact_confidence" />
        <input name="owner" />
        <input name="owner_user_soeid" />
        <input name="assignee" />
        <input name="assignee_user_soeid" />
        <input name="approver" />
        <input name="approver_user_soeid" />
        <input name="key_stakeholder" />
        <input name="rag_confidence" />
        <textarea name="blockers"></textarea>
        <textarea name="risks"></textarea>
        <select name="current_phase"><option value=""></option></select>
        <button id="solution-delete" type="button"></button>
        <button id="solution-submit" type="submit"></button>
      </form>
      <p id="solution-status"></p>
    </section>
  `;
  return {
    solutionModal: document.querySelector("#solution-modal"),
    solutionModalClose: document.querySelector("#solution-close"),
    solutionModalTitle: document.querySelector("#solution-title"),
    solutionForm: document.querySelector("#solution-form"),
    solutionSubmitBtn: document.querySelector("#solution-submit"),
    deleteSolutionBtn: document.querySelector("#solution-delete"),
    solutionFormStatus: document.querySelector("#solution-status"),
  };
}

function buildSolutionController(overrides = {}) {
  const deps = {
    state: { solutions: [], solutionDocuments: {} },
    els: solutionEls(),
    api: vi.fn(),
    hoursFromFteInput: (value) => Number(value || 0) * 160,
    fteFromHoursForInput: (hours) => String(Number(hours || 0) / 160),
    markIgnoreRefresh: vi.fn(),
    ignoreNextRefresh: new Set(),
    upsertById: vi.fn(),
    removeById: vi.fn(),
    populateSelects: vi.fn(),
    renderActiveView: vi.fn(),
    renderMasterTable: vi.fn(),
    renderDashboard: vi.fn(),
    renderKanban: vi.fn(),
    renderCalendar: vi.fn(),
    renderGantt: vi.fn(),
    renderSolutionTasks: vi.fn(),
    renderSolutionDocuments: vi.fn(),
    renderSolutionActivity: vi.fn(),
    setTaskFormVisibility: vi.fn(),
    setTaskActionButtonLabel: vi.fn(),
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    updateCurrentPhaseOptions: vi.fn(),
    updateTaskRepoPreview: vi.fn(),
    setSolutionTab: vi.fn(),
    timestampLabel: vi.fn(() => "12:00"),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    ...overrides,
  };
  return { controller: createSolutionEntityController(deps), deps };
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
        <input name="function" />
        <input name="area" />
        <select name="status"><option value="not_started"></option><option value="active"></option></select>
        <textarea name="description"></textarea>
        <textarea name="success_criteria"></textarea>
        <input name="sponsor" />
        <input name="sponsor_user_soeid" />
        <input name="owner" />
        <input name="owner_user_soeid" />
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
      <textarea name="description"></textarea>
      <input name="github_repo_url" />
      <input name="priority" />
      <input name="due_date" />
      <select name="status"><option value="to_do"></option><option value="in_progress"></option></select>
      <select name="assignee"><option value=""></option><option value="eng123"></option></select>
      <input name="assignee_user_soeid" />
      <input name="estimate_hours" />
      <input name="blocked" type="checkbox" />
      <input name="blocker_note" />
      <textarea name="acceptance_criteria"></textarea>
      <input name="capacity_hours" />
    </form>
    <div id="task-form-footer" class="hidden"></div>
    <button id="task-submit-btn" type="submit"></button>
    <button id="delete-task" type="button"></button>
    <p id="task-form-status"></p>
    <form id="solution-form"><input name="solution_id" /></form>
    <button id="show-task-form" type="button"></button>
    <div id="solution-task-table"><div data-id="task-1"><button class="edit-task-btn" type="button"></button></div></div>
  `;
  return {
    taskForm: document.querySelector("#task-form"),
    taskFormFooter: document.querySelector("#task-form-footer"),
    taskSubmitBtn: document.querySelector("#task-submit-btn"),
    deleteTaskBtn: document.querySelector("#delete-task"),
    taskFormStatus: document.querySelector("#task-form-status"),
    solutionForm: document.querySelector("#solution-form"),
    showTaskFormBtn: document.querySelector("#show-task-form"),
    solutionTaskTable: document.querySelector("#solution-task-table"),
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
      function: "  Finance  ",
      area: "  Data and Analytics  ",
      status: "active",
      description: " Keep spacing in long text ",
      success_criteria: "   ",
      sponsor: "  Sponsor Name  ",
      sponsor_user_soeid: " tu12345 ",
      owner: "  Project Owner  ",
      owner_user_soeid: " ow12345 ",
      strategic_objective: "",
      priority: "2",
    }));

    expect(payload).toEqual({
      program_id: "program-1",
      project_name: "Project Alpha",
      function: "Finance",
      area: "Data and Analytics",
      status: "active",
      description: " Keep spacing in long text ",
      success_criteria: null,
      sponsor: "Sponsor Name",
      sponsor_user_soeid: "tu12345",
      owner: "Project Owner",
      owner_user_soeid: "ow12345",
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
        project_id: " project-2 ",
        solution_name: "  Solution One  ",
        github_repo_url: " https://github.com/org/repo ",
        version: " 1.0.0 ",
        status: "active",
        priority: "1",
        owner: "  Owner Name  ",
        owner_user_soeid: " on12345 ",
        assignee: "Assignee Display",
        assignee_user_soeid: "",
        escalation: " Escalated request ",
        capacity_hours: "0.5",
        rag_status: "amber",
      }),
      { hoursFromFteInput: (value) => Number(value) * 160 }
    );

    expect(payload.project_id).toBe("project-2");
    expect(payload.solution_name).toBe("Solution One");
    expect(payload.github_repo_url).toBe("https://github.com/org/repo");
    expect(payload.version).toBe("1.0.0");
    expect(payload.owner).toBe("Owner Name");
    expect(payload.owner_user_soeid).toBe("on12345");
    expect(payload.assignee).toBe("Assignee Display");
    expect(payload.assignee_user_soeid).toBeNull();
    expect(payload.escalation).toBe("Escalated request");
    expect(payload.capacity_hours).toBe(80);
    expect(payload).not.toHaveProperty("capacity_fte_months");
  });

  it("clears a stale RAG reason when a solution returns to green", () => {
    const payload = buildSolutionPayload(
      formData({
        project_id: "project-2",
        solution_name: "Solution One",
        version: "1.0.0",
        status: "active",
        owner: "Owner Name",
        assignee: "Assignee Display",
        key_stakeholder: "Stakeholder",
        capacity_hours: "0",
        rag_status: "green",
        rag_reason: "No longer applicable",
      }),
      { hoursFromFteInput: (value) => Number(value) * 160 }
    );

    expect(payload.rag_status).toBe("green");
    expect(payload.rag_reason).toBeNull();
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
        description: " Explain the expected work ",
        github_repo_url: " https://github.com/org/task ",
        status: "in_progress",
        priority: "2",
        assignee: " eng123 ",
        estimate_hours: "0.25",
        blocked: "on",
        blocker_note: " Waiting on access ",
        acceptance_criteria: " Ship it ",
        capacity_hours: "0.5",
      }),
      commonDeps
    );

    expect(blocked.task_name).toBe("Task One");
    expect(blocked.description).toBe("Explain the expected work");
    expect(blocked.acceptance_criteria).toBe("Ship it");
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
      description: "Explain the work",
      github_repo_url: "https://github.com/org/repo",
      priority: 2,
      due_date: "2026-04-01",
      status: "in_progress",
      assignee: "Engineer One",
      assignee_user_soeid: "eng123",
      estimate_hours: 40,
      blocked: true,
      blocker_note: "Waiting",
      acceptance_criteria: "Complete",
      capacity_hours: 80,
    });

    expect(deps.els.taskForm.querySelector("[name='task_id']").value).toBe("task-1");
    expect(deps.els.taskForm.querySelector("[name='task_name']").value).toBe("Draft Task");
    expect(deps.els.taskForm.querySelector("[name='description']").value).toBe("Explain the work");
    expect(deps.els.taskForm.querySelector("[name='github_repo_url']").value).toBe("https://github.com/org/repo");
    expect(deps.els.taskForm.querySelector("[name='priority']").value).toBe("2");
    expect(deps.els.taskForm.querySelector("[name='due_date']").value).toBe("2026-04-01");
    expect(deps.els.taskForm.querySelector("[name='status']").value).toBe("in_progress");
    expect(deps.els.taskForm.querySelector("[name='assignee']").value).toBe("eng123");
    expect(deps.els.taskForm.querySelector("[name='estimate_hours']").value).toBe("0.25");
    expect(deps.els.taskForm.querySelector("[name='blocked']").checked).toBe(true);
    expect(deps.els.taskForm.querySelector("[name='blocker_note']").value).toBe("Waiting");
    expect(deps.els.taskForm.querySelector("[name='acceptance_criteria']").value).toBe("Complete");
    expect(deps.els.taskForm.querySelector("[name='capacity_hours']").value).toBe("0.5");
    expect(deps.els.deleteTaskBtn.disabled).toBe(false);
    expect(deps.els.taskSubmitBtn.textContent).toBe("Save Changes");
    expect(deps.resolveAssigneeSelectValue).toHaveBeenCalledWith("eng123", "Engineer One");
    expect(deps.updateTaskRepoPreview).toHaveBeenLastCalledWith("solution-1", "https://github.com/org/repo");

    controller.hideTaskForm();
    expect(deps.els.taskForm.classList.contains("hidden")).toBe(true);
    expect(deps.els.taskFormFooter.classList.contains("hidden")).toBe(true);
  });
});

describe("project entity controller", () => {
  it("opens and closes the project form with edit state", () => {
    const { controller, deps } = buildProjectController();

    controller.openProjectForm({
      project_id: "proj-1",
      project_name: "Project One",
      function: "Finance",
      area: "Data and Analytics",
      status: "active",
      description: "Description",
      success_criteria: "Criteria",
      sponsor: "Sponsor",
      sponsor_user_soeid: "sp123",
      owner: "Owner",
      owner_user_soeid: "ow123",
      strategic_objective: "Objective",
      priority: 1,
    });

    expect(deps.els.projectModal.classList.contains("hidden")).toBe(false);
    expect(deps.els.projectModalTitle.textContent).toBe("Edit Project");
    expect(deps.els.projectSubmitBtn.textContent).toBe("Save Changes");
    expect(deps.els.deleteProjectBtn.disabled).toBe(false);
    expect(deps.els.projectForm.querySelector("[name='project_name']").value).toBe("Project One");
    expect(deps.els.projectForm.querySelector("[name='function']").value).toBe("Finance");
    expect(deps.els.projectForm.querySelector("[name='area']").value).toBe("Data and Analytics");
    expect(deps.els.projectForm.querySelector("[name='owner']").value).toBe("Owner");
    expect(deps.els.projectForm.querySelector("[name='owner_user_soeid']").value).toBe("ow123");

    controller.closeProjectForm();

    expect(deps.els.projectModal.classList.contains("hidden")).toBe(true);
    expect(deps.els.projectModalTitle.textContent).toBe("Create Project");
    expect(deps.els.projectSubmitBtn.textContent).toBe("Create Project");
    expect(deps.els.deleteProjectBtn.disabled).toBe(true);
  });

  it("protects unsaved project changes before closing", async () => {
    const showConfirmModal = vi.fn().mockResolvedValue(false);
    const { controller, deps } = buildProjectController({ showConfirmModal });
    controller.bindProjectForm();
    controller.openProjectForm({
      project_id: "proj-1",
      program_id: "program-1",
      project_name: "Project One",
    });

    const nameField = deps.els.projectForm.querySelector("[name='project_name']");
    nameField.value = "Unsaved name";
    nameField.dispatchEvent(new Event("input", { bubbles: true }));

    const closed = await controller.closeProjectForm();

    expect(closed).toBe(false);
    expect(showConfirmModal).toHaveBeenCalledWith(expect.objectContaining({
      title: "Discard Project changes?",
      confirmLabel: "Discard Changes",
    }));
    expect(deps.els.projectModal.classList.contains("hidden")).toBe(false);
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

describe("entity form submissions", () => {
  const submissionCases = [
    {
      name: "program",
      build: buildProgramController,
      bind(controller) { controller.bindProgramForm(); },
      form(els) { return els.programForm; },
      nameField: "program_name",
      idField: "program_id",
      saved: { program_id: "program-saved", program_name: "Submitted" },
      upsertKey: "program_id",
    },
    {
      name: "project",
      build: buildProjectController,
      bind(controller) { controller.bindProjectForm(); },
      form(els) { return els.projectForm; },
      nameField: "project_name",
      idField: "project_id",
      saved: { project_id: "project-saved", project_name: "Submitted" },
      upsertKey: "project_id",
    },
    {
      name: "solution",
      build: buildSolutionController,
      bind(controller) { controller.bindSolutionForm(); },
      form(els) { return els.solutionForm; },
      nameField: "solution_name",
      idField: "solution_id",
      saved: { solution_id: "solution-saved", solution_name: "Submitted" },
      upsertKey: "solution_id",
    },
  ];

  it.each(submissionCases)("sends only one $name mutation while its save is pending", async (testCase) => {
    const request = deferred();
    const { controller, deps } = testCase.build({ api: vi.fn(() => request.promise) });
    const form = testCase.form(deps.els);
    testCase.bind(controller);
    form.querySelector(`[name="${testCase.nameField}"]`).value = "Submitted";

    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    expect(deps.api).toHaveBeenCalledTimes(1);
    request.reject(new Error("test cleanup"));
    await flushPromises();
  });

  it.each(submissionCases)("preserves a newer $name draft and reuses the created ID", async (testCase) => {
    const request = deferred();
    const { controller, deps } = testCase.build({ api: vi.fn(() => request.promise) });
    const form = testCase.form(deps.els);
    testCase.bind(controller);
    form.querySelector(`[name="${testCase.nameField}"]`).value = "Submitted";

    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.querySelector(`[name="${testCase.nameField}"]`).value = "Newer draft";
    request.resolve(testCase.saved);
    await flushPromises();

    expect(form.querySelector(`[name="${testCase.nameField}"]`).value).toBe("Newer draft");
    expect(form.querySelector(`[name="${testCase.idField}"]`).value).toBe(testCase.saved[testCase.idField]);
    expect(deps.upsertById).toHaveBeenCalledWith(
      deps.state[testCase.name === "program" ? "programs" : testCase.name === "project" ? "projects" : "solutions"],
      testCase.saved,
      testCase.upsertKey,
    );
  });

  it.each(submissionCases)("does not apply a $name save after its same-ID space object is replaced", async (testCase) => {
    const request = deferred();
    const { controller, deps } = testCase.build({ api: vi.fn(() => request.promise) });
    deps.state.user = { user_id: "user-1" };
    deps.state.activeSpace = { space_id: "space-1" };
    const form = testCase.form(deps.els);
    testCase.bind(controller);
    form.querySelector(`[name="${testCase.nameField}"]`).value = "Submitted";

    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    deps.state.activeSpace = { space_id: "space-1" };
    request.resolve(testCase.saved);
    await flushPromises();

    expect(deps.upsertById).not.toHaveBeenCalled();
  });

  it("does not attach a pending program create to the form after an explicit reset", async () => {
    const request = deferred();
    const { controller, deps } = buildProgramController({ api: vi.fn(() => request.promise) });
    controller.bindProgramForm();
    const form = deps.els.programForm;
    form.querySelector('[name="program_name"]').value = "Submitted";

    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.reset();
    form.querySelector('[name="program_name"]').value = "New draft after reset";
    request.resolve({ program_id: "program-saved", program_name: "Submitted" });
    await flushPromises();

    expect(form.querySelector('[name="program_id"]').value).toBe("");
    expect(form.querySelector('[name="program_name"]').value).toBe("New draft after reset");
    expect(deps.els.programModalTitle.textContent).toBe("Create Program");
  });
});

describe("entity delete editor races", () => {
  const deleteCases = [
    {
      name: "program",
      build: buildProgramController,
      open(controller, record) { controller.openProgramForm(record); },
      bind(controller) { controller.bindProgramForm(); },
      deleteButton(els) { return els.deleteProgramBtn; },
      modal(els) { return els.programModal; },
      form(els) { return els.programForm; },
      status(els) { return els.programFormStatus; },
      title(els) { return els.programModalTitle; },
      collection: "programs",
      idField: "program_id",
      nameField: "program_name",
      path: "/programs/entity-a",
      assertRefreshed(deps) { expect(deps.renderActiveView).toHaveBeenCalled(); },
    },
    {
      name: "project",
      build: buildProjectController,
      open(controller, record) { controller.openProjectForm(record); },
      bind(controller) { controller.bindProjectForm(); },
      deleteButton(els) { return els.deleteProjectBtn; },
      modal(els) { return els.projectModal; },
      form(els) { return els.projectForm; },
      status(els) { return els.projectFormStatus; },
      title(els) { return els.projectModalTitle; },
      collection: "projects",
      idField: "project_id",
      nameField: "project_name",
      path: "/projects/entity-a",
      assertRefreshed(deps) { expect(deps.renderMasterTable).toHaveBeenCalled(); },
    },
    {
      name: "solution",
      build: buildSolutionController,
      open(controller, record) { controller.openSolutionModal(record); },
      bind(controller) { controller.bindSolutionForm(); },
      deleteButton(els) { return els.deleteSolutionBtn; },
      modal(els) { return els.solutionModal; },
      form(els) { return els.solutionForm; },
      status(els) { return els.solutionFormStatus; },
      title(els) { return els.solutionModalTitle; },
      collection: "solutions",
      idField: "solution_id",
      nameField: "solution_name",
      path: "/solutions/entity-a",
      assertRefreshed(deps) { expect(deps.renderMasterTable).toHaveBeenCalled(); },
    },
  ];

  function recordFor(testCase, id, name) {
    return { [testCase.idField]: id, [testCase.nameField]: name };
  }

  function removeRecord(rows, id, idField) {
    const index = rows.findIndex((row) => row[idField] === id);
    if (index >= 0) rows.splice(index, 1);
  }

  it.each(deleteCases)("keeps another $name editor open after the confirmed delete succeeds", async (testCase) => {
    const request = deferred();
    const trackWorkflow = vi.fn();
    const { controller, deps } = testCase.build({
      api: vi.fn(() => request.promise),
      removeById: vi.fn(removeRecord),
      trackWorkflow,
    });
    deps.state.user = { user_id: "user-1" };
    deps.state.activeSpace = { space_id: "space-1" };
    const rows = deps.state[testCase.collection];
    rows.push(recordFor(testCase, "entity-a", "Entity A"), recordFor(testCase, "entity-b", "Entity B"));
    testCase.open(controller, rows[0]);
    testCase.bind(controller);

    testCase.deleteButton(deps.els).click();
    await vi.waitFor(() => expect(deps.api).toHaveBeenCalledWith(testCase.path, { method: "DELETE" }));
    testCase.open(controller, rows[1]);
    const noticeCallCount = deps.setDeliverableFormNotice.mock.calls.length;
    request.resolve({ ok: true });
    await vi.waitFor(() => expect(deps.removeById).toHaveBeenCalledWith(rows, "entity-a", testCase.idField));

    expect(rows.map((row) => row[testCase.idField])).toEqual(["entity-b"]);
    expect(testCase.form(deps.els).querySelector(`[name="${testCase.idField}"]`).value).toBe("entity-b");
    expect(testCase.modal(deps.els).classList.contains("hidden")).toBe(false);
    expect(testCase.title(deps.els).textContent).toMatch(/Edit/);
    expect(deps.setDeliverableFormNotice).toHaveBeenCalledTimes(noticeCallCount);
    expect(trackWorkflow).toHaveBeenCalledWith(testCase.collection, "delete", "success", { source: `${testCase.name}_form` });
    testCase.assertRefreshed(deps);
  });

  it.each(deleteCases)("keeps another $name editor and its notice untouched after delete fails", async (testCase) => {
    const request = deferred();
    const trackWorkflow = vi.fn();
    const { controller, deps } = testCase.build({
      api: vi.fn(() => request.promise),
      trackWorkflow,
    });
    deps.state.user = { user_id: "user-1" };
    deps.state.activeSpace = { space_id: "space-1" };
    const rows = deps.state[testCase.collection];
    rows.push(recordFor(testCase, "entity-a", "Entity A"), recordFor(testCase, "entity-b", "Entity B"));
    testCase.open(controller, rows[0]);
    testCase.bind(controller);

    testCase.deleteButton(deps.els).click();
    await vi.waitFor(() => expect(deps.api).toHaveBeenCalledWith(testCase.path, { method: "DELETE" }));
    testCase.open(controller, rows[1]);
    const noticeCallCount = deps.setDeliverableFormNotice.mock.calls.length;
    request.reject(new Error("Delete failed"));
    await vi.waitFor(() => expect(trackWorkflow).toHaveBeenCalledWith(
      testCase.collection,
      "delete",
      "failure",
      { source: `${testCase.name}_form` },
    ));

    expect(rows.map((row) => row[testCase.idField])).toEqual(["entity-a", "entity-b"]);
    expect(testCase.form(deps.els).querySelector(`[name="${testCase.idField}"]`).value).toBe("entity-b");
    expect(testCase.modal(deps.els).classList.contains("hidden")).toBe(false);
    expect(deps.setDeliverableFormNotice).toHaveBeenCalledTimes(noticeCallCount);
  });

  it.each(deleteCases)("does not send a $name delete if confirmation resolves after switching editors", async (testCase) => {
    const confirmation = deferred();
    const { controller, deps } = testCase.build({
      showConfirmModal: vi.fn(() => confirmation.promise),
    });
    deps.state.user = { user_id: "user-1" };
    deps.state.activeSpace = { space_id: "space-1" };
    const rows = deps.state[testCase.collection];
    rows.push(recordFor(testCase, "entity-a", "Entity A"), recordFor(testCase, "entity-b", "Entity B"));
    testCase.open(controller, rows[0]);
    testCase.bind(controller);

    testCase.deleteButton(deps.els).click();
    testCase.open(controller, rows[1]);
    confirmation.resolve(true);
    await flushPromises();

    expect(deps.api).not.toHaveBeenCalled();
    expect(testCase.form(deps.els).querySelector(`[name="${testCase.idField}"]`).value).toBe("entity-b");
    expect(testCase.modal(deps.els).classList.contains("hidden")).toBe(false);
  });
});
