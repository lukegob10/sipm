const HOURS_PER_FTE_MONTH = 160;
const DRAG_KIND_TASK = "task";
const DRAG_KIND_PERSON = "person";
const UNASSIGNED_TEAM_ID = "__unassigned__";
const STORAGE_KEY_PREFIX = "sipm-planning-ui-v1";
const FLASH_DURATION_MS = 2200;

function currentMonthToken() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function defaultBoardData() {
  return {
    teams: [],
    people: [],
    tasks: [],
    allocations: [],
  };
}

function defaultDrafts() {
  return {
    teamName: "",
    personName: "",
    personTeamId: "",
    personCapacity: "1.00",
    taskTitle: "",
    taskFte: "0.25",
  };
}

function defaultDetailDraft() {
  return {
    taskId: "",
    title: "",
    fte: "0.25",
    assignmentTarget: "",
  };
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
  personSearch: "",
  effortFilter: "all",
  teamFilter: "all",
  selectedTaskId: "",
  notice: { message: "", tone: "info" },
  undoStack: [],
  flashItems: [],
  flashTimer: 0,
  focusReturnTaskId: "",
  drafts: defaultDrafts(),
  detailDraft: defaultDetailDraft(),
  data: defaultBoardData(),
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

function storageKey(spaceId) {
  const scope = String(spaceId || "no-space").trim().toLowerCase() || "no-space";
  return `${STORAGE_KEY_PREFIX}:${scope}`;
}

function readStoredState(spaceId) {
  try {
    const raw = window.localStorage.getItem(storageKey(spaceId));
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistViewState() {
  try {
    window.localStorage.setItem(
      storageKey(boardState.spaceId),
      JSON.stringify({
        month: boardState.month || currentMonthToken(),
        teamFilter: boardState.teamFilter || "all",
        effortFilter: boardState.effortFilter || "all",
        search: boardState.search || "",
        selectedTaskId: boardState.selectedTaskId || "",
      })
    );
  } catch {
    // Ignore persistence failures.
  }
}

function restoreViewState(spaceId) {
  const stored = readStoredState(spaceId);
  boardState.month = /^\d{4}-\d{2}$/.test(String(stored.month || "")) ? String(stored.month) : currentMonthToken();
  boardState.teamFilter = String(stored.teamFilter || "all");
  boardState.effortFilter = String(stored.effortFilter || "all");
  boardState.search = String(stored.search || "");
  boardState.selectedTaskId = String(stored.selectedTaskId || "");
}

function clearFlashItems() {
  boardState.flashItems = [];
  if (boardState.flashTimer) {
    window.clearTimeout(boardState.flashTimer);
    boardState.flashTimer = 0;
  }
}

function flashTargets(items, tone = "success", duration = FLASH_DURATION_MS) {
  const normalized = (Array.isArray(items) ? items : [])
    .filter((item) => item && item.kind && item.id)
    .map((item) => ({
      kind: String(item.kind),
      id: String(item.id),
      tone: item.tone || tone,
    }));
  clearFlashItems();
  boardState.flashItems = normalized;
  if (!normalized.length) return;
  boardState.flashTimer = window.setTimeout(() => {
    boardState.flashItems = [];
    boardState.flashTimer = 0;
    rerender();
  }, duration);
}

function flashClass(kind, id) {
  const match = (boardState.flashItems || []).find((item) => item.kind === kind && item.id === String(id));
  if (!match) return "";
  return ` wab-flash wab-flash-${match.tone || "success"}`;
}

function setNotice(message, tone = "info") {
  boardState.notice = { message: String(message || ""), tone };
}

function resetBoardState(spaceId) {
  boardState.spaceId = spaceId || "";
  boardState.loaded = false;
  boardState.loading = false;
  boardState.error = "";
  boardState.personSearch = "";
  boardState.notice = { message: "", tone: "info" };
  boardState.undoStack = [];
  boardState.focusReturnTaskId = "";
  boardState.drafts = defaultDrafts();
  boardState.detailDraft = defaultDetailDraft();
  boardState.data = defaultBoardData();
  clearFlashItems();
  restoreViewState(spaceId);
}

function rerender() {
  if (!boardState.ctx) return;
  renderPlanning(boardState.ctx);
}

function selectedTask() {
  return (boardState.data.tasks || []).find((task) => task.id === boardState.selectedTaskId) || null;
}

function syncDetailDraft(task = selectedTask()) {
  if (!task) {
    boardState.detailDraft = defaultDetailDraft();
    return;
  }
  boardState.detailDraft = {
    taskId: task.id,
    title: task.title || "",
    fte: formatFte(task.fte_months),
    assignmentTarget: boardState.detailDraft.taskId === task.id ? (boardState.detailDraft.assignmentTarget || "") : "",
  };
}

function restoreTaskFocusSoon(taskId = boardState.focusReturnTaskId) {
  if (!taskId) return;
  window.requestAnimationFrame(() => {
    const root = boardState.ctx?.els?.planningBoard;
    if (!root) return;
    const target = Array.from(root.querySelectorAll(".wab-task-chip")).find(
      (node) => node.getAttribute("data-task-id") === taskId
    );
    if (!target || typeof target.focus !== "function") return;
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  });
}

function selectTask(taskId, { focusReturnTaskId = taskId } = {}) {
  boardState.selectedTaskId = String(taskId || "");
  boardState.focusReturnTaskId = String(focusReturnTaskId || boardState.focusReturnTaskId || "");
  syncDetailDraft();
  persistViewState();
  rerender();
}

function closeTaskDetail({ restoreFocus = true } = {}) {
  if (!boardState.selectedTaskId) return;
  const focusTargetId = restoreFocus ? (boardState.focusReturnTaskId || boardState.selectedTaskId) : "";
  boardState.selectedTaskId = "";
  boardState.detailDraft = defaultDetailDraft();
  persistViewState();
  rerender();
  if (focusTargetId) restoreTaskFocusSoon(focusTargetId);
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
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && payload.detail) ||
      (typeof payload === "string" && payload) ||
      response.statusText ||
      "Request failed";
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }
  return payload;
}

async function confirmAction(options = {}) {
  const ctx = boardState.ctx;
  if (typeof ctx?.showConfirmModal === "function") {
    return !!(await ctx.showConfirmModal(options));
  }
  setNotice(options.message || options.title || "Confirmation is unavailable right now.", "warn");
  rerender();
  return false;
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
      const [tasks, allocations] = await Promise.all([
        callApi(ctx, `/planning/work-allocation/tasks?month=${encodeURIComponent(month)}`),
        callApi(ctx, `/planning/work-allocation/allocations?month=${encodeURIComponent(month)}`),
      ]);
      boardState.data.tasks = Array.isArray(tasks) ? tasks : [];
      boardState.data.allocations = Array.isArray(allocations) ? allocations : [];
    } else {
      const [tasks, teams, people, allocations] = await Promise.all([
        callApi(ctx, `/planning/work-allocation/tasks?month=${encodeURIComponent(month)}`),
        callApi(ctx, "/planning/work-allocation/teams"),
        callApi(ctx, "/planning/work-allocation/people"),
        callApi(ctx, `/planning/work-allocation/allocations?month=${encodeURIComponent(month)}`),
      ]);
      boardState.data.teams = Array.isArray(teams) ? teams : [];
      boardState.data.people = Array.isArray(people) ? people : [];
      boardState.data.tasks = Array.isArray(tasks) ? tasks : [];
      boardState.data.allocations = Array.isArray(allocations) ? allocations : [];
    }
    boardState.loaded = true;
    const nextSelectedTask = selectedTask();
    if (!nextSelectedTask) {
      boardState.selectedTaskId = "";
      boardState.detailDraft = defaultDetailDraft();
    } else {
      syncDetailDraft(nextSelectedTask);
    }
    persistViewState();
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

function matchesPersonSearch(person) {
  const query = String(boardState.personSearch || "").trim().toLowerCase();
  if (!query) return true;
  return String(person?.name || "").toLowerCase().includes(query) || String(person?.id || "").toLowerCase().includes(query);
}

function applyBacklogFilters(tasks) {
  const search = String(boardState.search || "").trim().toLowerCase();
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

function parseAssignmentTarget(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  if (raw === "backlog") return { type: "backlog", id: "" };
  const [kind, ...rest] = raw.split(":");
  const id = rest.join(":").trim();
  if (!id) return null;
  if (kind === "team" || kind === "person") return { type: kind, id };
  return null;
}

function assignmentOptionsHtml(teams, people, selectedValue = "") {
  const teamOptions = teams
    .map((team) => {
      const value = `team:${team.id}`;
      return `<option value="team:${esc(team.id)}" ${selectedValue === value ? "selected" : ""}>${esc(team.name)}</option>`;
    })
    .join("");
  const personOptions = people
    .map((person) => {
      const team = teams.find((teamRow) => teamRow.id === person.team_id);
      const suffix = team?.name ? ` (${team.name})` : "";
      const value = `person:${person.id}`;
      return `<option value="person:${esc(person.id)}" ${selectedValue === value ? "selected" : ""}>${esc(person.name)}${esc(suffix)}</option>`;
    })
    .join("");
  return [
    `<option value="" ${selectedValue ? "" : "selected"}>Choose assignee</option>`,
    teamOptions ? `<optgroup label="Teams">${teamOptions}</optgroup>` : "",
    personOptions ? `<optgroup label="People">${personOptions}</optgroup>` : "",
  ].join("");
}

function taskChip(task, allocation) {
  const isSelected = boardState.selectedTaskId === task.id;
  const assigned = !!allocation;
  const assignee = allocation?.assignee_name || allocation?.assignee_id || "";
  const allocationId = allocation?.id || "";
  return `<button
    type="button"
    class="wab-task-chip${assigned ? " is-assigned" : ""}${isSelected ? " is-selected" : ""}${flashClass("task", task.id)}"
    draggable="true"
    data-task-id="${esc(task.id)}"
    data-allocation-id="${esc(allocationId)}"
    data-assigned="${assigned ? "1" : "0"}"
    aria-pressed="${isSelected ? "true" : "false"}"
  >
    <span class="wab-task-chip-title">${esc(task.title)}</span>
    <span class="wab-task-chip-meta">${formatFte(task.fte_months)} FTE-mo${assignee ? ` | ${esc(assignee)}` : ""}</span>
  </button>`;
}

function buildDetailPanelHtml(task, allocations, teams, people) {
  if (!task) {
    return `<aside class="wab-detail-panel">
      <div class="wab-detail-placeholder">
        <h3>Task Detail</h3>
        <p class="muted">Select a task to review assignment, capacity impact, and save changes.</p>
        <p class="muted wab-keyboard-hint">Keyboard: focus a task and press Enter or Space. Press Escape to close the detail panel.</p>
      </div>
    </aside>`;
  }

  const assignmentOptions = assignmentOptionsHtml(teams, people, boardState.detailDraft.assignmentTarget || "");
  const assigneeSummary = allocations.length
    ? allocations.map((allocation) => allocation.assignee_name || allocation.assignee_id || "").filter(Boolean).join(", ")
    : "Backlog";
  const allocationRows = allocations.length
    ? allocations
        .map((allocation) => {
          const toneClassName = flashClass(allocation.assignee_type, allocation.assignee_id);
          const label = allocation.assignee_name || allocation.assignee_id || "Unknown";
          const kindLabel = allocation.assignee_type === "team" ? "Team Queue" : "Person";
          return `<div class="wab-assignee-row${toneClassName}">
            <div class="wab-assignee-copy">
              <strong>${esc(label)}</strong>
              <span class="muted">${kindLabel} | ${formatFte(allocation.fte_months_allocated)} FTE-mo</span>
            </div>
            <button type="button" class="secondary" data-wab-action="remove-assignment" data-allocation-id="${esc(allocation.id)}">Remove</button>
          </div>`;
        })
        .join("")
    : '<p class="muted wab-empty-note">No assignees yet. Use the selector below or drag this task onto a team or person.</p>';

  return `<button type="button" class="wab-detail-backdrop" data-wab-action="close-task-detail" aria-label="Close task detail"></button>
    <aside class="wab-detail-panel wab-detail-panel-open" role="dialog" aria-modal="true" aria-label="Task detail">
      <div class="wab-detail-head">
        <div>
          <h3>Task Detail</h3>
          <p class="muted wab-detail-sub">Month ${esc(boardState.month)} | ${formatFte(task.fte_months)} FTE-mo</p>
        </div>
        <button type="button" class="secondary" data-wab-action="close-task-detail">Close</button>
      </div>
      <label class="wide">Title
        <input type="text" id="wab-detail-title" value="${esc(boardState.detailDraft.title || task.title)}" />
      </label>
      <label>FTE-Months
        <input type="number" id="wab-detail-fte" min="0.05" step="0.05" value="${esc(boardState.detailDraft.fte || formatFte(task.fte_months))}" />
      </label>
      <div class="wab-detail-summary">
        <div>
          <span class="wab-detail-label">Current Assignees</span>
          <strong>${esc(assigneeSummary)}</strong>
        </div>
        <div>
          <span class="wab-detail-label">Task ID</span>
          <strong>${esc(task.id)}</strong>
        </div>
      </div>
      <div class="wab-detail-section">
        <div class="wab-detail-section-head">
          <h4>Assign / Unassign</h4>
          <span class="muted">Drag and drop still works, but it is optional now.</span>
        </div>
        <div class="wab-detail-assign-row">
          <label class="wide">Assign To
            <select id="wab-detail-assignee-target">${assignmentOptions}</select>
          </label>
          <button type="button" data-wab-action="assign-task">Assign</button>
          <button type="button" class="secondary" data-wab-action="unassign-task"${allocations.length ? "" : " disabled"}>Backlog</button>
        </div>
        <div class="wab-assignee-list">${allocationRows}</div>
      </div>
      <div class="form-actions wab-detail-actions">
        <button type="button" data-wab-action="save-task">Save</button>
        <button type="button" class="secondary" data-wab-action="delete-task">Delete</button>
      </div>
    </aside>`;
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
  const selected = selectedTask();
  const selectedAllocations = selected ? allocationMap.get(selected.id) || [] : [];
  const selectedAssigneeSummary = selectedAllocations.length
    ? selectedAllocations.map((alloc) => alloc.assignee_name || alloc.assignee_id || "").filter(Boolean).join(", ")
    : "Backlog";

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
  if (!columns.find((column) => column.id === UNASSIGNED_TEAM_ID)) {
    columns.push({ id: UNASSIGNED_TEAM_ID, name: "Unassigned", virtual: true });
  }
  const visibleColumns = columns.filter((column) => boardState.teamFilter === "all" || boardState.teamFilter === column.id);

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
      const visiblePeople = teamPeople.filter(matchesPersonSearch);
      const teamCapacity = teamPeople.reduce((sum, person) => sum + Math.max(numberOr(person.capacity_fte_months, 1), 0), 0);
      const teamPersonLoad = teamPeople.reduce((sum, person) => {
        const allocations = personAllocationMap.get(person.id) || [];
        return sum + allocations.reduce((acc, item) => acc + numberOr(item.fte_months_allocated, 0), 0);
      }, 0);
      const teamDirectLoad = (teamAllocationMap.get(column.id) || []).reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
      const teamLoad = teamPersonLoad + teamDirectLoad;
      const teamRatio = teamCapacity > 0 ? teamLoad / teamCapacity : (teamLoad > 0 ? 1 : 0);
      const teamQueueCount = (teamAllocationMap.get(column.id) || []).length;

      const directAssignments = (teamAllocationMap.get(column.id) || [])
        .map((alloc) => {
          const task = tasks.find((row) => row.id === alloc.task_id) || {
            id: alloc.task_id,
            title: alloc.task_id,
            fte_months: alloc.fte_months_allocated,
          };
          return taskChip(task, alloc);
        })
        .join("");

      const peopleHtml = visiblePeople
        .map((person) => {
          const personCapacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
          const personAllocations = personAllocationMap.get(person.id) || [];
          const personLoad = personAllocations.reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
          const personRatio = personCapacity > 0 ? personLoad / personCapacity : (personLoad > 0 ? 1 : 0);
          const personTasksHtml = personAllocations
            .map((alloc) => {
              const task = tasks.find((row) => row.id === alloc.task_id) || {
                id: alloc.task_id,
                title: alloc.task_id,
                fte_months: alloc.fte_months_allocated,
              };
              return taskChip(task, alloc);
            })
            .join("");

          return `<section
            class="wab-person-card${flashClass("person", person.id)}"
            draggable="true"
            data-dropzone="person"
            data-person-id="${esc(person.id)}"
            data-person-team-id="${esc(person.team_id || UNASSIGNED_TEAM_ID)}"
            data-assign-target="person:${esc(person.id)}"
            tabindex="0"
            role="button"
            aria-label="Assign selected task to ${esc(person.name)}"
          >
            <div class="wab-person-head">
              <div>
                <div class="wab-person-name">${esc(person.name)}</div>
                <div class="wab-person-meta">${personAllocations.length} ${personAllocations.length === 1 ? "task" : "tasks"}</div>
              </div>
              <div class="wab-capacity-text ${toneClass(personRatio, personCapacity > 0)}">${formatFte(personLoad)} / ${formatFte(personCapacity)} FTE-mo</div>
            </div>
            <div class="wab-capacity-bar"><span class="${toneClass(personRatio, personCapacity > 0)}" style="width:${clampPercent(personRatio * 100)}%"></span></div>
            <div class="wab-task-stack">${personTasksHtml || '<p class="muted wab-empty-note">No assignments yet. Select a task, then press Enter here or drag one in.</p>'}</div>
          </section>`;
        })
        .join("");

      const teamDropLabel = column.virtual ? "Backlog Return" : "Team Assignment";
      const teamDropHelp = column.virtual
        ? "Press Enter here to move the selected task back to backlog, or drop tasks here to unassign them."
        : "Press Enter here to queue the selected task for this team, or drop tasks here.";
      const peopleEmptyMessage = teamPeople.length
        ? `No people match "${esc(boardState.personSearch)}" in this column.`
        : "No people in this team yet. Add a person above or move one into this column.";
      const teamTitleHtml = column.virtual
        ? `<div class="wab-team-name">${esc(column.name)}</div>`
        : `<div class="wab-team-title-row">
            <div class="wab-team-name">${esc(column.name)}</div>
            <button type="button" class="secondary wab-team-delete" data-wab-action="delete-team" data-team-id="${esc(column.id)}" title="Delete team">x</button>
          </div>`;

      return `<article class="wab-team-column${flashClass("team", column.id)}" data-dropzone="team" data-team-id="${esc(column.id)}">
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
        <div
          class="wab-team-assignment-zone"
          data-dropzone="team"
          data-team-id="${esc(column.id)}"
          data-assign-target="${column.id === UNASSIGNED_TEAM_ID ? "backlog" : `team:${esc(column.id)}`}"
          tabindex="0"
          role="button"
          aria-label="${column.id === UNASSIGNED_TEAM_ID ? "Move selected task to backlog" : `Assign selected task to ${esc(column.name)}`}"
        >
          <div class="wab-team-assignment-title">${esc(teamDropLabel)}</div>
          <p class="muted wab-team-assignment-help">${teamDropHelp}</p>
        </div>
        <div class="wab-section-head">
          <span>Team Queue</span>
          <span class="wab-section-count">${teamQueueCount}</span>
        </div>
        <div class="wab-team-direct">
          ${directAssignments || '<p class="muted wab-empty-note">No team-level assignments. Select a task and press Enter in the assignment zone to queue one here.</p>'}
        </div>
        <div class="wab-section-head">
          <span>People</span>
          <span class="wab-section-count">${visiblePeople.length}${visiblePeople.length !== teamPeople.length ? ` / ${teamPeople.length}` : ""}</span>
        </div>
        <div class="wab-people-grid">${peopleHtml || `<p class="muted wab-empty-note">${peopleEmptyMessage}</p>`}</div>
      </article>`;
    })
    .join("");

  const boardEmptyState =
    !teams.length && !people.length
      ? `<div class="wab-board-empty">
          <h3>Start This Allocation Board</h3>
          <p class="muted">Create a team, add people, then create tasks for ${esc(boardState.month)} to begin assigning work.</p>
        </div>`
      : "";

  const backlogEmptyState = !tasks.length
    ? '<p class="muted wab-empty-note">No tasks for this month yet. Use the task quick-add row below the toolbar to create your first task.</p>'
    : backlogTasks.length
      ? ""
      : assignedTaskIds.size
        ? '<p class="muted wab-empty-note">No matching backlog tasks. Clear the backlog filters or unassign a task from the detail panel.</p>'
        : '<p class="muted wab-empty-note">Nothing is waiting in backlog. Create a task or adjust the current filters.</p>';

  const notice =
    boardState.notice?.message
      ? `<div class="wab-notice ${boardState.notice.tone === "error" ? "error" : boardState.notice.tone === "warn" ? "warn" : "success"}">${esc(boardState.notice.message)}</div>`
      : "";

  const loading = boardState.loading ? '<p class="muted">Loading work allocation board...</p>' : "";
  const error = boardState.error ? `<p class="muted">${esc(boardState.error)}</p>` : "";
  const selectionSummary = selected
    ? `<div class="wab-selection-summary">
        <span class="wab-selection-label">Selected Task</span>
        <strong>${esc(selected.title)}</strong>
        <span class="muted">${esc(selectedAssigneeSummary)} | ${formatFte(selected.fte_months)} FTE-mo</span>
      </div>`
    : `<div class="wab-selection-summary wab-selection-summary-empty">
        <span class="wab-selection-label">Selected Task</span>
        <span class="muted">Choose a task to inspect assignments, save edits, or rebalance capacity.</span>
      </div>`;

  return `${notice}${loading}${error}
    <div class="wab-toolbar wab-toolbar-sticky">
      <div class="toolbar-group wab-toolbar-filters">
        <label class="inline-field">Month
          <input type="month" id="wab-month" value="${esc(boardState.month)}" />
        </label>
        <label class="inline-field">Team
          <select id="wab-team-filter">${teamOptions}</select>
        </label>
        <label class="inline-field">Effort
          <select id="wab-effort-filter">
            <option value="all" ${boardState.effortFilter === "all" ? "selected" : ""}>All</option>
            <option value="small" ${boardState.effortFilter === "small" ? "selected" : ""}>Small (<= 0.25)</option>
            <option value="medium" ${boardState.effortFilter === "medium" ? "selected" : ""}>Medium (0.26 - 0.50)</option>
            <option value="large" ${boardState.effortFilter === "large" ? "selected" : ""}>Large (> 0.50)</option>
          </select>
        </label>
        <label class="inline-field">Person
          <input type="text" id="wab-person-search" value="${esc(boardState.personSearch)}" placeholder="Search people" />
        </label>
        <label class="inline-field wab-search-field">Backlog Search
          <input type="text" id="wab-search" value="${esc(boardState.search)}" placeholder="Search backlog tasks" />
        </label>
      </div>
      <div class="toolbar-group wab-secondary-actions">
        <button type="button" class="secondary" data-wab-action="refresh">Refresh</button>
        <button type="button" class="secondary" data-wab-action="download-report">Download PDF Report</button>
        <button type="button" class="secondary" data-wab-action="undo" ${boardState.undoStack.length ? "" : "disabled"}>Undo</button>
      </div>
    </div>
    ${selectionSummary}
    <div class="wab-inline-stack">
      <div class="wab-inline-forms wab-inline-forms-planning">
        <label>Team Name
          <input type="text" id="wab-new-team-name" value="${esc(boardState.drafts.teamName)}" placeholder="Create a team" />
        </label>
        <div class="wab-inline-action">
          <button type="button" data-wab-action="add-team">Add Team</button>
        </div>
        <label>Person Name
          <input type="text" id="wab-new-person-name" value="${esc(boardState.drafts.personName)}" placeholder="Add a person" />
        </label>
        <label>Team
          <select id="wab-new-person-team">
            <option value="">Unassigned Team</option>
            ${teams.map((team) => `<option value="${esc(team.id)}" ${boardState.drafts.personTeamId === team.id ? "selected" : ""}>${esc(team.name)}</option>`).join("")}
          </select>
        </label>
        <label>Capacity
          <input type="number" id="wab-new-person-capacity" min="0.10" step="0.05" value="${esc(boardState.drafts.personCapacity)}" />
        </label>
        <div class="wab-inline-action">
          <button type="button" data-wab-action="add-person">Add Person</button>
        </div>
      </div>
      <div class="wab-inline-forms wab-inline-forms-planning">
        <label class="wide">Task Title
          <input type="text" id="wab-new-task-title" value="${esc(boardState.drafts.taskTitle)}" placeholder="Create backlog work for this month" />
        </label>
        <label>FTE-Months
          <input type="number" id="wab-new-task-fte" min="0.05" step="0.05" value="${esc(boardState.drafts.taskFte)}" />
        </label>
        <div class="wab-inline-action">
          <button type="button" data-wab-action="add-task">Add Task</button>
        </div>
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
    <div class="wab-layout${selected ? " has-detail" : ""}">
      <div class="wab-shell">
        <aside class="wab-backlog" data-dropzone="backlog" data-assign-target="backlog" tabindex="0" role="button" aria-label="Move selected task back to backlog">
          <div class="wab-panel-head">
            <div class="wab-panel-title-group">
              <h3>Backlog</h3>
              <p class="muted wab-panel-sub">Drop tasks here to unassign them. Drop people here to move them into Unassigned.</p>
            </div>
            <span class="pill muted">${backlogTasks.length}</span>
          </div>
          <div class="wab-task-list">${backlogTasks.map((task) => taskChip(task, null)).join("") || backlogEmptyState}</div>
        </aside>
        <section class="wab-board-columns">${boardEmptyState}${columnHtml}</section>
      </div>
      ${buildDetailPanelHtml(selected, selectedAllocations, teams, people)}
    </div>`;
}

