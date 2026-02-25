const DAY_MS = 24 * 60 * 60 * 1000;
const HOURS_PER_FTE_MONTH = 160;
const HOURS_PER_FTE_CAPACITY = 40;

const DASHBOARD_PREFS_KEY = "sipm-dashboard-view-prefs-v2";
const DEFAULT_PREFS = Object.freeze({
  scope: "active",
  sort: "risk_desc",
  rows: 10,
  horizon_days: 30,
});

const SCOPE_OPTIONS = new Set(["all", "active", "at_risk", "mine"]);
const SORT_OPTIONS = new Set(["risk_desc", "due_asc", "fte_desc", "project_alpha"]);
const ROW_OPTIONS = new Set([8, 10, 12, 16, 20]);
const HORIZON_OPTIONS = new Set([14, 30, 60, 90]);

const CLOSED_STATUSES = new Set(["complete", "abandoned"]);

const dashboardState = {
  ctx: null,
  bound: false,
  prefs: loadPrefs(),
};

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function num(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function parseDate(value) {
  if (!value) return null;
  const token = String(value).slice(0, 10);
  if (!token) return null;
  const parsed = new Date(`${token}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfDay(value) {
  const date = new Date(value.getTime());
  date.setHours(0, 0, 0, 0);
  return date;
}

function daysUntil(fromDate, toDate) {
  return Math.ceil((toDate.getTime() - fromDate.getTime()) / DAY_MS);
}

function daysAgo(fromDate, pastDate) {
  return Math.max(0, Math.ceil((fromDate.getTime() - pastDate.getTime()) / DAY_MS));
}

function statusKey(status) {
  return normalize(status);
}

function isClosedStatus(status) {
  return CLOSED_STATUSES.has(statusKey(status));
}

function ragStatusLabel(value) {
  const rag = normalize(value);
  if (rag === "red") return "Red";
  if (rag === "amber") return "Amber";
  if (rag === "green") return "Green";
  return "Unknown";
}

function ragPillMarkup(value) {
  const rag = normalize(value);
  if (rag === "red" || rag === "amber" || rag === "green") {
    return `<span class="pill rag-pill rag-${rag}">${ragStatusLabel(rag)}</span>`;
  }
  return `<span class="pill muted">${ragStatusLabel(rag)}</span>`;
}

function dueTone(days) {
  if (!Number.isFinite(days)) return "muted";
  if (days < 0) return "danger";
  if (days <= 7) return "warn";
  return "positive";
}

function dueLabel(days) {
  if (!Number.isFinite(days)) return "No due date";
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "Due today";
  return `Due in ${days}d`;
}

function userCapacityFte(user) {
  if (!user) return 1;
  const byFte = Number(user.capacity_fte_month);
  const byHours = Number(user.capacity_hours);
  if (Number.isFinite(byFte)) return Math.max(byFte, 0);
  if (Number.isFinite(byHours)) return Math.max(byHours, 0) / HOURS_PER_FTE_CAPACITY;
  return 1;
}

function solutionFte(solution) {
  if (!solution) return 0;
  const byFte = Number(solution.capacity_fte_months);
  const byHours = Number(solution.capacity_hours);
  if (Number.isFinite(byFte)) return Math.max(byFte, 0);
  if (Number.isFinite(byHours)) return Math.max(byHours, 0) / HOURS_PER_FTE_MONTH;
  return 0;
}

function formatFte(value) {
  return num(value, 0).toFixed(2);
}

function loadPrefs() {
  try {
    if (typeof localStorage === "undefined") return { ...DEFAULT_PREFS };
    const raw = localStorage.getItem(DASHBOARD_PREFS_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const parsed = JSON.parse(raw);
    return normalizePrefs(parsed);
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

function savePrefs() {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(DASHBOARD_PREFS_KEY, JSON.stringify(dashboardState.prefs));
  } catch {
    // Ignore persistence issues.
  }
}

function normalizePrefs(input) {
  const next = {
    scope: String(input?.scope || DEFAULT_PREFS.scope),
    sort: String(input?.sort || DEFAULT_PREFS.sort),
    rows: num(input?.rows, DEFAULT_PREFS.rows),
    horizon_days: num(input?.horizon_days, DEFAULT_PREFS.horizon_days),
  };

  if (!SCOPE_OPTIONS.has(next.scope)) next.scope = DEFAULT_PREFS.scope;
  if (!SORT_OPTIONS.has(next.sort)) next.sort = DEFAULT_PREFS.sort;
  if (!ROW_OPTIONS.has(next.rows)) next.rows = DEFAULT_PREFS.rows;
  if (!HORIZON_OPTIONS.has(next.horizon_days)) next.horizon_days = DEFAULT_PREFS.horizon_days;
  return next;
}

function updatePrefs(patch) {
  dashboardState.prefs = normalizePrefs({ ...dashboardState.prefs, ...patch });
  savePrefs();
}

function rerender() {
  if (!dashboardState.ctx) return;
  renderDashboard(dashboardState.ctx);
}

function currentUserTokens(state) {
  const tokens = new Set();
  const user = state?.user || null;
  const add = (value) => {
    const token = normalize(value);
    if (token) tokens.add(token);
  };
  add(user?.soeid);
  add(user?.display_name);
  add(user?.name);
  return tokens;
}

function isOwnedByCurrentUser(solution, tokens) {
  if (!solution || !tokens || !tokens.size) return false;
  const candidates = [
    solution.owner_user_soeid,
    solution.owner,
    solution.key_stakeholder,
  ];
  return candidates.some((value) => tokens.has(normalize(value)));
}

function riskScoreForSolution(row) {
  let score = 0;
  const rag = normalize(row.rag_status);

  if (rag === "red") score += 45;
  else if (rag === "amber") score += 24;

  if (row.status === "on_hold") score += 18;

  if (Number.isFinite(row.dueDays)) {
    if (row.dueDays < 0) score += 22;
    else if (row.dueDays <= row.horizonDays) score += 10;
  }

  if (row.blockedTasks > 0) score += Math.min(18, row.blockedTasks * 4);
  if (row.unassignedTasks > 0) score += Math.min(12, row.unassignedTasks * 3);

  if (!row.stakeholder || row.stakeholder === "Unassigned") score += 6;

  return clamp(Math.round(score), 0, 100);
}

function applyScope(rows, scope) {
  if (scope === "all") return rows;
  if (scope === "active") return rows.filter((row) => !row.isClosed);
  if (scope === "at_risk") return rows.filter((row) => !row.isClosed && row.riskScore >= 45);
  if (scope === "mine") return rows.filter((row) => !row.isClosed && row.isMine);
  return rows;
}

function sortRows(rows, sortKey) {
  const byAlpha = (a, b) => {
    const projectCmp = a.projectName.localeCompare(b.projectName);
    if (projectCmp !== 0) return projectCmp;
    return a.solutionName.localeCompare(b.solutionName);
  };

  const dueSortValue = (row) => (Number.isFinite(row.dueDays) ? row.dueDays : Number.POSITIVE_INFINITY);

  const sorted = [...rows];
  if (sortKey === "project_alpha") {
    sorted.sort(byAlpha);
  } else if (sortKey === "due_asc") {
    sorted.sort((a, b) => dueSortValue(a) - dueSortValue(b) || b.riskScore - a.riskScore || byAlpha(a, b));
  } else if (sortKey === "fte_desc") {
    sorted.sort((a, b) => b.fte - a.fte || b.riskScore - a.riskScore || byAlpha(a, b));
  } else {
    sorted.sort((a, b) => b.riskScore - a.riskScore || dueSortValue(a) - dueSortValue(b) || byAlpha(a, b));
  }
  return sorted;
}

function viewportRowBudget() {
  const height = typeof window !== "undefined" ? window.innerHeight : 960;
  if (height >= 1320) return { main: 10, secondary: 6 };
  if (height >= 1180) return { main: 9, secondary: 5 };
  if (height >= 1060) return { main: 8, secondary: 5 };
  if (height >= 940) return { main: 7, secondary: 4 };
  if (height >= 860) return { main: 6, secondary: 4 };
  return { main: 5, secondary: 3 };
}

function bindDashboardEvents(ctx) {
  const root = ctx?.els?.dashboardTopProjects;
  if (!root || dashboardState.bound) return;
  dashboardState.bound = true;

  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    if (target.id === "dashboard-main-scope") {
      updatePrefs({ scope: target.value || DEFAULT_PREFS.scope });
      rerender();
      return;
    }

    if (target.id === "dashboard-main-sort") {
      updatePrefs({ sort: target.value || DEFAULT_PREFS.sort });
      rerender();
      return;
    }

    if (target.id === "dashboard-main-rows") {
      updatePrefs({ rows: num(target.value, DEFAULT_PREFS.rows) });
      rerender();
      return;
    }

    if (target.id === "dashboard-main-horizon") {
      updatePrefs({ horizon_days: num(target.value, DEFAULT_PREFS.horizon_days) });
      rerender();
    }
  });

  root.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-dashboard-action") || "";
    if (action === "reset-view") {
      dashboardState.prefs = { ...DEFAULT_PREFS };
      savePrefs();
      rerender();
    }
  });
}

export function renderDashboard(ctx) {
  const { state, els, formatStatus } = ctx;
  dashboardState.ctx = ctx;
  bindDashboardEvents(ctx);

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
      const unassignedTasks = openLinked.filter((subcomponent) => {
        return !normalize(subcomponent.assignee) && !normalize(subcomponent.assignee_user_soeid);
      }).length;

      const dueDate = parseDate(solution.due_date);
      const dueDays = dueDate ? daysUntil(today, dueDate) : Number.NaN;
      const completedDate = parseDate(solution.completed_at) || parseDate(solution.updated_at);

      const row = {
        solutionId,
        projectId: String(solution.project_id || ""),
        projectName: projectNameById.get(String(solution.project_id || "")) || "Unmapped Project",
        solutionName: String(solution.solution_name || "Unnamed Solution"),
        stakeholder: String(solution.key_stakeholder || solution.owner || solution.owner_user_soeid || "Unassigned"),
        ownerUser: String(solution.owner_user_soeid || ""),
        status: statusKey(solution.status),
        statusRaw: String(solution.status || ""),
        rag_status: String(solution.rag_status || ""),
        fte: solutionFte(solution),
        dueDate,
        dueDays,
        openTasks: openLinked.length,
        blockedTasks,
        unassignedTasks,
        isClosed: isClosedStatus(solution.status),
        isMine: isOwnedByCurrentUser(solution, myTokens),
        completedDate,
        horizonDays: prefs.horizon_days,
      };
      row.riskScore = riskScoreForSolution(row);
      return row;
    })
    .filter((row) => row.solutionId);

  const activeRows = solutionRows.filter((row) => !row.isClosed);
  const atRiskRows = activeRows.filter((row) => row.riskScore >= 45);
  const overdueRows = activeRows.filter((row) => Number.isFinite(row.dueDays) && row.dueDays < 0);
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

  const scoped = applyScope(solutionRows, prefs.scope);
  const sorted = sortRows(scoped, prefs.sort);
  const rowBudget = viewportRowBudget();
  const mainRows = sorted.slice(0, Math.min(prefs.rows, rowBudget.main));
  const supportRows = rowBudget.secondary;

  const upcomingRows = [];
  const upcomingSeen = new Set();
  const workingSlots = Math.max(1, Math.ceil(supportRows * 0.6));
  const comingSlots = Math.max(1, supportRows - workingSlots);
  let usedWorkingSlots = 0;
  let usedComingSlots = 0;

  for (const row of workingRows) {
    if (upcomingRows.length >= supportRows || usedWorkingSlots >= workingSlots) break;
    if (upcomingSeen.has(row.solutionId)) continue;
    upcomingRows.push({ row, stage: "Working" });
    upcomingSeen.add(row.solutionId);
    usedWorkingSlots += 1;
  }
  for (const row of scheduledRows) {
    if (upcomingRows.length >= supportRows || usedComingSlots >= comingSlots) break;
    if (upcomingSeen.has(row.solutionId)) continue;
    upcomingRows.push({ row, stage: "Coming" });
    upcomingSeen.add(row.solutionId);
    usedComingSlots += 1;
  }
  for (const row of workingRows) {
    if (upcomingRows.length >= supportRows) break;
    if (upcomingSeen.has(row.solutionId)) continue;
    upcomingRows.push({ row, stage: "Working" });
    upcomingSeen.add(row.solutionId);
  }
  for (const row of scheduledRows) {
    if (upcomingRows.length >= supportRows) break;
    if (upcomingSeen.has(row.solutionId)) continue;
    upcomingRows.push({ row, stage: "Coming" });
    upcomingSeen.add(row.solutionId);
  }

  const completedRows = solutionRows
    .filter((row) => row.status === "complete" && row.completedDate)
    .filter((row) => daysAgo(today, row.completedDate) <= prefs.horizon_days)
    .sort((a, b) => (b.completedDate?.getTime() || 0) - (a.completedDate?.getTime() || 0))
    .slice(0, supportRows);
  const backlogRows = deferredRows.slice(0, supportRows);

  const formatStatusLabel = (value) => {
    if (typeof formatStatus === "function") return formatStatus(value);
    return String(value || "-");
  };

  if (els.dashboardSpaceCapacity) {
    const utilClass = utilizationPct >= 100 ? "danger" : utilizationPct >= 85 ? "warn" : "positive";
    const utilWidth = clamp(utilizationPct, 0, 140);
    els.dashboardSpaceCapacity.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Space Snapshot</h3>
          <p class="dashboard-card-sub">Capacity versus active delivery load</p>
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
    const mainRowsHtml = mainRows
      .map((row) => {
        const dueClass = dueTone(row.dueDays);
        const dueLabelText = dueLabel(row.dueDays);
        return `<tr>
          <td><strong>${esc(row.projectName)}</strong></td>
          <td>
            <div><strong>${esc(row.solutionName)}</strong></div>
            <div class="dashboard-cell-meta">${row.blockedTasks} blocked, ${row.unassignedTasks} unassigned</div>
            <div class="dashboard-cell-meta"><span class="pill ${dueClass}">${esc(dueLabelText)}</span></div>
          </td>
          <td>${esc(row.stakeholder)}</td>
          <td><span class="dashboard-fte-box">${formatFte(row.fte)}</span></td>
          <td>${ragPillMarkup(row.rag_status)}</td>
          <td>${formatStatusLabel(row.statusRaw)}</td>
        </tr>`;
      })
      .join("");

    const emptyRow = `<tr><td colspan="6" class="muted">No solutions match the current view options.</td></tr>`;

    els.dashboardTopProjects.innerHTML = `
      <div class="dashboard-main-head">
        <div class="dashboard-title-block">
          <h3>Important Projects &amp; Solutions</h3>
          <p class="dashboard-card-sub">Priority view of items that matter most right now.</p>
        </div>
        <details class="dashboard-control-disclosure">
          <summary class="dashboard-control-summary">Customize</summary>
          <div class="dashboard-control-popover">
            <div class="dashboard-toolbar">
              <label class="inline-field">Scope
                <select id="dashboard-main-scope">
                  <option value="all" ${prefs.scope === "all" ? "selected" : ""}>All Solutions</option>
                  <option value="active" ${prefs.scope === "active" ? "selected" : ""}>Active Only</option>
                  <option value="at_risk" ${prefs.scope === "at_risk" ? "selected" : ""}>At Risk</option>
                  <option value="mine" ${prefs.scope === "mine" ? "selected" : ""}>Owned By Me</option>
                </select>
              </label>

              <label class="inline-field">Sort
                <select id="dashboard-main-sort">
                  <option value="risk_desc" ${prefs.sort === "risk_desc" ? "selected" : ""}>Risk (High to Low)</option>
                  <option value="due_asc" ${prefs.sort === "due_asc" ? "selected" : ""}>Due Date (Soonest)</option>
                  <option value="fte_desc" ${prefs.sort === "fte_desc" ? "selected" : ""}>FTE (High to Low)</option>
                  <option value="project_alpha" ${prefs.sort === "project_alpha" ? "selected" : ""}>Project (A-Z)</option>
                </select>
              </label>

              <label class="inline-field">Rows
                <select id="dashboard-main-rows">
                  <option value="8" ${prefs.rows === 8 ? "selected" : ""}>8</option>
                  <option value="10" ${prefs.rows === 10 ? "selected" : ""}>10</option>
                  <option value="12" ${prefs.rows === 12 ? "selected" : ""}>12</option>
                  <option value="16" ${prefs.rows === 16 ? "selected" : ""}>16</option>
                  <option value="20" ${prefs.rows === 20 ? "selected" : ""}>20</option>
                </select>
              </label>

              <label class="inline-field">Horizon
                <select id="dashboard-main-horizon">
                  <option value="14" ${prefs.horizon_days === 14 ? "selected" : ""}>14 days</option>
                  <option value="30" ${prefs.horizon_days === 30 ? "selected" : ""}>30 days</option>
                  <option value="60" ${prefs.horizon_days === 60 ? "selected" : ""}>60 days</option>
                  <option value="90" ${prefs.horizon_days === 90 ? "selected" : ""}>90 days</option>
                </select>
              </label>
            </div>
            <div class="dashboard-control-actions">
              <button type="button" class="secondary" data-dashboard-action="reset-view">Reset View</button>
            </div>
          </div>
        </details>
      </div>
      <p class="dashboard-main-meta">
        Showing ${mainRows.length} of ${sorted.length} in view · ${activeRows.length} active · ${atRiskRows.length} at risk · ${overdueRows.length} overdue
      </p>

      <div class="table dashboard-table-shell">
        <table class="dashboard-main-table">
          <thead>
            <tr>
              <th>Project</th>
              <th>Solution</th>
              <th>Stakeholder</th>
              <th>FTE-mo</th>
              <th>RAG</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>${mainRowsHtml || emptyRow}</tbody>
        </table>
      </div>
    `;
  }

  if (els.dashboardCompletedQuarter) {
    const rows = completedRows
      .map((row) => {
        const completed = row.completedDate ? row.completedDate.toISOString().slice(0, 10) : "-";
        return `<tr>
          <td><strong>${esc(row.projectName)}</strong></td>
          <td>${esc(row.solutionName)}</td>
          <td>${esc(row.stakeholder)}</td>
          <td>${esc(completed)}</td>
        </tr>`;
      })
      .join("");

    els.dashboardCompletedQuarter.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Complete</h3>
          <p class="dashboard-card-sub">Delivered in the last ${prefs.horizon_days} days</p>
        </div>
      </div>
      ${rows
        ? `<div class="table dashboard-table-shell"><table class="dashboard-mini-table"><thead><tr><th>Project</th><th>Solution</th><th>Stakeholder</th><th>Completed</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : `<p class="muted dashboard-empty">No completed items in the last ${prefs.horizon_days} days.</p>`
      }
    `;
  }

  if (els.dashboardUpcomingQuarter) {
    const rows = upcomingRows
      .map((entry) => {
        const { row, stage } = entry;
        const stageClass = stage === "Working" ? "positive" : "warn";
        const dueClass = dueTone(row.dueDays);
        return `<tr>
          <td><span class="pill ${stageClass}">${esc(stage)}</span></td>
          <td><strong>${esc(row.projectName)}</strong><div class="dashboard-cell-meta">${esc(row.solutionName)}</div></td>
          <td><span class="dashboard-fte-box">${formatFte(row.fte)}</span></td>
          <td><span class="pill ${dueClass}">${esc(dueLabel(row.dueDays))}</span></td>
          <td>${esc(row.stakeholder)}</td>
        </tr>`;
      })
      .join("");

    els.dashboardUpcomingQuarter.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Upcoming</h3>
          <p class="dashboard-card-sub">Working now + coming work that fits current FTE</p>
        </div>
      </div>
      ${rows
        ? `<div class="table dashboard-table-shell"><table class="dashboard-mini-table"><thead><tr><th>Stage</th><th>Work Item</th><th>FTE-mo</th><th>Timing</th><th>Stakeholder</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : "<p class='muted dashboard-empty'>No working or upcoming items to show.</p>"
      }
    `;
  }

  if (els.dashboardBacklog) {
    const rows = backlogRows
      .map((entry) => {
        const row = entry.row;
        const dueClass = dueTone(row.dueDays);
        const shortfall = Math.max(0, entry.shortfall);
        return `<tr>
          <td><strong>${esc(row.projectName)}</strong><div class="dashboard-cell-meta">${esc(row.solutionName)}</div></td>
          <td><span class="dashboard-fte-box">${formatFte(row.fte)}</span></td>
          <td><span class="pill ${dueClass}">${esc(dueLabel(row.dueDays))}</span></td>
          <td>${esc(`Need +${formatFte(shortfall)} FTE-mo headroom`)}</td>
        </tr>`;
      })
      .join("");

    els.dashboardBacklog.innerHTML = `
      <div class="dashboard-card-head">
        <div>
          <h3>Backlog</h3>
          <p class="dashboard-card-sub">Work that cannot fit current FTE capacity (${formatFte(deferredDemand)} FTE-mo)</p>
        </div>
      </div>
      ${rows
        ? `<div class="table dashboard-table-shell"><table class="dashboard-mini-table"><thead><tr><th>Work Item</th><th>FTE-mo</th><th>Timing</th><th>Capacity Gap</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : "<p class='muted dashboard-empty'>No backlog outside current FTE headroom.</p>"
      }
    `;
  }
}
