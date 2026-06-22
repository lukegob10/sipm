import { statusPillMarkup } from "../../utils/display-tokens.js";

const PREFS_KEY_PREFIX = "sipm-program-dashboard-v1";
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

function resolveApiBase(ctx) {
  if (typeof window === "undefined") return "/api";
  const configured = ctx?.apiBase || window.SIPM_API_BASE || "/api";
  return String(configured || "/api").replace(/\/$/, "");
}

function dateValue(value) {
  const raw = String(value || "").slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
}

function statusIsClosed(value) {
  return CLOSED_STATUSES.has(normalize(value));
}

function statusMarkup(value, formatStatus) {
  const label = typeof formatStatus === "function" ? formatStatus(value) : displayValue(value);
  return statusPillMarkup(value, label, "program-dashboard-status");
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
    selectedProgramIds: [],
    collapsedProgramIds: new Set(),
    collapsedProjectIds: new Set(),
  };
}

function loadStateForSpace(programDashboardState, spaceId) {
  if (programDashboardState.prefsSpaceId === spaceId) return;
  const prefs = readPrefs(spaceId);
  programDashboardState.prefsSpaceId = spaceId;
  programDashboardState.selectedProgramIds = Array.isArray(prefs.selectedProgramIds)
    ? prefs.selectedProgramIds.map((id) => String(id || "")).filter(Boolean)
    : [String(prefs.selectedProgramId || "")].filter(Boolean);
  programDashboardState.collapsedProgramIds = new Set(
    Array.isArray(prefs.collapsedProgramIds) ? prefs.collapsedProgramIds.map((id) => String(id || "")) : []
  );
  programDashboardState.collapsedProjectIds = new Set(
    Array.isArray(prefs.collapsedProjectIds) ? prefs.collapsedProjectIds.map((id) => String(id || "")) : []
  );
}

function persistState(programDashboardState) {
  writePrefs(programDashboardState.prefsSpaceId, {
    selectedProgramIds: Array.isArray(programDashboardState.selectedProgramIds)
      ? programDashboardState.selectedProgramIds
      : [],
    collapsedProgramIds: Array.from(programDashboardState.collapsedProgramIds || []),
    collapsedProjectIds: Array.from(programDashboardState.collapsedProjectIds || []),
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
    const checked = Array.from(viewRoot.querySelectorAll("[data-program-dashboard-control='program']"))
      .filter((input) => input instanceof HTMLInputElement && input.checked)
      .map((input) => String(input.value || ""))
      .filter(Boolean);
    programDashboardState.selectedProgramIds = checked;
    persistState(programDashboardState);
    rerender();
  });

  viewRoot.addEventListener("click", async (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-program-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-program-dashboard-action") || "";

    if (action === "toggle-program") {
      event.preventDefault();
      const programId = String(actionEl.getAttribute("data-program-id") || "");
      if (!programId) return;
      if (!(programDashboardState.collapsedProgramIds instanceof Set)) {
        programDashboardState.collapsedProgramIds = new Set();
      }
      if (programDashboardState.collapsedProgramIds.has(programId)) {
        programDashboardState.collapsedProgramIds.delete(programId);
      } else {
        programDashboardState.collapsedProgramIds.add(programId);
      }
      persistState(programDashboardState);
      rerender();
      return;
    }

    if (action === "toggle-project") {
      event.preventDefault();
      const projectId = String(actionEl.getAttribute("data-project-id") || "");
      if (!projectId) return;
      if (!(programDashboardState.collapsedProjectIds instanceof Set)) {
        programDashboardState.collapsedProjectIds = new Set();
      }
      if (programDashboardState.collapsedProjectIds.has(projectId)) {
        programDashboardState.collapsedProjectIds.delete(projectId);
      } else {
        programDashboardState.collapsedProjectIds.add(projectId);
      }
      persistState(programDashboardState);
      rerender();
      return;
    }

    if (action === "collapse-projects" || action === "expand-projects") {
      event.preventDefault();
      const projectIds = String(actionEl.getAttribute("data-project-ids") || "")
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean);
      const programIds = String(actionEl.getAttribute("data-program-ids") || "")
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean);
      programDashboardState.collapsedProgramIds = action === "collapse-projects" ? new Set(programIds) : new Set();
      programDashboardState.collapsedProjectIds = action === "collapse-projects" ? new Set(projectIds) : new Set();
      persistState(programDashboardState);
      rerender();
      return;
    }

    if (action === "download-pdf") {
      event.preventDefault();
      try {
        await downloadProgramDashboardPdf(programDashboardState);
        if (typeof programDashboardState.ctx?.trackWorkflow === "function") {
          programDashboardState.ctx.trackWorkflow("program_dashboard", "report_download", "success", {
            source: "program_dashboard",
          });
        }
      } catch (err) {
        if (typeof programDashboardState.ctx?.trackWorkflow === "function") {
          programDashboardState.ctx.trackWorkflow("program_dashboard", "report_download", "failure", {
            source: "program_dashboard",
          });
        }
        console.error("Program dashboard PDF download failed", err);
        programDashboardState.ctx?.setStatus?.(err?.message || "PDF download failed", "danger");
      }
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

  });
}

