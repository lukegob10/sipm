import { ragTone, statusTone } from "../../utils/display-tokens.js";

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numericOrNull(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && !value.trim()) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function solutionFteMonths(solution) {
  const HOURS_PER_FTE_MONTH = 160;
  const direct = numericOrNull(solution?.capacity_fte_months);
  if (direct != null) return Math.max(direct, 0);
  const hours = numericOrNull(solution?.capacity_hours);
  if (hours != null) return Math.max(hours, 0) / HOURS_PER_FTE_MONTH;
  return 0;
}

function renderProjectNameLink(label, projectId) {
  const text = String(label || "").trim() || "-";
  const targetId = String(projectId || "").trim();
  if (!targetId) return esc(text);
  return `<button type="button" class="deliverables-name-link deliverables-name-link-project" data-action="edit" data-type="project" data-id="${esc(targetId)}">${esc(text)}</button>`;
}

function renderProgramNameLink(label, programId) {
  const text = String(label || "").trim() || "Unassigned Program";
  const targetId = String(programId || "").trim();
  if (!targetId || targetId === "__unassigned__") return esc(text);
  return `<button type="button" class="deliverables-name-link deliverables-name-link-program" data-action="edit" data-type="program" data-id="${esc(targetId)}">${esc(text)}</button>`;
}

