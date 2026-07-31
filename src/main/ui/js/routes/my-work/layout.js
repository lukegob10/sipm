export const MY_WORK_LAYOUT_STORAGE_KEY = "sipm-my-work-layout-v1";
export const DEFAULT_PLAN_WIDTH = 58;
export const MIN_PLAN_WIDTH = 40;
export const MAX_PLAN_WIDTH = 72;
export const PLAN_WIDTH_STEP = 4;

export function clampPlanWidth(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return DEFAULT_PLAN_WIDTH;
  return Math.min(MAX_PLAN_WIDTH, Math.max(MIN_PLAN_WIDTH, Math.round(numeric)));
}

export function normalizeMyWorkPlanLayout(value = {}) {
  return {
    collapsed: value?.collapsed === true,
    width: clampPlanWidth(value?.width),
  };
}

function browserStorage() {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readStoredMyWorkPlanLayout(storage = browserStorage()) {
  if (!storage) return normalizeMyWorkPlanLayout();
  try {
    return normalizeMyWorkPlanLayout(JSON.parse(storage.getItem(MY_WORK_LAYOUT_STORAGE_KEY) || "{}"));
  } catch {
    return normalizeMyWorkPlanLayout();
  }
}

export function persistMyWorkPlanLayout(value, storage = browserStorage()) {
  const normalized = normalizeMyWorkPlanLayout(value);
  if (!storage) return normalized;
  try {
    storage.setItem(MY_WORK_LAYOUT_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Layout persistence is optional; the controls still work for this session.
  }
  return normalized;
}

export function ensureMyWorkPlanLayout(workState) {
  if (!workState.planLayout) workState.planLayout = readStoredMyWorkPlanLayout();
  else workState.planLayout = normalizeMyWorkPlanLayout(workState.planLayout);
  return workState.planLayout;
}
