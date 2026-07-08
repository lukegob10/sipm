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

function sectionPage(dashboardState, sectionId, rowCount, pageSize) {
  dashboardState.pages = dashboardState.pages || {};
  const totalPages = Math.max(1, Math.ceil(Math.max(0, rowCount) / Math.max(1, pageSize)));
  const currentPage = clamp(Math.round(Number(dashboardState.pages[sectionId]) || 1), 1, totalPages);
  dashboardState.pages[sectionId] = currentPage;
  return currentPage;
}

function paginateSectionRows(dashboardState, sectionId, rows, pageSize) {
  const safePageSize = Math.max(1, pageSize);
  const page = sectionPage(dashboardState, sectionId, rows.length, safePageSize);
  const start = (page - 1) * safePageSize;
  return {
    page,
    pageSize: safePageSize,
    totalPages: Math.max(1, Math.ceil(rows.length / safePageSize)),
    totalRows: rows.length,
    rows: rows.slice(start, start + safePageSize),
  };
}

function renderDashboardPagination(sectionId, pagination) {
  if (!pagination || pagination.totalPages <= 1) return "";
  const from = (pagination.page - 1) * pagination.pageSize + 1;
  const to = Math.min(pagination.totalRows, pagination.page * pagination.pageSize);
  return `
    <div class="dashboard-pagination" aria-label="${sectionId} pagination">
      <button type="button" class="dashboard-page-btn" data-dashboard-action="page" data-dashboard-section="${sectionId}" data-dashboard-page-direction="prev"${pagination.page <= 1 ? " disabled" : ""} aria-label="Previous page">&lsaquo;</button>
      <span class="dashboard-page-status">Page ${pagination.page} of ${pagination.totalPages}</span>
      <button type="button" class="dashboard-page-btn" data-dashboard-action="page" data-dashboard-section="${sectionId}" data-dashboard-page-direction="next"${pagination.page >= pagination.totalPages ? " disabled" : ""} aria-label="Next page">&rsaquo;</button>
      <span class="dashboard-page-range">${from}-${to} of ${pagination.totalRows}</span>
    </div>
  `;
}

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
  const tasks = Array.isArray(state.tasks) ? state.tasks : [];
  const users = Array.isArray(state.users) ? state.users : [];

  const projectNameById = new Map(
    projects.map((project) => [String(project.project_id || ""), String(project.project_name || "Unnamed Project")])
  );
  const tasksBySolution = new Map();
  tasks.forEach((task) => {
    const solutionId = String(task.solution_id || "");
    if (!solutionId) return;
    const bucket = tasksBySolution.get(solutionId) || [];
    bucket.push(task);
    tasksBySolution.set(solutionId, bucket);
  });

  const myTokens = currentUserTokens(state);

  const solutionRows = solutions
    .map((solution) => {
      const solutionId = String(solution.solution_id || "");
      const linked = tasksBySolution.get(solutionId) || [];
      const openLinked = linked.filter((task) => !isClosedStatus(task.status));
      const blockedTasks = openLinked.filter((task) => !!task.blocked).length;
      const unassignedTasks = openLinked.filter(
        (task) => !normalize(task.assignee) && !normalize(task.assignee_user_soeid)
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
  const completedFilteredRows = applySectionSolutionFilter(
    dashboardState,
    completedAllRows,
    "completed",
    (row) => row.solutionId
  );
  const completedPagination = paginateSectionRows(dashboardState, "completed", completedFilteredRows, supportRows);
  const completedRows = completedPagination.rows;

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
  const upcomingFilteredRows = applySectionSolutionFilter(
    dashboardState,
    upcomingAllRows,
    "upcoming",
    (entry) => entry.row.solutionId
  )
    .map((entry) => ({ ...entry.row, stage: entry.stage }));
  const upcomingPagination = paginateSectionRows(dashboardState, "upcoming", upcomingFilteredRows, supportRows);
  const upcomingRows = upcomingPagination.rows;

  const backlogFilteredRows = applySectionSolutionFilter(
    dashboardState,
    deferredRows,
    "backlog",
    (entry) => entry.row.solutionId
  )
    .map((entry) => ({ ...entry.row, shortfall: entry.shortfall }));
  const backlogPagination = paginateSectionRows(dashboardState, "backlog", backlogFilteredRows, supportRows);
  const backlogRows = backlogPagination.rows;

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
  const mainPagination = paginateSectionRows(
    dashboardState,
    "main",
    filteredMainRows,
    Math.min(prefs.rows, rowBudget.main)
  );
  const mainRows = mainPagination.rows;

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
    els.dashboardSpaceCapacity.innerHTML = `
      <div class="dashboard-snapshot-bar" aria-label="Space capacity snapshot">
        <div class="dashboard-snapshot-stat"><span>Total Capacity</span><strong>${formatFte(totalSpaceCapacity)} FTE-mo</strong></div>
        <div class="dashboard-snapshot-stat"><span>Working Now</span><strong>${formatFte(workingDemand)} FTE-mo</strong></div>
        <div class="dashboard-snapshot-stat"><span>Utilization</span><strong>${utilizationPct.toFixed(1)}%</strong></div>
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
      ${renderDashboardPagination("main", mainPagination)}
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
      ${renderDashboardPagination("completed", completedPagination)}
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
      ${renderDashboardPagination("upcoming", upcomingPagination)}
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
      ${renderDashboardPagination("backlog", backlogPagination)}
    `;
  }
}

export { createDashboardState };
