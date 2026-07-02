import {
  UNASSIGNED_TEAM_ID,
  boardState,
} from "./state.js";
import {
  allocationWorkItemId,
  allocationWorkItemType,
  allocationsByWorkItem,
  applyProjectBacklogFilters,
  assignmentOptionsHtml,
  clampPercent,
  esc,
  flashClass,
  formatFte,
  matchesPersonSearch,
  numberOr,
  projectResidualFte,
  showCompletedOperationalWork,
  solutionRemainingFte,
  sortedPeople,
  sortedProjects,
  sortedSolutions,
  sortedTeams,
  toneClass,
  visibleBoardAllocations,
} from "./common.js";
import { selectedWorkItem } from "./selection.js";

function buildSolutionsByProject(solutions) {
  const map = new Map();
  solutions.forEach((solution) => {
    const list = map.get(solution.project_id) || [];
    list.push(solution);
    map.set(solution.project_id, list);
  });
  return map;
}

function allocationMapByAssignee(allocations) {
  const personAllocationMap = new Map();
  const teamAllocationMap = new Map();
  allocations.forEach((alloc) => {
    const map = alloc.assignee_type === "team" ? teamAllocationMap : personAllocationMap;
    const key = alloc.assignee_id || "";
    if (!key) return;
    const list = map.get(key) || [];
    list.push(alloc);
    map.set(key, list);
  });
  return { personAllocationMap, teamAllocationMap };
}

function projectById(projects) {
  return new Map(projects.map((project) => [project.id, project]));
}

function solutionById(solutions) {
  return new Map(solutions.map((solution) => [solution.id, solution]));
}

function workChipLabel(type) {
  if (type === "project") return "Project";
  if (type === "solution") return "Solution";
  return "Task";
}

function solutionChip(solution, allocation = null, { nested = false } = {}) {
  const selected = boardState.selectedWorkItemType === "solution" && boardState.selectedWorkItemId === solution.id;
  const allocated = numberOr(solution.allocated_fte_months, 0);
  const remaining = solutionRemainingFte(solution);
  const fte = allocation ? numberOr(allocation.fte_months_allocated, 0) : remaining || numberOr(solution.fte_months, 0.25);
  const assignee = allocation?.assignee_name || allocation?.assignee_id || "";
  return `<button
    type="button"
    class="wab-work-chip wab-solution-chip${nested ? " wab-solution-chip-nested" : ""}${allocation ? " is-assigned" : ""}${selected ? " is-selected" : ""}${allocated > 0 && !allocation ? " is-broken-out" : ""}${flashClass("solution", solution.id)}"
    draggable="true"
    data-work-item-type="solution"
    data-work-item-id="${esc(solution.id)}"
    data-allocation-id="${esc(allocation?.id || "")}"
    data-assigned="${allocation ? "1" : "0"}"
    aria-pressed="${selected ? "true" : "false"}"
  >
    <span class="wab-task-chip-title">${esc(solution.title)}</span>
    <span class="wab-task-chip-meta">${formatFte(fte)} FTE-mo${assignee ? ` | ${esc(assignee)}` : ""}</span>
    ${nested && allocated > 0 ? `<span class="wab-chip-note">${formatFte(allocated)} broken out</span>` : ""}
  </button>`;
}

function projectCard(project, childSolutions, allocation = null) {
  const selected = boardState.selectedWorkItemType === "project" && boardState.selectedWorkItemId === project.id;
  const residual = allocation ? numberOr(allocation.fte_months_allocated, 0) : projectResidualFte(project);
  const brokenOut = numberOr(project.allocated_solution_fte_months, 0);
  const total = numberOr(project.fte_months, residual);
  const assignee = allocation?.assignee_name || allocation?.assignee_id || "";
  const solutionHtml = childSolutions.length
    ? childSolutions.map((solution) => solutionChip(solution, null, { nested: true })).join("")
    : '<p class="muted wab-empty-note">No solutions under this project yet.</p>';

  return `<article
    class="wab-work-chip wab-project-card${allocation ? " is-assigned" : ""}${selected ? " is-selected" : ""}${flashClass("project", project.id)}"
    draggable="true"
    data-work-item-type="project"
    data-work-item-id="${esc(project.id)}"
    data-allocation-id="${esc(allocation?.id || "")}"
    data-assigned="${allocation ? "1" : "0"}"
    tabindex="0"
    role="button"
    aria-pressed="${selected ? "true" : "false"}"
  >
    <div class="wab-project-card-head">
      <div>
        <div class="wab-project-card-kicker">${workChipLabel("project")}</div>
        <h4>${esc(project.title)}</h4>
      </div>
      <span class="pill muted">${childSolutions.length}</span>
    </div>
    <div class="wab-project-card-meta">
      <span>Total ${formatFte(total)}</span>
      <span>Broken out ${formatFte(brokenOut)}</span>
      <span>Residual ${formatFte(residual)}</span>
    </div>
    ${assignee ? `<div class="wab-chip-note">Assigned to ${esc(assignee)}</div>` : ""}
    <div class="wab-solution-nest">${solutionHtml}</div>
  </article>`;
}