async function createAssignment(taskId, assigneeType, assigneeId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const task = (boardState.data.tasks || []).find((row) => row.id === taskId);
  if (!task) return;
  const existingSame = (boardState.data.allocations || []).find(
    (row) => row.task_id === taskId && row.assignee_type === assigneeType && row.assignee_id === assigneeId
  );
  if (existingSame) {
    setNotice("Task is already assigned there", "warn");
    rerender();
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
  flashTargets([{ kind: "task", id: taskId }, { kind: assigneeType, id: assigneeId }], "success");
  await refreshGlobal(ctx, "allocations");
  rerender();
}

async function unassignAllocation(
  allocationId,
  { pushUndo = true, noticeMessage = "Assignee removed from task", refresh = true, render = true } = {}
) {
  const ctx = boardState.ctx;
  const existing = (boardState.data.allocations || []).find((row) => row.id === allocationId);
  if (!existing) return;
  await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(existing.id)}`, {
    method: "DELETE",
  });
  boardState.data.allocations = (boardState.data.allocations || []).filter((row) => row.id !== existing.id);
  if (pushUndo) {
    boardState.undoStack.push({
      kind: "assign",
      payload: allocationToCreatePayload(existing),
    });
  }
  if (noticeMessage) setNotice(noticeMessage, "success");
  flashTargets([{ kind: "task", id: existing.task_id }, { kind: existing.assignee_type, id: existing.assignee_id }], "success");
  if (refresh) await refreshGlobal(ctx, "allocations");
  if (render) rerender();
}

async function unassignTask(taskId, { pushUndo = true } = {}) {
  const matches = (boardState.data.allocations || []).filter((row) => row.task_id === taskId);
  if (!matches.length) {
    setNotice("Task is already in backlog", "warn");
    rerender();
    return;
  }
  for (const allocation of matches) {
    await unassignAllocation(allocation.id, { pushUndo, noticeMessage: "", refresh: false, render: false });
  }
  await refreshGlobal(boardState.ctx, "allocations");
  setNotice(matches.length > 1 ? "Task unassigned from all assignees" : "Task moved back to backlog", "success");
  flashTargets([{ kind: "task", id: taskId }], "success");
  rerender();
}

async function movePersonToTeam(personId, teamId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const person = (boardState.data.people || []).find((row) => row.id === personId);
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
  flashTargets([
    { kind: "person", id: personId },
    { kind: "team", id: nextTeamToken },
  ]);
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

async function assignSelectedTaskToTarget(rawTarget) {
  const target = parseAssignmentTarget(rawTarget);
  const taskId = boardState.selectedTaskId;
  if (!taskId) {
    setNotice("Select a task first", "warn");
    rerender();
    return;
  }
  if (!target) return;
  if (target.type === "backlog") {
    await unassignTask(taskId, { pushUndo: true });
    return;
  }
  if (target.type === "team" && target.id === UNASSIGNED_TEAM_ID) {
    await unassignTask(taskId, { pushUndo: true });
    return;
  }
  await createAssignment(taskId, target.type, target.id, { pushUndo: true });
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
      const response = await fetch(`/api/planning/work-allocation/report.pdf?month=${encodeURIComponent(month)}`, {
        method: "GET",
        headers,
        credentials: "include",
      });
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
    if (action === "close-task-detail" || action === "close-task-modal") {
      closeTaskDetail({ restoreFocus: true });
      return;
    }
    if (action === "undo") {
      await performUndo();
      return;
    }
    if (action === "add-team") {
      const name = String(boardState.drafts.teamName || "").trim();
      if (!name) {
        setNotice("Team name is required", "warn");
        rerender();
        return;
      }
      const created = await callApi(ctx, "/planning/work-allocation/teams", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      boardState.drafts.teamName = "";
      setNotice("Team added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      if (created?.id) flashTargets([{ kind: "team", id: created.id }], "success");
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
      const teamPeopleCount = (boardState.data.people || []).filter((person) => person.team_id === teamId).length;
      const teamAllocations = (boardState.data.allocations || []).filter(
        (allocation) => allocation.assignee_type === "team" && allocation.assignee_id === teamId
      );
      const confirmed = await confirmAction({
        title: "Delete Team?",
        message: `Delete team "${team.name}"? ${teamPeopleCount} people will move to Unassigned. ${teamAllocations.length} team-level assignments will move back to Backlog.`,
        confirmLabel: "Delete Team",
      });
      if (!confirmed) return;

      for (const allocation of teamAllocations) {
        await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(allocation.id)}`, {
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
      const name = String(boardState.drafts.personName || "").trim();
      if (!name) {
        setNotice("Person name is required", "warn");
        rerender();
        return;
      }
      const teamId = String(boardState.drafts.personTeamId || "").trim() || null;
      const cap = Math.max(numberOr(boardState.drafts.personCapacity, 1), 0.1);
      const created = await callApi(ctx, "/planning/work-allocation/people", {
        method: "POST",
        body: JSON.stringify({ name, team_id: teamId, capacity_fte_months: cap }),
      });
      boardState.drafts.personName = "";
      boardState.drafts.personCapacity = "1.00";
      boardState.drafts.personTeamId = "";
      setNotice("Person added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      if (created?.id) flashTargets([{ kind: "person", id: created.id }], "success");
      await refreshGlobal(ctx, "users");
      return;
    }
    if (action === "add-task") {
      const title = String(boardState.drafts.taskTitle || "").trim();
      if (!title) {
        setNotice("Task title is required", "warn");
        rerender();
        return;
      }
      const fte = Math.max(numberOr(boardState.drafts.taskFte, 0.25), 0.05);
      const created = await callApi(ctx, `/planning/work-allocation/tasks?month=${encodeURIComponent(boardState.month)}`, {
        method: "POST",
        body: JSON.stringify({ title, fte_months: fte }),
      });
      boardState.selectedTaskId = created?.id || "";
      boardState.focusReturnTaskId = boardState.selectedTaskId;
      boardState.undoStack.push({ kind: "delete-task", taskId: created.id });
      boardState.drafts.taskTitle = "";
      boardState.drafts.taskFte = "0.25";
      setNotice("Task added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      if (created?.id) {
        flashTargets([{ kind: "task", id: created.id }], "success");
        selectTask(created.id, { focusReturnTaskId: created.id });
      }
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "assign-task") {
      const assignmentSelect = root.querySelector("#wab-detail-assignee-target");
      const target = String(assignmentSelect?.value || "").trim();
      if (!target) {
        setNotice("Choose a team or person first", "warn");
        rerender();
        return;
      }
      boardState.detailDraft.assignmentTarget = "";
      await assignSelectedTaskToTarget(target);
      return;
    }
    if (action === "remove-assignment") {
      const allocationId = String(actionEl?.getAttribute("data-allocation-id") || "").trim();
      if (!allocationId) return;
      await unassignAllocation(allocationId, { pushUndo: true, noticeMessage: "Assignee removed from task" });
      return;
    }
    if (action === "save-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      const title = String(boardState.detailDraft.title || "").trim();
      const fte = Math.max(numberOr(boardState.detailDraft.fte, 0.25), 0.05);
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
      flashTargets([{ kind: "task", id: selectedId }], "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "delete-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      const confirmed = await confirmAction({
        title: "Delete Task?",
        message: "Delete this task and remove its assignments?",
        confirmLabel: "Delete Task",
      });
      if (!confirmed) return;
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(selectedId)}`, {
        method: "DELETE",
      });
      boardState.selectedTaskId = "";
      boardState.detailDraft = defaultDetailDraft();
      persistViewState();
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
  return String(dataTransfer?.getData("application/x-wab-allocation-id") || "").trim();
}

function canDropOnZone(zone, dragKind) {
  if (!zone) return false;
  if (dragKind === DRAG_KIND_PERSON) {
    return zone.type === "team" || zone.type === "person" || zone.type === "backlog";
  }
  if (zone.type === "backlog" || zone.type === "person") return true;
  if (zone.type === "team") return !!zone.teamId;
  return false;
}

function clearDropTargets() {
  const root = boardState.ctx?.els?.planningBoard;
  if (!root) return;
  root.querySelectorAll(".is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
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
      selectTask(chip.getAttribute("data-task-id") || "", {
        focusReturnTaskId: chip.getAttribute("data-task-id") || "",
      });
    }
  });

  root.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "wab-search") {
      boardState.search = target.value || "";
      persistViewState();
      rerender();
      return;
    }
    if (target.id === "wab-person-search") {
      boardState.personSearch = target.value || "";
      rerender();
      return;
    }
    if (target.id === "wab-new-team-name") {
      boardState.drafts.teamName = target.value || "";
      return;
    }
    if (target.id === "wab-new-person-name") {
      boardState.drafts.personName = target.value || "";
      return;
    }
    if (target.id === "wab-new-person-capacity") {
      boardState.drafts.personCapacity = target.value || "1.00";
      return;
    }
    if (target.id === "wab-new-task-title") {
      boardState.drafts.taskTitle = target.value || "";
      return;
    }
    if (target.id === "wab-new-task-fte") {
      boardState.drafts.taskFte = target.value || "0.25";
      return;
    }
    if (target.id === "wab-detail-title") {
      boardState.detailDraft.title = target.value || "";
      return;
    }
    if (target.id === "wab-detail-fte") {
      boardState.detailDraft.fte = target.value || "0.25";
      return;
    }
  });

  root.addEventListener("change", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "wab-month") {
      const value = String(target.value || "").trim();
      if (!/^\d{4}-\d{2}$/.test(value)) return;
      boardState.month = value;
      persistViewState();
      await loadBoard(boardState.ctx, { allocationsOnly: true });
      return;
    }
    if (target.id === "wab-team-filter") {
      boardState.teamFilter = target.value || "all";
      persistViewState();
      rerender();
      return;
    }
    if (target.id === "wab-effort-filter") {
      boardState.effortFilter = target.value || "all";
      persistViewState();
      rerender();
      return;
    }
    if (target.id === "wab-new-person-team") {
      boardState.drafts.personTeamId = target.value || "";
      return;
    }
    if (target.id === "wab-detail-assignee-target") {
      boardState.detailDraft.assignmentTarget = target.value || "";
    }
  });

  root.addEventListener("keydown", async (event) => {
    if (!(event.target instanceof Element)) return;
    const key = event.key || "";
    if (key === "Escape" && boardState.selectedTaskId) {
      event.preventDefault();
      closeTaskDetail({ restoreFocus: true });
      return;
    }
    const chip = event.target.closest(".wab-task-chip");
    if (chip && (key === "Enter" || key === " ")) {
      event.preventDefault();
      selectTask(chip.getAttribute("data-task-id") || "", {
        focusReturnTaskId: chip.getAttribute("data-task-id") || "",
      });
      return;
    }
    const assignTarget = event.target.closest("[data-assign-target]");
    if (assignTarget && (key === "Enter" || key === " ")) {
      event.preventDefault();
      await assignSelectedTaskToTarget(assignTarget.getAttribute("data-assign-target") || "");
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

  const activeTask = selectedTask();
  if (activeTask && boardState.detailDraft.taskId !== activeTask.id) {
    syncDetailDraft(activeTask);
  }

  root.innerHTML = buildBoardMarkup();
}
