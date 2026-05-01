import {
  applyScope,
  clamp,
  createColumnDefinitions,
  currentUserTokens,
  daysAgo,
  daysUntil,
  formatFte,
  isClosedStatus,
  isOwnedByCurrentUser,
  normalize,
  parseDate,
  renderSectionTable,
  riskScoreForSolution,
  solutionFte,
  sortRows,
  startOfDay,
  userCapacityFte,
  viewportRowBudget,
} from "./common.js";
import {
  applySectionSolutionFilter,
  buildSectionOptions,
  createDashboardState,
  ensurePrefsLoaded,
  getSectionPrefs,
  normalizeSectionSolutionSelections,
  selectedColumnsForSection,
} from "./prefs.js";
import { bindDashboardEvents } from "./interactions.js";
import { renderDashboardConfigButton, renderDashboardConfigModal } from "./modal.js";

function renderDashboardSectionTable(dashboardState, { sectionId, rows, columnDefs, tableClass, emptyText }) {
  return renderSectionTable({
    columns: selectedColumnsForSection(dashboardState, sectionId, columnDefs),
    rows,
    columnDefs,
    tableClass,
    emptyText,
  });
}

export function renderDashboardView(dashboardState, ctx) {
  const { state, els, formatStatus } = ctx;
  dashboardState.ctx = ctx;
  ensurePrefsLoaded(dashboardState, state.activeSpace?.space_id || "no-space");
  bindDashboardEvents(dashboardState, () => {
    if (dashboardState.ctx) renderDashboardView(dashboardState, dashboardState.ctx);
  });

  const prefs = dashboardState.prefs;
  const today = startOfDay(new Date());

  const projects = Array.isArray(state.projects) ? state.projects : [];
  const solutions = Array.isArray(state.solutions) ? state.solutions : [];
  const subcomponents = Array.isArray(state.subcomponents) ? state.subcomponents : [];
  const users = Array.isArray(state.users) ? state.users : [];

  const projectNameById = new Map(
    projects.map((project) => [String(project.project_id || ""), String(project.project_name || "Unnamed Project")])
  );
  const subcomponentsBySolution = new Map();
  subcomponents.forEach((subcomponent) => {
    const solutionId = String(subcomponent.solution_id || "");
    if (!solutionId) return;
    const bucket = subcomponentsBySolution.get(solutionId) || [];
    bucket.push(subcomponent);
    subcomponentsBySolution.set(solutionId, bucket);
  });

  const myTokens = currentUserTokens(state);

  const solutionRows = solutions
    .map((solution) => {
      const solutionId = String(solution.solution_id || "");
      const linked = subcomponentsBySolution.get(solutionId) || [];
      const openLinked = linked.filter((subcomponent) => !isClosedStatus(subcomponent.status));
      const blockedTasks = openLinked.filter((subcomponent) => !!subcomponent.blocked).length;
      const unassignedTasks = openLinked.filter(
        (subcomponent) => !normalize(subcomponent.assignee) && !normalize(subcomponent.assignee_user_soeid)
      ).length;

      const dueDate = parseDate(solution.due_date);
      const dueDays = dueDate ? daysUntil(today, dueDate) : Number.NaN;
      const completedDate = parseDate(solution.completed_at) || parseDate(solution.updated_at);
      const row = {
        solutionId,
        projectId: String(solution.project_id || ""),
        projectName: projectNameById.get(String(solution.project_id || "")) || "Unmapped Project",
        solutionName: String(solution.solution_name || "Unnamed Solution"),
        stakeholder: String(solution.key_stakeholder || solution.owner || solution.owner_user_soeid || "Unassigned"),
        owner: String(solution.owner || solution.owner_user_soeid || "Unassigned"),
        ownerUser: String(solution.owner_user_soeid || ""),
        status: normalize(solution.status),
        statusRaw: String(solution.status || ""),
        rag_status: String(solution.rag_status || ""),
        fte: solutionFte(solution),
        dueDate,
        dueDateLabel: dueDate ? dueDate.toISOString().slice(0, 10) : "-",
        dueDays,
        openTasks: openLinked.length,
        blockedTasks,
        unassignedTasks,
        isClosed: isClosedStatus(solution.status),
        isMine: isOwnedByCurrentUser(solution, myTokens),
        completedDate,
        completedDateLabel: completedDate ? completedDate.toISOString().slice(0, 10) : "-",
        horizonDays: prefs.horizon_days,
      };
      row.riskScore = riskScoreForSolution(row);
      return row;
    })
    .filter((row) => row.solutionId);

  const activeRows = solutionRows.filter((row) => !row.isClosed);
  const isWorkingRow = (row) => row.status === "in_progress" || row.status === "active" || row.status === "on_hold";

  const totalSpaceCapacity = users
    .filter((user) => user && user.is_active !== false)
    .reduce((sum, user) => sum + userCapacityFte(user), 0);
  const workingRows = activeRows
    .filter((row) => isWorkingRow(row))
    .sort((a, b) => {
      const dueA = Number.isFinite(a.dueDays) ? a.dueDays : Number.POSITIVE_INFINITY;
      const dueB = Number.isFinite(b.dueDays) ? b.dueDays : Number.POSITIVE_INFINITY;
      return dueA - dueB || b.riskScore - a.riskScore;
    });
  const upcomingCandidates = activeRows
    .filter((row) => !isWorkingRow(row))
    .sort((a, b) => {
      const dueA = Number.isFinite(a.dueDays) ? a.dueDays : Number.POSITIVE_INFINITY;
      const dueB = Number.isFinite(b.dueDays) ? b.dueDays : Number.POSITIVE_INFINITY;
      return dueA - dueB || b.riskScore - a.riskScore || b.fte - a.fte;
    });
  const workingDemand = workingRows.reduce((sum, row) => sum + row.fte, 0);
  const utilizationPct = totalSpaceCapacity > 0 ? (workingDemand / totalSpaceCapacity) * 100 : 0;
  const headroom = Math.max(0, totalSpaceCapacity - workingDemand);

  const scheduledRows = [];
  const deferredRows = [];
  let scheduledDemand = 0;
  upcomingCandidates.forEach((row) => {
    const demand = Math.max(0, row.fte);
    if (demand <= 0 || scheduledDemand + demand <= headroom + 1e-9) {
      scheduledRows.push(row);
      scheduledDemand += demand;
      return;
    }
    deferredRows.push({ row, shortfall: scheduledDemand + demand - headroom });
  });
  const deferredDemand = deferredRows.reduce((sum, item) => sum + Math.max(0, item.row.fte), 0);

  const scopedRows = applyScope(solutionRows, prefs.scope);
  const sortedScopedRows = sortRows(scopedRows, prefs.sort);
  const rowBudget = viewportRowBudget();
  const supportRows = rowBudget.secondary;

  const completedAllRows = solutionRows
    .filter((row) => row.status === "complete" && row.completedDate)
    .filter((row) => daysAgo(today, row.completedDate) <= prefs.horizon_days)
    .sort((a, b) => (b.completedDate?.getTime() || 0) - (a.completedDate?.getTime() || 0));
  const completedRows = applySectionSolutionFilter(
    dashboardState,
    completedAllRows,
    "completed",
    (row) => row.solutionId
  ).slice(0, supportRows);

  const upcomingAllRows = [];
  const upcomingSeen = new Set();
  for (const row of workingRows) {
    if (upcomingSeen.has(row.solutionId)) continue;
    upcomingAllRows.push({ row, stage: "Working" });
    upcomingSeen.add(row.solutionId);
  }
  for (const row of scheduledRows) {
    if (upcomingSeen.has(row.solutionId)) continue;
    upcomingAllRows.push({ row, stage: "Coming" });
    upcomingSeen.add(row.solutionId);
  }
  const upcomingRows = applySectionSolutionFilter(
    dashboardState,
    upcomingAllRows,
    "upcoming",
    (entry) => entry.row.solutionId
  )
    .slice(0, supportRows)
    .map((entry) => ({ ...entry.row, stage: entry.stage }));

  const backlogRows = applySectionSolutionFilter(
    dashboardState,
    deferredRows,
    "backlog",
    (entry) => entry.row.solutionId
  )
    .slice(0, supportRows)
    .map((entry) => ({ ...entry.row, shortfall: entry.shortfall }));

  dashboardState.sectionOptions = {
    main: buildSectionOptions(sortedScopedRows),
    completed: buildSectionOptions(completedAllRows),
    upcoming: buildSectionOptions(upcomingAllRows, (entry) => entry.row),
    backlog: buildSectionOptions(deferredRows, (entry) => entry.row),
  };
  normalizeSectionSolutionSelections(dashboardState, dashboardState.sectionOptions);

  const filteredMainRows = applySectionSolutionFilter(dashboardState, sortedScopedRows, "main", (row) => row.solutionId);
  const scopedActiveRows = scopedRows.filter((row) => !row.isClosed);
  const scopedAtRiskRows = scopedActiveRows.filter((row) => row.riskScore >= 45);
  const scopedOverdueRows = scopedActiveRows.filter((row) => Number.isFinite(row.dueDays) && row.dueDays < 0);
  const mainRows = filteredMainRows.slice(0, Math.min(prefs.rows, rowBudget.main));

  const formatStatusLabel = (value) => {
    if (typeof formatStatus === "function") return formatStatus(value);
    return String(value || "-");
  };
  const columnDefsBySection = createColumnDefinitions(formatStatusLabel);
  dashboardState.columnDefsBySection = columnDefsBySection;

  if (dashboardState.modalSection) {
    renderDashboardConfigModal(dashboardState, dashboardState.modalSection, { columnDefsBySection });
  }

  if (els.dashboardSpaceCapacity) {
    const utilClass = utilizationPct >= 100 ? "danger" : utilizationPct >= 85 ? "warn" : "positive";
    const utilWidth = clamp(utilizationPct, 0, 140);
    els.dashboardSpaceCapacity.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Space Snapshot</h3>
          <p class="dashboard-card-sub">Executive capacity summary for the current solution view.</p>
        </div>
      </div>
      <div class="dashboard-capacity-lines">
        <div class="dashboard-capacity-line"><span>Total Capacity</span><strong>${formatFte(totalSpaceCapacity)} FTE-mo</strong></div>
        <div class="dashboard-capacity-line"><span>Working Now</span><strong>${formatFte(workingDemand)} FTE-mo</strong></div>
        <div class="dashboard-capacity-line"><span>Coming (Fits FTE)</span><strong>${formatFte(scheduledDemand)} FTE-mo</strong></div>
        <div class="dashboard-capacity-line"><span>Backlog (Outside FTE)</span><strong>${formatFte(deferredDemand)} FTE-mo</strong></div>
      </div>
      <div class="dashboard-util-wrap">
        <div class="dashboard-util-bar" role="img" aria-label="Capacity utilization ${Math.round(utilizationPct)} percent">
          <span class="${utilClass}" style="width:${utilWidth}%;"></span>
        </div>
        <div class="dashboard-util-meta">Utilization ${utilizationPct.toFixed(1)}% · Headroom ${formatFte(headroom)} FTE-mo</div>
      </div>
    `;
  }

  if (els.dashboardTopProjects) {
    const includedText = Array.isArray(getSectionPrefs(dashboardState, "main").solution_ids)
      ? `${filteredMainRows.length} included`
      : `${filteredMainRows.length} in scope`;
    els.dashboardTopProjects.innerHTML = `
      <div class="dashboard-main-head">
        <div class="dashboard-title-block">
          <h3>Current Deliverables</h3>
          <p class="dashboard-card-sub">Executive view of priority solutions and delivery pressure.</p>
        </div>
        ${renderDashboardConfigButton()}
      </div>
      <p class="dashboard-main-meta">
        ${mainRows.length} shown · ${includedText} · ${scopedAtRiskRows.length} at risk · ${scopedOverdueRows.length} overdue
      </p>
      ${renderDashboardSectionTable(dashboardState, {
        sectionId: "main",
        rows: mainRows,
        columnDefs: columnDefsBySection.main,
        tableClass: "dashboard-main-table",
        emptyText: "No solutions match the selected scope and inclusion list.",
      })}
    `;
  }

  if (els.dashboardCompletedQuarter) {
    els.dashboardCompletedQuarter.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Complete</h3>
          <p class="dashboard-card-sub">Solutions completed in the last ${prefs.horizon_days} days.</p>
        </div>
      </div>
      ${renderDashboardSectionTable(dashboardState, {
        sectionId: "completed",
        rows: completedRows,
        columnDefs: columnDefsBySection.completed,
        tableClass: "dashboard-mini-table",
        emptyText: `No completed items in the last ${prefs.horizon_days} days.`,
      })}
    `;
  }

  if (els.dashboardUpcomingQuarter) {
    els.dashboardUpcomingQuarter.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Upcoming</h3>
          <p class="dashboard-card-sub">Solutions in progress and upcoming work that fits available capacity.</p>
        </div>
      </div>
      ${renderDashboardSectionTable(dashboardState, {
        sectionId: "upcoming",
        rows: upcomingRows,
        columnDefs: columnDefsBySection.upcoming,
        tableClass: "dashboard-mini-table",
        emptyText: "No working or upcoming items to show.",
      })}
    `;
  }

  if (els.dashboardBacklog) {
    els.dashboardBacklog.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Backlog</h3>
          <p class="dashboard-card-sub">Solutions outside current capacity headroom (${formatFte(deferredDemand)} FTE-mo).</p>
        </div>
      </div>
      ${renderDashboardSectionTable(dashboardState, {
        sectionId: "backlog",
        rows: backlogRows,
        columnDefs: columnDefsBySection.backlog,
        tableClass: "dashboard-mini-table",
        emptyText: "No backlog outside current FTE headroom.",
      })}
    `;
  }
}

export { createDashboardState };
