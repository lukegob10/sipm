const PREFS_KEY_PREFIX = "sipm-program-dashboard-v1";
const VALID_TABS = new Set(["projects", "tasks"]);
const CLOSED_STATUSES = new Set(["complete", "abandoned"]);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

function displayValue(value, fallback = "-") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function dateValue(value) {
  const raw = String(value || "").slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
}

function statusIsClosed(value) {
  return CLOSED_STATUSES.has(normalize(value));
}

function statusTone(value) {
  const status = normalize(value);
  if (status === "complete") return "positive";
  if (status === "active" || status === "in_progress") return "positive";
  if (status === "on_hold") return "warn";
  if (status === "abandoned") return "danger";
  return "muted";
}

function statusMarkup(value, formatStatus) {
  const label = typeof formatStatus === "function" ? formatStatus(value) : displayValue(value);
  return `<span class="program-dashboard-status pill ${statusTone(value)}">${esc(label)}</span>`;
}

function progressMarkup(value) {
  const pct = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  return `
    <div class="program-dashboard-progress" aria-label="${pct}% complete">
      <span style="width:${pct}%;"></span>
      <strong>${pct}%</strong>
    </div>
  `;
}

function connectionLabel(programParts) {
  return programParts.subArea
    ? programParts.subArea.replace(/\s+/g, " ").trim().toUpperCase()
    : "PROGRAM";
}

function classificationForTask(task) {
  if (task?.blocked) return "Sequential - Hold";
  const priority = Number(task?.priority);
  if (Number.isFinite(priority) && priority <= 2) return "Entitlements";
  if (Number.isFinite(priority) && priority >= 4) return "Enhancement";
  return "New Source";
}

function classificationTone(label) {
  const normalized = normalize(label);
  if (normalized.includes("hold") || normalized.includes("entitlement")) return "warn";
  if (normalized.includes("enhancement")) return "muted";
  return "info";
}

function deckSlideNumber(activeTab) {
  return activeTab === "tasks" ? 3 : 2;
}

function prefsKey(spaceId) {
  return `${PREFS_KEY_PREFIX}:${String(spaceId || "no-space")}`;
}

function readPrefs(spaceId) {
  try {
    const raw = localStorage.getItem(prefsKey(spaceId));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writePrefs(spaceId, prefs) {
  try {
    localStorage.setItem(prefsKey(spaceId), JSON.stringify(prefs));
  } catch {
    // Preference persistence is optional.
  }
}

export function splitProgramName(value) {
  const text = String(value || "").trim();
  if (!text) return { team: "", subArea: "" };
  const separators = [" - ", " / ", " \u2013 ", " \u2014 "];
  const hits = separators
    .map((separator) => ({ separator, index: text.indexOf(separator) }))
    .filter((item) => item.index >= 0)
    .sort((a, b) => a.index - b.index);
  if (!hits.length) return { team: "", subArea: text };
  const first = hits[0];
  return {
    team: text.slice(0, first.index).trim(),
    subArea: text.slice(first.index + first.separator.length).trim() || text,
  };
}

export function createProgramDashboardState() {
  return {
    ctx: null,
    bound: false,
    prefsSpaceId: "",
    selectedProgramId: "",
    activeTab: "projects",
  };
}

function loadStateForSpace(programDashboardState, spaceId) {
  if (programDashboardState.prefsSpaceId === spaceId) return;
  const prefs = readPrefs(spaceId);
  programDashboardState.prefsSpaceId = spaceId;
  programDashboardState.selectedProgramId = String(prefs.selectedProgramId || "");
  programDashboardState.activeTab = VALID_TABS.has(prefs.activeTab) ? prefs.activeTab : "projects";
}

function persistState(programDashboardState) {
  writePrefs(programDashboardState.prefsSpaceId, {
    selectedProgramId: programDashboardState.selectedProgramId,
    activeTab: programDashboardState.activeTab,
  });
}

function bindProgramDashboardEvents(programDashboardState, rerender) {
  const viewRoot = typeof document !== "undefined" ? document.getElementById("view-program-dashboard") : null;
  if (!viewRoot || programDashboardState.bound) return;
  programDashboardState.bound = true;

  viewRoot.addEventListener("change", (event) => {
    if (!(event.target instanceof Element)) return;
    const control = event.target.closest("[data-program-dashboard-control]");
    if (!control) return;
    if (control.getAttribute("data-program-dashboard-control") !== "program") return;
    programDashboardState.selectedProgramId = String(event.target.value || "");
    persistState(programDashboardState);
    rerender();
  });

  viewRoot.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-program-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-program-dashboard-action") || "";

    if (action === "set-tab") {
      const tab = actionEl.getAttribute("data-program-dashboard-tab") || "projects";
      if (!VALID_TABS.has(tab)) return;
      programDashboardState.activeTab = tab;
      persistState(programDashboardState);
      rerender();
      return;
    }

    if (action === "open-project") {
      event.preventDefault();
      const projectId = String(actionEl.getAttribute("data-project-id") || "");
      programDashboardState.ctx?.openProgramDashboardProjectDrilldown?.(projectId);
      return;
    }

    if (action === "open-solution") {
      event.preventDefault();
      const solutionId = String(actionEl.getAttribute("data-solution-id") || "");
      programDashboardState.ctx?.openProgramDashboardSolutionDrilldown?.(solutionId);
      return;
    }

    if (action === "open-task") {
      event.preventDefault();
      const taskId = String(actionEl.getAttribute("data-task-id") || "");
      programDashboardState.ctx?.openProgramDashboardTaskDrilldown?.(taskId);
    }
  });
}

