export function renderMasterFilters(ctx) {
  const { els } = ctx;
  const root = els.masterFilters;
  if (!root) return;
  // Filters are rendered inside the deliverables table so headers, filters,
  // and row data share one horizontal scroll container and stay aligned.
  root.innerHTML = "";
}

export function renderMasterTable(ctx) {
  const {
    state,
    els,
    filteredDeliverables,
    deliverableKey,
    phaseDisplayName,
    solutionProgress,
    updateBulkSelectionCount,
    renderMasterQuickstart,
    renderKanban,
    renderCalendar,
    persistMasterViewState,
  } = ctx;

  if (!els.masterTable) return;
  const HOURS_PER_FTE_MONTH = 160;
  const numericOrNull = (value) => {
    if (value === null || value === undefined) return null;
    if (typeof value === "string" && !value.trim()) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const solutionFteMonths = (solution) => {
    const direct = numericOrNull(solution?.capacity_fte_months);
    if (direct != null) return Math.max(direct, 0);
    const hours = numericOrNull(solution?.capacity_hours);
    if (hours != null) return Math.max(hours, 0) / HOURS_PER_FTE_MONTH;
    return 0;
  };
  const rows = filteredDeliverables();
  if (typeof renderMasterQuickstart === "function") {
    renderMasterQuickstart(rows.length);
  }
  const prevFilters = {
    type: state.filters.type || "",
    project: state.filters.project || "",
    sponsor: state.filters.sponsor || "",
    solution: state.filters.solution || "",
    version: state.filters.version || "",
    owner: state.filters.owner || "",
    current_phase: state.filters.current_phase || "",
    priority: state.filters.priority || "",
    due: state.filters.due || "",
    rag: state.filters.rag || "",
    status: state.filters.status || "",
    progress: state.filters.progress || "",
  };
  const esc = (v) =>
    String(v || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  const renderProjectNameLink = (label, projectId) => {
    const text = String(label || "").trim() || "–";
    const targetId = String(projectId || "").trim();
    if (!targetId) return esc(text);
    return `<button type="button" class="deliverables-name-link deliverables-name-link-project" data-action="edit" data-type="project" data-id="${esc(targetId)}">${esc(text)}</button>`;
  };
  const renderSolutionNameLink = (label, solutionId) => {
    const text = String(label || "").trim() || "–";
    const targetId = String(solutionId || "").trim();
    if (!targetId) return esc(text);
    return `<button type="button" class="deliverables-name-link deliverables-name-link-solution" data-action="edit" data-type="solution" data-id="${esc(targetId)}">${esc(text)}</button>`;
  };
  const colgroup = `<colgroup>
      <col class="deliverable-select"><col class="deliverable-type"><col class="deliverable-project"><col class="deliverable-sponsor">
      <col class="deliverable-solution"><col class="deliverable-version"><col class="deliverable-owner">
      <col class="deliverable-phase"><col class="deliverable-priority"><col class="deliverable-due"><col class="deliverable-fte"><col class="deliverable-rag">
      <col class="deliverable-status"><col class="deliverable-progress"><col class="deliverable-actions">
    </colgroup>`;
  let html = `
    <table class="deliverables-table">${colgroup}
      <thead>
        <tr>
          <th></th>
          <th>Type</th>
          <th>Project</th>
          <th>Sponsor</th>
          <th>Solution</th>
          <th>Version</th>
          <th>Owner</th>
          <th>Phase</th>
          <th>Priority</th>
          <th>Due</th>
          <th>FTE-Months</th>
          <th>RAG</th>
          <th>Status</th>
          <th>%</th>
          <th></th>
        </tr>
        <tr class="filter-row">
          <td><input type="checkbox" id="deliverables-select-all" aria-label="Select all deliverables" /></td>
          <td>
            <select id="filter-type">
              <option value="">All</option>
              <option value="project" ${prevFilters.type === "project" ? "selected" : ""}>Project</option>
              <option value="solution" ${prevFilters.type === "solution" ? "selected" : ""}>Solution</option>
            </select>
          </td>
          <td><input class="table-filter" type="text" id="filter-project" placeholder="Project" value="${esc(prevFilters.project)}" /></td>
          <td><input class="table-filter" type="text" id="filter-sponsor" placeholder="Sponsor" value="${esc(prevFilters.sponsor)}" /></td>
          <td><input class="table-filter" type="text" id="filter-solution" placeholder="Solution" value="${esc(prevFilters.solution)}" /></td>
          <td><input class="table-filter" type="text" id="filter-version" placeholder="Version" value="${esc(prevFilters.version)}" /></td>
          <td><input class="table-filter" type="text" id="filter-owner" placeholder="Owner" value="${esc(prevFilters.owner)}" /></td>
          <td><input class="table-filter" type="text" id="filter-current-phase" placeholder="Phase" value="${esc(prevFilters.current_phase)}" /></td>
          <td><input class="table-filter table-filter-priority" type="number" id="filter-priority" min="0" max="5" placeholder="Priority" value="${esc(prevFilters.priority)}" /></td>
          <td><input class="table-filter" type="text" id="filter-due" placeholder="Due" value="${esc(prevFilters.due)}" /></td>
          <td></td>
          <td><input class="table-filter" type="text" id="filter-rag" placeholder="RAG" value="${esc(prevFilters.rag)}" /></td>
          <td><input class="table-filter" type="text" id="filter-status" placeholder="Status" value="${esc(prevFilters.status)}" /></td>
          <td><input class="table-filter" type="number" id="filter-progress" min="0" max="100" placeholder="%" value="${esc(prevFilters.progress)}" /></td>
          <td></td>
        </tr>
      </thead>
      <tbody>`;
  rows.forEach((row) => {
    const isSolution = row.type === "solution";
    const project = row.project;
    const solution = row.solution;
    const itemId = isSolution ? solution.solution_id : project.project_id;
    const key = deliverableKey(row.type, itemId);
    const checked = state.deliverableSelection.has(key) ? "checked" : "";
    const priorityValue = isSolution ? solution.priority : project.priority;
    const statusValue = isSolution ? solution.status : project.status;
    const normalizedRag = isSolution ? String(solution.rag_status || "green").toLowerCase() : "";
    const ragValue = normalizedRag === "red" || normalizedRag === "amber" ? normalizedRag : "green";
    const ragToneClass = `rag-${ragValue}`;
    const ragCell = isSolution
      ? `<select class="inline-select rag-select ${ragToneClass}" data-rag-state="${ragValue}" data-field="rag_status" data-type="solution" data-id="${solution.solution_id}">
          <option value="amber" ${ragValue === "amber" ? "selected" : ""}>Amber</option>
          <option value="red" ${ragValue === "red" ? "selected" : ""}>Red</option>
          <option value="green" ${ragValue === "green" ? "selected" : ""}>Green</option>
        </select>`
      : "—";
    const fteMonthsCell = isSolution ? solutionFteMonths(solution).toFixed(2) : "—";
    const statusCell = `<select class="inline-select" data-field="status" data-type="${row.type}" data-id="${itemId}">
        <option value="not_started" ${statusValue === "not_started" ? "selected" : ""}>Not started</option>
        <option value="active" ${statusValue === "active" ? "selected" : ""}>Active</option>
        <option value="on_hold" ${statusValue === "on_hold" ? "selected" : ""}>On hold</option>
        <option value="complete" ${statusValue === "complete" ? "selected" : ""}>Complete</option>
        <option value="abandoned" ${statusValue === "abandoned" ? "selected" : ""}>Abandoned</option>
      </select>`;
    const deliverableChip = `<button
      type="button"
      class="deliverable-chip-btn"
      data-action="edit"
      data-type="${row.type}"
      data-id="${itemId}"
      title="Open ${row.type === "project" ? "project" : "solution"}"
      aria-label="Open ${row.type === "project" ? "project" : "solution"}"
    ><span class="pill ${row.type === "project" ? "pill-project" : "pill-solution"}">${row.type === "project" ? "Project" : "Solution"}</span></button>`;
    const deliverableActions = `<div class="deliverable-actions">
        <button class="icon-btn" data-action="edit" data-type="${row.type}" data-id="${itemId}" title="Edit">✎</button>
        ${isSolution ? `<button class="icon-btn" data-action="add-subcomponent" data-type="solution" data-id="${solution.solution_id}" title="Add subcomponent">＋</button>` : ""}
      </div>`;
    html += `<tr class="deliverable-row ${isSolution ? "deliverable-row-solution" : "deliverable-row-project"}">
      <td><input type="checkbox" class="deliverable-select" data-type="${row.type}" data-id="${itemId}" ${checked} /></td>
      <td>${deliverableChip}</td>
      <td>${renderProjectNameLink(project?.project_name, project?.project_id)}</td>
      <td>${project?.sponsor || "–"}</td>
      <td>${renderSolutionNameLink(solution?.solution_name, solution?.solution_id)}</td>
      <td>${solution?.version || "–"}</td>
      <td>${solution?.owner || "–"}</td>
      <td>${isSolution ? phaseDisplayName(solution.current_phase) || "–" : "—"}</td>
      <td><input class="inline-input inline-input-priority" type="number" min="0" max="5" data-field="priority" data-type="${row.type}" data-id="${itemId}" value="${priorityValue ?? ""}" /></td>
      <td>${isSolution ? solution.due_date || "" : "—"}</td>
      <td>${fteMonthsCell}</td>
      <td>${ragCell}</td>
      <td>${statusCell}</td>
      <td>${isSolution ? `${solutionProgress(solution)}%` : "—"}</td>
      <td>${deliverableActions}</td>
    </tr>`;
  });
  html += "</tbody></table>";
  els.masterTable.innerHTML = html;

  const setFilterValue = (key, value) => {
    state.filters[key] = value;
    if (typeof persistMasterViewState === "function") persistMasterViewState();
  };
  const filterKeyFromId = (id) => id.replace("filter-", "").replaceAll("-", "_");
  let applyTimer = 0;
  const scheduleApply = () => {
    if (applyTimer) window.clearTimeout(applyTimer);
    applyTimer = window.setTimeout(() => {
      if (typeof persistMasterViewState === "function") persistMasterViewState();
      renderMasterTable(ctx);
      if (typeof renderKanban === "function") renderKanban();
      if (typeof renderCalendar === "function") renderCalendar();
    }, 180);
  };
  [
    "filter-project",
    "filter-sponsor",
    "filter-solution",
    "filter-version",
    "filter-owner",
    "filter-current-phase",
    "filter-priority",
    "filter-due",
    "filter-rag",
    "filter-status",
    "filter-progress",
  ].forEach((id) => {
    const el = els.masterTable.querySelector(`#${id}`);
    if (!el) return;
    const commit = () => {
      setFilterValue(filterKeyFromId(id), el.value);
    };
    const apply = () => {
      commit();
      scheduleApply();
    };
    el.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      commit();
      if (typeof persistMasterViewState === "function") persistMasterViewState();
      renderMasterTable(ctx);
      if (typeof renderKanban === "function") renderKanban();
      if (typeof renderCalendar === "function") renderCalendar();
    });
    el.addEventListener("change", apply);
  });

  const typeSelect = els.masterTable.querySelector("#filter-type");
  if (typeSelect) {
    typeSelect.addEventListener("change", () => {
      setFilterValue("type", typeSelect.value);
      if (typeof persistMasterViewState === "function") persistMasterViewState();
      renderMasterTable(ctx);
      if (typeof renderKanban === "function") renderKanban();
      if (typeof renderCalendar === "function") renderCalendar();
    });
  }

  const selectAll = els.masterTable.querySelector("#deliverables-select-all");
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      const boxes = els.masterTable?.querySelectorAll('input.deliverable-select') || [];
      state.deliverableSelection.clear();
      boxes.forEach((box) => {
        box.checked = selectAll.checked;
        if (selectAll.checked) {
          const type = box.getAttribute("data-type");
          const id = box.getAttribute("data-id");
          if (type && id) state.deliverableSelection.add(deliverableKey(type, id));
        }
      });
      updateBulkSelectionCount();
    });
  }

  updateBulkSelectionCount();
}