async function downloadProgramDashboardPdf(programDashboardState) {
  const ctx = programDashboardState.ctx || {};
  const activeSpaceId = ctx?.state?.activeSpace?.space_id || "";
  const publicSlug = String(ctx.publicSlug || "").trim();
  const isPublicMode = !!ctx.publicMode;
  const headers = { "Content-Type": "application/json" };
  if (!isPublicMode && activeSpaceId) headers["X-Space-Id"] = activeSpaceId;
  const reportUrl = isPublicMode
    ? `${resolveApiBase(ctx)}/public/program-dashboard/${encodeURIComponent(publicSlug)}/report.pdf`
    : `${resolveApiBase(ctx)}/programs/dashboard/report.pdf`;
  const response = await fetch(reportUrl, {
    method: "POST",
    headers,
    credentials: isPublicMode ? "omit" : "include",
    body: JSON.stringify({
      selected_program_ids: Array.isArray(programDashboardState.selectedProgramIds)
        ? programDashboardState.selectedProgramIds
        : [],
      collapsed_program_ids: Array.from(programDashboardState.collapsedProgramIds || []),
      collapsed_project_ids: Array.from(programDashboardState.collapsedProjectIds || []),
    }),
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
  const today = new Date().toISOString().slice(0, 10);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `program-dashboard-report-${today}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}

function programOptionMarkup(programs, selectedProgramIds) {
  const selectedIds = new Set(selectedProgramIds.map((id) => String(id || "")));
  return programs
    .map((program) => {
      const id = String(program.program_id || "");
      const checked = selectedIds.has(id) ? "checked" : "";
      const label = program.program_name || "Unnamed Program";
      return `<label class="program-dashboard-picker-option">
        <input type="checkbox" value="${esc(id)}" data-program-dashboard-control="program" ${checked} />
        <span>${esc(label)}</span>
      </label>`;
    })
    .join("");
}

function programPickerLabel(selectedPrograms) {
  if (selectedPrograms.length > 1) return "Multiple selected";
  return selectedPrograms[0]?.program_name || "Choose programs";
}

function programLabelMarkup(program) {
  return `<strong>${esc(displayValue(program?.program_name, "Unnamed Program"))}</strong>`;
}

function programToggleMarkup(program, collapsed, projectCount) {
  const id = String(program?.program_id || "");
  if (!id || !projectCount) return `<span class="program-dashboard-toggle-spacer" aria-hidden="true"></span>`;
  const label = collapsed ? "Expand program projects" : "Collapse program projects";
  return `<button type="button" class="program-dashboard-toggle" data-program-dashboard-action="toggle-program" data-program-id="${esc(id)}" aria-label="${label}: ${esc(program?.program_name || "Unnamed Program")}">${collapsed ? "+" : "-"}</button>`;
}

function projectLinkMarkup(project, readOnly = false) {
  const id = String(project?.project_id || "");
  const label = displayValue(project?.project_name, "Unnamed Project");
  if (!id || readOnly) return `<strong>${esc(label)}</strong>`;
  return `<button type="button" class="program-dashboard-link program-dashboard-project-link" data-program-dashboard-action="open-project" data-project-id="${esc(id)}">${esc(label)}</button>`;
}

function projectToggleMarkup(project, collapsed, solutionCount) {
  const id = String(project?.project_id || "");
  if (!id || !solutionCount) return `<span class="program-dashboard-toggle-spacer" aria-hidden="true"></span>`;
  const label = collapsed ? "Expand project deliverables" : "Collapse project deliverables";
  return `<button type="button" class="program-dashboard-toggle" data-program-dashboard-action="toggle-project" data-project-id="${esc(id)}" aria-label="${label}: ${esc(project?.project_name || "Unnamed Project")}">${collapsed ? "+" : "-"}</button>`;
}

function solutionLinkMarkup(solution, readOnly = false) {
  const id = String(solution?.solution_id || "");
  const label = displayValue(solution?.solution_name, "Unnamed Solution");
  if (!id || readOnly) return esc(label);
  return `<button type="button" class="program-dashboard-link program-dashboard-solution-link" data-program-dashboard-action="open-solution" data-solution-id="${esc(id)}">${esc(label)}</button>`;
}

function hierarchyLabelMarkup({ depth, rowType, toggleHtml, linkHtml }) {
  return `<div class="program-dashboard-label-content program-dashboard-depth-${esc(depth)} program-dashboard-row-${esc(rowType)}">
    <div class="program-dashboard-item-cell">
      ${toggleHtml || `<span class="program-dashboard-toggle-spacer" aria-hidden="true"></span>`}
      <span class="program-dashboard-level-marker" aria-hidden="true"></span>
      ${linkHtml}
    </div>
  </div>`;
}

const PROJECT_GRID_COLUMN_DEFS = [
  { key: "deliverable", label: "Deliverable", className: "program-dashboard-deliverable-cell" },
  { key: "owner", label: "Solution / Owner", className: "program-dashboard-owner-cell" },
  { key: "start", label: "Start", className: "program-dashboard-date-cell program-dashboard-start-cell" },
  { key: "end", label: "End", className: "program-dashboard-date-cell program-dashboard-end-cell" },
  { key: "status", label: "Status", className: "program-dashboard-status-cell" },
  { key: "phase", label: "Phase", className: "program-dashboard-phase-cell" },
  { key: "escalation", label: "Escalation", className: "program-dashboard-escalation-cell" },
  { key: "progress", label: "% Complete", className: "program-dashboard-progress-cell" },
];

function projectGridCell(column, content, role = "cell") {
  return `<div class="program-dashboard-grid-cell ${column.className}" role="${role}">${content ?? ""}</div>`;
}

function projectGridRow({ className, attrs = "", cells, role = "row", cellRole = "cell" }) {
  return `<div class="program-dashboard-grid-row ${className}" role="${role}" ${attrs}>
    ${PROJECT_GRID_COLUMN_DEFS.map((column) => projectGridCell(column, cells[column.key], cellRole)).join("")}
  </div>`;
}

function projectGridHeaderRow() {
  return projectGridRow({
    className: "program-dashboard-grid-header",
    role: "row",
    cellRole: "columnheader",
    cells: Object.fromEntries(PROJECT_GRID_COLUMN_DEFS.map((column) => [column.key, esc(column.label)])),
  });
}

function averageProgress(rows, solutionProgress) {
  if (!rows.length) return 0;
  const total = rows.reduce((sum, solution) => sum + Math.max(0, Math.min(100, Number(solutionProgress(solution)) || 0)), 0);
  return Math.round(total / rows.length);
}

function sortedDates(rows, key) {
  return rows.map((row) => dateValue(row?.[key])).filter(Boolean).sort();
}

function renderProjectsTable({
  programDashboardState,
  selectedProgram,
  selectedPrograms,
  projects,
  solutionsByProject,
  formatStatus,
  phaseDisplayName,
  solutionProgress,
  readOnly = false,
}) {
  if (!projects.length) {
    return `<p class="program-dashboard-empty muted">No projects are assigned to ${esc(selectedProgram.program_name || "the selected program")}.</p>`;
  }

  const collapsedProjectIds = programDashboardState.collapsedProjectIds instanceof Set
    ? programDashboardState.collapsedProjectIds
    : new Set();
  const collapsedProgramIds = programDashboardState.collapsedProgramIds instanceof Set
    ? programDashboardState.collapsedProgramIds
    : new Set();
  const projectsByProgram = new Map();
  projects.forEach((project) => {
    const programId = String(project.program_id || "");
    const rows = projectsByProgram.get(programId) || [];
    rows.push(project);
    projectsByProgram.set(programId, rows);
  });
  const programRows = (Array.isArray(selectedPrograms) ? selectedPrograms : [])
    .map((program) => ({
      program,
      projects: (projectsByProgram.get(String(program.program_id || "")) || [])
        .sort((a, b) => String(a.project_name || "").localeCompare(String(b.project_name || ""))),
    }))
    .filter((row) => row.projects.length);
  const rowsHtml = programRows
    .map(({ program, projects: programProjects }) => {
      const programId = String(program.program_id || "");
      const programCollapsed = collapsedProgramIds.has(programId);
      const programSolutions = programProjects.flatMap((project) => solutionsByProject.get(String(project.project_id || "")) || []);
      const programStartDates = sortedDates(programSolutions, "planned_start_date");
      const programEndDates = sortedDates(programSolutions, "due_date");
      const programRow = projectGridRow({
        className: `program-dashboard-program-row ${programCollapsed ? "program-dashboard-program-row-collapsed" : ""}`,
        attrs: `data-program-dashboard-program-id="${esc(programId)}"`,
        cells: {
          deliverable: hierarchyLabelMarkup({
            depth: 1,
            rowType: "program",
            toggleHtml: programToggleMarkup(program, programCollapsed, programProjects.length),
            linkHtml: programLabelMarkup(program),
          }),
          owner: "-",
          start: esc(programStartDates[0] || "-"),
          end: esc(programEndDates[programEndDates.length - 1] || "-"),
          status: "-",
          phase: "-",
          escalation: "",
          progress: progressMarkup(averageProgress(programSolutions, solutionProgress)),
        },
      });
      const projectRows = programCollapsed
        ? ""
        : programProjects.map((project) => {
          const projectId = String(project.project_id || "");
          const projectSolutions = solutionsByProject.get(String(project.project_id || "")) || [];
          const collapsed = collapsedProjectIds.has(projectId);
          const startDates = sortedDates(projectSolutions, "planned_start_date");
          const endDates = sortedDates(projectSolutions, "due_date");
          const projectStart = startDates[0] || "-";
          const projectEnd = endDates[endDates.length - 1] || "-";
          const progress = projectSolutions.length
            ? averageProgress(projectSolutions, solutionProgress)
            : (normalize(project.status) === "complete" ? 100 : 0);
          const projectRow = projectGridRow({
            className: `program-dashboard-group-row program-dashboard-project-row ${collapsed ? "program-dashboard-group-row-collapsed" : ""}`,
            attrs: `data-program-dashboard-project-id="${esc(projectId)}"`,
            cells: {
              deliverable: hierarchyLabelMarkup({
                depth: 2,
                rowType: "project",
                toggleHtml: projectToggleMarkup(project, collapsed, projectSolutions.length),
                linkHtml: projectLinkMarkup(project, readOnly),
              }),
              owner: esc(displayValue(project.sponsor || project.sponsor_user_soeid)),
              start: esc(projectStart),
              end: esc(projectEnd),
              status: statusMarkup(project.status, formatStatus),
              phase: "-",
              escalation: "",
              progress: progressMarkup(progress),
            },
          });
          const solutionRows = collapsed
            ? ""
            : projectSolutions
              .map((solution) => projectGridRow({
                  className: "program-dashboard-child-row",
                  attrs: `data-program-dashboard-solution-id="${esc(solution.solution_id || "")}"`,
                  cells: {
                    deliverable: hierarchyLabelMarkup({
                      depth: 3,
                      rowType: "solution",
                      toggleHtml: "",
                      linkHtml: solutionLinkMarkup(solution, readOnly),
                    }),
                    owner: esc(displayValue(solution.owner || solution.owner_user_soeid || solution.assignee || solution.key_stakeholder)),
                    start: esc(displayValue(dateValue(solution.planned_start_date))),
                    end: esc(displayValue(dateValue(solution.due_date))),
                    status: statusMarkup(solution.status, formatStatus),
                    phase: esc(displayValue(phaseDisplayName(solution.current_phase))),
                    escalation: esc(displayValue(solution.escalation, "")),
                    progress: progressMarkup(solutionProgress(solution)),
                  },
                }))
              .join("");
          return `${projectRow}${solutionRows}`;
        })
          .join("");
      return `${programRow}${projectRows}`;
    })
    .join("");
  const projectIds = projects.map((project) => String(project.project_id || "")).filter(Boolean);
  const programIds = programRows.map((row) => String(row.program?.program_id || "")).filter(Boolean);

  return `
    <div class="program-dashboard-table-shell program-dashboard-project-grid-shell">
      <div class="program-dashboard-table-actions">
        <button type="button" class="program-dashboard-table-action" data-program-dashboard-action="expand-projects">Expand All</button>
        <button type="button" class="program-dashboard-table-action" data-program-dashboard-action="collapse-projects" data-program-ids="${esc(programIds.join(","))}" data-project-ids="${esc(projectIds.join(","))}">Collapse All</button>
        <button type="button" class="program-dashboard-table-action" data-program-dashboard-action="download-pdf">Download PDF</button>
      </div>
      <div class="program-dashboard-project-grid" role="table" aria-label="Projects and solutions">
        ${projectGridHeaderRow()}
        ${rowsHtml}
      </div>
    </div>
  `;
}

function renderSummary({ projectCount, solutionCount, completeCount, activeCount, notStartedCount }) {
  return `
    <div class="program-dashboard-summary">
      <span>${projectCount} projects</span>
      <span>${solutionCount} solutions</span>
      <span><strong>${activeCount}</strong> active</span>
      <span><strong>${completeCount}</strong> complete</span>
      <span><strong>${notStartedCount}</strong> not started</span>
    </div>
  `;
}

export function renderProgramDashboardView(programDashboardState, ctx) {
  const { state, els, formatStatus, phaseDisplayName, solutionProgress } = ctx;
  const readOnly = !!(ctx.readOnly || ctx.publicMode);
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
        <p class="program-dashboard-empty muted">Create a program before using this dashboard.</p>
      </div>
    `;
    return;
  }

  const programIds = new Set(programs.map((program) => String(program.program_id || "")));
  const validSelectedProgramIds = (Array.isArray(programDashboardState.selectedProgramIds) ? programDashboardState.selectedProgramIds : [])
    .map((id) => String(id || ""))
    .filter((id) => programIds.has(id));
  if (!validSelectedProgramIds.length) {
    validSelectedProgramIds.push(String(programs[0]?.program_id || ""));
  }
  if (validSelectedProgramIds.join("|") !== (programDashboardState.selectedProgramIds || []).join("|")) {
    programDashboardState.selectedProgramIds = validSelectedProgramIds;
    persistState(programDashboardState);
  }

  const selectedProgramIdSet = new Set(validSelectedProgramIds);
  const selectedPrograms = programs.filter((program) => selectedProgramIdSet.has(String(program.program_id || "")));
  const selectedProgram = selectedPrograms[0] || programs[0];
  const multipleProgramsSelected = selectedPrograms.length > 1;
  const programParts = splitProgramName(selectedProgram?.program_name);
  const projects = (Array.isArray(state.projects) ? state.projects : [])
    .filter((project) => selectedProgramIdSet.has(String(project.program_id || "")))
    .sort((a, b) => String(a.project_name || "").localeCompare(String(b.project_name || "")));
  const projectIds = new Set(projects.map((project) => String(project.project_id || "")));
  const allSolutions = (Array.isArray(state.solutions) ? state.solutions : [])
    .filter((solution) => projectIds.has(String(solution.project_id || "")))
    .sort((a, b) => String(a.solution_name || "").localeCompare(String(b.solution_name || "")));
  const solutionsByProject = new Map();
  allSolutions.forEach((solution) => {
    const key = String(solution.project_id || "");
    const rows = solutionsByProject.get(key) || [];
    rows.push(solution);
    solutionsByProject.set(key, rows);
  });

  const activeSolutions = allSolutions.filter((solution) => !statusIsClosed(solution.status));
  const completeCount = allSolutions.filter((row) => normalize(row.status) === "complete").length;
  const notStartedCount = allSolutions.filter((row) => {
    const status = normalize(row.status);
    return status === "not_started" || status === "to_do" || !status;
  }).length;
  const activeCount = activeSolutions.filter((solution) => normalize(solution.status) === "active" || normalize(solution.status) === "in_progress").length;
  const progressForSolution = typeof solutionProgress === "function"
    ? solutionProgress
    : (solution) => (normalize(solution?.status) === "complete" ? 100 : 0);
  const displayPhase = typeof phaseDisplayName === "function"
    ? phaseDisplayName
    : (phaseId) => displayValue(phaseId);

  const bodyHtml = renderProjectsTable({
    programDashboardState,
    selectedProgram: multipleProgramsSelected ? { program_name: "the selected programs" } : selectedProgram,
    selectedPrograms,
    projects,
    solutionsByProject,
    formatStatus,
    phaseDisplayName: displayPhase,
    solutionProgress: progressForSolution,
    readOnly,
  });

  const titleText = multipleProgramsSelected
    ? "Program Dashboard"
    : `${programParts.team ? `${programParts.team} - ` : ""}${programParts.subArea || selectedProgram.program_name}`;
  const subtitleText = "Platform data pipeline and source onboarding projects";

  root.innerHTML = `
    <div class="program-dashboard-stage">
      <div class="program-dashboard-slide product-surface">
        <div class="program-dashboard-header">
          <div>
            <p class="program-dashboard-kicker">${esc(multipleProgramsSelected ? "Program" : (programParts.team || "Program"))} &middot; ${esc(multipleProgramsSelected ? "Dashboard" : (programParts.subArea || "Dashboard"))}</p>
            <h2>${esc(titleText)}</h2>
            <p class="program-dashboard-subtitle">${esc(subtitleText)}</p>
          </div>
          <div class="program-dashboard-picker">
            <span>Program</span>
            <details class="program-dashboard-picker-menu">
              <summary>${esc(programPickerLabel(selectedPrograms))}</summary>
              <div class="program-dashboard-picker-options">
                ${programOptionMarkup(programs, validSelectedProgramIds)}
              </div>
            </details>
          </div>
        </div>
        <div class="program-dashboard-toolbar">
          ${renderSummary({
            projectCount: projects.length,
            solutionCount: allSolutions.length,
            completeCount,
            activeCount,
            notStartedCount,
          })}
        </div>
        ${bodyHtml}
      </div>
    </div>
  `;
}
