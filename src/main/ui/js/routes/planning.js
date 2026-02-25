const HOURS_PER_FTE_MONTH = 160;
const DRAG_KIND_TASK = "task";
const DRAG_KIND_PERSON = "person";
const UNASSIGNED_TEAM_ID = "__unassigned__";

function currentMonthToken() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const boardState = {
  bound: false,
  ctx: null,
  spaceId: "",
  loaded: false,
  loading: false,
  error: "",
  month: currentMonthToken(),
  search: "",
  effortFilter: "all",
  teamFilter: "all",
  selectedTaskId: "",
  notice: { message: "", tone: "info" },
  undoStack: [],
  data: {
    teams: [],
    people: [],
    tasks: [],
    allocations: [],
  },
};

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numberOr(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function formatFte(value) {
  return numberOr(value, 0).toFixed(2);
}

function toneClass(value, hasCapacity = true) {
  if (!hasCapacity && value > 0) return "over";
  if (value > 1) return "over";
  if (value >= 0.8) return "warn";
  return "ok";
}

async function callApi(ctx, path, options = {}) {
  if (typeof ctx.api === "function") return ctx.api(path, options);
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body,
    credentials: "include",
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message = payload?.detail || response.statusText || "Request failed";
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }
  return payload;
}

function setNotice(message, tone = "info") {
  boardState.notice = { message: String(message || ""), tone };
}

function resetBoardState(spaceId) {
  boardState.spaceId = spaceId || "";
  boardState.loaded = false;
  boardState.loading = false;
  boardState.error = "";
  boardState.month = currentMonthToken();
  boardState.search = "";
  boardState.effortFilter = "all";
  boardState.teamFilter = "all";
  boardState.selectedTaskId = "";
  boardState.notice = { message: "", tone: "info" };
  boardState.undoStack = [];
  boardState.data = {
    teams: [],
    people: [],
    tasks: [],
    allocations: [],
  };
}

function rerender() {
  if (!boardState.ctx) return;
  renderPlanning(boardState.ctx);
}

async function refreshGlobal(ctx, entity) {
  if (typeof ctx.refreshFromServer !== "function") return;
  try {
    await ctx.refreshFromServer(entity);
  } catch {
    // Non-blocking. Board data is refreshed separately.
  }
}

async function loadBoard(ctx, { allocationsOnly = false } = {}) {
  if (boardState.loading) return;
  boardState.loading = true;
  boardState.error = "";
  rerender();
  try {
    const month = boardState.month || currentMonthToken();
    if (allocationsOnly && boardState.loaded) {
      const allocations = await callApi(ctx, `/planning/work-allocation/allocations?month=${encodeURIComponent(month)}`);
      boardState.data.allocations = Array.isArray(allocations) ? allocations : [];
    } else {
      const tasks = await callApi(ctx, "/planning/work-allocation/tasks?month=" + encodeURIComponent(month));
      const [teams, people, allocations] = await Promise.all([
        callApi(ctx, "/planning/work-allocation/teams"),
        callApi(ctx, "/planning/work-allocation/people"),
        callApi(ctx, `/planning/work-allocation/allocations?month=${encodeURIComponent(month)}`),
      ]);
      boardState.data.teams = Array.isArray(teams) ? teams : [];
      boardState.data.people = Array.isArray(people) ? people : [];
      boardState.data.tasks = Array.isArray(tasks) ? tasks : [];
      boardState.data.allocations = Array.isArray(allocations) ? allocations : [];
      boardState.loaded = true;
    }
  } catch (err) {
    boardState.error = err?.message || "Failed to load board data";
    setNotice(boardState.error, "error");
  } finally {
    boardState.loading = false;
    rerender();
  }
}

function allocationsByTask() {
  const map = new Map();
  (boardState.data.allocations || []).forEach((allocation) => {
    if (!allocation?.task_id) return;
    const list = map.get(allocation.task_id) || [];
    list.push(allocation);
    map.set(allocation.task_id, list);
  });
  return map;
}

function allocationToCreatePayload(allocation) {
  return {
    task_id: allocation.task_id,
    assignee_type: allocation.assignee_type,
    assignee_id: allocation.assignee_id,
    month: allocation.month,
    fte_months_allocated: allocation.fte_months_allocated,
  };
}

function sortedTeams() {
  return [...(boardState.data.teams || [])].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
}

function sortedPeople() {
  return [...(boardState.data.people || [])].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
}

function sortedTasks() {
  return [...(boardState.data.tasks || [])].sort((a, b) => (a.title || "").localeCompare(b.title || ""));
}

function applyBacklogFilters(tasks) {
  const search = (boardState.search || "").trim().toLowerCase();
  const effortFilter = boardState.effortFilter || "all";
  return tasks.filter((task) => {
    const title = String(task?.title || "").toLowerCase();
    if (search && !title.includes(search)) return false;
    const effort = numberOr(task?.fte_months, 0);
    if (effortFilter === "small" && effort > 0.25) return false;
    if (effortFilter === "medium" && (effort <= 0.25 || effort > 0.5)) return false;
    if (effortFilter === "large" && effort <= 0.5) return false;
    return true;
  });
}

