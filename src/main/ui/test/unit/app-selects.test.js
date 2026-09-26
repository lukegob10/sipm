import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { Linter } from "eslint";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Execute the actual app builders without starting the app's network/controllers.
const appSource = readFileSync(resolve("src/main/ui/js/app.js"), "utf8");
const builderNames = new Set([
  "escapeHtml", "populateSelects", "populateCapacityUserOptions",
  "updateCurrentPhaseOptions", "phaseDisplayName", "projectLabel", "programNameForProject",
]);
const builders = [];
const diagnostics = new Linter().verify(appSource, [{
  languageOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: { builders: { rules: { collect: { create: () => ({
    FunctionDeclaration(node) {
      if (builderNames.has(node.id.name)) builders.push(appSource.slice(...node.range));
    },
  }) } } } },
  rules: { "builders/collect": "error" },
}]);
if (diagnostics.length || builders.length !== builderNames.size) {
  throw new Error("Could not load the app's option builders");
}

function harness() {
  document.body.innerHTML = `
    <form id="project"><select name="program_id"></select></form>
    <section id="solution-modal"><form id="solution">
      <input name="solution_id"><select name="project_id"></select><select name="current_phase"></select>
    </form></section>
    <form id="team"><select name="team_id"></select></form>
    <form id="task"><select name="assignee"></select><input name="assignee_user_soeid"></form>
    <datalist id="capacity"></datalist>
    <select id="ai-type"><option>project</option><option>solution</option><option>task</option></select>
    <select id="ai-id"></select>`;
  const els = {
    projectForm: document.querySelector("#project"),
    solutionForm: document.querySelector("#solution"),
    solutionModal: document.querySelector("#solution-modal"),
    teamMemberForm: document.querySelector("#team"),
    taskForm: document.querySelector("#task"),
    capacityUserOptions: document.querySelector("#capacity"),
    aiEntityType: document.querySelector("#ai-type"),
    aiEntityId: document.querySelector("#ai-id"),
  };
  const state = {
    programs: [], projects: [], phases: [], teams: [], users: [], solutions: [], tasks: [],
    kanbanFilters: {}, calendarFilters: {},
  };
  const refresh = () => runInNewContext(`${builders.join("\n")}\npopulateSelects();`, {
    state, els,
    normalizeScopedProjectFilter: () => false,
    normalizeScopedOwnerFilter: () => false,
    persistKanbanViewState: vi.fn(),
    persistCalendarViewState: vi.fn(),
    createTasksWorkbenchContext: () => ({}),
    populateTasksWorkbenchOptions: vi.fn(),
  });
  return { state, els, refresh };
}

describe("app option rendering", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it.each([
    ["users", "soeid", "display_name", '#task [name="assignee"]', null],
    ["teams", "team_id", "name", '#team [name="team_id"]', null],
    ["programs", "program_id", "program_name", '#project [name="program_id"]', null],
    ["projects", "project_id", "project_name", '#solution [name="project_id"]', null],
    ["phases", "phase_id", "phase_name", '#solution [name="current_phase"]', null],
    ["projects", "project_id", "project_name", "#ai-id", "project"],
    ["solutions", "solution_id", "solution_name", "#ai-id", "solution"],
    ["tasks", "task_id", "task_name", "#ai-id", "task"],
  ])("renders %s option values and labels as data in %s/%s", (collection, idField, labelField, selector, aiType) => {
    const { state, els, refresh } = harness();
    const id = 'id" data-injected="true';
    const label = 'Name </option><option value="forged">Forged</option><option> & "quote"';
    state[collection] = [{ [idField]: id, [labelField]: label }];
    if (aiType) els.aiEntityType.value = aiType;

    refresh();

    const select = document.querySelector(selector);
    expect([...select.options].map((option) => option.value).filter(Boolean)).toEqual([id]);
    const option = [...select.options].find((item) => item.value === id);
    expect(option.textContent).toBe(label);
    expect(option.getAttributeNames()).toEqual(["value"]);
    expect(document.querySelector("[data-injected]")).toBeNull();
    if (collection === "users") {
      select.value = id;
      select.dispatchEvent(new Event("change"));
      expect(els.taskForm.elements.namedItem("assignee_user_soeid").value).toBe(id);
    }
  });

  it("keeps quoted capacity display names inside a single datalist value", () => {
    const { state, els, refresh } = harness();
    const name = 'Name"><span data-injected="true">Forged</span><option value="other';
    state.users = [{ soeid: "member", display_name: name }];

    refresh();

    expect([...els.capacityUserOptions.options].map((option) => option.value)).toEqual([name]);
    expect(els.capacityUserOptions.querySelector("[data-injected]")).toBeNull();
  });
});