function allocationChip(allocation, projectsById, solutionsById, solutionsByProject) {
  const type = allocationWorkItemType(allocation);
  const id = allocationWorkItemId(allocation);
  if (type === "project") {
    const project = projectsById.get(id);
    if (!project) return "";
    return projectCard(project, solutionsByProject.get(project.id) || [], allocation);
  }
  if (type === "solution") {
    const solution = solutionsById.get(id);
    if (!solution) return "";
    return solutionChip(solution, allocation);
  }
  return "";
}

function buildDetailPanelHtml(workItem, allocations, teams, people) {
  if (!workItem) return "";
  const type = boardState.selectedWorkItemType || "";
  const totalFte = numberOr(workItem.fte_months, 0.25);
  const allocatedFte = allocations.reduce((sum, allocation) => sum + numberOr(allocation.fte_months_allocated, 0), 0);
  const remainingFte = type === "project" ? projectResidualFte(workItem) : solutionRemainingFte(workItem);
  const assignmentOptions = assignmentOptionsHtml(teams, people, boardState.detailDraft.assignmentTarget || "");
  const assigneeSummary = allocations.length
    ? allocations.map((allocation) => allocation.assignee_name || allocation.assignee_id || "").filter(Boolean).join(", ")
    : "Backlog";
  const kindLabel = type === "project" ? "Project" : "Solution";
  const canEditFte = type === "solution";
  const allocationRows = allocations.length
    ? allocations.map((allocation) => {
      const toneClassName = flashClass(allocation.assignee_type, allocation.assignee_id);
      const label = allocation.assignee_name || allocation.assignee_id || "Unknown";
      const allocationKindLabel = allocation.assignee_type === "team" ? "Team Queue" : "Person";
      return `<div class="wab-assignee-row${toneClassName}">
        <div class="wab-assignee-copy">
          <strong>${esc(label)}</strong>
          <span class="muted">${allocationKindLabel} | ${formatFte(allocation.fte_months_allocated)} FTE-mo</span>
        </div>
        <button type="button" class="secondary" data-wab-action="remove-assignment" data-allocation-id="${esc(allocation.id)}">Remove</button>
      </div>`;
    }).join("")
    : `<p class="muted wab-empty-note">No assignees yet. Assign this ${kindLabel.toLowerCase()} from here or drag it onto a team or person.</p>`;

  return `<div class="wab-modal-shell wab-task-modal-shell">
    <button type="button" class="wab-modal-backdrop wab-task-modal-backdrop" data-wab-action="close-task-modal" aria-label="Close planning detail"></button>
    <aside class="wab-modal-card wab-detail-panel wab-detail-panel-open" role="dialog" aria-modal="true" aria-labelledby="wab-task-modal-title">
      <div class="wab-detail-head">
        <div>
          <h3 id="wab-task-modal-title">${kindLabel} Planning</h3>
          <p class="muted wab-detail-sub">Month ${esc(boardState.month)} | ${formatFte(totalFte)} FTE-mo total</p>
        </div>
        <button type="button" class="secondary" data-wab-action="close-task-modal">Close</button>
      </div>
      <label class="wide">${kindLabel}
        <input type="text" id="wab-detail-title" value="${esc(workItem.title)}" disabled />
      </label>
      <label>Split FTE-Months
        <input type="number" id="wab-detail-fte" min="${canEditFte ? "0.05" : "0"}" step="0.05" value="${esc(boardState.detailDraft.fte || formatFte(remainingFte))}" ${canEditFte ? "" : "disabled"} />
      </label>
      <div class="wab-detail-summary">
        <div>
          <span class="wab-detail-label">Current Assignees</span>
          <strong>${esc(assigneeSummary)}</strong>
        </div>
        <div>
          <span class="wab-detail-label">${type === "project" ? "Residual" : "Remaining"}</span>
          <strong>${formatFte(remainingFte)} FTE-mo</strong>
        </div>
        <div>
          <span class="wab-detail-label">Broken Out</span>
          <strong>${formatFte(allocatedFte)} FTE-mo</strong>
        </div>
      </div>
      <div class="wab-detail-section">
        <div class="wab-detail-section-head">
          <h4>Assign / Unassign</h4>
          <span class="muted">${type === "project" ? "Project FTE is residual after solution splits." : "Drag solution chips directly to a team or person to split them out."}</span>
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
    </aside>
  </div>`;
}

