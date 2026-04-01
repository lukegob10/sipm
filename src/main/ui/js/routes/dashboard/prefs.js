import {
  DASHBOARD_PREFS_KEY_PREFIX,
  DASHBOARD_PREFS_LEGACY_KEY,
  DASHBOARD_SECTION_COLUMNS,
  DASHBOARD_SECTION_DEFAULTS,
  DASHBOARD_SECTIONS,
  DEFAULT_PREFS,
  HORIZON_OPTIONS,
  ROW_OPTIONS,
  SORT_OPTIONS,
  SCOPE_OPTIONS,
  emptySectionOptions,
  normalize,
  num,
} from "./common.js";

export function createDashboardState() {
  return {
    ctx: null,
    bound: false,
    prefs: normalizePrefs(DEFAULT_PREFS),
    prefsSpaceId: "",
    sectionOptions: emptySectionOptions(),
    modalSection: null,
    lastConfigSection: "main",
    columnDefsBySection: null,
  };
}

export function currentDashboardSpaceId(dashboardState) {
  return normalize(dashboardState.ctx?.state?.activeSpace?.space_id || "no-space") || "no-space";
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

export function dashboardPrefsStorageKey(spaceId = "no-space") {
  return `${DASHBOARD_PREFS_KEY_PREFIX}:${normalize(spaceId || "no-space") || "no-space"}`;
}

export function loadPrefs(spaceId = "no-space") {
  const defaultPrefs = normalizePrefs(DEFAULT_PREFS);
  try {
    if (typeof localStorage === "undefined") return defaultPrefs;
    const scopedKey = dashboardPrefsStorageKey(spaceId);
    const persistLoadedPrefs = (prefs) => {
      localStorage.setItem(scopedKey, JSON.stringify(prefs));
      return prefs;
    };
    const raw = localStorage.getItem(scopedKey);
    if (!raw) {
      const legacyRaw = localStorage.getItem(DASHBOARD_PREFS_LEGACY_KEY);
      if (!legacyRaw) {
        return persistLoadedPrefs(defaultPrefs);
      }
      const legacyParsed = normalizePrefs(JSON.parse(legacyRaw));
      localStorage.removeItem(DASHBOARD_PREFS_LEGACY_KEY);
      return persistLoadedPrefs(legacyParsed);
    }
    const parsed = JSON.parse(raw);
    const normalized = normalizePrefs(parsed);
    if (JSON.stringify(parsed) !== JSON.stringify(normalized)) {
      localStorage.setItem(scopedKey, JSON.stringify(normalized));
    }
    return normalized;
  } catch {
    try {
      if (typeof localStorage !== "undefined") {
        localStorage.setItem(dashboardPrefsStorageKey(spaceId), JSON.stringify(defaultPrefs));
      }
    } catch {
      // Ignore persistence issues.
    }
    return defaultPrefs;
  }
}

export function savePrefs(dashboardState, spaceId = dashboardState.prefsSpaceId || currentDashboardSpaceId(dashboardState)) {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(dashboardPrefsStorageKey(spaceId), JSON.stringify(dashboardState.prefs));
  } catch {
    // Ignore persistence issues.
  }
}

export function ensurePrefsLoaded(dashboardState, spaceId = currentDashboardSpaceId(dashboardState)) {
  const targetSpaceId = normalize(spaceId || "no-space") || "no-space";
  if (dashboardState.prefsSpaceId === targetSpaceId) return;
  dashboardState.prefs = loadPrefs(targetSpaceId);
  dashboardState.prefsSpaceId = targetSpaceId;
}

export function normalizePrefs(input) {
  const next = {
    scope: String(input?.scope || DEFAULT_PREFS.scope),
    sort: String(input?.sort || DEFAULT_PREFS.sort),
    rows: num(input?.rows, DEFAULT_PREFS.rows),
    horizon_days: num(input?.horizon_days, DEFAULT_PREFS.horizon_days),
    last_config_section: String(input?.last_config_section || DEFAULT_PREFS.last_config_section),
  };

  if (!SCOPE_OPTIONS.has(next.scope)) next.scope = DEFAULT_PREFS.scope;
  if (!SORT_OPTIONS.has(next.sort)) next.sort = DEFAULT_PREFS.sort;
  if (!ROW_OPTIONS.has(next.rows)) next.rows = DEFAULT_PREFS.rows;
  if (!HORIZON_OPTIONS.has(next.horizon_days)) next.horizon_days = DEFAULT_PREFS.horizon_days;
  if (!DASHBOARD_SECTIONS.includes(next.last_config_section)) next.last_config_section = DEFAULT_PREFS.last_config_section;

  const sections = {};
  DASHBOARD_SECTIONS.forEach((sectionId) => {
    sections[sectionId] = normalizeSectionPrefs(sectionId, input?.sections?.[sectionId]);
  });

  return {
    ...next,
    sections,
  };
}

