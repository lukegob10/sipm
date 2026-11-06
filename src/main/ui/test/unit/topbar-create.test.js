import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTopbarCreateController } from "../../js/shell/topbar-create.js";

function buildHarness(overrides = {}) {
  document.body.innerHTML = `
    <div id="topbar-create-shell">
      <button id="topbar-create-toggle" aria-expanded="false"></button>
      <div id="topbar-create-panel" class="hidden" role="menu">
        <button id="topbar-create-program" role="menuitem">Program</button>
        <button id="topbar-create-project" role="menuitem">Project</button>
        <button id="topbar-create-solution" role="menuitem">Solution</button>
        <button id="topbar-create-task" role="menuitem">Task</button>
      </div>
    </div>
    <button id="outside"></button>
    <div id="task-create-picker-modal" class="hidden"><form id="task-create-picker-form"><select name="solution_id" id="task-create-picker-select"></select></form><button id="task-create-picker-cancel">Cancel</button></div>
  `;
  const els = {
    topbarCreateToggle: document.getElementById("topbar-create-toggle"),
    topbarCreatePanel: document.getElementById("topbar-create-panel"),
    topbarCreateProgram: document.getElementById("topbar-create-program"),
    topbarCreateProject: document.getElementById("topbar-create-project"),
    topbarCreateSolution: document.getElementById("topbar-create-solution"),
    topbarCreateTask: document.getElementById("topbar-create-task"),
    taskCreatePickerModal: document.getElementById("task-create-picker-modal"),
    taskCreatePickerForm: document.getElementById("task-create-picker-form"),
    taskCreatePickerSelect: document.getElementById("task-create-picker-select"),
    taskCreatePickerCancel: document.getElementById("task-create-picker-cancel"),
  };
  const state = overrides.state || { solutions: [], projects: [] };
  const openSolutionModal = vi.fn();
  const showTaskForm = vi.fn();
  const setStatus = vi.fn();
  const controller = createTopbarCreateController({
    state,
    els,
    escapeHtml: String,
    openProgramForm: vi.fn(),
    openProjectForm: vi.fn(),
    openSolutionModal,
    showTaskForm,
    ensureCreateData: overrides.ensureCreateData,
    setStatus,
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
  });
  controller.bindTopbarCreateMenu();
  controller.bindTaskCreatePicker();
  return { controller, els, state, openSolutionModal, showTaskForm, setStatus, outside: document.getElementById("outside") };
}