export function buildBoardMarkup() {
  const showCompleted = showCompletedOperationalWork();
  const teams = sortedTeams();
  const people = sortedPeople();
  const projects = sortedProjects();
  const solutions = sortedSolutions();
  const hiddenProjectCount = showCompleted ? 0 : Math.max((boardState.data.projects || []).length - projects.length, 0);
  const hiddenSolutionCount = showCompleted ? 0 : Math.max((boardState.data.solutions || []).length - solutions.length, 0);
  const allocationMap = allocationsByWorkItem();
  const visibleAllocations = visibleBoardAllocations(boardState.ctx);
  const projectsById = projectById(projects);
  const solutionsById = solutionById(solutions);
  const solutionsByProject = buildSolutionsByProject(solutions);
  const { personAllocationMap, teamAllocationMap } = allocationMapByAssignee(visibleAllocations);

  const assignedProjectIds = new Set(
    visibleAllocations
      .filter((allocation) => allocationWorkItemType(allocation) === "project")
      .map((allocation) => allocationWorkItemId(allocation))
  );
  const backlogProjects = applyProjectBacklogFilters(
    projects.filter((project) => !assignedProjectIds.has(project.id) && projectResidualFte(project) > 0),
    solutionsByProject
  );

  const totalCapacity = people.reduce((sum, person) => sum + Math.max(numberOr(person.capacity_fte_months, 1), 0), 0);
  const totalAllocated = visibleAllocations.reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
  const selected = selectedWorkItem();
  const selectedKey = selected ? `${boardState.selectedWorkItemType}:${selected.id}` : "";
  const selectedAllocations = selectedKey ? allocationMap.get(selectedKey) || [] : [];
  const selectedAssigneeSummary = selectedAllocations.length
    ? selectedAllocations.map((alloc) => alloc.assignee_name || alloc.assignee_id || "").filter(Boolean).join(", ")
    : "Backlog";

  const teamOptions = [
    '<option value="all">All teams</option>',
    ...teams.map((team) => `<option value="${esc(team.id)}" ${boardState.teamFilter === team.id ? "selected" : ""}>${esc(team.name)}</option>`),
  ].join("");

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

  const columnHtml = visibleColumns.map((column) => {
    const teamPeople = peopleByTeam.get(column.id) || [];
    const visiblePeople = teamPeople.filter(matchesPersonSearch);
    const teamCapacity = teamPeople.reduce((sum, person) => sum + Math.max(numberOr(person.capacity_fte_months, 1), 0), 0);
    const teamPersonLoad = teamPeople.reduce((sum, person) => sum + numberOr(personLoadById.get(person.id), 0), 0);
    const teamDirectLoad = (teamAllocationMap.get(column.id) || []).reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
    const teamLoad = teamPersonLoad + teamDirectLoad;
    const teamRatio = teamCapacity > 0 ? teamLoad / teamCapacity : (teamLoad > 0 ? 1 : 0);
    const teamQueue = teamAllocationMap.get(column.id) || [];

    const directAssignments = teamQueue
      .map((alloc) => allocationChip(alloc, projectsById, solutionsById, solutionsByProject))
      .filter(Boolean)
      .join("");

    const peopleHtml = visiblePeople.map((person) => {
      const personCapacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
      const personAllocations = personAllocationMap.get(person.id) || [];
      const personLoad = personAllocations.reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
      const personRatio = personCapacity > 0 ? personLoad / personCapacity : (personLoad > 0 ? 1 : 0);
      const personWorkHtml = personAllocations
        .map((alloc) => allocationChip(alloc, projectsById, solutionsById, solutionsByProject))
        .filter(Boolean)
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
        aria-label="Assign selected work to ${esc(person.name)}"
      >
        <div class="wab-person-head">
          <div>
            <div class="wab-person-name">${esc(person.name)}</div>
            <div class="wab-person-meta">${personAllocations.length} ${personAllocations.length === 1 ? "item" : "items"}</div>
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
        <div class="wab-task-stack">${personWorkHtml || '<p class="muted wab-empty-note">No assignments yet. Select work, then press Enter here or drag it in.</p>'}</div>
      </section>`;
    }).join("");

    const peopleEmptyMessage = teamPeople.length
      ? `No people match "${esc(boardState.personSearch)}" in this column.`
      : "No people in this team yet. Drag someone in from Unassigned or add a person above.";

    return `<article class="wab-team-column${flashClass("team", column.id)}" data-dropzone="team" data-team-id="${esc(column.id)}">
      <header class="wab-team-head">
        <div class="wab-team-title-row">
          <div class="wab-team-name">${esc(column.name)}</div>
          <button type="button" class="secondary wab-team-delete" data-wab-action="delete-team" data-team-id="${esc(column.id)}" title="Delete team">Delete Team</button>
        </div>
        <div class="wab-team-meta">
          <span>${teamPeople.length} ${teamPeople.length === 1 ? "person" : "people"}</span>
          <span>${teamQueue.length} ${teamQueue.length === 1 ? "team item" : "team items"}</span>
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
        aria-label="Assign selected work to ${esc(column.name)}"
      >
        <div class="wab-team-assignment-title">Team Assignment</div>
        <p class="muted wab-team-assignment-help">Drop projects here, or drop solutions to split their FTE.</p>
      </div>
      <div class="wab-section-head">
        <span>Team Queue</span>
        <span class="wab-section-count">${teamQueue.length}</span>
      </div>
      <div class="wab-team-direct">
        ${directAssignments || '<p class="muted wab-empty-note">No team-level assignments. Drop a project or solution here to queue one.</p>'}
      </div>
      <div class="wab-section-head">
        <span>People</span>
        <span class="wab-section-count">${visiblePeople.length}${visiblePeople.length !== teamPeople.length ? ` / ${teamPeople.length}` : ""}</span>
      </div>
      <div class="wab-people-grid">${peopleHtml || `<p class="muted wab-empty-note">${peopleEmptyMessage}</p>`}</div>
    </article>`;
  }).join("") || (
    !teams.length
      ? `<div class="wab-board-empty">
          <h3>No teams yet</h3>
          <p class="muted">${people.length ? "Create a team, then drag people in from Unassigned to start allocating work." : `Create a team, add people, then route projects and solutions for ${esc(boardState.month)}.`}</p>
        </div>`
      : `<div class="wab-board-empty">
          <h3>No teams in view</h3>
          <p class="muted">Clear the team filter to bring your team columns back into view.</p>
        </div>`
  );

  const backlogEmptyState = !projects.length
    ? '<p class="muted wab-empty-note">No projects are available for planning.</p>'
    : backlogProjects.length
      ? ""
      : assignedProjectIds.size
        ? '<p class="muted wab-empty-note">No matching residual project work. Clear filters or remove an assignment to bring it back.</p>'
        : '<p class="muted wab-empty-note">Nothing is waiting in backlog. Adjust filters or add project/solution records in the portfolio views.</p>';
  const unassignedEmptyState = unassignedPeople.length
    ? `<p class="muted wab-empty-note">No unassigned people match "${esc(boardState.personSearch)}".</p>`
    : '<p class="muted wab-empty-note">Everyone is assigned to a team. Drag a person here to take them off the board.</p>';
  const unassignedPeopleHtml = visibleUnassignedPeople.map((person) => {
    const personCapacity = Math.max(numberOr(person.capacity_fte_months, 1), 0);
    const personAllocations = personAllocationMap.get(person.id) || [];
    const personLoad = personAllocations.reduce((sum, alloc) => sum + numberOr(alloc.fte_months_allocated, 0), 0);
    const personRatio = personCapacity > 0 ? personLoad / personCapacity : (personLoad > 0 ? 1 : 0);
    const itemCount = personAllocations.length;
    const itemSummary = itemCount ? `${itemCount} ${itemCount === 1 ? "item attached" : "items attached"}` : "No active items";
    return `<article
      class="wab-unassigned-person-card${flashClass("person", person.id)}"
      draggable="true"
      data-person-id="${esc(person.id)}"
    >
      <div class="wab-unassigned-person-head">
        <div class="wab-unassigned-person-name">${esc(person.name)}</div>
        <span class="pill muted">${itemCount}</span>
      </div>
      <div class="wab-unassigned-person-meta">${esc(itemSummary)}</div>
      <div class="wab-capacity-text wab-unassigned-person-capacity ${toneClass(personRatio, personCapacity > 0)}">${formatFte(personLoad)} / ${formatFte(personCapacity)} FTE-mo</div>
    </article>`;
  }).join("");
  const unassignedCountLabel = visibleUnassignedPeople.length !== unassignedPeople.length
    ? `${visibleUnassignedPeople.length} / ${unassignedPeople.length}`
    : `${unassignedPeople.length}`;

  const notice = boardState.notice?.message
    ? `<div class="wab-notice ${boardState.notice.tone === "error" ? "error" : boardState.notice.tone === "warn" ? "warn" : "success"}">${esc(boardState.notice.message)}</div>`
    : "";
  const loading = boardState.loading ? '<p class="muted">Loading work allocation board...</p>' : "";
  const error = boardState.error ? `<p class="muted">${esc(boardState.error)}</p>` : "";
  const hiddenCompletedCount = hiddenProjectCount + hiddenSolutionCount;
  const hiddenCompletedNote = hiddenCompletedCount
    ? `<p class="muted wab-hidden-completed-note">${hiddenCompletedCount} completed or abandoned task, project, or solution item${hiddenCompletedCount === 1 ? "" : "s"} hidden. Use Show Completed in the top bar to review them.</p>`
    : "";
  const selectedPill = selected
    ? `<div class="wab-selected-pill">
        <span class="wab-selected-pill-label">Selected ${esc(workChipLabel(boardState.selectedWorkItemType))}</span>
        <strong>${esc(selected.title)}</strong>
        <span class="muted">${esc(selectedAssigneeSummary)} | ${formatFte(selected.remaining_fte_months ?? selected.residual_fte_months ?? selected.fte_months)} FTE-mo</span>
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
          <option value="small" ${boardState.effortFilter === "small" ? "selected" : ""}>Small (&lt;= 0.25)</option>
          <option value="medium" ${boardState.effortFilter === "medium" ? "selected" : ""}>Medium (0.26 - 0.50)</option>
          <option value="large" ${boardState.effortFilter === "large" ? "selected" : ""}>Large (&gt; 0.50)</option>
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
            <span class="wab-toolbar-card-label">Portfolio Backlog</span>
            <h3>${projects.length} project${projects.length === 1 ? "" : "s"} ready</h3>
          </div>
          <p class="muted">Create projects and solutions in the portfolio views; this board plans their capacity.</p>
        </div>
      </section>
    </div>`);
  }

  if (boardState.topPanel === "guide") {
    toolbarPanels.push(`<div class="wab-toolbar-panel wab-toolbar-guide-grid" data-wab-panel="guide">
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">Project Backlog</span>
        <p class="muted">Projects carry their child solutions until solution work is split out.</p>
      </div>
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">Residual Load</span>
        <p class="muted">Project FTE shrinks as child solution FTE is assigned.</p>
      </div>
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">Solution Split</span>
        <p class="muted">Drop a solution chip directly on a team or person to pull it out of the parent project.</p>
      </div>
      <div class="wab-toolbar-card">
        <span class="wab-toolbar-card-label">People</span>
        <p class="muted">People must be on a team before taking direct work.</p>
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
            <input type="text" id="wab-search" value="${esc(boardState.search)}" placeholder="Search projects or solutions" />
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
          <strong>${backlogProjects.length}</strong>
          <span class="muted">${projects.length} visible projects</span>
        </div>
        <div class="wab-stat-chip">
          <span class="wab-stat-label">Solutions</span>
          <strong>${solutions.length}</strong>
          <span class="muted">${visibleAllocations.filter((row) => allocationWorkItemType(row) === "solution").length} splits</span>
        </div>
        <div class="wab-stat-chip">
          <span class="wab-stat-label">Attention</span>
          <strong>${teamOverCapacity + peopleOverCapacity}</strong>
          <span class="muted">${teamOverCapacity} teams, ${peopleOverCapacity} people over capacity</span>
        </div>
        ${selectedPill}
      </div>
      ${toolbarPanels.join("")}
    </div>
    <div class="wab-layout">
      <div class="wab-shell">
        <aside class="wab-side-rail wab-backlog" data-dropzone="backlog" data-assign-target="backlog" tabindex="0" role="button" aria-label="Move selected work back to backlog">
          <div class="wab-panel-head">
            <div class="wab-panel-title-group">
              <h3>Project Backlog</h3>
              <p class="muted wab-panel-sub">Drop assigned project or solution work here to unassign it.</p>
            </div>
            <span class="pill muted">${backlogProjects.length}</span>
          </div>
          <div class="wab-task-list">${backlogProjects.map((project) => projectCard(project, solutionsByProject.get(project.id) || [], null)).join("") || backlogEmptyState}</div>
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
