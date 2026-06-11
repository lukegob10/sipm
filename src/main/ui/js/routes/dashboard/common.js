import {
  DAY_MS,
  dateOnlyToDate,
  daysBetweenDateOnly,
  startOfDateOnlyDay,
} from "../../utils/date-only.js";
import {
  ragPillMarkup as sharedRagPillMarkup,
  statusPillMarkup,
} from "../../utils/display-tokens.js";

const HOURS_PER_FTE_MONTH = 160;
const HOURS_PER_FTE_CAPACITY = 40;

export const DASHBOARD_PREFS_KEY_PREFIX = "sipm-dashboard-view-prefs-v4";
export const DASHBOARD_PREFS_LEGACY_KEY = "sipm-dashboard-view-prefs-v3";
export const DEFAULT_PREFS = Object.freeze({
  scope: "active",
  sort: "risk_desc",
  rows: 10,
  horizon_days: 30,
  last_config_section: "main",
});

export const SCOPE_OPTIONS = new Set(["all", "active", "at_risk", "mine"]);
export const SORT_OPTIONS = new Set(["risk_desc", "due_asc", "fte_desc", "project_alpha"]);
export const ROW_OPTIONS = new Set([8, 10, 12, 16, 20]);
export const HORIZON_OPTIONS = new Set([14, 30, 60, 90]);

const CLOSED_STATUSES = new Set(["complete", "abandoned"]);

export const DASHBOARD_SECTIONS = Object.freeze(["main", "completed", "upcoming", "backlog"]);
export const DASHBOARD_SECTION_TITLES = Object.freeze({
  main: "Current Deliverables",
  completed: "Complete",
  upcoming: "Upcoming",
  backlog: "Backlog",
});

export const DASHBOARD_SECTION_DEFAULTS = Object.freeze({
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

export const DASHBOARD_SECTION_COLUMNS = Object.freeze({
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

export function emptySectionOptions() {
  return {
    main: [],
    completed: [],
    upcoming: [],
    backlog: [],
  };
}

export function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function num(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

export function parseDate(value) {
  return dateOnlyToDate(value);
}

export function startOfDay(value) {
  return startOfDateOnlyDay(value);
}

export function daysUntil(fromDate, toDate) {
  return daysBetweenDateOnly(fromDate, toDate);
}

export function daysAgo(fromDate, pastDate) {
  return Math.max(0, Math.ceil((fromDate.getTime() - pastDate.getTime()) / DAY_MS));
}

export function statusKey(status) {
  return normalize(status);
}

export function isClosedStatus(status) {
  return CLOSED_STATUSES.has(statusKey(status));
}

export const ragPillMarkup = sharedRagPillMarkup;

export function dueTone(days) {
  if (!Number.isFinite(days)) return "muted";
  if (days < 0) return "danger";
  if (days <= 7) return "warn";
  return "positive";
}

export function dueLabel(days) {
  if (!Number.isFinite(days)) return "No due date";
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "Due today";
  return `Due in ${days}d`;
}

export function userCapacityFte(user) {
  if (!user) return 1;
  const byFte = Number(user.capacity_fte_month);
  const byHours = Number(user.capacity_hours);
  if (Number.isFinite(byFte)) return Math.max(byFte, 0);
  if (Number.isFinite(byHours)) return Math.max(byHours, 0) / HOURS_PER_FTE_CAPACITY;
  return 1;
}

export function solutionFte(solution) {
  if (!solution) return 0;
  const byFte = Number(solution.capacity_fte_months);
  const byHours = Number(solution.capacity_hours);
  if (Number.isFinite(byFte)) return Math.max(byFte, 0);
  if (Number.isFinite(byHours)) return Math.max(byHours, 0) / HOURS_PER_FTE_MONTH;
  return 0;
}

export function formatFte(value) {
  return num(value, 0).toFixed(2);
}

export function currentUserTokens(state) {
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

export function isOwnedByCurrentUser(solution, tokens) {
  if (!solution || !tokens || !tokens.size) return false;
  const candidates = [solution.owner_user_soeid, solution.owner, solution.key_stakeholder];
  return candidates.some((value) => tokens.has(normalize(value)));
}

export function riskScoreForSolution(row) {
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

export function applyScope(rows, scope) {
  if (scope === "all") return rows;
  if (scope === "active") return rows.filter((row) => !row.isClosed);
  if (scope === "at_risk") return rows.filter((row) => !row.isClosed && row.riskScore >= 45);
  if (scope === "mine") return rows.filter((row) => !row.isClosed && row.isMine);
  return rows;
}

export function sortRows(rows, sortKey) {
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

export function viewportRowBudget() {
  const height = typeof window !== "undefined" ? window.innerHeight : 960;
  if (height >= 1320) return { main: 10, secondary: 6 };
  if (height >= 1180) return { main: 9, secondary: 5 };
  if (height >= 1060) return { main: 8, secondary: 5 };
  if (height >= 940) return { main: 7, secondary: 4 };
  if (height >= 860) return { main: 6, secondary: 4 };
  return { main: 5, secondary: 3 };
}

export function displayValue(value, fallback = "—") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

export function dashboardActionButtonMarkup(action, attrName, attrValue, label, extraClass = "") {
  const attrToken = attrName && attrValue ? ` ${attrName}="${esc(attrValue)}"` : "";
  return `<button type="button" class="${extraClass ? esc(extraClass) : "dashboard-inline-action"}" data-dashboard-action="${action}"${attrToken}>${esc(label)}</button>`;
}

export function dashboardSolutionLinkMarkup(solutionId, label) {
  if (!solutionId) return `<strong>${esc(label)}</strong>`;
  return `<button type="button" class="dashboard-solution-link" data-dashboard-action="open-solution" data-solution-id="${esc(solutionId)}">${esc(label)}</button>`;
}

export function dashboardProjectLinkMarkup(projectId, label, extraClass = "") {
  if (!projectId) return `<strong>${esc(label)}</strong>`;
  const classToken = extraClass ? ` ${extraClass}` : "";
  return `<button type="button" class="dashboard-project-link${classToken}" data-dashboard-action="open-project" data-project-id="${esc(projectId)}">${esc(label)}</button>`;
}

export function createColumnDefinitions(formatStatusLabel) {
  const allColumns = {
    solution: {
      label: "Solution",
      render: (row) => `<div class="dashboard-solution-cell">
        <div>${dashboardSolutionLinkMarkup(row.solutionId, row.solutionName)}</div>
      </div>`,
    },
    solution_id: {
      label: "Solution ID",
      render: (row) => esc(displayValue(row.solutionId)),
    },
    project: {
      label: "Project",
      render: (row) => dashboardProjectLinkMarkup(row.projectId, row.projectName, " strong"),
    },
    project_id: {
      label: "Project ID",
      render: (row) => esc(displayValue(row.projectId)),
    },
    status: {
      label: "Status",
      render: (row) => statusPillMarkup(row.statusRaw, formatStatusLabel(row.statusRaw)),
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

export function renderSectionTable({ columns, rows, columnDefs, tableClass, emptyText }) {
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
    <div class="table dashboard-table-shell">
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

export function calculateColumnWidths(columns) {
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