function normalizeTeamId(value) {
  const token = String(value || "").trim();
  if (!token || token === UNASSIGNED_TEAM_ID) return null;
  return token;
}

function taskChip(task, allocation) {
  const isSelected = boardState.selectedTaskId === task.id;
  const assigned = !!allocation;
  const assignee = allocation?.assignee_name || allocation?.assignee_id || "";
  const allocationId = allocation?.id || "";
  return `<button type="button" class="wab-task-chip${assigned ? " is-assigned" : ""}${isSelected ? " is-selected" : ""}" draggable="true" data-task-id="${esc(task.id)}" data-allocation-id="${esc(allocationId)}" data-assigned="${assigned ? "1" : "0"}">
    <span class="wab-task-chip-title">${esc(task.title)}</span>
    <span class="wab-task-chip-meta">${formatFte(task.fte_months)} FTE-mo${assignee ? ` | ${esc(assignee)}` : ""}</span>
  </button>`;
}

function buildBoardMarkup() {
  const teams = sortedTeams();
  const people = sortedPeople();
  const tasks = sortedTasks();
  const allocationMap = allocationsByTask();
  const assignedTaskIds = new Set(Array.from(allocationMap.keys()));
  const backlogTasks = applyBacklogFilters(tasks.filter((task) => !assignedTaskIds.has(task.id)));

  const totalCapacity = people.reduce((sum, person) => sum + Math.max(numberOr(person.capacity_fte_months, 1), 0), 0);
  const totalAllocated = (boardState.data.allocations || []).reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);

  const teamOptions = [
    '<option value="all">All teams</option>',
    ...teams.map((team) => `<option value="${esc(team.id)}" ${boardState.teamFilter === team.id ? "selected" : ""}>${esc(team.name)}</option>`),
    `<option value="${UNASSIGNED_TEAM_ID}" ${boardState.teamFilter === UNASSIGNED_TEAM_ID ? "selected" : ""}>Unassigned Team</option>`,
  ].join("");

  const allocationList = boardState.data.allocations || [];
  const personAllocationMap = new Map();
  const teamAllocationMap = new Map();
  allocationList.forEach((alloc) => {
    if (alloc.assignee_type === "person") {
      const list = personAllocationMap.get(alloc.assignee_id) || [];
      list.push(alloc);
      personAllocationMap.set(alloc.assignee_id, list);
    } else if (alloc.assignee_type === "team") {
      const list = teamAllocationMap.get(alloc.assignee_id) || [];
      list.push(alloc);
      teamAllocationMap.set(alloc.assignee_id, list);
    }
  });

  const peopleByTeam = new Map();
  people.forEach((person) => {
    const key = person.team_id || UNASSIGNED_TEAM_ID;
    const list = peopleByTeam.get(key) || [];
    list.push(person);
    peopleByTeam.set(key, list);
  });

  const personLoadById = new Map();
  people.forEach((person) => {
    const allocations = personAllocationMap.get(person.id) || [];
    const load = allocations.reduce((sum, item) => sum + numberOr(item.fte_months_allocated, 0), 0);
    personLoadById.set(person.id, load);
  });

  const columns = teams.map((team) => ({ id: team.id, name: team.name, virtual: false }));
  if (!columns.find((col) => col.id === UNASSIGNED_TEAM_ID)) {
    columns.push({ id: UNASSIGNED_TEAM_ID, name: "Unassigned", virtual: true });
  }

  const visibleColumns = columns.filter((col) => boardState.teamFilter === "all" || boardState.teamFilter === col.id);

  const peopleOverCapacity = people.reduce((count, person) => {
    const capacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
    const load = numberOr(personLoadById.get(person.id), 0);
    const ratio = capacity > 0 ? load / capacity : (load > 0 ? 1 : 0);
    return count + (ratio > 1 ? 1 : 0);
  }, 0);

  const teamOverCapacity = columns.reduce((count, column) => {
    if (column.virtual) return count;
    const teamPeople = peopleByTeam.get(column.id) || [];
    const teamCapacity = teamPeople.reduce((sum, person) => sum + Math.max(numberOr(person.capacity_fte_months, 1), 0), 0);
    const teamPersonLoad = teamPeople.reduce((sum, person) => sum + numberOr(personLoadById.get(person.id), 0), 0);
    const teamDirectLoad = (teamAllocationMap.get(column.id) || []).reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
    const teamLoad = teamPersonLoad + teamDirectLoad;
    const ratio = teamCapacity > 0 ? teamLoad / teamCapacity : (teamLoad > 0 ? 1 : 0);
    return count + (ratio > 1 ? 1 : 0);
  }, 0);

  const columnHtml = visibleColumns
    .map((column) => {
      const teamPeople = peopleByTeam.get(column.id) || [];
      const teamCapacity = teamPeople.reduce((sum, p) => sum + Math.max(numberOr(p.capacity_fte_months, 1), 0), 0);
      const teamPersonLoad = teamPeople.reduce((sum, p) => {
        const allocations = personAllocationMap.get(p.id) || [];
        return sum + allocations.reduce((acc, item) => acc + numberOr(item.fte_months_allocated, 0), 0);
      }, 0);
      const teamDirectLoad = (teamAllocationMap.get(column.id) || []).reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
      const teamLoad = teamPersonLoad + teamDirectLoad;
      const teamRatio = teamCapacity > 0 ? teamLoad / teamCapacity : (teamLoad > 0 ? 1 : 0);
      const teamQueueCount = (teamAllocationMap.get(column.id) || []).length;

      const directAssignments = (teamAllocationMap.get(column.id) || [])
        .map((alloc) => taskChip(tasks.find((task) => task.id === alloc.task_id) || { id: alloc.task_id, title: alloc.task_id, fte_months: alloc.fte_months_allocated }, alloc))
        .join("");

      const peopleHtml = teamPeople
        .map((person) => {
          const personCapacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
          const personAllocations = personAllocationMap.get(person.id) || [];
          const personLoad = personAllocations.reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
          const personRatio = personCapacity > 0 ? personLoad / personCapacity : (personLoad > 0 ? 1 : 0);
          const personTasksHtml = personAllocations
            .map((alloc) => {
              const task = tasks.find((item) => item.id === alloc.task_id) || {
                id: alloc.task_id,
                title: alloc.task_id,
                fte_months: alloc.fte_months_allocated,
              };
              return taskChip(task, alloc);
            })
            .join("");

          return `<section class="wab-person-card" draggable="true" data-dropzone="person" data-person-id="${esc(person.id)}" data-person-team-id="${esc(person.team_id || UNASSIGNED_TEAM_ID)}">
            <div class="wab-person-head">
              <div>
                <div class="wab-person-name">${esc(person.name)}</div>
                <div class="wab-person-meta">${personAllocations.length} ${personAllocations.length === 1 ? "task" : "tasks"}</div>
              </div>
              <div class="wab-capacity-text ${toneClass(personRatio, personCapacity > 0)}">${formatFte(personLoad)} / ${formatFte(personCapacity)} FTE-mo</div>
            </div>
            <div class="wab-capacity-bar"><span class="${toneClass(personRatio, personCapacity > 0)}" style="width:${clampPercent(personRatio * 100)}%"></span></div>
            <div class="wab-task-stack">${personTasksHtml || '<p class="muted wab-empty-note">Drop tasks here</p>'}</div>
          </section>`;
        })
        .join("");

      const teamDropLabel = column.virtual ? "Unassigned Bucket" : "Team Assignment";
      const teamDropHelp = column.virtual
        ? "Drop tasks or people anywhere in this column to clear assignment/team mapping"
        : "Drop tasks or people anywhere in this column for team assignment";

      const teamTitleHtml = column.virtual
        ? `<div class="wab-team-name">${esc(column.name)}</div>`
        : `<div class="wab-team-title-row">
            <div class="wab-team-name">${esc(column.name)}</div>
            <button type="button" class="secondary wab-team-delete" data-wab-action="delete-team" data-team-id="${esc(column.id)}" title="Delete team">&times;</button>
          </div>`;

      return `<article class="wab-team-column" data-dropzone="team" data-team-id="${esc(column.id)}">
        <header class="wab-team-head">
          ${teamTitleHtml}
          <div class="wab-team-meta">
            <span>${teamPeople.length} ${teamPeople.length === 1 ? "person" : "people"}</span>
            <span>${teamQueueCount} ${teamQueueCount === 1 ? "team task" : "team tasks"}</span>
          </div>
          <div class="wab-capacity-text ${toneClass(teamRatio, teamCapacity > 0)}">${formatFte(teamLoad)} / ${formatFte(teamCapacity)} FTE-mo</div>
          <div class="wab-capacity-bar"><span class="${toneClass(teamRatio, teamCapacity > 0)}" style="width:${clampPercent(teamRatio * 100)}%"></span></div>
          <p class="muted wab-team-help">Capacity load (team queue + person assignments)</p>
        </header>
        <div class="wab-team-assignment-zone" data-dropzone="team" data-team-id="${esc(column.id)}">
          <div class="wab-team-assignment-title">${esc(teamDropLabel)}</div>
          <p class="muted wab-team-assignment-help">${esc(teamDropHelp)}</p>
        </div>
        <div class="wab-section-head">
          <span>Team Queue</span>
          <span class="wab-section-count">${teamQueueCount}</span>
        </div>
        <div class="wab-team-direct">
          ${directAssignments || '<p class="muted wab-empty-note">No team-level assignments</p>'}
        </div>
        <div class="wab-section-head">
          <span>People</span>
          <span class="wab-section-count">${teamPeople.length}</span>
        </div>
        <div class="wab-people-grid">${peopleHtml || '<p class="muted wab-empty-note">No people in this team</p>'}</div>
      </article>`;
    })
    .join("");

  const selectedTask = tasks.find((task) => task.id === boardState.selectedTaskId) || null;
  const selectedAllocations = selectedTask ? allocationMap.get(selectedTask.id) || [] : [];
  const selectedAssigneeList = selectedAllocations
    .map((alloc) => String(alloc.assignee_name || alloc.assignee_id || "").trim())
    .filter(Boolean);
  const selectedAssigneeLabel = selectedAssigneeList.length
    ? selectedAssigneeList.join(", ")
    : "Backlog";

  const taskModalHtml = selectedTask
    ? `<div class="wab-modal-shell" role="dialog" aria-modal="true" aria-label="Task details">
        <div class="wab-modal-backdrop" data-wab-action="close-task-modal"></div>
        <div class="wab-detail-card wab-modal-card">
          <div class="wab-modal-head">
            <h3>Task Details</h3>
            <button type="button" class="secondary" data-wab-action="close-task-modal">Close</button>
          </div>
        <label class="wide">Title <input type="text" id="wab-detail-title" value="${esc(selectedTask.title)}" /></label>
        <label>FTE-Months <input type="number" id="wab-detail-fte" min="0.05" step="0.05" value="${formatFte(selectedTask.fte_months)}" /></label>
        <p class="muted">Month: <strong>${esc(boardState.month)}</strong></p>
        <p class="muted">Assignees: <strong>${esc(selectedAssigneeLabel)}</strong></p>
        <div class="form-actions">
          <button type="button" data-wab-action="save-task">Save</button>
          <button type="button" class="secondary" data-wab-action="delete-task">Delete</button>
          ${selectedAllocations.length ? '<button type="button" class="secondary" data-wab-action="unassign-task">Unassign All</button>' : ""}
        </div>
      </div>
    </div>`
    : "";

  return `<div class="wab-toolbar">
      <div class="toolbar-group">
        <label class="inline-field">Month
          <input type="month" id="wab-month" value="${esc(boardState.month)}" />
        </label>
        <label class="inline-field">Team
          <select id="wab-team-filter">${teamOptions}</select>
        </label>
        <button type="button" class="secondary wab-mini-icon" data-wab-action="add-team" title="Create team">+</button>
        <button type="button" class="secondary" data-wab-action="refresh">Refresh</button>
        <button type="button" class="secondary" data-wab-action="download-report">Download PDF Report</button>
        <button type="button" class="secondary" data-wab-action="undo" ${boardState.undoStack.length ? "" : "disabled"}>Undo Last Action</button>
      </div>
      <div class="toolbar-group wab-totals">
        <span class="pill muted">Backlog ${backlogTasks.length}</span>
        <span class="pill muted">Assigned ${assignedTaskIds.size}</span>
        <span class="pill muted">Alloc links ${(boardState.data.allocations || []).length}</span>
      </div>
    </div>
    <div class="wab-summary-strip">
      <div class="wab-summary-card">
        <span class="wab-summary-label">Capacity</span>
        <strong>${formatFte(totalAllocated)} / ${formatFte(totalCapacity)} FTE-mo</strong>
        <span class="wab-summary-sub">${totalCapacity > 0 ? clampPercent((totalAllocated / totalCapacity) * 100) : 0}% utilized</span>
      </div>
      <div class="wab-summary-card">
        <span class="wab-summary-label">Visible Columns</span>
        <strong>${visibleColumns.length}</strong>
        <span class="wab-summary-sub">${teamOverCapacity} over capacity</span>
      </div>
      <div class="wab-summary-card">
        <span class="wab-summary-label">People</span>
        <strong>${people.length}</strong>
        <span class="wab-summary-sub">${peopleOverCapacity} over capacity</span>
      </div>
      <div class="wab-summary-card">
        <span class="wab-summary-label">Tasks</span>
        <strong>${tasks.length}</strong>
        <span class="wab-summary-sub">${backlogTasks.length} in backlog</span>
      </div>
    </div>
    <div class="wab-legend">
      <span class="wab-legend-item"><span class="wab-legend-swatch backlog"></span>Backlog: unassigned tasks</span>
      <span class="wab-legend-item"><span class="wab-legend-swatch team"></span>Team Queue: assigned to team</span>
      <span class="wab-legend-item"><span class="wab-legend-swatch person"></span>Person Card: assigned to person</span>
    </div>
    <p class="muted wab-team-model-note">Team columns map to team tags. Use <code>+</code> to create teams, and <code>&times;</code> in a team header to remove one.</p>
    <div class="wab-shell">
      <aside class="wab-backlog" data-dropzone="backlog">
        <div class="wab-panel-head">
          <div class="wab-panel-title-group">
            <h3>Backlog</h3>
            <p class="muted wab-panel-sub">Drop tasks here to unassign. Drop people here to move them to Unassigned.</p>
          </div>
          <label class="inline-field">Filter
            <select id="wab-effort-filter">
              <option value="all" ${boardState.effortFilter === "all" ? "selected" : ""}>All</option>
              <option value="small" ${boardState.effortFilter === "small" ? "selected" : ""}>Small (<= 0.25)</option>
              <option value="medium" ${boardState.effortFilter === "medium" ? "selected" : ""}>Medium (0.26 - 0.50)</option>
              <option value="large" ${boardState.effortFilter === "large" ? "selected" : ""}>Large (> 0.50)</option>
            </select>
          </label>
        </div>
        <label class="wide">Search <input type="text" id="wab-search" value="${esc(boardState.search)}" placeholder="Search backlog tasks" /></label>
        <div class="wab-task-list">${backlogTasks.map((task) => taskChip(task, null)).join("") || '<p class="muted wab-empty-note">No matching backlog tasks.</p>'}</div>
      </aside>
      <section class="wab-board-columns">${columnHtml || '<p class="muted">No teams or people yet. Add a team and person to begin allocation.</p>'}</section>
    </div>
    ${taskModalHtml}`;
}

