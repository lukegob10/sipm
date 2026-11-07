import { it, expect, vi } from "vitest";
import { createSolutionEntityController } from "../../js/entities/solutions.js";
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

it("preserves a phase and status changed after opening the solution editor", async () => {
  const original = { solution_id:'a', project_id:'project-1', solution_name:'Old', version:'1', status:'not_started', current_phase:null, priority:3, rag_status:'green' };
  let server = {...original};
  const {controller, deps} = buildSolutionController({ api: vi.fn(async (_path, options) => { server = {...server, ...JSON.parse(options.body)}; return {...server}; }) });
  controller.bindSolutionForm();
  controller.openSolutionModal(original);
  server = {...server, status:'active', current_phase:'phase-2'};
  deps.els.solutionForm.querySelector('[name="solution_name"]').value = 'Renamed';
  deps.els.solutionForm.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
  await vi.waitFor(() => expect(deps.api).toHaveBeenCalledTimes(1));
  expect(server.status).toBe('active');
  expect(server.current_phase).toBe('phase-2');
});

it('sends explicit clears and coupled RAG and identity values', async () => {
  const original = {solution_id:'a', project_id:'project-1', solution_name:'Old', version:'1', status:'not_started', priority:3, rag_status:'green', owner:'Alex', owner_user_soeid:'ax1', description:'Old text'};
  const {controller, deps} = buildSolutionController({api:vi.fn(async (_path, options) => ({...original, ...JSON.parse(options.body)}))});
  controller.bindSolutionForm(); controller.openSolutionModal(original);
  deps.els.solutionForm.querySelector('[name="description"]').value = '';
  deps.els.solutionForm.querySelector('[name="owner"]').value = '';
  deps.els.solutionForm.querySelector('[name="owner_user_soeid"]').value = '';
  const rag = deps.els.solutionForm.querySelector('[name="rag_status"]'); rag.add(new Option('Red', 'red')); rag.value = 'red';
  deps.els.solutionForm.querySelector('[name="rag_reason"]').value = 'Risk';
  deps.els.solutionForm.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(() => expect(deps.api).toHaveBeenCalledTimes(1));
  expect(JSON.parse(deps.api.mock.calls[0][1].body)).toEqual({description:'', owner:'', owner_user_soeid:null, rag_status:'red', rag_reason:'Risk'});
});

it('keeps later draft edits relative to the just-saved values', async () => {
  const original = {solution_id:'a', project_id:'project-1', solution_name:'Old', version:'1', status:'not_started', priority:3, rag_status:'green'};
  let finish;
  const {controller, deps} = buildSolutionController({api:vi.fn().mockImplementationOnce(() => new Promise(r => {finish = r;})).mockResolvedValue({...original,solution_name:'Later'})});
  controller.bindSolutionForm(); controller.openSolutionModal(original);
  const name = deps.els.solutionForm.querySelector('[name="solution_name"]'); name.value='Submitted';
  deps.els.solutionForm.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  name.value='Later'; finish({...original,solution_name:'Submitted'});
  await vi.waitFor(() => expect(deps.els.solutionSubmitBtn.disabled).toBe(false));
  deps.els.solutionForm.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(() => expect(deps.api).toHaveBeenCalledTimes(2));
  expect(JSON.parse(deps.api.mock.calls[1][1].body)).toEqual({solution_name:'Later'});
});

it('does not replace a dirty solution editor if discard is cancelled', async () => {
  let finish;
  const {controller,deps}=buildSolutionController({showConfirmModal:()=>new Promise(r=>{finish=r;})});
  controller.bindSolutionForm();
  controller.openSolutionModal({solution_id:'a',project_id:'project-1',solution_name:'First'});
  const name=deps.els.solutionForm.querySelector('[name="solution_name"]');
  name.value='Draft';name.dispatchEvent(new Event('input',{bubbles:true}));
  const pending=controller.openSolutionModal({solution_id:'b',project_id:'project-1',solution_name:'Second'});
  expect(name.value).toBe('Draft');finish(false);
  expect(await pending).toBe(false);expect(name.value).toBe('Draft');
});

it('does not replace a newly edited solution while task confirmation is pending', async () => {
  let finish;
  const {controller,deps}=buildSolutionController({confirmTaskDraftDiscard:()=>new Promise(r=>{finish=r;})});
  controller.bindSolutionForm();
  // Simulate the initial modal having opened before a nested task was edited.
  deps.els.solutionModal.classList.remove('hidden');
  const name=deps.els.solutionForm.querySelector('[name="solution_name"]');name.value='First';
  const pending=controller.openSolutionModal({solution_id:'b',project_id:'project-1',solution_name:'Second'});
  name.value='Newer';name.dispatchEvent(new Event('input',{bubbles:true}));
  finish(true);expect(await pending).toBe(false);expect(name.value).toBe('Newer');
});