function programOptionMarkup(programs, selectedProgramId) {
  return programs
    .map((program) => {
      const id = String(program.program_id || "");
      return `<option value="${esc(id)}" ${id === selectedProgramId ? "selected" : ""}>${esc(program.program_name || "Unnamed Program")}</option>`;
    })
    .join("");
}

function projectLinkMarkup(project) {
  const id = String(project?.project_id || "");
  const label = displayValue(project?.project_name, "Unnamed Project");
  if (!id) return `<strong>${esc(label)}</strong>`;
  return `<button type="button" class="program-dashboard-link program-dashboard-project-link" data-program-dashboard-action="open-project" data-project-id="${esc(id)}">${esc(label)}</button>`;
}

function solutionLinkMarkup(solution) {
  const id = String(solution?.solution_id || "");
  const label = displayValue(solution?.solution_name, "Unnamed Solution");
  if (!id) return esc(label);
  return `<button type="button" class="program-dashboard-link program-dashboard-solution-link" data-program-dashboard-action="open-solution" data-solution-id="${esc(id)}">${esc(label)}</button>`;
}

function taskLinkMarkup(task) {
  const id = String(task?.task_id || "");
  const label = displayValue(task?.task_name, "Unnamed Task");
  if (!id) return esc(label);
  return `<button type="button" class="program-dashboard-link program-dashboard-task-link" data-program-dashboard-action="open-task" data-task-id="${esc(id)}">${esc(label)}</button>`;
}

function averageProgress(rows, solutionProgress) {
  if (!rows.length) return 0;
  const total = rows.reduce((sum, solution) => sum + Math.max(0, Math.min(100, Number(solutionProgress(solution)) || 0)), 0);
  return Math.round(total / rows.length);
}