async function createAssignment(taskId, assigneeType, assigneeId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const task = (boardState.data.tasks || []).find((item) => item.id === taskId);
  if (!task) return;
  const existingSame = (boardState.data.allocations || []).find(
    (item) => item.task_id === taskId && item.assignee_type === assigneeType && item.assignee_id === assigneeId
  );
  if (existingSame) {
    return;
  }
  const payload = {
    task_id: taskId,
    assignee_type: assigneeType,
    assignee_id: assigneeId,
    month: boardState.month,
    fte_months_allocated: numberOr(task.fte_months, 0.25),
  };
  const created = await callApi(ctx, "/planning/work-allocation/allocations", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  boardState.data.allocations.push(created);
  if (pushUndo) {
    boardState.undoStack.push({ kind: "unassign", allocationId: created.id });
  }
  setNotice("Assignee added to task", "success");
  await refreshGlobal(ctx, "allocations");
  rerender();
}

async function unassignAllocation(
  allocationId,
  { pushUndo = true, noticeMessage = "Assignee removed from task", refresh = true, render = true } = {}
) {
  const ctx = boardState.ctx;
  const existing = (boardState.data.allocations || []).find((item) => item.id === allocationId);
  if (!existing) return;
  await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(existing.id)}`, {
    method: "DELETE",
  });
  boardState.data.allocations = (boardState.data.allocations || []).filter((item) => item.id !== existing.id);
  if (pushUndo) {
    boardState.undoStack.push({
      kind: "assign",
      payload: allocationToCreatePayload(existing),
    });
  }
  if (noticeMessage) setNotice(noticeMessage, "success");
  if (refresh) await refreshGlobal(ctx, "allocations");
  if (render) rerender();
}

async function unassignTask(taskId, { pushUndo = true } = {}) {
  const matches = (boardState.data.allocations || []).filter((item) => item.task_id === taskId);
  if (!matches.length) return;
  for (const allocation of matches) {
    await unassignAllocation(allocation.id, { pushUndo, noticeMessage: "", refresh: false, render: false });
  }
  await refreshGlobal(boardState.ctx, "allocations");
  setNotice(matches.length > 1 ? "Task unassigned from all assignees" : "Task moved back to backlog", "success");
  rerender();
}

async function movePersonToTeam(personId, teamId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const person = (boardState.data.people || []).find((item) => item.id === personId);
  if (!person) return;

  const previousTeamId = person.team_id || UNASSIGNED_TEAM_ID;
  const nextTeamId = normalizeTeamId(teamId);
  const nextTeamToken = nextTeamId || UNASSIGNED_TEAM_ID;
  if (previousTeamId === nextTeamToken) return;

  const updated = await callApi(ctx, `/planning/work-allocation/people/${encodeURIComponent(personId)}`, {
    method: "PATCH",
    body: JSON.stringify({ team_id: nextTeamId }),
  });

  boardState.data.people = (boardState.data.people || []).map((row) => (row.id === personId ? updated : row));
  if (pushUndo) {
    boardState.undoStack.push({
      kind: "move-person",
      personId,
      teamId: previousTeamId,
    });
  }
  setNotice("Person moved to team", "success");
  await refreshGlobal(ctx, "users");
  rerender();
}

async function performUndo() {
  const ctx = boardState.ctx;
  const next = boardState.undoStack.pop();
  if (!next) return;
  try {
    if (next.kind === "unassign") {
      await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(next.allocationId)}`, { method: "DELETE" });
    } else if (next.kind === "assign") {
      await callApi(ctx, "/planning/work-allocation/allocations", {
        method: "POST",
        body: JSON.stringify(next.payload),
      });
    } else if (next.kind === "delete-task") {
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(next.taskId)}`, { method: "DELETE" });
    } else if (next.kind === "restore-assignment") {
      const current = (boardState.data.allocations || []).find((row) => row.task_id === next.taskId);
      if (current) {
        await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(current.id)}`, { method: "DELETE" });
      }
      await callApi(ctx, "/planning/work-allocation/allocations", {
        method: "POST",
        body: JSON.stringify(next.payload),
      });
    } else if (next.kind === "move-person") {
      await callApi(ctx, `/planning/work-allocation/people/${encodeURIComponent(next.personId)}`, {
        method: "PATCH",
        body: JSON.stringify({ team_id: normalizeTeamId(next.teamId) }),
      });
    }
    setNotice("Undo applied", "success");
    await loadBoard(ctx, { allocationsOnly: false });
    await refreshGlobal(ctx, "all");
  } catch (err) {
    setNotice(`Undo failed: ${err?.message || err}`, "error");
    rerender();
  }
}

