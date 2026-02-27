const DAY_MS = 24 * 60 * 60 * 1000;
const HOURS_PER_FTE_MONTH = 160;
const HOURS_PER_FTE_CAPACITY = 40;

const DASHBOARD_PREFS_KEY = "sipm-dashboard-view-prefs-v3";
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

const DASHBOARD_SECTIONS = Object.freeze(["main", "completed", "upcoming", "backlog"]);
const DASHBOARD_SECTION_TITLES = Object.freeze({
  main: "Current Deliverables",
  completed: "Complete",
  upcoming: "Upcoming",
  backlog: "Backlog",
});

const DASHBOARD_SECTION_DEFAULTS = Object.freeze({
  main: Object.freeze({ columns: Object.freeze(["solution", "rag", "timing", "fte"]), solution_ids: null }),
  completed: Object.freeze({ columns: Object.freeze(["solution", "completed"]), solution_ids: null }),
  upcoming: Object.freeze({ columns: Object.freeze(["solution", "stage", "timing"]), solution_ids: null }),
  backlog: Object.freeze({ columns: Object.freeze(["solution", "timing", "gap"]), solution_ids: null }),
});

const DASHBOARD_ALL_COLUMNS = Object.freeze([
  "solution",
  "solution_id",
  "project",
  "project_id",
  "status",
  "rag",
  "risk",
  "timing",
  "due_date",
  "completed",
  "fte",
  "open_tasks",
  "blocked_tasks",
  "unassigned_tasks",
  "stakeholder",
  "owner",
  "stage",
  "gap",
  "is_mine",
]);

const DASHBOARD_SECTION_COLUMNS = Object.freeze({
  main: DASHBOARD_ALL_COLUMNS,
  completed: DASHBOARD_ALL_COLUMNS,
  upcoming: DASHBOARD_ALL_COLUMNS,
  backlog: DASHBOARD_ALL_COLUMNS,
});

const DASHBOARD_COLUMN_WIDTH_UNITS = Object.freeze({
  solution: 4.4,
  solution_id: 2.0,
  project: 2.5,
  project_id: 2.0,
  owner: 2.2,
  risk: 1.3,
  rag: 1.2,
  timing: 1.8,
  due_date: 1.6,
  fte: 1.2,
  open_tasks: 1.4,
  blocked_tasks: 1.5,
  unassigned_tasks: 1.8,
  status: 1.8,
  stakeholder: 2.3,
  stage: 1.4,
  completed: 1.6,
  gap: 2.7,
  is_mine: 1.3,
});

const DASHBOARD_COLUMN_MIN_WIDTH_PCT = Object.freeze({
  solution: 24,
  solution_id: 11,
  project: 14,
  project_id: 11,
  owner: 12,
  risk: 8,
  rag: 8,
  timing: 11,
  due_date: 10,
  fte: 8,
  open_tasks: 9,
  blocked_tasks: 9,
  unassigned_tasks: 11,
  status: 11,
  stakeholder: 14,
  stage: 10,
  completed: 11,
  gap: 18,
  is_mine: 9,
});

function emptySectionOptions() {
  return {
    main: [],
    completed: [],
    upcoming: [],
    backlog: [],
  };
}