describe("topbar create menu", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("loads task dependencies before deciding whether a solution exists", async () => {
    const solution = { solution_id: "sol-1", project_id: "proj-1", solution_name: "Existing" };
    const state = { authed: true, currentView: "my-work", activeSpace: { space_id: "a" }, user: { user_id: "u" }, solutions: [], projects: [] };
    const ensureCreateData = vi.fn(async () => { state.solutions = [solution]; return true; });
    const { els, openSolutionModal, showTaskForm } = buildHarness({ state, ensureCreateData });

    els.topbarCreateTask.click();
    await vi.waitFor(() => expect(showTaskForm).toHaveBeenCalledWith(solution));

    expect(ensureCreateData).toHaveBeenCalledWith(expect.arrayContaining(["projects", "solutions", "tasks"]));
    expect(openSolutionModal).toHaveBeenCalledWith(solution, "tasks");
  });

  it.each([
    ["topbarCreateProject", ["programs", "users"]],
    ["topbarCreateSolution", ["phases", "programs", "projects", "users"]],
  ])("loads dependencies for %s", async (button, dependencies) => {
    const state = { authed: true, currentView: "my-work", activeSpace: { space_id: "a" }, user: { user_id: "u" }, solutions: [], projects: [] };
    const ensureCreateData = vi.fn().mockResolvedValue(true);
    const { els } = buildHarness({ state, ensureCreateData });
    els[button].click();
    await vi.waitFor(() => expect(ensureCreateData).toHaveBeenCalledWith(dependencies));
  });

  it("does not open an editor when required data fails to load", async () => {
    const state = { authed: true, currentView: "my-work", activeSpace: { space_id: "a" }, user: { user_id: "u" }, solutions: [], projects: [] };
    const warning = vi.spyOn(console, "warn").mockImplementation(() => {});
    const ensureCreateData = vi.fn().mockRejectedValue(new Error("unavailable"));
    const { els, openSolutionModal, showTaskForm, setStatus } = buildHarness({ state, ensureCreateData });

    els.topbarCreateTask.click();
    await vi.waitFor(() => expect(setStatus).toHaveBeenCalledWith(expect.stringContaining("Could not load"), "danger"));
    expect(openSolutionModal).not.toHaveBeenCalled();
    expect(showTaskForm).not.toHaveBeenCalled();
    warning.mockRestore();
  });

  it("does not open an editor after the active space changes during loading", async () => {
    const state = { authed: true, currentView: "my-work", activeSpace: { space_id: "a" }, user: { user_id: "u" }, solutions: [], projects: [] };
    let finish;
    const ensureCreateData = vi.fn(() => new Promise((resolve) => { finish = resolve; }));
    const { els, openSolutionModal, showTaskForm } = buildHarness({ state, ensureCreateData });

    els.topbarCreateTask.click();
    state.activeSpace = { space_id: "b" };
    finish(true);
    await Promise.resolve();
    expect(openSolutionModal).not.toHaveBeenCalled();
    expect(showTaskForm).not.toHaveBeenCalled();
  });

  it("closes when keyboard focus moves out of the menu", () => {
    const { els, outside } = buildHarness();
    els.topbarCreateToggle.click();
    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(false);
    expect(document.activeElement).toBe(els.topbarCreateProgram);

    outside.focus();

    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(true);
    expect(els.topbarCreateToggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(outside);
  });

  it("keeps the menu open while keyboard focus moves between menu items", () => {
    const { els } = buildHarness();
    els.topbarCreateToggle.click();

    els.topbarCreateProject.focus();

    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(false);
    expect(els.topbarCreateToggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("closes when its toggle is clicked after focus returns from a menu item", () => {
    const { els } = buildHarness();
    els.topbarCreateToggle.click();

    els.topbarCreateToggle.focus();
    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(false);
    els.topbarCreateToggle.click();

    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(true);
    expect(els.topbarCreateToggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(els.topbarCreateToggle);
  });
});

it.each(['cancel', 'space change'])('does not continue task creation after %s during solution opening', async (scenario) => {
  const solution = { solution_id: 's', project_id: 'p', solution_name: 'S' };
  const state = { authed:true, currentView:'my-work', user:{user_id:'u'}, activeSpace:{space_id:'a'}, solutions:[solution], projects:[] };
  const {els,openSolutionModal,showTaskForm} = buildHarness({state,ensureCreateData:vi.fn().mockResolvedValue(true)});
  const form = document.createElement('form'); form.innerHTML='<input name="solution_id" value="s">'; els.solutionForm=form;
  let finish; openSolutionModal.mockImplementation(()=>new Promise(r=>{finish=r;}));
  els.topbarCreateTask.click();
  await vi.waitFor(()=>expect(openSolutionModal).toHaveBeenCalled());
  expect(showTaskForm).not.toHaveBeenCalled();
  if (scenario === 'space change') state.activeSpace={space_id:'b'};
  finish(scenario !== 'cancel'); await Promise.resolve();
  expect(showTaskForm).not.toHaveBeenCalled();
});


it("focuses the picker and restores the Create button only in its original context", async () => {
  const state = { authed: true, currentView: "master", activeSpace: { space_id: "a" }, user: { user_id: "u" }, projects: [], solutions: [
    { solution_id: "s1", solution_name: "One" }, { solution_id: "s2", solution_name: "Two" },
  ] };
  const { els, outside } = buildHarness({ state, ensureCreateData: vi.fn().mockResolvedValue(true) });
  els.topbarCreateTask.click();
  await vi.waitFor(() => expect(document.activeElement).toBe(els.taskCreatePickerSelect));
  els.taskCreatePickerCancel.click();
  expect(document.activeElement).toBe(els.topbarCreateToggle);
  els.topbarCreateTask.click();
  await vi.waitFor(() => expect(document.activeElement).toBe(els.taskCreatePickerSelect));
  state.activeSpace = { space_id: "b" };
  outside.focus();
  els.taskCreatePickerCancel.click();
  expect(document.activeElement).toBe(outside);
});