async function onAction(action, actionEl = null) {
  const ctx = boardState.ctx;
  const root = ctx.els?.planningBoard;
  if (!root) return;

  try {
    if (action === "refresh") {
      await loadBoard(ctx, { allocationsOnly: false });
      return;
    }
    if (action === "download-report") {
      const month = boardState.month || currentMonthToken();
      const headers = {};
      const activeSpaceId = ctx?.state?.activeSpace?.space_id || "";
      if (activeSpaceId) headers["X-Space-Id"] = activeSpaceId;
      const response = await fetch(
        `/api/planning/work-allocation/report.pdf?month=${encodeURIComponent(month)}`,
        {
          method: "GET",
          headers,
          credentials: "include",
        }
      );
      if (!response.ok) {
        const text = await response.text();
        let message = `Download failed (${response.status})`;
        try {
          const payload = text ? JSON.parse(text) : null;
          if (payload?.detail) message = String(payload.detail);
          else if (text) message = text;
        } catch {
          if (text) message = text;
        }
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `work-allocation-report-${month}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      setNotice("Report downloaded", "success");
      rerender();
      return;
    }
    if (action === "close-task-modal") {
      boardState.selectedTaskId = "";
      rerender();
      return;
    }
    if (action === "undo") {
      await performUndo();
      return;
    }
    if (action === "add-team") {
      const name = String(window.prompt("New team name") || "").trim();
      if (!name) {
        setNotice("Team creation cancelled", "warn");
        rerender();
        return;
      }
      await callApi(ctx, "/planning/work-allocation/teams", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setNotice("Team added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "teams");
      return;
    }
    if (action === "delete-team") {
      const teamId = String(actionEl?.getAttribute("data-team-id") || "").trim();
      if (!teamId || teamId === UNASSIGNED_TEAM_ID) return;
      const team = (boardState.data.teams || []).find((row) => row.id === teamId);
      if (!team) {
        setNotice("Team not found", "warn");
        rerender();
        return;
      }
      const teamPeopleCount = (boardState.data.people || []).filter((p) => p.team_id === teamId).length;
      const teamAllocations = (boardState.data.allocations || []).filter((a) => a.assignee_type === "team" && a.assignee_id === teamId);
      const confirmMessage = [
        `Delete team "${team.name}"?`,
        `${teamPeopleCount} people will move to Unassigned.`,
        teamAllocations.length ? `${teamAllocations.length} team-level assignments will be moved back to Backlog.` : "No team-level assignments to move.",
      ].join("\n");
      if (!window.confirm(confirmMessage)) return;

      for (const alloc of teamAllocations) {
        await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(alloc.id)}`, {
          method: "DELETE",
        });
      }
      await callApi(ctx, `/planning/work-allocation/teams/${encodeURIComponent(teamId)}`, {
        method: "DELETE",
      });
      setNotice("Team deleted", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "teams");
      await refreshGlobal(ctx, "users");
      await refreshGlobal(ctx, "allocations");
      return;
    }
    if (action === "add-person") {
      const nameEl = root.querySelector("#wab-new-person-name");
      const teamEl = root.querySelector("#wab-new-person-team");
      const capEl = root.querySelector("#wab-new-person-capacity");
      const name = String(nameEl?.value || "").trim();
      if (!name) {
        setNotice("Person name is required", "warn");
        rerender();
        return;
      }
      const teamId = String(teamEl?.value || "").trim() || null;
      const cap = Math.max(numberOr(capEl?.value, 1), 0.1);
      await callApi(ctx, "/planning/work-allocation/people", {
        method: "POST",
        body: JSON.stringify({ name, team_id: teamId, capacity_fte_months: cap }),
      });
      if (nameEl) nameEl.value = "";
      if (capEl) capEl.value = "1.00";
      if (teamEl) teamEl.value = "";
      setNotice("Person added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "users");
      return;
    }
    if (action === "add-task") {
      const titleEl = root.querySelector("#wab-new-task-title");
      const fteEl = root.querySelector("#wab-new-task-fte");
      const title = String(titleEl?.value || "").trim();
      if (!title) {
        setNotice("Task title is required", "warn");
        rerender();
        return;
      }
      const fte = Math.max(numberOr(fteEl?.value, 0.25), 0.05);
      const created = await callApi(ctx, "/planning/work-allocation/tasks?month=" + encodeURIComponent(boardState.month), {
        method: "POST",
        body: JSON.stringify({ title, fte_months: fte }),
      });
      boardState.selectedTaskId = created.id;
      boardState.undoStack.push({ kind: "delete-task", taskId: created.id });
      if (titleEl) titleEl.value = "";
      if (fteEl) fteEl.value = "0.25";
      setNotice("Task added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "save-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      const titleEl = root.querySelector("#wab-detail-title");
      const fteEl = root.querySelector("#wab-detail-fte");
      const title = String(titleEl?.value || "").trim();
      const fte = Math.max(numberOr(fteEl?.value, 0.25), 0.05);
      if (!title) {
        setNotice("Task title is required", "warn");
        rerender();
        return;
      }
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(selectedId)}?month=${encodeURIComponent(boardState.month)}`, {
        method: "PATCH",
        body: JSON.stringify({ title, fte_months: fte }),
      });
      setNotice("Task updated", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "delete-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      if (!window.confirm("Delete this task?")) return;
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(selectedId)}`, {
        method: "DELETE",
      });
      boardState.selectedTaskId = "";
      setNotice("Task deleted", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "unassign-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      await unassignTask(selectedId, { pushUndo: true });
      return;
    }
  } catch (err) {
    setNotice(err?.message || "Action failed", "error");
    rerender();
  }
}

