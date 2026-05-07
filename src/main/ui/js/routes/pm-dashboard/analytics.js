import {
  dateOnlyToDate,
  daysBetweenDateOnly,
  startOfDateOnlyDay,
} from "../../utils/date-only.js";

const CLOSED_SOLUTION_STATUSES = new Set(["complete", "abandoned"]);
const CLOSED_SUBCOMPONENT_STATUSES = new Set(["complete", "abandoned"]);

export const SOLUTION_STATUS_ORDER = ["not_started", "active", "on_hold", "complete", "abandoned"];
export const SUBCOMPONENT_STATUS_ORDER = ["to_do", "in_progress", "on_hold", "complete", "abandoned"];

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

export function parseDate(value) {
  return dateOnlyToDate(value);
}

export function startOfDay(value) {
  return startOfDateOnlyDay(value);
}

export function daysUntil(fromDate, toDate) {
  return daysBetweenDateOnly(fromDate, toDate);
}

export function isClosedSolutionStatus(status) {
  return CLOSED_SOLUTION_STATUSES.has(String(status || "").toLowerCase());
}

export function isClosedSubcomponentStatus(status) {
  return CLOSED_SUBCOMPONENT_STATUSES.has(String(status || "").toLowerCase());
}

export function nonEmpty(value) {
  return String(value || "").trim().length > 0;
}

export function scoreTone(score) {
  if (score >= 70) return "danger";
  if (score >= 45) return "warn";
  return "positive";
}

export function healthTone(score) {
  if (score >= 85) return "positive";
  if (score >= 70) return "warn";
  return "danger";
}

export function utilTone(utilization, capacity, allocated) {
  if (capacity <= 0 && allocated > 0) return "danger";
  if (utilization >= 100) return "danger";
  if (utilization >= 85) return "warn";
  return "positive";
}

export function dueDeltaLabel(days) {
  if (!Number.isFinite(days)) return "No due date";
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "Due today";
  return `Due in ${days}d`;
}

export function isoDateLabel(value) {
  const date = parseDate(value);
  if (!date) return "—";
  return date.toISOString().slice(0, 10);
}

export function formatFteValue(value, formatFte) {
  if (typeof formatFte === "function") return formatFte(value);
  return num(value).toFixed(2);
}

export function renderPMDashboardRowLink(label, action, attrs = {}) {
  const extraAttrs = Object.entries(attrs)
    .filter(([, value]) => String(value || "").trim())
    .map(([name, value]) => ` ${name}="${esc(value)}"`)
    .join("");
  return `<button type="button" class="pm-row-link" data-pm-dashboard-action="${esc(action)}"${extraAttrs}>${esc(label)}</button>`;
}

export function renderPMDashboardProjectLink(label, projectId) {
  if (!String(projectId || "").trim()) return `<strong>${esc(label)}</strong>`;
  return renderPMDashboardRowLink(label, "open-project", {
    "data-project-id": projectId,
    "aria-label": `Open project ${label}`,
  });
}

export function renderPMDashboardSolutionLink(label, solutionId) {
  if (!String(solutionId || "").trim()) return `<strong>${esc(label)}</strong>`;
  return renderPMDashboardRowLink(label, "open-solution", {
    "data-solution-id": solutionId,
    "aria-label": `Open solution ${label}`,
  });
}

export function normalizePMDashboardIdentity(value) {
  return String(value || "").trim().toLowerCase();
}

export function buildPMDashboardOwnerDirectory(users) {
  const activeUsers = Array.isArray(users) ? users.filter((user) => user && user.is_active !== false) : [];
  const soeidToKey = new Map();
  const displayNameCounts = new Map();

  activeUsers.forEach((user) => {
    const soeid = String(user?.soeid || "").trim();
    const displayName = String(user?.display_name || "").trim();
    const soeidToken = normalizePMDashboardIdentity(soeid);
    const displayNameToken = normalizePMDashboardIdentity(displayName);
    if (soeidToken) soeidToKey.set(soeidToken, soeid);
    if (displayNameToken && soeid) {
      displayNameCounts.set(displayNameToken, (displayNameCounts.get(displayNameToken) || 0) + 1);
    }
  });

  const uniqueDisplayNameToKey = new Map();
  activeUsers.forEach((user) => {
    const soeid = String(user?.soeid || "").trim();
    const displayNameToken = normalizePMDashboardIdentity(user?.display_name);
    if (!soeid || !displayNameToken) return;
    if ((displayNameCounts.get(displayNameToken) || 0) !== 1) return;
    uniqueDisplayNameToKey.set(displayNameToken, soeid);
  });

  return { soeidToKey, uniqueDisplayNameToKey };
}

export function resolvePMDashboardOwnerAssigneeKey(soeidValue, labelValue, ownerDirectory) {
  const soeidToken = normalizePMDashboardIdentity(soeidValue);
  if (soeidToken && ownerDirectory?.soeidToKey?.has(soeidToken)) {
    return ownerDirectory.soeidToKey.get(soeidToken) || "";
  }
  const labelToken = normalizePMDashboardIdentity(labelValue);
  if (!labelToken || labelToken === "unassigned") return "";
  if (ownerDirectory?.soeidToKey?.has(labelToken)) {
    return ownerDirectory.soeidToKey.get(labelToken) || "";
  }
  return ownerDirectory?.uniqueDisplayNameToKey?.get(labelToken) || "";
}

export function renderPMDashboardOwnerLink(label, assigneeKey) {
  const ownerLabel = String(label || "Unassigned").trim() || "Unassigned";
  const resolvedKey = String(assigneeKey || "").trim();
  if (!resolvedKey || resolvedKey === "unassigned") return esc(ownerLabel);
  return renderPMDashboardRowLink(ownerLabel, "open-capacity-allocations", {
    "data-assignee-key": resolvedKey,
    "aria-label": `Open workload for ${ownerLabel}`,
  });
}

export function renderPMDashboardTimelineLink(row) {
  if (row.itemKind === "solution") {
    return renderPMDashboardSolutionLink(row.name, row.solutionId);
  }
  if (!String(row.subcomponentId || "").trim()) return `<strong>${esc(row.name)}</strong>`;
  return renderPMDashboardRowLink(row.name, "open-subcomponent", {
    "data-subcomponent-id": row.subcomponentId,
    "aria-label": `Open task ${row.name}`,
  });
}

export function renderPMDashboardCapacityLink(row) {
  const assigneeKey = String(row?.key || "").trim();
  const label = String(row?.label || "Unassigned").trim() || "Unassigned";
  if (!assigneeKey || assigneeKey === "unassigned") return `<strong>${esc(label)}</strong>`;
  return renderPMDashboardRowLink(row.label, "open-capacity-allocations", {
    "data-assignee-key": row.key,
    "aria-label": `Open workload for ${row.label}`,
  });
}