function renderProjectsTable({
  selectedProgram,
  projects,
  solutionsByProject,
  programParts,
  formatStatus,
  solutionProgress,
}) {
  if (!projects.length) {
    return `<p class="program-dashboard-empty muted">No projects are assigned to ${esc(selectedProgram.program_name || "this program")}.</p>`;
  }

  const rowsHtml = projects
    .map((project) => {
      const projectSolutions = solutionsByProject.get(String(project.project_id || "")) || [];
      const startDates = projectSolutions.map((solution) => dateValue(solution.planned_start_date)).filter(Boolean).sort();
      const endDates = projectSolutions.map((solution) => dateValue(solution.due_date)).filter(Boolean).sort();
      const projectStart = startDates[0] || "-";
      const projectEnd = endDates[endDates.length - 1] || "-";
      const progress = projectSolutions.length
        ? averageProgress(projectSolutions, solutionProgress)
        : (normalize(project.status) === "complete" ? 100 : 0);
      const programLabel = displayValue(selectedProgram.program_name, "Program");
      const projectRow = `
        <tr class="program-dashboard-group-row">
          <td><span class="program-dashboard-tag">${esc(programLabel)}</span></td>
          <td>${esc(programParts.subArea)}</td>
          <td>${projectLinkMarkup(project)}</td>
          <td>${esc(projectStart)}</td>
          <td>${esc(projectEnd)}</td>
          <td>${statusMarkup(project.status, formatStatus)}</td>
          <td>-</td>
          <td>${esc(displayValue(project.sponsor || project.sponsor_user_soeid))}</td>
          <td>${progressMarkup(progress)}</td>
        </tr>
      `;
      const solutionRows = projectSolutions
        .map((solution) => `
          <tr class="program-dashboard-child-row">
            <td></td>
            <td></td>
            <td><span class="program-dashboard-indent">${solutionLinkMarkup(solution)}</span></td>
            <td>${esc(displayValue(dateValue(solution.planned_start_date)))}</td>
            <td>${esc(displayValue(dateValue(solution.due_date)))}</td>
            <td>${statusMarkup(solution.status, formatStatus)}</td>
            <td>${esc(displayValue(solution.current_phase))}</td>
            <td>${esc(displayValue(solution.owner || solution.assignee || solution.key_stakeholder))}</td>
            <td>${progressMarkup(solutionProgress(solution))}</td>
          </tr>
        `)
        .join("");
      return `${projectRow}${solutionRows}`;
    })
    .join("");

  return `
    <div class="program-dashboard-table-shell">
      <table class="program-dashboard-table program-dashboard-project-table">
        <thead>
          <tr>
            <th>Program</th>
            <th>Sub-Area</th>
            <th>Project / Solution</th>
            <th>Start</th>
            <th>End</th>
            <th>Status</th>
            <th>Phase</th>
            <th>Owner</th>
            <th>% Complete</th>
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
  `;
}