function getDropzone(eventTarget) {
  if (!eventTarget?.closest) return null;
  const zone = eventTarget.closest("[data-dropzone]");
  if (!zone) return null;
  return {
    el: zone,
    type: zone.getAttribute("data-dropzone") || "",
    personId: zone.getAttribute("data-person-id") || "",
    teamId: zone.getAttribute("data-team-id") || "",
  };
}

function plainDragData(dataTransfer) {
  return String(dataTransfer?.getData("text/plain") || "").trim();
}

function dragKindFromDataTransfer(dataTransfer) {
  const kind = String(dataTransfer?.getData("application/x-wab-kind") || "").trim();
  if (kind === DRAG_KIND_PERSON) return DRAG_KIND_PERSON;
  if (kind === DRAG_KIND_TASK) return DRAG_KIND_TASK;
  if (String(dataTransfer?.getData("application/x-wab-person-id") || "").trim()) return DRAG_KIND_PERSON;
  if (String(dataTransfer?.getData("application/x-wab-task-id") || "").trim()) return DRAG_KIND_TASK;
  const plain = plainDragData(dataTransfer);
  if (plain.startsWith("person:")) return DRAG_KIND_PERSON;
  if (plain.startsWith("task:")) return DRAG_KIND_TASK;
  if (plain) return DRAG_KIND_TASK;
  return DRAG_KIND_TASK;
}

