import { bindMasterTableInteractions, buildMasterTable } from "./master/table.js";

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderMasterFilters(ctx) {
  const { els, state, persistMasterViewState, renderMasterTable, renderKanban, renderCalendar, renderGantt } = ctx;
  const root = els.masterFilters;
  if (!root) return;
  const query = String(state.filters?.query || "");
  root.innerHTML = `
    <div class="deliverables-query-surface">
      <label class="deliverables-query-field">
        <span>Search Deliverables</span>
        <input
          type="search"
          id="filter-query"
          data-master-query
          value="${esc(query)}"
          placeholder="Search or use field:value, e.g. project:server status:active owner:alex"
        />
      </label>
      <div class="deliverables-outline-actions" aria-label="Deliverables outline controls">
        <button type="button" class="secondary" data-master-outline-action="expand-all">Expand All</button>
        <button type="button" class="secondary" data-master-outline-action="collapse-all">Collapse All</button>
      </div>
    </div>
  `;

  const rerenderDependents = () => {
    if (typeof renderMasterTable === "function") renderMasterTable();
    if (typeof renderKanban === "function") renderKanban();
    if (typeof renderCalendar === "function") renderCalendar();
    if (typeof renderGantt === "function") renderGantt();
  };
  const commitQuery = (input) => {
    state.filters = { query: input.value };
    if (typeof persistMasterViewState === "function") persistMasterViewState();
  };
  root.querySelectorAll("[data-master-query]").forEach((input) => {
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      commitQuery(input);
      rerenderDependents();
    });
    input.addEventListener("change", () => {
      commitQuery(input);
      rerenderDependents();
    });
  });
  root.querySelectorAll("[data-master-outline-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-master-outline-action");
      if (action === "expand-all") {
        state.masterCollapsed = new Set();
      } else if (action === "collapse-all") {
        const keys = [];
        (state.programs || []).forEach((program) => {
          if (program?.program_id) keys.push(`program:${program.program_id}`);
        });
        (state.projects || []).forEach((project) => {
          if (project?.project_id) keys.push(`project:${project.project_id}`);
        });
        state.masterCollapsed = new Set(keys);
      }
      if (typeof persistMasterViewState === "function") persistMasterViewState();
      if (typeof renderMasterTable === "function") renderMasterTable();
    });
  });
}

export function renderMasterTable(ctx) {
  const { els, renderMasterQuickstart } = ctx;
  if (!els.masterTable) return;
  const { html, rowCount } = buildMasterTable(ctx);
  if (typeof renderMasterQuickstart === "function") {
    renderMasterQuickstart(rowCount);
  }
  els.masterTable.innerHTML = html;
  bindMasterTableInteractions(ctx);
}

export function render(ctx) {
  renderMasterFilters(ctx);
  renderMasterTable(ctx);
}