export function updatePrefs(dashboardState, patch) {
  const mergedSections = {
    ...(dashboardState.prefs?.sections || {}),
    ...((patch && patch.sections) || {}),
  };
  dashboardState.prefs = normalizePrefs({
    ...(dashboardState.prefs || normalizePrefs(DEFAULT_PREFS)),
    ...(patch || {}),
    sections: mergedSections,
  });
  savePrefs(dashboardState);
}

export function getSectionPrefs(dashboardState, sectionId) {
  const section = dashboardState.prefs?.sections?.[sectionId];
  return section || cloneSectionDefaults(sectionId);
}

export function selectedColumnsForSection(dashboardState, sectionId, columnDefs) {
  const allowedColumns = new Set(DASHBOARD_SECTION_COLUMNS[sectionId] || []);
  const selected = [];
  const rawColumns = Array.isArray(getSectionPrefs(dashboardState, sectionId).columns)
    ? getSectionPrefs(dashboardState, sectionId).columns
    : [];
  rawColumns.forEach((columnId) => {
    if (!allowedColumns.has(columnId)) return;
    if (!columnDefs[columnId]) return;
    if (!selected.includes(columnId)) selected.push(columnId);
  });

  if (selected.length) return selected;

  return cloneSectionDefaults(sectionId).columns.filter((columnId) => !!columnDefs[columnId]);
}

export function updateSectionPrefs(dashboardState, sectionId, patch) {
  if (!DASHBOARD_SECTIONS.includes(sectionId)) return;
  const current = getSectionPrefs(dashboardState, sectionId);
  const hasSolutionIds =
    patch && typeof patch === "object" && Object.prototype.hasOwnProperty.call(patch, "solution_ids");

  updatePrefs(dashboardState, {
    sections: {
      [sectionId]: {
        columns: Array.isArray(patch?.columns) ? [...patch.columns] : current.columns,
        solution_ids: hasSolutionIds ? patch.solution_ids : current.solution_ids,
      },
    },
  });
}

export function buildSectionOptions(rows, pickRow = (entry) => entry) {
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

export function normalizeSectionSolutionSelections(
  dashboardState,
  sectionOptionsBySection = dashboardState.sectionOptions
) {
  const nextSections = {};
  let changed = false;

  DASHBOARD_SECTIONS.forEach((sectionId) => {
    const current = getSectionPrefs(dashboardState, sectionId);
    const solutionIds = Array.isArray(current.solution_ids) ? current.solution_ids : null;
    if (!solutionIds) return;

    const validSolutionIds = new Set(
      (sectionOptionsBySection?.[sectionId] || [])
        .map((option) => String(option.solutionId || "").trim())
        .filter(Boolean)
    );
    const filteredIds = solutionIds.filter((solutionId) => validSolutionIds.has(String(solutionId || "").trim()));
    const normalizedIds = filteredIds.length ? filteredIds : null;
    const unchanged = Array.isArray(normalizedIds)
      ? solutionIds.length === normalizedIds.length && solutionIds.every((solutionId, index) => solutionId === normalizedIds[index])
      : normalizedIds === null && solutionIds.length === 0;
    if (unchanged) return;

    changed = true;
    nextSections[sectionId] = {
      ...current,
      solution_ids: normalizedIds,
    };
  });

  if (!changed) return false;
  dashboardState.prefs = normalizePrefs({
    ...(dashboardState.prefs || normalizePrefs(DEFAULT_PREFS)),
    sections: {
      ...(dashboardState.prefs?.sections || {}),
      ...nextSections,
    },
  });
  savePrefs(dashboardState);
  return true;
}

export function applySectionSolutionFilter(
  dashboardState,
  rows,
  sectionId,
  idFromRow = (row) => row.solutionId
) {
  const solutionIds = getSectionPrefs(dashboardState, sectionId).solution_ids;
  if (!Array.isArray(solutionIds)) return rows;
  const selected = new Set(solutionIds);
  return rows.filter((row) => selected.has(String(idFromRow(row) || "").trim()));
}

export { cloneSectionDefaults };