function renderTasksTable({
  selectedProgram,
  tasks,
  hiddenClosedCount,
  projectById,
  solutionById,
  programParts,
  formatStatus,
}) {
  if (!tasks.length) {
    const suffix = hiddenClosedCount
      ? ` ${hiddenClosedCount} completed or abandoned task${hiddenClosedCount === 1 ? "" : "s"} are hidden.`
      : "";
    return `<p class="program-dashboard-empty muted">No tasks match ${esc(selectedProgram.program_name || "this program")}.${suffix}</p>`;
  }

  const rowsHtml = tasks
    .map((task) => {
      const project = projectById.get(String(task.project_id || ""));
      const solution = solutionById.get(String(task.solution_id || ""));
      const classification = classificationForTask(task);
      const system = solution?.solution_name || project?.project_name || "-";
      const customer = project?.sponsor || project?.sponsor_user_soeid || "TAP";
      return `
        <tr>
          <td><span class="program-dashboard-tag">${esc(connectionLabel(programParts))}</span></td>
          <td><span class="program-dashboard-tag ${classificationTone(classification)}">${esc(classification)}</span></td>
          <td>${esc(displayValue(system))}</td>
          <td>${taskLinkMarkup(task)}</td>
          <td>${esc(displayValue(task.assignee || task.assignee_user_soeid, "Unassigned"))}</td>
          <td>${esc(displayValue(customer))}</td>
          <td>${statusMarkup(task.status, formatStatus)}</td>
          <td>${esc(displayValue(dateValue(task.due_date)))}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="program-dashboard-table-shell">
      <table class="program-dashboard-table program-dashboard-task-table">
        <thead>
          <tr>
            <th>Connection</th>
            <th>Classification</th>
            <th>System</th>
            <th>Description</th>
            <th>Project Contact</th>
            <th>Customer</th>
            <th>Status</th>
            <th>Target Date</th>
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
  `;
}

function tabButton(tab, activeTab, label) {
  const active = tab === activeTab;
  return `<button type="button" class="program-dashboard-tab ${active ? "active" : ""}" data-program-dashboard-action="set-tab" data-program-dashboard-tab="${esc(tab)}" aria-pressed="${active ? "true" : "false"}">${esc(label)}</button>`;
}

function renderSummary({ activeTab, projectCount, solutionCount, visibleCount, completeCount, activeCount, notStartedCount, hiddenClosedCount }) {
  const visibleLabel = activeTab === "projects" ? "projects" : "total tasks";
  const hiddenText = activeTab === "tasks" && hiddenClosedCount
    ? ` - ${hiddenClosedCount} closed hidden`
    : "";
  return `
    <div class="program-dashboard-summary">
      <span>${projectCount} projects</span>
      <span>${solutionCount} solutions</span>
      <span>${visibleCount} ${visibleLabel}</span>
      <span><strong>${activeCount}</strong> active</span>
      <span><strong>${completeCount}</strong> complete</span>
      <span><strong>${notStartedCount}</strong> not started${esc(hiddenText)}</span>
    </div>
  `;
}

export function renderProgramDashboardView(programDashboardState, ctx) {
  const { state, els, formatStatus, solutionProgress, showCompletedOperationalWork } = ctx;
  const root = els.programDashboardRoot || document.getElementById("program-dashboard-root");
  if (!root) return;

  programDashboardState.ctx = ctx;
  bindProgramDashboardEvents(programDashboardState, () => {
    if (programDashboardState.ctx) renderProgramDashboardView(programDashboardState, programDashboardState.ctx);
  });

  const spaceId = String(state.activeSpace?.space_id || "no-space");
  loadStateForSpace(programDashboardState, spaceId);

  const programs = Array.isArray(state.programs) ? state.programs : [];
  if (!programs.length) {
    root.innerHTML = `
      <div class="program-dashboard-stage">
        <p class="view-breadcrumb">Insight / Program Dashboard</p>
        <h2>Program Dashboard</h2>
        <p class="program-dashboard-empty muted">Create a program before using this dashboard.</p>
      </div>
    `;
    return;
  }

  const programIds = new Set(programs.map((program) => String(program.program_id || "")));
  if (!programIds.has(programDashboardState.selectedProgramId)) {
    programDashboardState.selectedProgramId = String(programs[0]?.program_id || "");
    persistState(programDashboardState);
  }
  if (!VALID_TABS.has(programDashboardState.activeTab)) {
    programDashboardState.activeTab = "projects";
    persistState(programDashboardState);
  }

  const selectedProgram = programs.find((program) => String(program.program_id || "") === programDashboardState.selectedProgramId) || programs[0];
  const programParts = splitProgramName(selectedProgram?.program_name);
  const projects = (Array.isArray(state.projects) ? state.projects : [])
    .filter((project) => String(project.program_id || "") === String(selectedProgram.program_id || ""))
    .sort((a, b) => String(a.project_name || "").localeCompare(String(b.project_name || "")));
  const projectIds = new Set(projects.map((project) => String(project.project_id || "")));
  const projectById = new Map(projects.map((project) => [String(project.project_id || ""), project]));
  const allSolutions = (Array.isArray(state.solutions) ? state.solutions : [])
    .filter((solution) => projectIds.has(String(solution.project_id || "")))
    .sort((a, b) => String(a.solution_name || "").localeCompare(String(b.solution_name || "")));
  const solutionById = new Map(allSolutions.map((solution) => [String(solution.solution_id || ""), solution]));
  const solutionsByProject = new Map();
  allSolutions.forEach((solution) => {
    const key = String(solution.project_id || "");
    const rows = solutionsByProject.get(key) || [];
    rows.push(solution);
    solutionsByProject.set(key, rows);
  });

  const allProgramTasks = (Array.isArray(state.tasks) ? state.tasks : [])
    .filter((task) => projectIds.has(String(task.project_id || "")))
    .sort((a, b) => {
      const dueA = dateValue(a.due_date) || "9999-12-31";
      const dueB = dateValue(b.due_date) || "9999-12-31";
      return dueA.localeCompare(dueB) || String(a.task_name || "").localeCompare(String(b.task_name || ""));
    });
  const hideClosedTasks = typeof showCompletedOperationalWork === "function"
    ? !showCompletedOperationalWork()
    : true;
  const visibleTasks = hideClosedTasks
    ? allProgramTasks.filter((task) => !statusIsClosed(task.status))
    : allProgramTasks;
  const hiddenClosedCount = hideClosedTasks
    ? allProgramTasks.length - visibleTasks.length
    : 0;

  const activeSolutions = allSolutions.filter((solution) => !statusIsClosed(solution.status));
  const activeTasks = visibleTasks.filter((task) => !statusIsClosed(task.status));
  const activeTab = programDashboardState.activeTab;
  const tabRows = activeTab === "projects" ? allSolutions : visibleTasks;
  const completeCount = tabRows.filter((row) => normalize(row.status) === "complete").length;
  const notStartedCount = tabRows.filter((row) => {
    const status = normalize(row.status);
    return status === "not_started" || status === "to_do" || !status;
  }).length;
  const activeCount = activeTab === "projects"
    ? activeSolutions.filter((solution) => normalize(solution.status) === "active" || normalize(solution.status) === "in_progress").length
    : activeTasks.filter((task) => normalize(task.status) === "active" || normalize(task.status) === "in_progress").length;
  const progressForSolution = typeof solutionProgress === "function"
    ? solutionProgress
    : (solution) => (normalize(solution?.status) === "complete" ? 100 : 0);

  const bodyHtml = activeTab === "projects"
    ? renderProjectsTable({
      selectedProgram,
      projects,
      solutionsByProject,
      programParts,
      formatStatus,
      solutionProgress: progressForSolution,
    })
    : renderTasksTable({
      selectedProgram,
      tasks: visibleTasks,
      hiddenClosedCount,
      projectById,
      solutionById,
      programParts,
      formatStatus,
    });

  const activeSlide = deckSlideNumber(activeTab);
  const titleText = activeTab === "projects"
    ? `${programParts.team ? `${programParts.team} - ` : ""}${programParts.subArea || selectedProgram.program_name}`
    : `${programParts.subArea || selectedProgram.program_name} - Open Tasks & Milestones`;
  const subtitleText = activeTab === "projects"
    ? "Platform data pipeline and source onboarding projects"
    : "Granular task tracker for active data connections, entitlements, and enhancements";
  const crumbText = activeTab === "projects"
    ? `${programParts.team || "TAP"} - ${programParts.subArea || "Projects"}`
    : `${programParts.team || "TAP"} - ${programParts.subArea || "Data Sourcing"} - Open Tasks`;

  root.innerHTML = `
    <div class="program-dashboard-stage">
      <div class="program-dashboard-slide">
        <div class="program-dashboard-brandbar">
          <div class="program-dashboard-brand"><span>citi</span><i></i><strong>Project &amp; Solutions Dashboard</strong></div>
          <div class="program-dashboard-slide-path">${esc(crumbText)}</div>
        </div>
        <div class="program-dashboard-header">
          <div>
            <p class="program-dashboard-kicker">${esc(programParts.team || "Program")} &middot; ${esc(programParts.subArea || "Dashboard")}</p>
            <h2>${esc(titleText)}</h2>
            <p class="program-dashboard-subtitle">${esc(subtitleText)}</p>
          </div>
          <label class="program-dashboard-picker">
            <span>Program</span>
            <select data-program-dashboard-control="program">${programOptionMarkup(programs, String(selectedProgram.program_id || ""))}</select>
          </label>
        </div>
        <div class="program-dashboard-toolbar">
          ${renderSummary({
            activeTab,
            projectCount: projects.length,
            solutionCount: allSolutions.length,
            visibleCount: activeTab === "tasks" ? visibleTasks.length : projects.length,
            completeCount,
            activeCount,
            notStartedCount,
            hiddenClosedCount,
          })}
          <div class="program-dashboard-tabs" role="tablist" aria-label="Program dashboard views">
            <span class="program-dashboard-slide-count">Slide ${activeSlide} / 7</span>
            ${tabButton("projects", activeTab, "Projects & Solutions")}
            ${tabButton("tasks", activeTab, "Open Tasks")}
          </div>
        </div>
        ${bodyHtml}
        <div class="program-dashboard-slide-footer">
          <span>Slide ${activeSlide} of 7</span>
        </div>
      </div>
    </div>
  `;
}