const dashboardState = {
  ctx: null,
  bound: false,
  prefs: loadPrefs(),
  sectionOptions: emptySectionOptions(),
  modalSection: null,
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

function cloneSectionDefaults(sectionId) {
  const base = DASHBOARD_SECTION_DEFAULTS[sectionId] || { columns: [], solution_ids: null };
  return {
    columns: [...base.columns],
    solution_ids: null,
  };
}

function normalizeSectionPrefs(sectionId, input) {
  const defaults = cloneSectionDefaults(sectionId);
  const allowedColumns = new Set(DASHBOARD_SECTION_COLUMNS[sectionId] || []);

  const columns = [];
  const inputColumns = Array.isArray(input?.columns) ? input.columns : [];
  inputColumns.forEach((columnId) => {
    const token = String(columnId || "").trim();
    if (!token || !allowedColumns.has(token) || columns.includes(token)) return;
    columns.push(token);
  });

  let solutionIds = null;
  if (Array.isArray(input?.solution_ids)) {
    const cleaned = [];
    input.solution_ids.forEach((solutionId) => {
      const token = String(solutionId || "").trim();
      if (token && !cleaned.includes(token)) cleaned.push(token);
    });
    solutionIds = cleaned;
  }

  return {
    columns: columns.length ? columns : defaults.columns,
    solution_ids: solutionIds,
  };
}

function loadPrefs() {
  try {
    if (typeof localStorage === "undefined") return normalizePrefs(DEFAULT_PREFS);
    const raw = localStorage.getItem(DASHBOARD_PREFS_KEY);
    if (!raw) return normalizePrefs(DEFAULT_PREFS);
    const parsed = JSON.parse(raw);
    return normalizePrefs(parsed);
  } catch {
    return normalizePrefs(DEFAULT_PREFS);
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

  const sections = {};
  DASHBOARD_SECTIONS.forEach((sectionId) => {
    sections[sectionId] = normalizeSectionPrefs(sectionId, input?.sections?.[sectionId]);
  });

  return {
    ...next,
    sections,
  };
}

function updatePrefs(patch) {
  const mergedSections = {
    ...(dashboardState.prefs?.sections || {}),
    ...((patch && patch.sections) || {}),
  };
  dashboardState.prefs = normalizePrefs({
    ...(dashboardState.prefs || normalizePrefs(DEFAULT_PREFS)),
    ...(patch || {}),
    sections: mergedSections,
  });
  savePrefs();
}

function getSectionPrefs(sectionId) {
  const section = dashboardState.prefs?.sections?.[sectionId];
  return section || cloneSectionDefaults(sectionId);
}

function selectedColumnsForSection(sectionId, columnDefs) {
  const allowedColumns = new Set(DASHBOARD_SECTION_COLUMNS[sectionId] || []);
  const selected = [];
  const rawColumns = Array.isArray(getSectionPrefs(sectionId).columns) ? getSectionPrefs(sectionId).columns : [];
  rawColumns.forEach((columnId) => {
    if (!allowedColumns.has(columnId)) return;
    if (!columnDefs[columnId]) return;
    if (!selected.includes(columnId)) selected.push(columnId);
  });

  if (selected.length) return selected;

  return cloneSectionDefaults(sectionId).columns.filter((columnId) => !!columnDefs[columnId]);
}

function updateSectionPrefs(sectionId, patch) {
  if (!DASHBOARD_SECTIONS.includes(sectionId)) return;
  const current = getSectionPrefs(sectionId);
  const hasSolutionIds =
    patch && typeof patch === "object" && Object.prototype.hasOwnProperty.call(patch, "solution_ids");

  updatePrefs({
    sections: {
      [sectionId]: {
        columns: Array.isArray(patch?.columns) ? [...patch.columns] : current.columns,
        solution_ids: hasSolutionIds ? patch.solution_ids : current.solution_ids,
      },
    },
  });
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
  const candidates = [solution.owner_user_soeid, solution.owner, solution.key_stakeholder];
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

function buildSectionOptions(rows, pickRow = (entry) => entry) {
  const byId = new Map();
  rows.forEach((entry) => {
    const row = pickRow(entry);
    const solutionId = String(row?.solutionId || "").trim();
    if (!solutionId || byId.has(solutionId)) return;
    byId.set(solutionId, {
      solutionId,
      projectName: String(row?.projectName || "Unmapped Project"),
      solutionName: String(row?.solutionName || "Unnamed Solution"),
    });
  });
  return [...byId.values()].sort((a, b) => {
    const projectCmp = a.projectName.localeCompare(b.projectName);
    if (projectCmp !== 0) return projectCmp;
    return a.solutionName.localeCompare(b.solutionName);
  });
}

function applySectionSolutionFilter(rows, sectionId, idFromRow = (row) => row.solutionId) {
  const solutionIds = getSectionPrefs(sectionId).solution_ids;
  if (!Array.isArray(solutionIds)) return rows;
  const selected = new Set(solutionIds);
  return rows.filter((row) => selected.has(String(idFromRow(row) || "").trim()));
}

function displayValue(value, fallback = "—") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function createColumnDefinitions(formatStatusLabel) {
  const allColumns = {
    solution: {
      label: "Solution",
      render: (row) =>
        `<div><strong>${esc(row.solutionName)}</strong></div><div class="dashboard-cell-meta">${esc(row.projectName)}</div>`,
    },
    solution_id: {
      label: "Solution ID",
      render: (row) => esc(displayValue(row.solutionId)),
    },
    project: {
      label: "Project",
      render: (row) => `<strong>${esc(row.projectName)}</strong>`,
    },
    project_id: {
      label: "Project ID",
      render: (row) => esc(displayValue(row.projectId)),
    },
    status: {
      label: "Status",
      render: (row) => esc(formatStatusLabel(row.statusRaw)),
    },
    rag: {
      label: "RAG",
      render: (row) => ragPillMarkup(row.rag_status),
    },
    risk: {
      label: "Risk",
      render: (row) => esc(String(clamp(Math.round(num(row.riskScore, 0)), 0, 100))),
    },
    timing: {
      label: "Timing",
      render: (row) => `<span class="pill ${dueTone(row.dueDays)}">${esc(dueLabel(row.dueDays))}</span>`,
    },
    due_date: {
      label: "Due Date",
      render: (row) => esc(displayValue(row.dueDateLabel)),
    },
    completed: {
      label: "Completed",
      render: (row) => esc(displayValue(row.completedDateLabel)),
    },
    fte: {
      label: "FTE-mo",
      render: (row) => `<span class="dashboard-fte-box">${formatFte(row.fte)}</span>`,
    },
    open_tasks: {
      label: "Open Tasks",
      render: (row) => esc(String(Math.max(0, num(row.openTasks, 0)))),
    },
    blocked_tasks: {
      label: "Blocked Tasks",
      render: (row) => esc(String(Math.max(0, num(row.blockedTasks, 0)))),
    },
    unassigned_tasks: {
      label: "Unassigned Tasks",
      render: (row) => esc(String(Math.max(0, num(row.unassignedTasks, 0)))),
    },
    stakeholder: {
      label: "Stakeholder",
      render: (row) => esc(displayValue(row.stakeholder)),
    },
    owner: {
      label: "Owner",
      render: (row) => esc(displayValue(row.owner)),
    },
    stage: {
      label: "Stage",
      render: (row) => {
        const stage = String(row.stage || "").trim();
        if (!stage) return "—";
        const stageClass = normalize(stage) === "working" ? "positive" : "warn";
        return `<span class="pill ${stageClass}">${esc(stage)}</span>`;
      },
    },
    gap: {
      label: "Capacity Gap",
      render: (row) => {
        const shortfall = num(row.shortfall, Number.NaN);
        if (!Number.isFinite(shortfall)) return "—";
        return esc(`Need +${formatFte(Math.max(0, shortfall))} FTE-mo headroom`);
      },
    },
    is_mine: {
      label: "Owned By Me",
      render: (row) => `<span class="pill ${row.isMine ? "positive" : "muted"}">${row.isMine ? "Yes" : "No"}</span>`,
    },
  };

  return {
    main: allColumns,
    completed: allColumns,
    upcoming: allColumns,
    backlog: allColumns,
  };
}

function renderSectionTable({ sectionId, rows, columnDefs, tableClass, emptyText }) {
  const columns = selectedColumnsForSection(sectionId, columnDefs);
  const widths = calculateColumnWidths(columns);
  const colgroupHtml = columns
    .map((columnId, index) => {
      const width = widths[index];
      return `<col class="dashboard-col-width dashboard-col-${esc(columnId)}" style="width:${width.toFixed(2)}%;" />`;
    })
    .join("");
  const headerHtml = columns
    .map((columnId) => `<th class="dashboard-col-${esc(columnId)}">${esc(columnDefs[columnId].label)}</th>`)
    .join("");
  const bodyRows = rows
    .map((row) => {
      const cells = columns
        .map((columnId) => `<td class="dashboard-col-${esc(columnId)}">${columnDefs[columnId].render(row)}</td>`)
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  const emptyRow = `<tr><td colspan="${Math.max(columns.length, 1)}" class="muted">${esc(emptyText)}</td></tr>`;

  return `
    <div
      class="table dashboard-table-shell dashboard-interactive-table"
      role="button"
      tabindex="0"
      data-dashboard-action="open-config"
      data-dashboard-section="${sectionId}"
      aria-label="Customize ${esc(DASHBOARD_SECTION_TITLES[sectionId] || "dashboard")} table"
    >
      <table class="${tableClass} dashboard-condensed-table">
        <colgroup>${colgroupHtml}</colgroup>
        <thead>
          <tr>${headerHtml}</tr>
        </thead>
        <tbody>${bodyRows || emptyRow}</tbody>
      </table>
    </div>
  `;
}

function columnWidthUnit(columnId) {
  return Number(DASHBOARD_COLUMN_WIDTH_UNITS[columnId]) || 1.6;
}

function columnMinWidthPct(columnId) {
  return Number(DASHBOARD_COLUMN_MIN_WIDTH_PCT[columnId]) || 8;
}

function calculateColumnWidths(columns) {
  if (!Array.isArray(columns) || !columns.length) return [];

  const units = columns.map((columnId) => columnWidthUnit(columnId));
  const mins = columns.map((columnId) => columnMinWidthPct(columnId));
  const sumMins = mins.reduce((sum, value) => sum + value, 0);

  if (sumMins >= 100) {
    return mins.map((value) => (value / sumMins) * 100);
  }

  const widths = new Array(columns.length).fill(0);
  const locked = new Array(columns.length).fill(false);
  let remaining = 100;

  while (true) {
    const unlocked = [];
    let unlockedUnits = 0;
    for (let index = 0; index < columns.length; index += 1) {
      if (locked[index]) continue;
      unlocked.push(index);
      unlockedUnits += units[index];
    }

    if (!unlocked.length || unlockedUnits <= 0) break;

    let changed = false;
    for (const index of unlocked) {
      const proposed = (remaining * units[index]) / unlockedUnits;
      if (proposed + 1e-6 < mins[index]) {
        widths[index] = mins[index];
        locked[index] = true;
        remaining -= mins[index];
        changed = true;
      }
    }

    if (remaining <= 0) {
      const assigned = widths.reduce((sum, value) => sum + value, 0);
      if (assigned > 0) return widths.map((value) => (value / assigned) * 100);
      return columns.map(() => 100 / columns.length);
    }

    if (!changed) {
      const finalUnlocked = [];
      let finalUnits = 0;
      for (let index = 0; index < columns.length; index += 1) {
        if (locked[index]) continue;
        finalUnlocked.push(index);
        finalUnits += units[index];
      }
      if (!finalUnlocked.length || finalUnits <= 0) break;
      for (const index of finalUnlocked) {
        widths[index] = (remaining * units[index]) / finalUnits;
      }
      break;
    }
  }

  const total = widths.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return columns.map(() => 100 / columns.length);
  return widths.map((value) => (value / total) * 100);
}

function ensureDashboardConfigModal() {
  if (typeof document === "undefined") return null;
  let modal = document.getElementById("dashboard-config-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "dashboard-config-modal";
  modal.className = "modal hidden";
  modal.setAttribute("aria-hidden", "true");
  modal.innerHTML = `
    <div class="modal-backdrop" data-dashboard-action="close-config"></div>
    <div class="modal-content dashboard-config-modal-content" role="dialog" aria-modal="true" aria-labelledby="dashboard-config-title">
      <div class="modal-header">
        <h3 id="dashboard-config-title">Customize Table</h3>
        <button type="button" class="secondary" data-dashboard-action="close-config">Close</button>
      </div>
      <p id="dashboard-config-description" class="muted"></p>
      <div class="dashboard-config-layout">
        <section class="dashboard-config-panel">
          <div class="modal-section-title">Columns</div>
          <div id="dashboard-config-columns" class="dashboard-config-checklist"></div>
        </section>
        <section class="dashboard-config-panel">
          <div class="dashboard-config-list-head">
            <div class="modal-section-title">Solutions Included</div>
            <div class="dashboard-config-list-actions">
              <button type="button" class="text-link" data-dashboard-action="select-all-solutions">Select all</button>
              <button type="button" class="text-link" data-dashboard-action="clear-solutions">Clear</button>
            </div>
          </div>
          <div id="dashboard-config-solutions" class="dashboard-config-checklist dashboard-config-solutions"></div>
        </section>
      </div>
      <div class="form-actions">
        <button type="button" class="secondary" data-dashboard-action="reset-table-config">Reset</button>
        <button type="button" class="secondary" data-dashboard-action="close-config">Cancel</button>
        <button type="button" class="primary" data-dashboard-action="apply-table-config">Apply</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  return modal;
}

function renderDashboardConfigModal(sectionId, options = {}) {
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  if (!DASHBOARD_SECTIONS.includes(sectionId)) return;

  const columnDefsBySection = options.columnDefsBySection || {};
  const columnDefs = columnDefsBySection[sectionId] || {};
  const sectionPrefs = options.useDefaults ? cloneSectionDefaults(sectionId) : getSectionPrefs(sectionId);
  const selectedColumns = new Set(Array.isArray(sectionPrefs.columns) ? sectionPrefs.columns : []);
  const selectedSolutions = Array.isArray(sectionPrefs.solution_ids) ? new Set(sectionPrefs.solution_ids) : null;
  const sectionOptions = dashboardState.sectionOptions[sectionId] || [];

  const titleEl = modal.querySelector("#dashboard-config-title");
  const descriptionEl = modal.querySelector("#dashboard-config-description");
  const columnsEl = modal.querySelector("#dashboard-config-columns");
  const solutionsEl = modal.querySelector("#dashboard-config-solutions");
  if (!titleEl || !descriptionEl || !columnsEl || !solutionsEl) return;

  titleEl.textContent = `Customize ${DASHBOARD_SECTION_TITLES[sectionId] || "Dashboard"}`;
  descriptionEl.textContent = "Choose executive columns, reorder them, and pick which project solutions appear in this table.";

  const columnOrder = DASHBOARD_SECTION_COLUMNS[sectionId] || [];
  const modalColumnOrder = [
    ...[...selectedColumns].filter((columnId) => columnOrder.includes(columnId)),
    ...columnOrder.filter((columnId) => !selectedColumns.has(columnId)),
  ];
  columnsEl.innerHTML = modalColumnOrder
    .filter((columnId) => !!columnDefs[columnId])
    .map((columnId) => {
      const checked = selectedColumns.has(columnId) ? "checked" : "";
      const label = columnDefs[columnId].label;
      return `
        <div class="dashboard-config-item dashboard-config-column-item" data-column-id="${esc(columnId)}">
          <label class="dashboard-config-item-check">
            <input type="checkbox" name="dashboard-config-column" value="${esc(columnId)}" ${checked} />
            <span>${esc(label)}</span>
          </label>
          <div class="dashboard-config-item-move">
            <button type="button" class="secondary dashboard-config-move-btn" data-dashboard-action="move-column-up" data-column-id="${esc(columnId)}" aria-label="Move ${esc(label)} up">↑</button>
            <button type="button" class="secondary dashboard-config-move-btn" data-dashboard-action="move-column-down" data-column-id="${esc(columnId)}" aria-label="Move ${esc(label)} down">↓</button>
          </div>
        </div>
      `;
    })
    .join("");

  if (!sectionOptions.length) {
    solutionsEl.innerHTML = `<p class="dashboard-config-empty muted">No solutions available in this window.</p>`;
    return;
  }

  solutionsEl.innerHTML = sectionOptions
    .map((option) => {
      const checked = selectedSolutions ? selectedSolutions.has(option.solutionId) : true;
      return `
        <label class="dashboard-config-item dashboard-config-solution-item">
          <input type="checkbox" name="dashboard-config-solution" value="${esc(option.solutionId)}" ${checked ? "checked" : ""} />
          <span>
            <strong>${esc(option.solutionName)}</strong>
            <span class="dashboard-cell-meta">${esc(option.projectName)}</span>
          </span>
        </label>
      `;
    })
    .join("");
}

function openDashboardConfigModal(sectionId) {
  if (!DASHBOARD_SECTIONS.includes(sectionId)) return;
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  dashboardState.modalSection = sectionId;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  const firstInput = modal.querySelector("input");
  if (firstInput instanceof HTMLElement) firstInput.focus();
}

function closeDashboardConfigModal() {
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  dashboardState.modalSection = null;
}

function setAllModalSolutionChecks(checked) {
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  modal.querySelectorAll("input[name='dashboard-config-solution']").forEach((input) => {
    input.checked = checked;
  });
}

function resetModalDraft(columnDefsBySection) {
  const sectionId = dashboardState.modalSection;
  if (!sectionId) return;
  renderDashboardConfigModal(sectionId, { useDefaults: true, columnDefsBySection });
}

function moveModalColumn(direction, columnId) {
  const modal = ensureDashboardConfigModal();
  if (!modal || !columnId) return;

  const columnsEl = modal.querySelector("#dashboard-config-columns");
  if (!(columnsEl instanceof HTMLElement)) return;

  const items = Array.from(columnsEl.querySelectorAll(".dashboard-config-column-item"));
  const index = items.findIndex((item) => String(item.getAttribute("data-column-id") || "") === columnId);
  if (index < 0) return;

  if (direction === "up" && index > 0) {
    columnsEl.insertBefore(items[index], items[index - 1]);
    return;
  }
  if (direction === "down" && index < items.length - 1) {
    columnsEl.insertBefore(items[index + 1], items[index]);
  }
}

function applyModalConfig() {
  const sectionId = dashboardState.modalSection;
  if (!sectionId) return;
  const modal = ensureDashboardConfigModal();
  if (!modal) return;

  const checkedColumns = Array.from(
    modal.querySelectorAll("input[name='dashboard-config-column']:checked")
  ).map((input) => String(input.value || "").trim());
  const checkedSolutions = Array.from(
    modal.querySelectorAll("input[name='dashboard-config-solution']:checked")
  ).map((input) => String(input.value || "").trim());
  const totalSolutions = modal.querySelectorAll("input[name='dashboard-config-solution']").length;

  const defaults = cloneSectionDefaults(sectionId);
  const columns = checkedColumns.length ? checkedColumns : defaults.columns;
  const solutionIds = totalSolutions === 0 || checkedSolutions.length === totalSolutions ? null : checkedSolutions;

  updateSectionPrefs(sectionId, {
    columns,
    solution_ids: solutionIds,
  });

  closeDashboardConfigModal();
  rerender();
}

function bindDashboardEvents(ctx) {
  const viewRoot = typeof document !== "undefined" ? document.getElementById("view-dashboard") : null;
  if (!viewRoot || dashboardState.bound) return;
  dashboardState.bound = true;

  viewRoot.addEventListener("change", (event) => {
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

  viewRoot.addEventListener("keydown", (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    const trigger = event.target.closest("[data-dashboard-action='open-config']");
    if (!trigger) return;
    event.preventDefault();
    const sectionId = String(trigger.getAttribute("data-dashboard-section") || "");
    openDashboardConfigModal(sectionId);
    renderDashboardConfigModal(sectionId, {
      columnDefsBySection: dashboardState.columnDefsBySection || {},
    });
  });

  viewRoot.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-dashboard-action") || "";

    if (action === "reset-view") {
      updatePrefs({
        scope: DEFAULT_PREFS.scope,
        sort: DEFAULT_PREFS.sort,
        rows: DEFAULT_PREFS.rows,
        horizon_days: DEFAULT_PREFS.horizon_days,
      });
      rerender();
      return;
    }

    if (action === "open-config") {
      const sectionId = String(actionEl.getAttribute("data-dashboard-section") || "");
      openDashboardConfigModal(sectionId);
      renderDashboardConfigModal(sectionId, {
        columnDefsBySection: dashboardState.columnDefsBySection || {},
      });
    }
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-dashboard-action") || "";

    if (action === "close-config") {
      closeDashboardConfigModal();
      return;
    }
    if (action === "select-all-solutions") {
      setAllModalSolutionChecks(true);
      return;
    }
    if (action === "clear-solutions") {
      setAllModalSolutionChecks(false);
      return;
    }
    if (action === "move-column-up") {
      moveModalColumn("up", String(actionEl.getAttribute("data-column-id") || ""));
      return;
    }
    if (action === "move-column-down") {
      moveModalColumn("down", String(actionEl.getAttribute("data-column-id") || ""));
      return;
    }
    if (action === "reset-table-config") {
      resetModalDraft(dashboardState.columnDefsBySection || {});
      return;
    }
    if (action === "apply-table-config") {
      applyModalConfig();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!dashboardState.modalSection) return;
    closeDashboardConfigModal();
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
        status: statusKey(solution.status),
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
  const filteredMainRows = applySectionSolutionFilter(sortedScopedRows, "main", (row) => row.solutionId);
  const scopedActiveRows = scopedRows.filter((row) => !row.isClosed);
  const scopedAtRiskRows = scopedActiveRows.filter((row) => row.riskScore >= 45);
  const scopedOverdueRows = scopedActiveRows.filter((row) => Number.isFinite(row.dueDays) && row.dueDays < 0);

  const rowBudget = viewportRowBudget();
  const mainRows = filteredMainRows.slice(0, Math.min(prefs.rows, rowBudget.main));
  const supportRows = rowBudget.secondary;

  const completedAllRows = solutionRows
    .filter((row) => row.status === "complete" && row.completedDate)
    .filter((row) => daysAgo(today, row.completedDate) <= prefs.horizon_days)
    .sort((a, b) => (b.completedDate?.getTime() || 0) - (a.completedDate?.getTime() || 0));
  const completedRows = applySectionSolutionFilter(completedAllRows, "completed", (row) => row.solutionId).slice(
    0,
    supportRows
  );

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
  const upcomingRows = applySectionSolutionFilter(upcomingAllRows, "upcoming", (entry) => entry.row.solutionId)
    .slice(0, supportRows)
    .map((entry) => ({ ...entry.row, stage: entry.stage }));

  const backlogRows = applySectionSolutionFilter(deferredRows, "backlog", (entry) => entry.row.solutionId)
    .slice(0, supportRows)
    .map((entry) => ({ ...entry.row, shortfall: entry.shortfall }));

  dashboardState.sectionOptions = {
    main: buildSectionOptions(sortedScopedRows),
    completed: buildSectionOptions(completedAllRows),
    upcoming: buildSectionOptions(upcomingAllRows, (entry) => entry.row),
    backlog: buildSectionOptions(deferredRows, (entry) => entry.row),
  };

  const formatStatusLabel = (value) => {
    if (typeof formatStatus === "function") return formatStatus(value);
    return String(value || "-");
  };
  const columnDefsBySection = createColumnDefinitions(formatStatusLabel);
  dashboardState.columnDefsBySection = columnDefsBySection;

  if (dashboardState.modalSection) {
    renderDashboardConfigModal(dashboardState.modalSection, { columnDefsBySection });
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
    const includedText = Array.isArray(getSectionPrefs("main").solution_ids)
      ? `${filteredMainRows.length} included`
      : `${filteredMainRows.length} in scope`;
    els.dashboardTopProjects.innerHTML = `
      <div class="dashboard-main-head">
        <div class="dashboard-title-block">
          <h3>Current Deliverables</h3>
          <p class="dashboard-card-sub">Executive view of priority solutions and delivery pressure.</p>
        </div>
      </div>
      <p class="dashboard-main-meta">
        ${mainRows.length} shown · ${includedText} · ${scopedAtRiskRows.length} at risk · ${scopedOverdueRows.length} overdue
      </p>
      ${renderSectionTable({
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
      ${renderSectionTable({
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
      ${renderSectionTable({
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
      ${renderSectionTable({
        sectionId: "backlog",
        rows: backlogRows,
        columnDefs: columnDefsBySection.backlog,
        tableClass: "dashboard-mini-table",
        emptyText: "No backlog outside current FTE headroom.",
      })}
    `;
  }
}
