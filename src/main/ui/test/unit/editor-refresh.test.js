import { beforeEach, describe, expect, it, vi } from "vitest";

import { bindTaskRefreshDraft, restoreEditorSelections } from "../../js/shell/data-store.js";
import { createFormDraftGuard } from "../../js/utils/form-draft.js";

function createHarness() {
  document.body.innerHTML = `
    <section id="project-modal"><form id="project-form">
      <input name="project_id"><input name="project_name">
    </form></section>
    <section id="solution-modal">
      <div class="modal-tabs"><button class="tab active" data-tab="tasks">Tasks</button></div>
      <form id="solution-form"><input name="solution_id"><input name="solution_name"></form>
      <form id="task-form"><input name="task_id"><input name="task_name"></form>
    </section>`;
  const els = {
    projectModal: document.querySelector("#project-modal"),
    solutionModal: document.querySelector("#solution-modal"),
    projectForm: document.querySelector("#project-form"),
    solutionForm: document.querySelector("#solution-form"),
    taskForm: document.querySelector("#task-form"),
  };
  const projectDraft = createFormDraftGuard({ form: els.projectForm });
  const solutionDraft = createFormDraftGuard({ form: els.solutionForm });
  projectDraft.bind();
  solutionDraft.bind();
  const taskDraft = bindTaskRefreshDraft(els.taskForm);
  const fill = (form, row) => {
    form.reset();
    Object.entries(row).forEach(([key, value]) => { form.elements.namedItem(key).value = value; });
  };
  const context = {
    els,
    state: {
      projects: [{ project_id: "p1", project_name: "Server project" }],
      solutions: [{ solution_id: "s1", solution_name: "Server solution" }],
      tasks: [{ task_id: "t1", task_name: "Server task" }],
    },
    openProjectForm: vi.fn((project) => { fill(els.projectForm, project); projectDraft.capture(); }),
    openSolutionModal: vi.fn((solution) => {
      fill(els.solutionForm, solution);
      solutionDraft.capture();
      els.taskForm.classList.add("hidden");
    }),
    fillTaskForm: vi.fn((task) => {
      fill(els.taskForm, task);
      els.taskForm.classList.remove("hidden");
    }),
  };
  context.openProjectForm(context.state.projects[0]);
  context.openSolutionModal(context.state.solutions[0]);
  context.fillTaskForm(context.state.tasks[0]);
  return { context, projectDraft, solutionDraft, taskDraft };
}

function edit(form, field, value) {
  const input = form.elements.namedItem(field);
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
  return input;
}

describe("editor refresh", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("keeps dirty project and solution drafts, focus, and their original baselines", async () => {
    const { context, projectDraft, solutionDraft } = createHarness();
    await Promise.resolve();
    edit(context.els.projectForm, "project_name", "Unsaved project");
    const focused = edit(context.els.solutionForm, "solution_name", "Unsaved solution");

    restoreEditorSelections(context, "p1", "s1", "");

    expect(context.els.projectForm.elements.namedItem("project_name").value).toBe("Unsaved project");
    expect(focused.value).toBe("Unsaved solution");
    expect(document.activeElement).toBe(focused);
    expect(projectDraft.isDirty()).toBe(true);
    expect(solutionDraft.isDirty()).toBe(true);
  });

  it("keeps a dirty task editor open when its clean parent solution refreshes", async () => {
    const { context, taskDraft } = createHarness();
    await Promise.resolve();
    const focused = edit(context.els.taskForm, "task_name", "Unsaved task");

    restoreEditorSelections(context, "", "s1", "t1");
    await Promise.resolve();

    expect(focused.value).toBe("Unsaved task");
    expect(document.activeElement).toBe(focused);
    expect(context.els.taskForm.classList.contains("hidden")).toBe(false);
    expect(taskDraft.isDirty()).toBe(true);
    expect(context.openSolutionModal).toHaveBeenCalledTimes(1);
  });

  it("preserves a new task draft without an entity ID", async () => {
    const { context } = createHarness();
    context.fillTaskForm({ task_id: "", task_name: "" });
    await Promise.resolve();
    edit(context.els.taskForm, "task_name", "New task draft");

    restoreEditorSelections(context, "", "s1", "");

    expect(context.els.taskForm.classList.contains("hidden")).toBe(false);
    expect(context.els.taskForm.elements.namedItem("task_name").value).toBe("New task draft");
  });

  it("updates clean forms with fresh server values and preserves the selected solution tab", async () => {
    const { context, taskDraft } = createHarness();
    await Promise.resolve();
    context.state.projects[0].project_name = "Fresh project";
    context.state.solutions[0].solution_name = "Fresh solution";
    context.state.tasks[0].task_name = "Fresh task";

    restoreEditorSelections(context, "p1", "s1", "t1");
    await Promise.resolve();

    expect(context.els.projectForm.elements.namedItem("project_name").value).toBe("Fresh project");
    expect(context.els.solutionForm.elements.namedItem("solution_name").value).toBe("Fresh solution");
    expect(context.els.taskForm.elements.namedItem("task_name").value).toBe("Fresh task");
    expect(context.openSolutionModal).toHaveBeenLastCalledWith(context.state.solutions[0], "tasks");
    expect(taskDraft.isDirty()).toBe(false);
  });

  it("does not reopen a task editor that the user closed", async () => {
    const { context } = createHarness();
    await Promise.resolve();
    context.els.taskForm.classList.add("hidden");

    restoreEditorSelections(context, "", "s1", "t1");

    expect(context.els.taskForm.classList.contains("hidden")).toBe(true);
    expect(context.fillTaskForm).toHaveBeenCalledTimes(1);
  });

  it("captures successful saves and explicit entity changes as clean task state", async () => {
    const { context, taskDraft } = createHarness();
    await Promise.resolve();
    edit(context.els.taskForm, "task_name", "Edited task");
    expect(taskDraft.isDirty()).toBe(true);

    context.fillTaskForm({ task_id: "t1", task_name: "Saved task" });
    await Promise.resolve();
    expect(taskDraft.isDirty()).toBe(false);
    edit(context.els.taskForm, "task_name", "Another edit");
    context.fillTaskForm({ task_id: "t2", task_name: "Different task" });
    await Promise.resolve();
    expect(taskDraft.isDirty()).toBe(false);
    expect(context.els.taskForm.elements.namedItem("task_id").value).toBe("t2");
  });
});