function personIdFromDataTransfer(dataTransfer) {
  const explicit = String(dataTransfer?.getData("application/x-wab-person-id") || "").trim();
  if (explicit) return explicit;
  const plain = plainDragData(dataTransfer);
  if (plain.startsWith("person:")) return plain.slice("person:".length).trim();
  return "";
}

function taskIdFromDataTransfer(dataTransfer) {
  const explicit = String(dataTransfer?.getData("application/x-wab-task-id") || "").trim();
  if (explicit) return explicit;
  const plain = plainDragData(dataTransfer);
  if (!plain) return "";
  if (plain.startsWith("task:")) return plain.slice("task:".length).trim();
  if (plain.startsWith("person:")) return "";
  return plain;
}

function allocationIdFromDataTransfer(dataTransfer) {
  const explicit = String(dataTransfer?.getData("application/x-wab-allocation-id") || "").trim();
  return explicit || "";
}

function canDropOnZone(zone, dragKind) {
  if (!zone) return false;
  if (dragKind === DRAG_KIND_PERSON) {
    return zone.type === "team" || zone.type === "person" || zone.type === "backlog";
  }
  if (zone.type === "backlog" || zone.type === "person") return true;
  if (zone.type === "team") {
    return !!zone.teamId;
  }
  return false;
}

