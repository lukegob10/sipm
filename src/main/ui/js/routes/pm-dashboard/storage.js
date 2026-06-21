export const PM_DASHBOARD_STORAGE_KEY_PREFIX = "sipm-pm-dashboard-ui-v1";
export const DEFAULT_PM_DASHBOARD_SECTION = "actions";
export const PM_DASHBOARD_SECTION_IDS = new Set([
  DEFAULT_PM_DASHBOARD_SECTION,
  "health",
  "risks",
  "timeline",
  "capacity",
  "status",
]);

export function monthKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${date.getFullYear()}-${month}`;
}

export function currentMonthToken() {
  return monthKey(new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()));
}

export function normalizeMonthToken(value) {
  const token = String(value || "").trim();
  return /^\d{4}-\d{2}$/.test(token) ? token : "";
}

export function normalizePMDashboardSection(value) {
  const token = String(value || "").trim().toLowerCase();
  return PM_DASHBOARD_SECTION_IDS.has(token) ? token : DEFAULT_PM_DASHBOARD_SECTION;
}

export function pmDashboardStorageKey(spaceId) {
  const scope = String(spaceId || "no-space").trim().toLowerCase() || "no-space";
  return `${PM_DASHBOARD_STORAGE_KEY_PREFIX}:${scope}`;
}

export function pmDashboardActiveSectionStorageKey() {
  return `${PM_DASHBOARD_STORAGE_KEY_PREFIX}:active-section`;
}

export function readStoredCapacityMonth(spaceId) {
  if (typeof window === "undefined" || !window.localStorage) return "";
  try {
    return normalizeMonthToken(window.localStorage.getItem(pmDashboardStorageKey(spaceId)) || "");
  } catch {
    return "";
  }
}

export function persistCapacityMonth(spaceId, monthToken) {
  const normalized = normalizeMonthToken(monthToken);
  if (!normalized || typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(pmDashboardStorageKey(spaceId), normalized);
  } catch {
    // Ignore persistence failures.
  }
}

export function readStoredActiveSection() {
  if (typeof window === "undefined" || !window.localStorage) return DEFAULT_PM_DASHBOARD_SECTION;
  try {
    return normalizePMDashboardSection(window.localStorage.getItem(pmDashboardActiveSectionStorageKey()) || "");
  } catch {
    return DEFAULT_PM_DASHBOARD_SECTION;
  }
}

export function persistActiveSection(sectionId) {
  const normalized = normalizePMDashboardSection(sectionId);
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(pmDashboardActiveSectionStorageKey(), normalized);
  } catch {
    // Ignore persistence failures.
  }
}

export function ensureActiveSection(pmDashboardState) {
  if (!pmDashboardState.activeSection) {
    pmDashboardState.activeSection = readStoredActiveSection();
  }
  const normalized = normalizePMDashboardSection(pmDashboardState.activeSection);
  if (pmDashboardState.activeSection !== normalized) {
    persistActiveSection(normalized);
  }
  pmDashboardState.activeSection = normalized;
  return normalized;
}

export function ensureCapacityMonth(pmDashboardState, spaceId) {
  const normalizedSpaceId = String(spaceId || "").trim();
  if (pmDashboardState.capacitySpaceId !== normalizedSpaceId) {
    pmDashboardState.capacitySpaceId = normalizedSpaceId;
    const restoredMonth = readStoredCapacityMonth(normalizedSpaceId);
    pmDashboardState.capacityMonth = restoredMonth || currentMonthToken();
    if (!restoredMonth) persistCapacityMonth(normalizedSpaceId, pmDashboardState.capacityMonth);
  }
  const normalizedMonth = normalizeMonthToken(pmDashboardState.capacityMonth) || currentMonthToken();
  if (pmDashboardState.capacityMonth !== normalizedMonth) {
    persistCapacityMonth(normalizedSpaceId, normalizedMonth);
  }
  pmDashboardState.capacityMonth = normalizedMonth;
  return normalizedMonth;
}