function renderSolutionNameLink(label, solutionId) {
  const text = String(label || "").trim() || "-";
  const targetId = String(solutionId || "").trim();
  if (!targetId) return esc(text);
  return `<button type="button" class="deliverables-name-link deliverables-name-link-solution" data-action="edit" data-type="solution" data-id="${esc(targetId)}">${esc(text)}</button>`;
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function collapseKey(kind, id, fallback = "") {
  const target = String(id || fallback || "").trim() || "__missing__";
  return `${kind}:${target}`;
}

function collapsedSet(state) {
  return state.masterCollapsed instanceof Set ? state.masterCollapsed : new Set();
}

function renderOutlineToggle(key, collapsed, label) {
  const action = collapsed ? "Expand" : "Collapse";
  const iconPath = collapsed ? "M9 6l6 6-6 6" : "M6 9l6 6 6-6";
  return `<button type="button" class="master-outline-toggle master-tree-toggle" data-action="toggle-master-collapse" data-master-collapse-key="${esc(key)}" aria-expanded="${collapsed ? "false" : "true"}" aria-label="${action} ${esc(label)}" title="${action}"><svg class="master-tree-toggle-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${iconPath}"></path></svg></button>`;
}

function renderOutlineSummary(parts) {
  const summary = parts.filter(Boolean).join(" | ");
  return summary ? `<span class="deliverable-outline-summary">${esc(summary)}</span>` : "";
}

const editIconSvg = '<svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 20h4l10.5-10.5-4-4L4 16v4z"></path><path d="M13.5 6.5l4 4"></path></svg>';
const addIconSvg = '<svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>';

export function buildMasterTable(ctx) {
  const {
    state,
    filteredDeliverables,
    phaseDisplayName,
    formatStatus,
    solutionProgress,
  } = ctx;
  const rows = filteredDeliverables();
  const colgroup = `<colgroup>
      <col class="deliverable-solution"><col class="deliverable-version"><col class="deliverable-owner">
      <col class="deliverable-phase"><col class="deliverable-priority"><col class="deliverable-due"><col class="deliverable-fte"><col class="deliverable-rag">
      <col class="deliverable-status"><col class="deliverable-progress"><col class="deliverable-actions">
    </colgroup>`;
  let html = `
    <table class="deliverables-table">${colgroup}
      <thead>
        <tr>
          <th class="deliverable-tree-header" aria-label="Program, project, and deliverable tree"></th>
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
      </thead>
      <tbody>`;
  let visibleRows = 0;
  let programCollapsed = false;
  let projectCollapsed = false;
  const searchActive = String(state.filters?.query || "").trim().length > 0;
  rows.forEach((row) => {
    if (row.type === "program-header") {
      const key = collapseKey("program", row.program?.program_id, row.programKey);
      programCollapsed = !searchActive && collapsedSet(state).has(key);
      projectCollapsed = false;
      visibleRows += 1;
      const programLabel = row.program?.program_name || "Unassigned Program";
      html += `<tr class="deliverable-outline-row deliverable-row-program-header" data-master-row-key="${esc(key)}">
      <td colspan="11">
        <div class="deliverable-program-band deliverable-tree-depth-program">
          <div class="deliverable-outline-main">
            ${renderOutlineToggle(key, programCollapsed, programLabel)}
            <div class="deliverable-outline-title">
              <span class="deliverable-outline-kicker">Program</span>
              <span class="deliverable-outline-name deliverable-outline-name-program">${renderProgramNameLink(programLabel, row.program?.program_id)}</span>
            </div>
          </div>
          ${renderOutlineSummary([
            pluralize(Number(row.projectCount || 0), "project"),
            pluralize(Number(row.solutionCount || 0), "solution"),
            pluralize(Number(row.atRiskCount || 0), "at risk", "at risk"),
            pluralize(Number(row.dueSoonCount || 0), "due soon", "due soon"),
          ])}
        </div>
      </td>
    </tr>`;
      return;
    }

    if (programCollapsed) return;

    if (row.type === "project-header") {
      const key = collapseKey("project", row.project?.project_id, row.projectKey);
      projectCollapsed = !searchActive && collapsedSet(state).has(key);
      const statusLabel = typeof formatStatus === "function" ? formatStatus(row.project?.status) : row.project?.status;
      const solutionCount = Number(row.solutionCount || 0);
      visibleRows += 1;
      const projectLabel = row.project?.project_name || "Unassigned Project";
      html += `<tr class="deliverable-outline-row deliverable-row-project-header" data-master-row-key="${esc(key)}">
      <td colspan="11">
        <div class="deliverable-project-band deliverable-tree-depth-project">
          <div class="deliverable-outline-main">
            ${renderOutlineToggle(key, projectCollapsed, projectLabel)}
            <div class="deliverable-outline-title">
              <span class="deliverable-outline-kicker">Project</span>
              <span class="deliverable-outline-name deliverable-outline-name-project">${renderProjectNameLink(projectLabel, row.project?.project_id)}</span>
            </div>
          </div>
          ${renderOutlineSummary([
            statusLabel || "-",
            pluralize(solutionCount, "solution"),
            `${Number(row.progress || 0)}% avg`,
            `P${row.project?.priority ?? "-"}`,
            row.project?.owner || row.project?.owner_user_soeid || "No owner",
          ])}
        </div>
      </td>
    </tr>`;
      return;
    }

    if (projectCollapsed) return;

    const solution = row.solution;
    const itemId = solution.solution_id;
    const priorityValue = solution.priority;
    const statusValue = solution.status;
    const normalizedRag = String(solution.rag_status || "green").toLowerCase();
    const ragValue = normalizedRag === "red" || normalizedRag === "amber" ? normalizedRag : "green";
    const ragToneClass = `rag-${ragValue} ${ragTone(ragValue)}`;
    const safeSolutionId = esc(itemId);
    const ragCell = `<select class="inline-select rag-select ${ragToneClass}" data-rag-state="${ragValue}" data-field="rag_status" data-type="solution" data-id="${safeSolutionId}">
          <option value="amber" ${ragValue === "amber" ? "selected" : ""}>Amber</option>
          <option value="red" ${ragValue === "red" ? "selected" : ""}>Red</option>
          <option value="green" ${ragValue === "green" ? "selected" : ""}>Green</option>
        </select>`;
    const fteMonthsCell = solutionFteMonths(solution).toFixed(2);
    const statusState = String(statusValue || "").toLowerCase();
    const statusCell = `<select class="inline-select status-select ${statusTone(statusState)}" data-status-state="${esc(statusState)}" data-field="status" data-type="solution" data-id="${safeSolutionId}">
        <option value="not_started" ${statusValue === "not_started" ? "selected" : ""}>Not started</option>
        <option value="active" ${statusValue === "active" ? "selected" : ""}>Active</option>
        <option value="on_hold" ${statusValue === "on_hold" ? "selected" : ""}>On hold</option>
        <option value="complete" ${statusValue === "complete" ? "selected" : ""}>Complete</option>
        <option value="abandoned" ${statusValue === "abandoned" ? "selected" : ""}>Abandoned</option>
      </select>`;
    const deliverableActions = `<div class="deliverable-actions">
        <button type="button" class="icon-btn" data-action="edit" data-type="solution" data-id="${safeSolutionId}" aria-label="Edit solution" title="Edit" data-tooltip="Edit">${editIconSvg}</button>
        <button type="button" class="icon-btn" data-action="add-task" data-type="solution" data-id="${safeSolutionId}" aria-label="Add task" title="Add task" data-tooltip="Add task">${addIconSvg}</button>
      </div>`;
    visibleRows += 1;
    html += `<tr class="deliverable-row deliverable-row-solution">
      <td class="deliverable-solution-tree-cell deliverable-tree-depth-solution">${renderSolutionNameLink(solution?.solution_name, solution?.solution_id)}</td>
      <td>${esc(solution?.version || "-")}</td>
      <td>${esc(solution?.owner || "-")}</td>
      <td>${esc(phaseDisplayName(solution.current_phase) || "-")}</td>
      <td><input class="inline-input inline-input-priority" type="number" min="0" max="5" data-field="priority" data-type="solution" data-id="${safeSolutionId}" value="${esc(priorityValue ?? "")}" /></td>
      <td>${esc(solution.due_date || "")}</td>
      <td>${fteMonthsCell}</td>
      <td>${ragCell}</td>
      <td>${statusCell}</td>
      <td>${esc(solutionProgress(solution))}%</td>
      <td>${deliverableActions}</td>
    </tr>`;
  });
  html += "</tbody></table>";
  return { html, rowCount: visibleRows };
}

export function bindMasterTableInteractions(ctx) {
  void ctx;
}