function clearDropTargets() {
  const root = boardState.ctx?.els?.planningBoard;
  if (!root) return;
  root.querySelectorAll(".is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
}

function bindBoardEvents() {
  const root = boardState.ctx?.els?.planningBoard;
  if (!root || boardState.bound) return;
  boardState.bound = true;

  root.addEventListener("click", async (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-wab-action]");
    if (actionEl) {
      event.preventDefault();
      const action = actionEl.getAttribute("data-wab-action") || "";
      await onAction(action, actionEl);
      return;
    }
    const chip = event.target.closest(".wab-task-chip");
    if (chip) {
      boardState.selectedTaskId = chip.getAttribute("data-task-id") || "";
      rerender();
    }
  });

  root.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "wab-search") {
      boardState.search = target.value || "";
      rerender();
      return;
    }
    if (target.id === "wab-effort-filter") {
      boardState.effortFilter = target.value || "all";
      rerender();
    }
  });

  root.addEventListener("change", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "wab-month") {
      const value = String(target.value || "").trim();
      if (!/^\d{4}-\d{2}$/.test(value)) return;
      boardState.month = value;
      await loadBoard(boardState.ctx, { allocationsOnly: true });
      return;
    }
    if (target.id === "wab-team-filter") {
      boardState.teamFilter = target.value || "all";
      rerender();
      return;
    }
    if (target.id === "wab-effort-filter") {
      boardState.effortFilter = target.value || "all";
      rerender();
    }
  });

  root.addEventListener("dragstart", (event) => {
    if (!(event.target instanceof Element)) return;
    const chip = event.target.closest(".wab-task-chip");
    if (chip && event.dataTransfer) {
      const taskId = chip.getAttribute("data-task-id") || "";
      const allocationId = chip.getAttribute("data-allocation-id") || "";
      event.dataTransfer.setData("application/x-wab-kind", DRAG_KIND_TASK);
      event.dataTransfer.setData("text/plain", `task:${taskId}`);
      event.dataTransfer.setData("application/x-wab-task-id", taskId);
      event.dataTransfer.setData("application/x-wab-allocation-id", allocationId);
      event.dataTransfer.setData("application/x-wab-assigned", chip.getAttribute("data-assigned") || "0");
      event.dataTransfer.effectAllowed = "move";
      return;
    }
    const personCard = event.target.closest(".wab-person-card[data-person-id]");
    if (personCard && event.dataTransfer) {
      const personId = personCard.getAttribute("data-person-id") || "";
      if (!personId) return;
      event.dataTransfer.setData("application/x-wab-kind", DRAG_KIND_PERSON);
      event.dataTransfer.setData("application/x-wab-person-id", personId);
      event.dataTransfer.setData("text/plain", `person:${personId}`);
      event.dataTransfer.effectAllowed = "move";
    }
  });

  root.addEventListener("dragover", (event) => {
    if (!(event.target instanceof Element)) return;
    const zone = getDropzone(event.target);
    if (!zone) return;
    const dragKind = dragKindFromDataTransfer(event.dataTransfer);
    if (!canDropOnZone(zone, dragKind)) return;
    event.preventDefault();
    clearDropTargets();
    zone.el.classList.add("is-drop-target");
  });

  root.addEventListener("dragleave", (event) => {
    if (!(event.target instanceof Element)) return;
    const zone = getDropzone(event.target);
    if (!zone) return;
    zone.el.classList.remove("is-drop-target");
  });

  root.addEventListener("drop", async (event) => {
    if (!(event.target instanceof Element)) return;
    const zone = getDropzone(event.target);
    if (!zone) return;
    const dragKind = dragKindFromDataTransfer(event.dataTransfer);
    if (!canDropOnZone(zone, dragKind)) return;
    event.preventDefault();
    clearDropTargets();
    try {
      if (dragKind === DRAG_KIND_PERSON) {
        const personId = personIdFromDataTransfer(event.dataTransfer);
        if (!personId) return;
        if (zone.type === "backlog") {
          await movePersonToTeam(personId, UNASSIGNED_TEAM_ID, { pushUndo: true });
          return;
        }
        if (zone.type === "person") {
          const targetTeamId = zone.el.getAttribute("data-person-team-id") || UNASSIGNED_TEAM_ID;
          await movePersonToTeam(personId, targetTeamId, { pushUndo: true });
          return;
        }
        if (zone.type !== "team") return;
        await movePersonToTeam(personId, zone.teamId, { pushUndo: true });
        return;
      }
      const taskId = taskIdFromDataTransfer(event.dataTransfer);
      if (!taskId) return;
      if (zone.type === "backlog") {
        const allocationId = allocationIdFromDataTransfer(event.dataTransfer);
        if (allocationId) {
          await unassignAllocation(allocationId, { pushUndo: true, noticeMessage: "Assignee removed from task" });
        } else {
          await unassignTask(taskId, { pushUndo: true });
        }
        return;
      }
      if (zone.type === "person" && zone.personId) {
        await createAssignment(taskId, "person", zone.personId, { pushUndo: true });
        return;
      }
      if (zone.type === "team" && zone.teamId) {
        if (zone.teamId === UNASSIGNED_TEAM_ID) {
          const allocationId = allocationIdFromDataTransfer(event.dataTransfer);
          if (allocationId) {
            await unassignAllocation(allocationId, { pushUndo: true, noticeMessage: "Assignee removed from task" });
          } else {
            await unassignTask(taskId, { pushUndo: true });
          }
          return;
        }
        await createAssignment(taskId, "team", zone.teamId, { pushUndo: true });
      }
    } catch (err) {
      setNotice(err?.message || "Drop failed", "error");
      rerender();
    }
  });

  root.addEventListener("dragend", () => {
    clearDropTargets();
  });
}

export function renderPlanning(ctx) {
  boardState.ctx = ctx;
  const root = ctx.els?.planningBoard;
  if (!root) return;

  const nextSpaceId = ctx.state?.activeSpace?.space_id || "";
  if (nextSpaceId !== boardState.spaceId) {
    resetBoardState(nextSpaceId);
  }

  bindBoardEvents();

  if (!boardState.loaded && !boardState.loading) {
    void loadBoard(ctx, { allocationsOnly: false });
  }

  const notice = boardState.notice?.message
    ? `<div class="wab-notice ${boardState.notice.tone === "error" ? "error" : boardState.notice.tone === "warn" ? "warn" : "success"}">${esc(boardState.notice.message)}</div>`
    : "";

  const loading = boardState.loading ? '<p class="muted">Loading work allocation board...</p>' : "";
  const error = boardState.error ? `<p class="muted">${esc(boardState.error)}</p>` : "";

  root.innerHTML = `${notice}${loading}${error}${buildBoardMarkup()}`;
}
