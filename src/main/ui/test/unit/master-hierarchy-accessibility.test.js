import { describe, expect, it, vi } from "vitest";
import { buildMasterTable } from "../../js/routes/master/table.js";
import { renderMasterQuickstart } from "../../js/routes/master/quickstart.js";
import { renderMasterFilters } from "../../js/routes/master.js";

function quickstartContext(projects, solutions) {
  return { els: { masterQuickstart: document.createElement("div") }, state: { programs: [{ program_id: "p", program_name: "Program" }], projects, solutions, filters: {} }, showCompletedOperationalWork: () => false, isClosedProjectStatus: (s) => s === "complete", isClosedSolutionStatus: (s) => s === "complete" };
}

describe("deliverables hierarchy controls", () => {
  it("offers setup and hidden-completed actions even when an empty program header is visible", () => {
    const empty = quickstartContext([], []);
    renderMasterQuickstart(empty, 1);
    expect(empty.els.masterQuickstart.textContent).toContain("Create first project");
    const closed = quickstartContext([{ project_id: "closed", status: "complete" }], []);
    renderMasterQuickstart(closed, 1);
    expect(closed.els.masterQuickstart.textContent).toContain("Completed Work Hidden");
    expect(closed.els.masterQuickstart.querySelector('[data-quick-action="show-completed"]')).not.toBeNull();
    const activeChild = quickstartContext([{ project_id: "closed", status: "complete" }], [{ project_id: "closed", status: "active" }]);
    renderMasterQuickstart(activeChild, 2);
    expect(activeChild.els.masterQuickstart.classList.contains("hidden")).toBe(true);
  });

  it("names row controls and disables outline changes while search expands matches", () => {
    const state = { filters: { query: "alpha" }, masterCollapsed: new Set(["program:p"]) };
    const program = { program_id: "p", program_name: "Program" };
    const project = { project_id: "q", project_name: "Project" };
    const solution = { solution_id: "s", solution_name: 'Alpha "One"', status: "active", rag_status: "green", priority: 2 };
    const rows = [{ type: "program-header", program }, { type: "project-header", project }, { type: "solution", solution }];
    const root = document.createElement("div");
    root.innerHTML = buildMasterTable({ state, filteredDeliverables: () => rows, formatStatus: (s) => s, phaseDisplayName: () => "", solutionProgress: () => 0 }).html;
    expect([...root.querySelectorAll('[data-master-collapse-key]')].every((button) => button.disabled && button.getAttribute("aria-expanded") === "true")).toBe(true);
    expect(root.querySelector('[data-field="priority"]').getAttribute("aria-label")).toBe('Priority for Alpha "One"');
    expect(root.querySelector('[data-field="rag_status"]').getAttribute("aria-label")).toBe('RAG for Alpha "One"');
    expect(root.querySelector('[data-field="status"]').getAttribute("aria-label")).toBe('Status for Alpha "One"');
    const filters = document.createElement("div");
    renderMasterFilters({ state, els: { masterFilters: filters }, renderMasterTable: vi.fn() });
    expect(filters.querySelector('[data-master-outline-action="collapse-all"]').disabled).toBe(true);
    expect(filters.querySelector('[data-master-search-outline-note]').hidden).toBe(false);
    filters.querySelector('[data-master-outline-action="collapse-all"]').click();
    expect([...state.masterCollapsed]).toEqual(["program:p"]);
    const input = filters.querySelector("[data-master-query]");
    input.value = ""; input.dispatchEvent(new Event("change"));
    expect(filters.querySelector('[data-master-outline-action="collapse-all"]').disabled).toBe(false);
    expect(filters.querySelector('[data-master-search-outline-note]').hidden).toBe(true);
  });
});
