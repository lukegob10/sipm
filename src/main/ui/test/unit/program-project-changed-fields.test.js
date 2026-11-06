import { it, expect, vi } from "vitest";
import { createProgramEntityController } from "../../js/entities/programs.js";
import { createProjectEntityController } from "../../js/entities/projects.js";
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
  const deps = {
    state,
    els: projectEls(),
    api: vi.fn(),
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


it.each(["program", "project"])("preserves unrelated external edits when saving a stale %s editor", async (kind) => {
  const original = kind === 'program' ? {program_id:'a',program_name:'Old',description:'Original'} : {project_id:'a',program_id:'program-1',project_name:'Old',status:'not_started',description:'Original',priority:3};
  let server = {...original};
  const api = vi.fn(async (_path, options) => { server = {...server,...JSON.parse(options.body)};return {...server}; });
  const {controller,deps} = kind === 'program' ? buildProgramController({api}) : buildProjectController({api});
  const form = kind === 'program' ? deps.els.programForm : deps.els.projectForm;
  if(kind === 'program') {controller.bindProgramForm(); controller.openProgramForm(original);} else {controller.bindProjectForm();controller.openProjectForm(original);}
  server.description = 'Changed elsewhere';
  form.querySelector(`[name="${kind}_name"]`).value='Renamed';
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
  expect(server.description).toBe('Changed elsewhere');
});

it('keeps project owner and sponsor identity pairs together while clearing fields', async () => {
  const original={project_id:'a',program_id:'program-1',project_name:'Old',status:'not_started',priority:3,owner:'Alex',owner_user_soeid:'ax1',sponsor:'Sam',sponsor_user_soeid:'ss1',description:'Text'};
  const {controller,deps}=buildProjectController({api:vi.fn(async (_path, options)=>({...original,...JSON.parse(options.body)}))});
  controller.bindProjectForm(); controller.openProjectForm(original);
  const form=deps.els.projectForm;
  for(const name of ['owner','owner_user_soeid','sponsor','sponsor_user_soeid','description']) form.querySelector(`[name="${name}"]`).value='';
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(()=>expect(deps.api).toHaveBeenCalledTimes(1));
  expect(JSON.parse(deps.api.mock.calls[0][1].body)).toEqual({owner:'',owner_user_soeid:null,sponsor:'',sponsor_user_soeid:null,description:''});
});

it.each(['program','project'])('preserves later edits after a %s save', async (kind) => {
  const original=kind==='program'?{program_id:'a',program_name:'Old'}:{project_id:'a',program_id:'program-1',project_name:'Old',status:'not_started',priority:3};
  let finish;
  const api=vi.fn().mockImplementationOnce(()=>new Promise(r=>{finish=r;})).mockResolvedValue({...original,[`${kind}_name`]:'Later'});
  const {controller,deps}=kind==='program'?buildProgramController({api}):buildProjectController({api});
  const form=kind==='program'?deps.els.programForm:deps.els.projectForm;
  const submit=kind==='program'?deps.els.programSubmitBtn:deps.els.projectSubmitBtn;
  if(kind==='program'){controller.bindProgramForm();controller.openProgramForm(original);}else{controller.bindProjectForm();controller.openProjectForm(original);}
  const name=form.querySelector(`[name="${kind}_name"]`);name.value='Submitted';
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));name.value='Later';
  finish({...original,[`${kind}_name`]:'Submitted'});
  await vi.waitFor(()=>expect(submit.disabled).toBe(false));
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(()=>expect(api).toHaveBeenCalledTimes(2));
  expect(JSON.parse(api.mock.calls[1][1].body)).toEqual({[`${kind}_name`]:'Later'});
});

it.each(['program','project'])('keeps complete %s create payloads', async (kind) => {
  const api=vi.fn().mockResolvedValue(kind==='program'?{program_id:'new',program_name:'New'}:{project_id:'new',program_id:'program-1',project_name:'New'});
  const {controller,deps}=kind==='program'?buildProgramController({api}):buildProjectController({api});
  const form=kind==='program'?deps.els.programForm:deps.els.projectForm;
  if(kind==='program'){controller.bindProgramForm();controller.openProgramForm();}else{controller.bindProjectForm();controller.openProjectForm();}
  form.querySelector(`[name="${kind}_name"]`).value='New';
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(()=>expect(api).toHaveBeenCalledTimes(1));
  const payload=JSON.parse(api.mock.calls[0][1].body);
  expect(payload[`${kind}_name`]).toBe('New');
  expect(payload).toHaveProperty('description');
  if(kind==='project') expect(payload).toHaveProperty('program_id','program-1');
});
