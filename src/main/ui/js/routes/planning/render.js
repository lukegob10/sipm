import {
  UNASSIGNED_TEAM_ID,
  boardState,
} from "./state.js";
import {
  allocationsByTask,
  applyBacklogFilters,
  assignmentOptionsHtml,
  clampPercent,
  esc,
  flashClass,
  formatFte,
  matchesPersonSearch,
  numberOr,
  showCompletedOperationalWork,
  sortedPeople,
  sortedTasks,
  sortedTeams,
  toneClass,
  visibleBoardAllocations,
} from "./common.js";
import { selectedTask } from "./selection.js";

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
  if (!task) return "";

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

  return `<div class="wab-modal-shell wab-task-modal-shell">
    <button type="button" class="wab-modal-backdrop wab-task-modal-backdrop" data-wab-action="close-task-modal" aria-label="Close task detail"></button>
    <aside class="wab-modal-card wab-detail-panel wab-detail-panel-open" role="dialog" aria-modal="true" aria-labelledby="wab-task-modal-title">
      <div class="wab-detail-head">
        <div>
          <h3 id="wab-task-modal-title">Task Detail</h3>
          <p class="muted wab-detail-sub">Month ${esc(boardState.month)} | ${formatFte(task.fte_months)} FTE-mo</p>
        </div>
        <button type="button" class="secondary" data-wab-action="close-task-modal">Close</button>
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
    </aside>
  </div>`;
}

export function buildBoardMarkup() {
  const showCompleted = showCompletedOperationalWork();
  const teams = sortedTeams();
  const people = sortedPeople();
  const tasks = sortedTasks();
  const hiddenTaskCount = showCompleted ? 0 : Math.max((boardState.data.tasks || []).length - tasks.length, 0);
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
  ].join("");

  const allocationList = visibleBoardAllocations(boardState.ctx, tasks);
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

  const visibleColumns = teams.filter((team) => boardState.teamFilter === "all" || boardState.teamFilter === team.id);
  const unassignedPeople = peopleByTeam.get(UNASSIGNED_TEAM_ID) || [];
  const visibleUnassignedPeople = unassignedPeople.filter(matchesPersonSearch);

  const peopleOverCapacity = people.reduce((count, person) => {
    const capacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
    const load = numberOr(personLoadById.get(person.id), 0);
    const ratio = capacity > 0 ? load / capacity : (load > 0 ? 1 : 0);
    return count + (ratio > 1 ? 1 : 0);
  }, 0);

  const teamOverCapacity = teams.reduce((count, team) => {
    const teamPeople = peopleByTeam.get(team.id) || [];
    const teamCapacity = teamPeople.reduce((sum, person) => sum + Math.max(numberOr(person.capacity_fte_months, 1), 0), 0);
    const teamPersonLoad = teamPeople.reduce((sum, person) => sum + numberOr(personLoadById.get(person.id), 0), 0);
    const teamDirectLoad = (teamAllocationMap.get(team.id) || []).reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
    const teamLoad = teamPersonLoad + teamDirectLoad;
    const ratio = teamCapacity > 0 ? teamLoad / teamCapacity : (teamLoad > 0 ? 1 : 0);
    return count + (ratio > 1 ? 1 : 0);
  }, 0);

  const activeAdvancedFilters = [
    boardState.teamFilter !== "all",
    boardState.effortFilter !== "all",
    String(boardState.personSearch || "").trim(),
  ].filter(Boolean).length;
  const hasSearchFilters = !!String(boardState.search || "").trim();
  const hasAnyFilter = activeAdvancedFilters > 0 || hasSearchFilters;
  const capacityPercent = totalCapacity > 0 ? clampPercent((totalAllocated / totalCapacity) * 100) : 0;

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
              <div class="wab-person-head-actions">
                <div class="wab-capacity-text ${toneClass(personRatio, personCapacity > 0)}">${formatFte(personLoad)} / ${formatFte(personCapacity)} FTE-mo</div>
                <button
                  type="button"
                  class="secondary wab-person-unassign"
                  data-wab-action="move-person-to-unassigned"
                  data-person-id="${esc(person.id)}"
                  title="Move ${esc(person.name)} to Unassigned"
                >Unassign</button>
              </div>
            </div>
            <div class="wab-capacity-bar"><span class="${toneClass(personRatio, personCapacity > 0)}" style="width:${clampPercent(personRatio * 100)}%"></span></div>
            <div class="wab-task-stack">${personTasksHtml || '<p class="muted wab-empty-note">No assignments yet. Select a task, then press Enter here or drag one in.</p>'}</div>
          </section>`;
        })
        .join("");

      const teamDropLabel = "Team Assignment";
      const teamDropHelp = "Press Enter here to queue the selected task for this team, or drop tasks here.";
      const peopleEmptyMessage = teamPeople.length
        ? `No people match "${esc(boardState.personSearch)}" in this column.`
        : "No people in this team yet. Drag someone in from Unassigned or add a person above.";
      const teamTitleHtml = `<div class="wab-team-title-row">
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
          data-assign-target="team:${esc(column.id)}"
          tabindex="0"
          role="button"
          aria-label="Assign selected task to ${esc(column.name)}"
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
    .join("")
    || (
      !teams.length
        ? `<div class="wab-board-empty">
            <h3>No teams yet</h3>
            <p class="muted">${people.length ? "Create a team, then drag people in from Unassigned to start allocating work." : `Create a team, add people, then create tasks for ${esc(boardState.month)} to begin assigning work.`}</p>
          </div>`
        : `<div class="wab-board-empty">
            <h3>No teams in view</h3>
            <p class="muted">Clear the team filter to bring your team columns back into view.</p>
          </div>`
    );

  const backlogEmptyState = !tasks.length
    ? '<p class="muted wab-empty-note">No tasks for this month yet. Use the task quick-add row below the toolbar to create your first task.</p>'
    : backlogTasks.length
      ? ""
      : assignedTaskIds.size
        ? '<p class="muted wab-empty-note">No matching backlog tasks. Clear the backlog filters or unassign a task from the detail panel.</p>'
        : '<p class="muted wab-empty-note">Nothing is waiting in backlog. Create a task or adjust the current filters.</p>';
  const unassignedEmptyState = unassignedPeople.length
    ? `<p class="muted wab-empty-note">No unassigned people match "${esc(boardState.personSearch)}".</p>`
    : '<p class="muted wab-empty-note">Everyone is assigned to a team. Drag a person here to take them off the board.</p>';
  const unassignedPeopleHtml = visibleUnassignedPeople
    .map((person) => {
      const personCapacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
      const personAllocations = personAllocationMap.get(person.id) || [];
      const personLoad = personAllocations.reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
      const personRatio = personCapacity > 0 ? personLoad / personCapacity : (personLoad > 0 ? 1 : 0);
      const taskCount = personAllocations.length;
      const taskSummary = taskCount ? `${taskCount} ${taskCount === 1 ? "task attached" : "tasks attached"}` : "No active tasks";
      return `<article
        class="wab-unassigned-person-card${flashClass("person", person.id)}"
        draggable="true"
        data-person-id="${esc(person.id)}"
      >
        <div class="wab-unassigned-person-head">
          <div class="wab-unassigned-person-name">${esc(person.name)}</div>
          <span class="pill muted">${taskCount}</span>
        </div>
        <div class="wab-unassigned-person-meta">${esc(taskSummary)}</div>
        <div class="wab-capacity-text wab-unassigned-person-capacity ${toneClass(personRatio, personCapacity > 0)}">${formatFte(personLoad)} / ${formatFte(personCapacity)} FTE-mo</div>
      </article>`;
    })
    .join("");
  const unassignedCountLabel = visibleUnassignedPeople.length !== unassignedPeople.length
    ? `${visibleUnassignedPeople.length} / ${unassignedPeople.length}`
    : `${unassignedPeople.length}`;

  const notice =
    boardState.notice?.message
      ? `<div class="wab-notice ${boardState.notice.tone === "error" ? "error" : boardState.notice.tone === "warn" ? "warn" : "success"}">${esc(boardState.notice.message)}</div>`
      : "";

  const loading = boardState.loading ? '<p class="muted">Loading work allocation board...</p>' : "";
  const error = boardState.error ? `<p class="muted">${esc(boardState.error)}</p>` : "";
  const hiddenCompletedNote = hiddenTaskCount
    ? `<p class="muted wab-hidden-completed-note">${hiddenTaskCount} completed or abandoned task${hiddenTaskCount === 1 ? "" : "s"} hidden. Use Show Completed in the top bar to review them.</p>`
    : "";
  const selectedPill = selected
    ? `<div class="wab-selected-pill">
        <span class="wab-selected-pill-label">Selected Task</span>
        <strong>${esc(selected.title)}</strong>
        <span class="muted">${esc(selectedAssigneeSummary)} | ${formatFte(selected.fte_months)} FTE-mo</span>
      </div>`
    : "";

  const toolsPendingCount = boardState.undoStack.length;
  const toolbarPanels = [];

  if (boardState.topPanel === "filters") {
    toolbarPanels.push(`<div class="wab-toolbar-panel wab-toolbar-panel-grid" data-wab-panel="filters">
      <label class="inline-field">Team
        <select id="wab-team-filter">${teamOptions}</select>
      </label>
      <label class="inline-field">Effort
        <select id="wab-effort-filter">
          <option value="all" ${boardState.effortFilter === "all" ? "selected" : ""}>All effort</option>
          <option value="small" ${boardState.effortFilter === "small" ? "selected" : ""}>Small (<= 0.25)</option>
          <option value="medium" ${boardState.effortFilter === "medium" ? "selected" : ""}>Medium (0.26 - 0.50)</option>
          <option value="large" ${boardState.effortFilter === "large" ? "selected" : ""}>Large (> 0.50)</option>
        </select>
      </label>
      <label class="inline-field">Person
        <input type="text" id="wab-person-search" value="${esc(boardState.personSearch)}" placeholder="Search people" />
      </label>
      <div class="wab-toolbar-panel-actions">
        <button type="button" class="secondary" data-wab-action="reset-filters" ${hasAnyFilter ? "" : "disabled"}>Clear Filters</button>
      </div>
    </div>`);
  }

  if (boardState.topPanel === "create") {
    toolbarPanels.push(`<div class="wab-toolbar-panel wab-toolbar-create-grid" data-wab-panel="create">
      <section class="wab-toolbar-card">
        <div class="wab-toolbar-card-head">
          <div>
            <span class="wab-toolbar-card-label">People & Teams</span>
            <h3>Build capacity structure</h3>
          </div>
          <p class="muted">Create a team, then add people where they should land.</p>
        </div>
        <div class="wab-create-stack wab-create-stack-flat">
          <div class="wab-create-group-head">
            <span class="wab-create-group-label">Add Team</span>
            <p class="muted">Create a team lane for routing work.</p>
          </div>
          <div class="wab-create-form wab-create-row wab-create-row-team">
            <label class="wab-create-field wab-create-field-grow">Team Name
              <input type="text" id="wab-new-team-name" value="${esc(boardState.drafts.teamName)}" placeholder="e.g. Platform Delivery" />
            </label>
            <div class="wab-create-action">
              <button type="button" class="secondary" data-wab-action="add-team">Add Team</button>
            </div>
          </div>
          <div class="wab-create-divider"></div>
          <div class="wab-create-group-head">
            <span class="wab-create-group-label">Add Person</span>
            <p class="muted">Place someone on a team now or leave them unassigned.</p>
          </div>
          <div class="wab-create-form wab-create-row wab-create-row-person">
            <label class="wab-create-field wab-create-field-grow">Person Name
              <input type="text" id="wab-new-person-name" value="${esc(boardState.drafts.personName)}" placeholder="e.g. Taylor Reed" />
            </label>
            <label class="wab-create-field wab-create-field-team">Team
              <select id="wab-new-person-team">
                <option value="">Unassigned Team</option>
                ${teams.map((team) => `<option value="${esc(team.id)}" ${boardState.drafts.personTeamId === team.id ? "selected" : ""}>${esc(team.name)}</option>`).join("")}
              </select>
            </label>
            <label class="wab-create-field wab-create-field-capacity">Capacity
              <input type="number" id="wab-new-person-capacity" min="0.10" step="0.05" value="${esc(boardState.drafts.personCapacity)}" />
            </label>
            <div class="wab-create-action">
              <button type="button" class="secondary" data-wab-action="add-person">Add Person</button>
            </div>
          </div>
        </div>
      </section>
      <section class="wab-toolbar-card">
        <div class="wab-toolbar-card-head">
          <div>
            <span class="wab-toolbar-card-label">Backlog</span>
            <h3>Create monthly work</h3>
          </div>
          <p class="muted">Add a task for the selected month, then assign it from the board.</p>
        </div>
        <div class="wab-create-form wab-create-row wab-create-row-backlog">
          <label class="wab-create-field wab-create-field-grow">Task Title
            <input type="text" id="wab-new-task-title" value="${esc(boardState.drafts.taskTitle)}" placeholder="Create backlog work for this month" />
          </label>
          <label class="wab-create-field-capacity">FTE-Months
            <input type="number" id="wab-new-task-fte" min="0.05" step="0.05" value="${esc(boardState.drafts.taskFte)}" />
          </label>
          <div class="wab-create-action">
            <button type="button" data-wab-action="add-task">Add Task</button>
          </div>
        </div>
      </section>
    </div>`);
  }

  if (boardState.topPanel === "guide") {
    toolbarPanels.push(`<div class="wab-toolbar-panel wab-toolbar-guide-grid" data-wab-panel="guide">
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">Backlog</span>
        <p class="muted">Unassigned tasks waiting for a team or person.</p>
      </div>
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">Team Queue</span>
        <p class="muted">Work assigned to a team before it is routed to an individual.</p>
      </div>
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">People</span>
        <p class="muted">Team people can take work directly. Unassigned people stay parked on the right until moved onto a team.</p>
      </div>
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">Keyboard</span>
        <p class="muted">Select a task with Enter or Space, assign with the detail panel, close with Escape.</p>
      </div>
    </div>`);
  }

  if (boardState.topPanel === "tools") {
    toolbarPanels.push(`<div class="wab-toolbar-panel wab-toolbar-tools-grid" data-wab-panel="tools">
      <button type="button" class="secondary" data-wab-action="refresh">Refresh</button>
      <button type="button" class="secondary" data-wab-action="download-report">Download PDF Report</button>
      <button type="button" class="secondary" data-wab-action="undo" ${boardState.undoStack.length ? "" : "disabled"}>Undo</button>
    </div>`);
  }

  return `${notice}${loading}${error}${hiddenCompletedNote}
    <div class="wab-toolbar wab-toolbar-sticky">
      <div class="wab-toolbar-main">
        <div class="toolbar-group wab-toolbar-primary">
          <label class="inline-field">Month
            <input type="month" id="wab-month" value="${esc(boardState.month)}" />
          </label>
          <label class="inline-field wab-search-field">Backlog Search
            <input type="text" id="wab-search" value="${esc(boardState.search)}" placeholder="Search backlog tasks" />
          </label>
        </div>
        <div class="toolbar-group wab-toolbar-actions">
          <button type="button" class="secondary wab-toolbar-toggle${boardState.topPanel === "filters" ? " active" : ""}" data-wab-action="toggle-filters" aria-expanded="${boardState.topPanel === "filters" ? "true" : "false"}">
            Filters${activeAdvancedFilters ? ` <span class="wab-toolbar-toggle-count">${activeAdvancedFilters}</span>` : ""}
          </button>
          <button type="button" class="secondary wab-toolbar-toggle${boardState.topPanel === "create" ? " active" : ""}" data-wab-action="toggle-create" aria-expanded="${boardState.topPanel === "create" ? "true" : "false"}">Add</button>
          <button type="button" class="secondary wab-toolbar-toggle${boardState.topPanel === "guide" ? " active" : ""}" data-wab-action="toggle-guide" aria-expanded="${boardState.topPanel === "guide" ? "true" : "false"}">Guide</button>
          <button type="button" class="secondary wab-toolbar-toggle${boardState.topPanel === "tools" ? " active" : ""}" data-wab-action="toggle-tools" aria-expanded="${boardState.topPanel === "tools" ? "true" : "false"}">
            More${toolsPendingCount ? ` <span class="wab-toolbar-toggle-count">${toolsPendingCount}</span>` : ""}
          </button>
        </div>
      </div>
      <div class="wab-toolbar-meta">
        <div class="wab-stat-chip">
          <span class="wab-stat-label">Capacity</span>
          <strong>${capacityPercent}%</strong>
          <span class="muted">${formatFte(totalAllocated)} / ${formatFte(totalCapacity)} FTE-mo</span>
        </div>
        <div class="wab-stat-chip">
          <span class="wab-stat-label">Backlog</span>
          <strong>${backlogTasks.length}</strong>
          <span class="muted">${tasks.length} total tasks</span>
        </div>
        <div class="wab-stat-chip">
          <span class="wab-stat-label">Attention</span>
          <strong>${teamOverCapacity + peopleOverCapacity}</strong>
          <span class="muted">${teamOverCapacity} teams, ${peopleOverCapacity} people over capacity</span>
        </div>
        <div class="wab-stat-chip">
          <span class="wab-stat-label">Visible</span>
          <strong>${visibleColumns.length}</strong>
          <span class="muted">${people.length} people on board</span>
        </div>
        ${selectedPill}
      </div>
      ${toolbarPanels.join("")}
    </div>
    <div class="wab-layout">
      <div class="wab-shell">
        <aside class="wab-side-rail wab-backlog" data-dropzone="backlog" data-assign-target="backlog" tabindex="0" role="button" aria-label="Move selected task back to backlog">
          <div class="wab-panel-head">
            <div class="wab-panel-title-group">
              <h3>Backlog</h3>
              <p class="muted wab-panel-sub">Drop tasks here to unassign them and return them to backlog.</p>
            </div>
            <span class="pill muted">${backlogTasks.length}</span>
          </div>
          <div class="wab-task-list">${backlogTasks.map((task) => taskChip(task, null)).join("") || backlogEmptyState}</div>
        </aside>
        <section class="wab-board-columns">${columnHtml}</section>
        <aside class="wab-side-rail wab-unassigned-rail" data-dropzone="unassigned" aria-label="Move people here to make them unassigned">
          <div class="wab-panel-head">
            <div class="wab-panel-title-group">
              <h3>Unassigned People</h3>
              <p class="muted wab-panel-sub">Drag people here to park them off the board. Move them onto a team before assigning new work.</p>
            </div>
            <span class="pill muted">${unassignedCountLabel}</span>
          </div>
          <div class="wab-unassigned-dropzone" aria-hidden="true">
            <div class="wab-unassigned-drop-title">Drop People Here</div>
            <p class="muted wab-unassigned-drop-help">Move a person out of a team without mixing them into backlog work.</p>
          </div>
          <div class="wab-unassigned-list">${unassignedPeopleHtml || unassignedEmptyState}</div>
        </aside>
      </div>
    </div>
    ${buildDetailPanelHtml(selected, selectedAllocations, teams, people)}`;
}

export function renderPlanningView(root) {
  root.innerHTML = buildBoardMarkup();
}
