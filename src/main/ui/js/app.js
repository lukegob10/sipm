const API_BASE = "/api";
const HOURS_PER_FTE_MONTH = 160;
const HOURS_PER_FTE_CAPACITY = 40;
const APP_ASSET_VERSION = (() => {
  try {
    return new URL(import.meta.url).searchParams.get("v") || Date.now().toString();
  } catch {
    return Date.now().toString();
  }
})();

// Prevent stale CSS by cache-busting the linked stylesheet on each load.
(() => {
  const sheet = document.querySelector('link[rel="stylesheet"][href*="styles.css"]');
  if (sheet) {
    const url = new URL(sheet.href, location.origin);
    url.searchParams.set("v", Date.now().toString());
    sheet.href = url.toString();
  }
})();

const els = {
  navButtons: document.querySelectorAll(".nav-btn[data-view]"),
  navAdminSection: document.getElementById("nav-admin-section"),
  views: document.querySelectorAll(".view"),
  status: document.getElementById("connection-status"),
  spaceSwitcher: document.getElementById("space-switcher"),
  spaceRolePill: document.getElementById("space-role-pill"),
  currentUser: document.getElementById("current-user"),
  logoutBtn: document.getElementById("logout-btn"),
  themeToggle: document.getElementById("theme-toggle"),
  appShell: document.getElementById("app-shell"),
  authScreen: document.getElementById("auth-screen"),
  authTabLogin: document.getElementById("auth-tab-login"),
  authTabRegister: document.getElementById("auth-tab-register"),
  authTabs: document.getElementById("auth-tabs"),
  loginForm: document.getElementById("login-form"),
  registerForm: document.getElementById("register-form"),
  resetLink: document.getElementById("reset-link"),
  authError: document.getElementById("auth-error"),
  authNotice: document.getElementById("auth-notice"),
  resetScreen: document.getElementById("reset-screen"),
  verifyTempForm: document.getElementById("verify-temp-form"),
  resetForm: document.getElementById("reset-form"),
  resetError: document.getElementById("reset-error"),
  resetSuccess: document.getElementById("reset-success"),
  idleModal: document.getElementById("idle-modal"),
  idleStay: document.getElementById("idle-stay"),
  idleLogout: document.getElementById("idle-logout"),
  masterFilters: document.getElementById("master-filters"),
  masterQuickstart: document.getElementById("master-quickstart"),
  masterTable: document.getElementById("master-table"),
  subcomponentsWorkbenchSearch: document.getElementById("subcomponents-workbench-search"),
  subcomponentsWorkbenchProject: document.getElementById("subcomponents-workbench-project"),
  subcomponentsWorkbenchSolution: document.getElementById("subcomponents-workbench-solution"),
  subcomponentsWorkbenchAssignee: document.getElementById("subcomponents-workbench-assignee"),
  subcomponentsWorkbenchStatus: document.getElementById("subcomponents-workbench-status"),
  subcomponentsWorkbenchPriority: document.getElementById("subcomponents-workbench-priority"),
  subcomponentsWorkbenchClearFilters: document.getElementById("subcomponents-workbench-clear-filters"),
  subcomponentsWorkbenchTable: document.getElementById("subcomponents-workbench-table"),
  subcomponentsWorkbenchKpis: document.getElementById("subcomponents-workbench-kpis"),
  subcomponentsWorkbenchSelectionCount: document.getElementById("subcomponents-workbench-selection-count"),
  subcomponentsWorkbenchSavedSelect: document.getElementById("subcomponents-workbench-saved-select"),
  subcomponentsWorkbenchSavedName: document.getElementById("subcomponents-workbench-saved-name"),
  subcomponentsWorkbenchSavedSave: document.getElementById("subcomponents-workbench-saved-save"),
  subcomponentsWorkbenchSavedDelete: document.getElementById("subcomponents-workbench-saved-delete"),
  subcomponentsWorkbenchSavedStatus: document.getElementById("subcomponents-workbench-saved-status"),
  subcomponentsWorkbenchBulkAction: document.getElementById("subcomponents-workbench-bulk-action"),
  subcomponentsWorkbenchBulkStatus: document.getElementById("subcomponents-workbench-bulk-status"),
  subcomponentsWorkbenchBulkAssignee: document.getElementById("subcomponents-workbench-bulk-assignee"),
  subcomponentsWorkbenchBulkShift: document.getElementById("subcomponents-workbench-bulk-shift"),
  subcomponentsWorkbenchBulkApply: document.getElementById("subcomponents-workbench-bulk-apply"),
  subcomponentsWorkbenchForm: document.getElementById("subcomponents-workbench-form"),
  subcomponentsWorkbenchReset: document.getElementById("subcomponents-workbench-reset"),
  subcomponentsWorkbenchClose: document.getElementById("subcomponents-workbench-close"),
  subcomponentsWorkbenchContext: document.getElementById("subcomponents-workbench-context"),
  subcomponentsWorkbenchActivity: document.getElementById("subcomponents-workbench-activity"),
  subcomponentsWorkbenchLayout: document.getElementById("subcomponents-workbench-layout"),
  subcomponentsWorkbenchDrawer: document.getElementById("subcomponents-workbench-drawer"),
  createProjectBtn: document.getElementById("create-project"),
  createSolutionBtn: document.getElementById("create-solution"),
  projectModal: document.getElementById("project-modal"),
  projectModalClose: document.getElementById("project-modal-close"),
  projectModalTitle: document.getElementById("project-modal-title"),
  solutionModal: document.getElementById("solution-modal"),
  solutionModalClose: document.getElementById("solution-modal-close"),
  solutionModalTitle: document.getElementById("solution-modal-title"),
  confirmModal: document.getElementById("confirm-modal"),
  confirmModalTitle: document.getElementById("confirm-modal-title"),
  confirmModalMessage: document.getElementById("confirm-modal-message"),
  confirmModalClose: document.getElementById("confirm-modal-close"),
  confirmModalCancel: document.getElementById("confirm-modal-cancel"),
  confirmModalConfirm: document.getElementById("confirm-modal-confirm"),
  solutionActivity: document.getElementById("solution-activity"),
  solutionSubcomponentTable: document.getElementById("solution-subcomponent-table"),
  subcomponentViewToggle: document.getElementById("subcomponent-view-toggle"),
  presetMy: document.getElementById("preset-my"),
  presetOverdue: document.getElementById("preset-overdue"),
  presetBlocked: document.getElementById("preset-blocked"),
  presetClear: document.getElementById("preset-clear"),
  bulkSelectedCount: document.getElementById("bulk-selected-count"),
  bulkAction: document.getElementById("bulk-action"),
  bulkStatus: document.getElementById("bulk-status"),
  bulkOwner: document.getElementById("bulk-owner"),
  bulkApply: document.getElementById("bulk-apply"),
  dashboardCards: document.getElementById("dashboard-cards"),
  dashboardSpaceCapacity: document.getElementById("dashboard-space-capacity"),
  dashboardTopProjects: document.getElementById("dashboard-top-projects"),
  dashboardCompletedQuarter: document.getElementById("dashboard-completed-quarter"),
  dashboardUpcomingQuarter: document.getElementById("dashboard-upcoming-quarter"),
  dashboardBacklog: document.getElementById("dashboard-backlog"),
  pmDashboardSummary: document.getElementById("pm-dashboard-summary"),
  pmDashboardHealth: document.getElementById("pm-dashboard-health"),
  pmDashboardRisks: document.getElementById("pm-dashboard-risks"),
  pmDashboardTimeline: document.getElementById("pm-dashboard-timeline"),
  pmDashboardCapacity: document.getElementById("pm-dashboard-capacity"),
  pmDashboardStatus: document.getElementById("pm-dashboard-status"),
  pmDashboardActions: document.getElementById("pm-dashboard-actions"),
  teamForm: document.getElementById("team-form"),
  teamList: document.getElementById("team-list"),
  deleteTeamBtn: document.getElementById("delete-team"),
  teamMemberForm: document.getElementById("team-member-form"),
  teamMemberList: document.getElementById("team-member-list"),
  deleteMemberBtn: document.getElementById("delete-member"),
  capacityUserForm: document.getElementById("capacity-user-form"),
  capacityUserList: document.getElementById("capacity-user-list"),
  capacityTeamFilter: document.getElementById("capacity-team-filter"),
  capacityNameFilter: document.getElementById("capacity-name-filter"),
  capacityReload: document.getElementById("capacity-reload"),
  capacityClearFilters: document.getElementById("capacity-clear-filters"),
  capacityUserOptions: document.getElementById("capacity-user-options"),
  rosterUpload: document.getElementById("roster-upload"),
  rosterDownload: document.getElementById("roster-download"),
  rosterFile: document.getElementById("roster-file"),
  rosterImportResult: document.getElementById("roster-import-result"),
  capacityUserDelete: document.getElementById("capacity-user-delete"),
  spaceCreateForm: document.getElementById("space-create-form"),
  spaceList: document.getElementById("space-list"),
  spaceAdminNote: document.getElementById("space-admin-note"),
  spaceMembershipForm: document.getElementById("space-membership-form"),
  spaceMembershipNote: document.getElementById("space-membership-note"),
  spaceMembershipSpaceSelect: document.getElementById("space-membership-space-select"),
  spaceMembershipList: document.getElementById("space-membership-list"),
  globalAdminForm: document.getElementById("global-admin-form"),
  globalAdminRevoke: document.getElementById("global-admin-revoke"),
  globalAdminList: document.getElementById("global-admin-list"),
  globalAdminNote: document.getElementById("global-admin-note"),
  projectForm: document.getElementById("project-form"),
  projectSubmitBtn: document.getElementById("project-submit-btn"),
  projectFormStatus: document.getElementById("project-form-status"),
  csvActionsToggle: document.getElementById("csv-actions-toggle"),
  csvActionsMenu: document.getElementById("csv-actions-menu"),
  projectsDownload: document.getElementById("projects-download"),
  projectsUpload: document.getElementById("projects-upload"),
  projectsFile: document.getElementById("projects-file"),
  projectsImportResult: document.getElementById("projects-import-result"),
  solutionForm: document.getElementById("solution-form"),
  solutionSubmitBtn: document.getElementById("solution-submit-btn"),
  solutionFormStatus: document.getElementById("solution-form-status"),
  solutionsDownload: document.getElementById("solutions-download"),
  solutionsUpload: document.getElementById("solutions-upload"),
  solutionsFile: document.getElementById("solutions-file"),
  solutionsImportResult: document.getElementById("solutions-import-result"),
  csvUploadModal: document.getElementById("csv-upload-modal"),
  csvUploadBackdrop: document.getElementById("csv-upload-backdrop"),
  csvUploadClose: document.getElementById("csv-upload-close"),
  csvUploadTitle: document.getElementById("csv-upload-title"),
  csvUploadDescription: document.getElementById("csv-upload-description"),
  csvDropzone: document.getElementById("csv-dropzone"),
  csvUploadFile: document.getElementById("csv-upload-file"),
  csvUploadFileName: document.getElementById("csv-upload-file-name"),
  csvDownloadTemplate: document.getElementById("csv-download-template"),
  csvSubmitUpload: document.getElementById("csv-submit-upload"),
  csvUploadStatus: document.getElementById("csv-upload-status"),
  phasesTable: document.getElementById("phases-table"),
  subcomponentForm: document.getElementById("subcomponent-form"),
  subcomponentFormStatus: document.getElementById("subcomponent-form-status"),
  showSubcomponentFormBtn: document.getElementById("show-subcomponent-form"),
  kanbanBoard: document.getElementById("kanban-board"),
  calendarGrid: document.getElementById("calendar-grid"),
  calendarMonthInput: document.getElementById("calendar-month"),
  calendarPrev: document.getElementById("calendar-prev"),
  calendarNext: document.getElementById("calendar-next"),
  kanbanFilterProject: document.getElementById("kanban-filter-project"),
  kanbanFilterOwner: document.getElementById("kanban-filter-owner"),
  calendarFilterProject: document.getElementById("calendar-filter-project"),
  calendarFilterOwner: document.getElementById("calendar-filter-owner"),
  calendarModal: document.getElementById("calendar-modal"),
  calendarModalTitle: document.getElementById("calendar-modal-title"),
  calendarModalList: document.getElementById("calendar-modal-list"),
  calendarModalClose: document.getElementById("calendar-modal-close"),
  planningBoard: document.getElementById("planning-board"),
  planningSearch: document.getElementById("planning-search"),
  planningTeamTagFilter: document.getElementById("planning-team-tag-filter"),
  planningFilterOver: document.getElementById("planning-filter-over"),
  planningFilterUnder: document.getElementById("planning-filter-under"),
  planningFrom: document.getElementById("planning-from"),
  planningTo: document.getElementById("planning-to"),
  planningLayout: document.getElementById("planning-layout"),
  planningDrawer: document.getElementById("planning-drawer"),
  planningAllocationDrawer: document.getElementById("planning-allocation-drawer"),
  planningWindowDrawer: document.getElementById("planning-window-drawer"),
  planningAddAllocation: document.getElementById("planning-add-allocation"),
  planningCloseAllocation: document.getElementById("planning-close-allocation"),
  planningCloseWindow: document.getElementById("planning-close-window"),
  planningWindowForm: document.getElementById("planning-window-form"),
  allocationForm: document.getElementById("allocation-form"),
  planningWindowSelect: document.getElementById("planning-window-select"),
  allocationWindowHint: document.getElementById("allocation-window-hint"),
  allocationStatus: document.getElementById("allocation-status"),
  editWindowBtn: document.getElementById("edit-window-btn"),
  saveWindowBtn: document.getElementById("save-window-btn"),
  clearWindowBtn: document.getElementById("clear-window-btn"),
  planningModal: document.getElementById("planning-modal"),
  planningModalTitle: document.getElementById("planning-modal-title"),
  planningModalBody: document.getElementById("planning-modal-body"),
  planningModalClose: document.getElementById("planning-modal-close"),
  planningRoster: document.getElementById("planning-roster"),
  planningWindowSummary: document.getElementById("planning-window-summary"),
  planningKpis: document.getElementById("planning-kpis"),
  newSubcomponentBtn: document.getElementById("new-subcomponent"),
  deleteProjectBtn: document.getElementById("delete-project"),
  deleteSolutionBtn: document.getElementById("delete-solution"),
  deleteSubcomponentBtn: document.getElementById("delete-subcomponent"),
};

const normalize = (value) => (value || "").toString().trim().toLowerCase();
const normalizeSpaceRole = (value) => normalize(value).replace(/[\s-]+/g, "_");
const isSpaceAdminRole = (value) => normalizeSpaceRole(value) === "space_admin";

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numberOr(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeMonthStart(value) {
  if (!value) return "";
  const iso = String(value).slice(0, 10);
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return "";
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-01`;
}

function monthInputToDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^\d{4}-\d{2}$/.test(raw)) return `${raw}-01`;
  return normalizeMonthStart(raw);
}

function allocationMonthStart(allocation) {
  return normalizeMonthStart(allocation?.month_start || allocation?.week_start);
}

function allocationFteMonths(allocation) {
  if (!allocation) return 0;
  if (Number.isFinite(Number(allocation.fte_months))) return Number(allocation.fte_months);
  if (Number.isFinite(Number(allocation.hours))) return Number(allocation.hours) / HOURS_PER_FTE_MONTH;
  return 0;
}

function userCapacityFteMonth(user) {
  if (!user) return 1;
  if (Number.isFinite(Number(user.capacity_fte_month))) return Number(user.capacity_fte_month);
  if (Number.isFinite(Number(user.capacity_hours))) return Number(user.capacity_hours) / HOURS_PER_FTE_CAPACITY;
  return 1;
}

function formatFte(value) {
  return numberOr(value, 0).toFixed(2);
}

function hoursFromFteInput(value) {
  const fte = Math.max(numberOr(value, 0), 0);
  return Math.round(fte * HOURS_PER_FTE_MONTH);
}

function hoursFromNullableFteInput(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  return hoursFromFteInput(value);
}

function fteFromHoursForInput(hoursValue, fallback = 0) {
  const hours = numberOr(hoursValue, Number.NaN);
  if (!Number.isFinite(hours)) return formatFte(fallback);
  return formatFte(hours / HOURS_PER_FTE_MONTH);
}

function createTeamCapacityState() {
  return {
    loading: false,
    error: "",
    lastLoadedAt: "",
    lastLoadedSpaceId: "",
    lastLoadedSpaceName: "",
    requestId: 0,
  };
}

const state = {
  user: null,
  authed: false,
  spaces: [],
  activeSpace: null,
  spaceMembershipSpaceId: "",
  spaceMembersBySpace: {},
  spaceMembersLoadedBySpace: {},
  globalAdmins: [],
  globalAdminsLoaded: false,
  authMode: "login",
  phases: [],
  projects: [],
  solutions: [],
  solutionPhases: {}, // solution_id -> phases
  subcomponents: [],
  teams: [],
  users: [],
  allocations: [],
  planningWindows: [],
  filters: {},
  deliverableSelection: new Set(),
  deliverablesPreset: "",
  subcomponentView: "table",
  subcomponentsWorkbench: {
    preset: "all",
    filters: {
      search: "",
      project_id: "",
      solution_id: "",
      assignee: "",
      assignee_name: "",
      status: "",
      priority_max: "",
    },
    selected: new Set(),
    activeSubcomponentId: "",
    visibleIds: [],
    savedViews: [],
    selectedSavedViewId: "",
    activityRequestId: 0,
    drawerOpen: false,
    drawerReturnSubcomponentId: "",
    drawerReturnScrollY: null,
    suppressAutoScrollOnce: false,
  },
  currentView: "master",
  theme: "dark",
  loading: false,
  pendingRefresh: false,
  calendarMonth: (() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  })(),
  kanbanFilters: { project: "", owner: "" },
  calendarFilters: { project: "", owner: "" },
  planningGroupCollapsed: new Set(),
  capacitySelectedSoeid: "",
  teamCapacity: createTeamCapacityState(),
  structureStudio: null,
  loadedEntities: new Set(),
};

let liveSyncStarted = false;
let refreshInFlight = false;
const pendingRefreshEntities = new Set();
const ignoreNextRefresh = new Set();
let suppressHashChange = false;
let viewPrefetchTimer = null;
const IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const IDLE_WARN_MS = 55 * 60 * 1000;
const ACCESS_REFRESH_INTERVAL_MS = 4 * 60 * 1000;
const SUBCOMPONENTS_WORKBENCH_SAVED_VIEWS_KEY_PREFIX = "sipm-subcomponents-workbench-views";
let idleLastActive = Date.now();
let idleWarned = false;
let idleInterval = null;
let idleListenersBound = false;
let sessionRefreshPromise = null;
let lastSessionRefreshAt = 0;
let pendingConfirmResolve = null;
let confirmReturnFocusEl = null;
const csvUploadState = {
  kind: "",
  file: null,
};

const DATA_ENTITIES = ["phases", "projects", "solutions", "subcomponents", "teams", "users", "allocations", "windows"];
const KNOWN_VIEWS = [
  "master",
  "subcomponents-workbench",
  "dashboard",
  "pm-dashboard",
  "kanban",
  "calendar",
  "planning",
  "team-capacity",
  "spaces",
  "access",
];
const ADMIN_VIEWS = new Set(["team-capacity", "spaces", "access"]);
const VIEW_DATA_REQUIREMENTS = {
  master: ["phases", "projects", "solutions", "subcomponents", "users"],
  "subcomponents-workbench": ["projects", "solutions", "subcomponents", "users"],
  dashboard: ["projects", "solutions", "users"],
  "pm-dashboard": ["projects", "solutions", "subcomponents", "users", "allocations", "windows"],
  kanban: ["phases", "projects", "solutions"],
  calendar: ["projects", "solutions"],
  planning: ["projects", "solutions", "subcomponents", "teams", "users", "allocations", "windows"],
  "team-capacity": ["users", "allocations"],
  spaces: [],
  access: [],
};
const VIEW_PREFETCH_TARGET = {
  master: "dashboard",
  "subcomponents-workbench": "planning",
  dashboard: "pm-dashboard",
  "pm-dashboard": "kanban",
  kanban: "planning",
  calendar: "planning",
  planning: "team-capacity",
  "team-capacity": "spaces",
  spaces: "access",
  access: "planning",
};
const ROUTE_MODULE_LOADERS = {
  master: () => import(`./routes/master.js?v=${APP_ASSET_VERSION}`),
  "subcomponents-workbench": () => import(`./routes/subcomponents-workbench.js?v=${APP_ASSET_VERSION}`),
  dashboard: () => import(`./routes/dashboard.js?v=${APP_ASSET_VERSION}`),
  "pm-dashboard": () => import(`./routes/pm-dashboard.js?v=${APP_ASSET_VERSION}`),
  kanban: () => import(`./routes/kanban.js?v=${APP_ASSET_VERSION}`),
  calendar: () => import(`./routes/calendar.js?v=${APP_ASSET_VERSION}`),
  planning: () => import(`./routes/planning.js?v=${APP_ASSET_VERSION}`),
  "team-capacity": () => import(`./routes/team-capacity.js?v=${APP_ASSET_VERSION}`),
  spaces: () => import(`./routes/spaces.js?v=${APP_ASSET_VERSION}`),
  access: () => import(`./routes/access.js?v=${APP_ASSET_VERSION}`),
};
const routeModuleCache = {};
const routeModuleInFlight = {};

function getRouteModule(view) {
  return routeModuleCache[normalizeView(view)] || null;
}

async function ensureRouteModule(view) {
  const key = normalizeView(view);
  const loader = ROUTE_MODULE_LOADERS[key];
  if (!loader) return null;
  if (routeModuleCache[key]) return routeModuleCache[key];
  if (routeModuleInFlight[key]) return routeModuleInFlight[key];
  routeModuleInFlight[key] = loader()
    .then((mod) => {
      routeModuleCache[key] = mod || {};
      return routeModuleCache[key];
    })
    .catch((err) => {
      console.warn(`Failed to load route module '${key}'`, err);
      return null;
    })
    .finally(() => {
      delete routeModuleInFlight[key];
    });
  return routeModuleInFlight[key];
}

function normalizeView(view) {
  const candidate = (view || "").toString().trim().toLowerCase();
  if (candidate === "settings") return "team-capacity";
  return KNOWN_VIEWS.includes(candidate) ? candidate : "master";
}

function isAdminView(view) {
  return ADMIN_VIEWS.has(normalizeView(view));
}

function userCanAccessAdminViews() {
  if (!state.authed) return false;
  if (userIsGlobalAdmin()) return true;
  return isSpaceAdminRole(state.activeSpace?.space_role);
}

function canAccessView(view) {
  const normalized = normalizeView(view);
  if (normalized === "access") return state.authed && userIsGlobalAdmin();
  if (normalized === "team-capacity" || normalized === "spaces") return userCanAccessAdminViews();
  if (isAdminView(normalized)) return false;
  return true;
}

function resolveAccessibleView(view) {
  const normalized = normalizeView(view);
  if (!canAccessView(normalized)) {
    return "master";
  }
  return normalized;
}

function viewFromHash() {
  const raw = (window.location.hash || "").trim();
  if (!raw) return "master";
  const stripped = raw.replace(/^#\/?/, "").split("?")[0].trim().toLowerCase();
  return normalizeView(stripped);
}

function syncHashForView(view, replace = false) {
  const target = `#/${normalizeView(view)}`;
  if (window.location.hash === target) return;
  suppressHashChange = true;
  if (replace) {
    window.history.replaceState(null, "", target);
  } else {
    window.location.hash = target;
  }
  window.setTimeout(() => {
    suppressHashChange = false;
  }, 0);
}

function entitiesForView(view) {
  return VIEW_DATA_REQUIREMENTS[normalizeView(view)] || VIEW_DATA_REQUIREMENTS.master;
}

function isKnownEntity(entity) {
  return DATA_ENTITIES.includes(entity);
}

function clearDataState() {
  state.phases = [];
  state.projects = [];
  state.solutions = [];
  state.solutionPhases = {};
  state.subcomponents = [];
  state.teams = [];
  state.users = [];
  state.allocations = [];
  state.planningWindows = [];
  state.loadedEntities = new Set();
  state.capacitySelectedSoeid = "";
  state.teamCapacity = createTeamCapacityState();
  if (state.subcomponentsWorkbench) {
    state.subcomponentsWorkbench.selected = new Set();
    state.subcomponentsWorkbench.activeSubcomponentId = "";
    state.subcomponentsWorkbench.visibleIds = [];
    state.subcomponentsWorkbench.activityRequestId = 0;
    state.subcomponentsWorkbench.drawerOpen = false;
    state.subcomponentsWorkbench.drawerReturnSubcomponentId = "";
    state.subcomponentsWorkbench.drawerReturnScrollY = null;
    state.subcomponentsWorkbench.suppressAutoScrollOnce = false;
  }
}

function markIgnoreRefresh(entity) {
  if (entity) ignoreNextRefresh.add(entity);
}

async function fetchEntityData(entity) {
  if (entity === "phases") return api("/phases");
  if (entity === "projects") return api("/projects");
  if (entity === "solutions") return api("/solutions");
  if (entity === "subcomponents") return api("/subcomponents");
  if (entity === "teams") return api("/teams");
  if (entity === "users") return api("/users");
  if (entity === "allocations") return api("/resource-allocations");
  if (entity === "windows") return api("/planning/windows");
  throw new Error(`Unknown data entity: ${entity}`);
}

function applyEntityData(entity, data) {
  if (entity === "phases") {
    state.phases = Array.isArray(data) ? data : [];
    state.solutionPhases = {};
  } else if (entity === "projects") {
    state.projects = Array.isArray(data) ? data : [];
  } else if (entity === "solutions") {
    state.solutions = Array.isArray(data) ? data : [];
  } else if (entity === "subcomponents") {
    state.subcomponents = Array.isArray(data) ? data : [];
  } else if (entity === "teams") {
    state.teams = Array.isArray(data) ? data : [];
  } else if (entity === "users") {
    state.users = Array.isArray(data) ? data : [];
  } else if (entity === "allocations") {
    state.allocations = Array.isArray(data) ? data : [];
  } else if (entity === "windows") {
    state.planningWindows = Array.isArray(data) ? data : [];
  }
  state.loadedEntities.add(entity);
}

function scheduleViewPrefetch(view) {
  const targetView = VIEW_PREFETCH_TARGET[normalizeView(view)];
  if (!targetView || !state.authed) return;
  const needed = entitiesForView(targetView).filter((entity) => !state.loadedEntities.has(entity));
  if (!needed.length) return;
  if (viewPrefetchTimer) window.clearTimeout(viewPrefetchTimer);
  viewPrefetchTimer = window.setTimeout(async () => {
    if (!state.authed || state.loading || refreshInFlight) return;
    try {
      const results = await Promise.allSettled(needed.map((entity) => fetchEntityData(entity)));
      let changed = false;
      results.forEach((result, idx) => {
        if (result.status !== "fulfilled") return;
        applyEntityData(needed[idx], result.value);
        changed = true;
      });
      if (changed) populateSelects();
    } catch (err) {
      console.warn("Prefetch skipped", err);
    }
  }, 450);
}

async function refreshFromServer(entity = "all") {
  const ent = (entity || "all").toString();
  if (!state.authed) return;

  if (ignoreNextRefresh.has(ent)) {
    ignoreNextRefresh.delete(ent);
    return;
  }

  if (state.loading || refreshInFlight) {
    pendingRefreshEntities.add(ent);
    return;
  }

  const selectedProjectId = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
  const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  const selectedSubcomponentId = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";

  refreshInFlight = true;
  try {
    const entities = ent === "all" ? DATA_ENTITIES : (isKnownEntity(ent) ? [ent] : DATA_ENTITIES);
    const results = await Promise.allSettled(entities.map((key) => fetchEntityData(key)));
    const errors = [];
    let changed = false;
    results.forEach((result, idx) => {
      if (result.status !== "fulfilled") {
        errors.push(result.reason);
        return;
      }
      applyEntityData(entities[idx], result.value);
      changed = true;
    });
    if (errors.length) {
      const authError = errors.find((err) => err && err.status === 401);
      if (authError) {
        handleAuthError(authError);
        return;
      }
      console.warn("Refresh failed", errors);
    }
    if (changed) populateSelects();
    renderActiveView();
    restoreSelections(selectedProjectId, selectedSolutionId, selectedSubcomponentId);
  } catch (err) {
    console.warn("Refresh failed", err);
    if (handleAuthError(err)) {
      setStatus("Sign in required", "warn");
    }
  } finally {
    refreshInFlight = false;
    if (pendingRefreshEntities.size) {
      const pending = Array.from(pendingRefreshEntities);
      pendingRefreshEntities.clear();
      if (pending.includes("all") || pending.length > 1) {
        refreshFromServer("all");
      } else {
        refreshFromServer(pending[0]);
      }
    }
  }
}

function setStatus(text, type = "") {
  if (!els.status) return;
  els.status.textContent = text;
  els.status.className = `pill ${type}`;
}

const importResultTimers = new WeakMap();

function clearImportResult(el) {
  if (!el) return;
  const timer = importResultTimers.get(el);
  if (timer) {
    clearTimeout(timer);
    importResultTimers.delete(el);
  }
  el.textContent = "";
  el.classList.remove("error");
}

function setImportResult(el, message, isError = false, autoClearMs = null) {
  if (!el) return;
  clearImportResult(el);
  if (!message) return;
  el.textContent = message;
  el.classList.toggle("error", !!isError);
  const clearAfter = autoClearMs == null ? (isError ? 12000 : 5000) : autoClearMs;
  if (clearAfter > 0) {
    const timer = setTimeout(() => clearImportResult(el), clearAfter);
    importResultTimers.set(el, timer);
  }
}

const deliverableFormNoticeTimers = new WeakMap();

function clearDeliverableFormNotice(statusEl) {
  if (!statusEl) return;
  const timer = deliverableFormNoticeTimers.get(statusEl);
  if (timer) {
    clearTimeout(timer);
    deliverableFormNoticeTimers.delete(statusEl);
  }
  statusEl.textContent = "";
  statusEl.classList.remove("notice-success", "notice-error");
}

function timestampLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function setDeliverableFormNotice(statusEl, message, tone = "info", autoClearMs = 0) {
  if (!statusEl) return;
  clearDeliverableFormNotice(statusEl);
  if (!message) return;
  statusEl.textContent = message;
  if (tone === "success") statusEl.classList.add("notice-success");
  if (tone === "error") statusEl.classList.add("notice-error");
  if (autoClearMs > 0) {
    const timer = setTimeout(() => clearDeliverableFormNotice(statusEl), autoClearMs);
    deliverableFormNoticeTimers.set(statusEl, timer);
  }
}

function setAuthVisible(show) {
  if (els.authScreen) els.authScreen.classList.toggle("hidden", !show);
  if (els.appShell) els.appShell.classList.toggle("hidden", show);
}

function setResetVisible(show) {
  if (els.resetScreen) els.resetScreen.classList.toggle("hidden", !show);
  if (els.authScreen) els.authScreen.classList.toggle("hidden", show);
  if (els.appShell) els.appShell.classList.toggle("hidden", show);
}


function rolePillText(ctx) {
  if (!ctx) return "";
  const role = normalizeSpaceRole(ctx.space_role || "member").replace(/_/g, " ");
  if (ctx.is_global_admin) return `global admin • ${ctx.space_name || ""}`;
  return `${role} • ${ctx.space_name || ""}`;
}

function syncRoleAwareActions() {
  const canUseAdminActions = userCanAccessAdminViews();
  [
    els.deleteProjectBtn,
    els.deleteSolutionBtn,
    els.deleteSubcomponentBtn,
  ].forEach((button) => {
    if (!button) return;
    button.classList.toggle("hidden", !canUseAdminActions);
    if (!canUseAdminActions) {
      button.disabled = true;
    }
  });
}

function syncRoleAwareNavigation() {
  const adminButtons = Array.from(els.navButtons || []).filter((btn) => isAdminView(btn.dataset.view));
  let hasAnyVisibleAdminButton = false;
  adminButtons.forEach((btn) => {
    const allowed = canAccessView(btn.dataset.view || "");
    btn.classList.toggle("hidden", !allowed);
    if (allowed) hasAnyVisibleAdminButton = true;
  });
  if (els.navAdminSection) {
    els.navAdminSection.classList.toggle("hidden", !hasAnyVisibleAdminButton);
  }
  syncRoleAwareActions();
  if (!canAccessView(state.currentView)) {
    setView("master", { replaceHash: true });
  }
}


function renderSpaceSwitcher() {
  if (els.spaceSwitcher) {
    if (!state.authed) {
      els.spaceSwitcher.innerHTML = "<option value=''>Sign in</option>";
      els.spaceSwitcher.disabled = true;
    } else {
      const active = state.activeSpace;
      const options = (state.spaces || [])
        .map((space) => `<option value="${space.space_id}">${space.name}</option>`)
        .join("");
      if (!options && active?.space_id) {
        els.spaceSwitcher.innerHTML = `<option value="${active.space_id}">${active.space_name || active.space_id}</option>`;
      } else {
        els.spaceSwitcher.innerHTML = options || "<option value=''>No spaces</option>";
      }
      els.spaceSwitcher.disabled = !state.spaces?.length;
      if (active?.space_id) {
        els.spaceSwitcher.value = active.space_id;
      }
    }
  }
  if (els.spaceRolePill) {
    const text = state.authed ? rolePillText(state.activeSpace) : "";
    els.spaceRolePill.textContent = text || "no active space";
    els.spaceRolePill.classList.toggle("muted", !text);
  }
  syncRoleAwareNavigation();
}


async function refreshSpaceContext(options = {}) {
  const apiOptions = options.apiOptions || {};
  if (!state.authed) {
    state.spaces = [];
    state.activeSpace = null;
    state.spaceMembershipSpaceId = "";
    state.spaceMembersBySpace = {};
    state.spaceMembersLoadedBySpace = {};
    state.globalAdmins = [];
    state.globalAdminsLoaded = false;
    state.subcomponentsWorkbench.savedViews = [];
    state.subcomponentsWorkbench.selectedSavedViewId = "";
    renderSpaceSwitcher();
    updateSubcomponentsWorkbenchSavedViewsUI();
    return;
  }
  const [spaces, activeSpace] = await Promise.all([
    api("/spaces", apiOptions),
    api("/auth/active-space", apiOptions),
  ]);
  state.spaces = Array.isArray(spaces) ? spaces : [];
  state.activeSpace = activeSpace || null;
  if (state.activeSpace?.space_id && !state.spaces.some((s) => s.space_id === state.activeSpace.space_id)) {
    state.spaces.unshift({
      space_id: state.activeSpace.space_id,
      name: state.activeSpace.space_name || state.activeSpace.space_id,
      slug: "",
      is_active: true,
    });
  }
  const visibleSpaceIds = new Set((state.spaces || []).map((space) => space.space_id));
  Object.keys(state.spaceMembersBySpace || {}).forEach((spaceId) => {
    if (!visibleSpaceIds.has(spaceId)) delete state.spaceMembersBySpace[spaceId];
  });
  Object.keys(state.spaceMembersLoadedBySpace || {}).forEach((spaceId) => {
    if (!visibleSpaceIds.has(spaceId)) delete state.spaceMembersLoadedBySpace[spaceId];
  });
  if (!state.spaceMembershipSpaceId || !visibleSpaceIds.has(state.spaceMembershipSpaceId)) {
    state.spaceMembershipSpaceId = state.activeSpace?.space_id || state.spaces[0]?.space_id || "";
  }
  renderSpaceSwitcher();
  loadSubcomponentsWorkbenchSavedViews();
  updateSubcomponentsWorkbenchSavedViewsUI();
}


function setAuthed(user) {
  state.user = user;
  state.authed = !!user;
  lastSessionRefreshAt = user ? Date.now() : 0;
  if (!user) {
    sessionRefreshPromise = null;
  }
  if (els.currentUser) {
    els.currentUser.textContent = user ? user.display_name || user.email : "Not signed in";
    els.currentUser.classList.toggle("muted", !user);
  }
  if (els.logoutBtn) {
    els.logoutBtn.disabled = !user;
  }
  if (els.resetScreen) {
    els.resetScreen.classList.add("hidden");
  }
  if (user) {
    showAuthNotice("");
    resetIdleTimer();
    startIdleWatch();
  } else {
    clearDataState();
    state.spaces = [];
    state.activeSpace = null;
    state.spaceMembershipSpaceId = "";
    state.spaceMembersBySpace = {};
    state.spaceMembersLoadedBySpace = {};
    state.globalAdmins = [];
    state.globalAdminsLoaded = false;
    state.subcomponentsWorkbench.savedViews = [];
    state.subcomponentsWorkbench.selectedSavedViewId = "";
    stopIdleWatch();
  }
  setAuthVisible(!state.authed);
  if (!state.authed) {
    setStatus("Sign in required", "warn");
  }
  renderSpaceSwitcher();
  updateSubcomponentsWorkbenchSavedViewsUI();
}

function setAuthMode(mode) {
  state.authMode = mode;
  els.authTabLogin?.classList.toggle("active", mode === "login");
  els.authTabRegister?.classList.toggle("active", mode === "register");
  els.authTabs?.classList.toggle("hidden", false);
  els.loginForm?.classList.toggle("hidden", mode !== "login");
  els.registerForm?.classList.toggle("hidden", mode !== "register");
  els.resetLink?.classList.toggle("hidden", mode !== "login");
  if (els.authError) els.authError.textContent = "";
}

function showAuthError(message) {
  if (els.authError) {
    els.authError.textContent = message || "";
  }
}

function showAuthNotice(message) {
  if (!els.authNotice) return;
  els.authNotice.textContent = message || "";
  els.authNotice.classList.toggle("hidden", !message);
}

function showResetError(message) {
  if (els.resetError) els.resetError.textContent = message || "";
}

function showResetSuccess(message) {
  if (els.resetSuccess) els.resetSuccess.textContent = message || "";
}

function showIdleModal() {
  if (!els.idleModal) return;
  els.idleModal.classList.remove("hidden");
}

function hideIdleModal() {
  if (!els.idleModal) return;
  els.idleModal.classList.add("hidden");
}

function resetIdleTimer() {
  idleLastActive = Date.now();
  if (idleWarned) {
    idleWarned = false;
    hideIdleModal();
  }
  maybeRefreshSessionOnActivity();
}

function startIdleWatch() {
  stopIdleWatch();
  if (!idleListenersBound) {
    const events = ["mousemove", "keydown", "click", "scroll", "touchstart"];
    events.forEach((evt) => window.addEventListener(evt, resetIdleTimer, { passive: true }));
    idleListenersBound = true;
  }
  idleInterval = setInterval(() => {
    if (!state.authed) return;
    const elapsed = Date.now() - idleLastActive;
    if (!idleWarned && elapsed >= IDLE_WARN_MS) {
      idleWarned = true;
      showIdleModal();
    }
    if (elapsed >= IDLE_TIMEOUT_MS) {
      handleSessionExpired();
    }
  }, 30 * 1000);
}

function stopIdleWatch() {
  if (idleInterval) {
    clearInterval(idleInterval);
    idleInterval = null;
  }
  hideIdleModal();
}

async function refreshSessionTokens(options = {}) {
  const force = !!options.force;
  const allowLoggedOut = !!options.allowLoggedOut;
  const silentFailure = !!options.silentFailure;

  if (!force && !state.authed && !allowLoggedOut) {
    return null;
  }
  if (!force && Date.now() - lastSessionRefreshAt < ACCESS_REFRESH_INTERVAL_MS) {
    return state.user || {};
  }
  if (sessionRefreshPromise) {
    return sessionRefreshPromise;
  }

  const headers = {};
  if (state.activeSpace?.space_id) {
    headers["X-Space-Id"] = state.activeSpace.space_id;
  }

  sessionRefreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers,
      });
      const text = await res.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = text || null;
      }

      if (!res.ok) {
        const detail = data && data.detail !== undefined ? data.detail : data;
        const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : res.statusText;
        const err = new Error(message || res.statusText);
        err.status = res.status;
        throw err;
      }

      if (data && typeof data === "object") {
        setAuthed(data);
      }
      lastSessionRefreshAt = Date.now();

      try {
        await refreshSpaceContext({ apiOptions: { skipAuthRefresh: true } });
      } catch (err) {
        console.warn("Space context refresh after token refresh failed", err);
      }

      return data || {};
    } catch (err) {
      if (!silentFailure && err && (err.status === 401 || err.status === 423)) {
        handleSessionExpired();
      } else if (!silentFailure) {
        console.warn("Session refresh failed", err);
      }
      return null;
    } finally {
      sessionRefreshPromise = null;
    }
  })();

  return sessionRefreshPromise;
}

function maybeRefreshSessionOnActivity() {
  if (!state.authed) return;
  if (sessionRefreshPromise) return;
  if (Date.now() - lastSessionRefreshAt < ACCESS_REFRESH_INTERVAL_MS) return;
  refreshSessionTokens({ force: false }).catch(() => {});
}

async function api(path, options = {}) {
  const {
    timeoutMs: timeoutOption,
    skipAuthRefresh = false,
    _retriedAfterRefresh = false,
    ...requestOptions
  } = options;
  const headers = { ...(requestOptions.headers || {}) };
  if (state.authed && state.activeSpace?.space_id && !headers["X-Space-Id"]) {
    headers["X-Space-Id"] = state.activeSpace.space_id;
  }
  const isFormData = requestOptions.body instanceof FormData;
  if (!isFormData && requestOptions.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const timeoutMs = Number.isFinite(timeoutOption) ? timeoutOption : 15000;
  let controller = null;
  let timeoutId = null;
  if (!requestOptions.signal && timeoutMs > 0) {
    controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  }
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      ...requestOptions,
      headers,
      signal: requestOptions.signal || controller?.signal,
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text || null;
    }
    if (!res.ok) {
      if (res.status === 401 && state.authed && !_retriedAfterRefresh && !skipAuthRefresh) {
        const refreshed = await refreshSessionTokens({ force: true });
        if (refreshed) {
          return api(path, {
            ...options,
            _retriedAfterRefresh: true,
            skipAuthRefresh: true,
          });
        }
      }
      const detail = data && data.detail !== undefined ? data.detail : data;
      const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : res.statusText;
      const err = new Error(message || res.statusText);
      err.status = res.status;
      err.path = path;
      throw err;
    }
    return data;
  } catch (err) {
    if (err && err.name === "AbortError") {
      const timeoutErr = new Error(`Request timed out: ${path}`);
      timeoutErr.status = 408;
      timeoutErr.path = path;
      throw timeoutErr;
    }
    throw err;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

function handleAuthError(err) {
  if (err && err.status === 401) {
    handleSessionExpired();
    setAuthVisible(true);
    return true;
  }
  return false;
}

function handleSessionExpired() {
  sessionRefreshPromise = null;
  lastSessionRefreshAt = 0;
  setAuthed(null);
  showAuthNotice("Your session expired due to inactivity. Please sign in again.");
}

async function fetchCurrentUser() {
  try {
    const me = await api("/auth/me");
    setAuthed(me);
    return me;
  } catch (err) {
    if (err.status === 401) {
      const refreshed = await refreshSessionTokens({
        force: true,
        allowLoggedOut: true,
        silentFailure: true,
      });
      if (refreshed) {
        return state.user;
      }
      setAuthed(null);
      return null;
    }
    throw err;
  }
}

async function performLogin(email, password) {
  return api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ soeid: email, password }),
  });
}

async function performRegister(display_name, email, password) {
  return api("/auth/register", {
    method: "POST",
    body: JSON.stringify({ display_name, soeid: email, password }),
  });
}

function isResetPath() {
  return window.location.pathname.replace(/\/+$/, "") === "/reset-password";
}


function bindAuthUI() {
  setAuthMode("login");
  els.authTabLogin?.addEventListener("click", () => setAuthMode("login"));
  els.authTabRegister?.addEventListener("click", () => setAuthMode("register"));
  els.resetLink?.addEventListener("click", () => {
    window.location.href = "/reset-password";
  });

  els.loginForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    showAuthError("");
    const form = new FormData(els.loginForm);
    try {
      const user = await performLogin(form.get("soeid"), form.get("password"));
      setAuthed(user);
      setAuthVisible(false);
      startLiveSyncOnce();
      await refreshSpaceContext();
      await loadData();
    } catch (err) {
      if (!handleAuthError(err)) {
        showAuthError(err.message || "Login failed");
      }
    }
  });

  els.registerForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    showAuthError("");
    const form = new FormData(els.registerForm);
    try {
      const user = await performRegister(form.get("display_name"), form.get("soeid"), form.get("password"));
      setAuthed(user);
      setAuthVisible(false);
      startLiveSyncOnce();
      await refreshSpaceContext();
      await loadData();
    } catch (err) {
      if (!handleAuthError(err)) {
        showAuthError(err.message || "Registration failed");
      }
    }
  });

  els.verifyTempForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    showResetError("");
    showResetSuccess("");
    const form = new FormData(els.verifyTempForm);
    try {
      await api("/auth/verify-temp-password", {
        method: "POST",
        body: JSON.stringify({
          soeid: form.get("soeid"),
          temp_password: form.get("temp_password"),
        }),
      });
      els.verifyTempForm?.classList.add("hidden");
      els.resetForm?.classList.remove("hidden");
      showResetSuccess("Temporary password verified. Set a new password.");
    } catch (err) {
      showResetError(err.message || "Verification failed");
    }
  });

  els.resetForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    showResetError("");
    showResetSuccess("");
    const form = new FormData(els.resetForm);
    try {
      await api("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          new_password: form.get("new_password"),
          confirm_password: form.get("confirm_password"),
        }),
      });
      showResetSuccess("Password reset complete. Redirecting to login...");
      setTimeout(() => {
        window.location.href = "/";
      }, 1200);
    } catch (err) {
      showResetError(err.message || "Reset failed");
    }
  });


  els.logoutBtn?.addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (err) {
      console.warn("Logout error", err);
    } finally {
      setAuthed(null);
      setAuthVisible(true);
    }
  });

  els.idleStay?.addEventListener("click", async () => {
    try {
      const user = await refreshSessionTokens({ force: true });
      if (!user) throw new Error("Session refresh failed");
      setStatus("Online", "positive");
      resetIdleTimer();
      hideIdleModal();
    } catch (err) {
      handleSessionExpired();
    }
  });

  els.idleLogout?.addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (err) {
      console.warn("Logout error", err);
    } finally {
      setAuthed(null);
      setAuthVisible(true);
    }
  });
}

function startLiveSyncOnce() {
  if (liveSyncStarted) return;
  initLiveSync();
  liveSyncStarted = true;
}

function initSubcomponentsWorkbench() {
  bindSubcomponentsWorkbenchControls();
}

async function bootstrapAuth() {
  if (isResetPath()) {
    showResetError("");
    showResetSuccess("");
    els.verifyTempForm?.classList.remove("hidden");
    els.resetForm?.classList.add("hidden");
    setResetVisible(true);
    setStatus("Password reset", "warn");
    return;
  }
  setStatus("Checking session...", "warn");
  setAuthVisible(true);
  const user = await fetchCurrentUser();
  if (user) {
    setAuthVisible(false);
    startLiveSyncOnce();
    await refreshSpaceContext();
    if (state.currentView === "team-capacity") {
      await loadTeamCapacityData({ force: true });
    } else {
      await loadData();
    }
  } else {
    setStatus("Sign in required", "warn");
  }
}

async function loadData(options = {}) {
  const force = !!options.force;
  const silent = !!options.silent;
  const requestedEntities = Array.isArray(options.entities) ? options.entities.filter(isKnownEntity) : null;
  if (!state.authed) {
    setStatus("Sign in required", "warn");
    setAuthVisible(true);
    return;
  }
  const targetEntities = requestedEntities && requestedEntities.length
    ? [...new Set(requestedEntities)]
    : entitiesForView(state.currentView);
  const entitiesToFetch = force
    ? targetEntities
    : targetEntities.filter((entity) => !state.loadedEntities.has(entity));
  if (!entitiesToFetch.length) {
    renderActiveView();
    scheduleViewPrefetch(state.currentView);
    return;
  }
  const selectedProjectId = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
  const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  const selectedSubcomponentId = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";
  if (state.loading) {
    state.pendingRefresh = true;
    return;
  }
  state.loading = true;
  try {
    if (!silent) setStatus("Loading...", "warn");
    if (!silent) renderActiveView();
    const results = await Promise.allSettled(entitiesToFetch.map((entity) => fetchEntityData(entity)));
    const errors = [];
    results.forEach((result, idx) => {
      if (result.status === "fulfilled") {
        applyEntityData(entitiesToFetch[idx], result.value);
      } else {
        errors.push({ key: entitiesToFetch[idx], error: result.reason });
      }
    });

    if (errors.length) {
      const authError = errors.find((e) => e.error && e.error.status === 401);
      if (authError) {
        handleAuthError(authError.error);
        return;
      }
      const labels = errors.map((e) => e.key).join(", ");
      console.error("Load failed", errors);
      setStatus(`Load failed: ${labels}`, "danger");
      return;
    }

    populateSelects();

    if ((requestedEntities == null || requestedEntities.includes("projects") || requestedEntities.includes("solutions"))
      && !state.projects.length && !state.solutions.length) {
      setStatus("No data loaded", "warn");
    } else if (!silent) {
      setStatus("Online", "positive");
    }
    renderActiveView();
    restoreSelections(selectedProjectId, selectedSolutionId, selectedSubcomponentId);
    scheduleViewPrefetch(state.currentView);
  } catch (err) {
    console.error(err);
    if (handleAuthError(err)) {
      setStatus("Sign in required", "warn");
    } else {
      setStatus(err?.message ? `Error: ${err.message}` : "Error", "danger");
    }
  } finally {
    state.loading = false;
    if (state.pendingRefresh) {
      state.pendingRefresh = false;
      loadData();
    }
    if (pendingRefreshEntities.size) {
      const pending = Array.from(pendingRefreshEntities);
      pendingRefreshEntities.clear();
      if (pending.includes("all") || pending.length > 1) {
        refreshFromServer("all");
      } else {
        refreshFromServer(pending[0]);
      }
    }
  }
}

function setView(view, options = {}) {
  const previousView = state.currentView;
  const requestedView = normalizeView(view);
  const nextView = resolveAccessibleView(requestedView);
  const fromHash = !!options.fromHash;
  const replaceHash = !!options.replaceHash;
  const redirected = requestedView !== nextView;
  state.currentView = nextView;
  if (nextView === "subcomponents-workbench" && previousView !== nextView && state.subcomponentsWorkbench) {
    state.subcomponentsWorkbench.drawerOpen = false;
    state.subcomponentsWorkbench.drawerReturnSubcomponentId = "";
    state.subcomponentsWorkbench.drawerReturnScrollY = null;
    state.subcomponentsWorkbench.suppressAutoScrollOnce = false;
  }
  els.views.forEach((v) => v.classList.toggle("active", v.id === `view-${nextView}`));
  els.navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === nextView));
  if (!fromHash || redirected) {
    syncHashForView(nextView, redirected ? true : replaceHash);
  }
  const hasLazyModule = !!ROUTE_MODULE_LOADERS[nextView];
  if (hasLazyModule) {
    ensureRouteModule(nextView).then((loaded) => {
      if (state.currentView !== nextView) return;
      if (loaded) {
        renderActiveView();
      }
    });
  }
  if (state.authed) {
    if (nextView === "team-capacity") {
      loadTeamCapacityData({ force: true }).catch((err) => {
        console.warn("Team capacity load failed", err);
      });
    } else {
      loadData({ entities: entitiesForView(nextView) }).catch((err) => {
        console.warn("View load failed", err);
      });
    }
    renderActiveView();
    return;
  }
  renderActiveView();
}

function applyTheme(theme) {
  state.theme = theme;
  document.body.classList.toggle("theme-light", theme === "light");
  if (els.themeToggle) {
    els.themeToggle.textContent = theme === "light" ? "Dark Mode" : "Light Mode";
  }
  try {
    localStorage.setItem("jira-lite-theme", theme);
  } catch (e) {
    console.warn("Theme preference not saved", e);
  }
}

function initTheme() {
  let saved = "dark";
  try {
    saved = localStorage.getItem("jira-lite-theme") || "dark";
  } catch (e) {
    console.warn("Theme preference not loaded", e);
  }
  applyTheme(saved === "light" ? "light" : "dark");
  els.themeToggle?.addEventListener("click", () => {
    const next = document.body.classList.contains("theme-light") ? "dark" : "light";
    applyTheme(next);
  });
}

function upsertById(list, item, idKey) {
  if (!item || !list) return;
  const id = item[idKey];
  if (!id) return;
  const idx = list.findIndex((row) => row[idKey] === id);
  if (idx === -1) list.push(item);
  else list[idx] = item;
}

function removeById(list, id, idKey) {
  if (!Array.isArray(list) || !id || !idKey) return;
  const idx = list.findIndex((row) => row && row[idKey] === id);
  if (idx === -1) return;
  list.splice(idx, 1);
}

function findUserBySoeid(soeid) {
  if (!soeid) return null;
  return state.users.find((u) => u.soeid === soeid) || null;
}

function resolveAssigneeSelectValue(assigneeUserId, assigneeName) {
  if (assigneeUserId) return assigneeUserId;
  if (!assigneeName) return "";
  const match = state.users.find((u) => u.display_name === assigneeName);
  return match ? match.soeid : "";
}

function assigneeKeyFromAlloc(alloc) {
  return alloc.assignee_user_soeid || alloc.assignee || "unassigned";
}

function assigneeLabelFromKey(key) {
  const user = findUserBySoeid(key);
  if (user) return user.display_name || key;
  if (key === "unassigned") return "Unassigned";
  return key;
}

function populateCapacityUserOptions() {
  if (!els.capacityUserOptions) return;
  const options = state.users
    .filter((u) => u.display_name || u.soeid)
    .map((u) => `<option value="${u.display_name || u.soeid}"></option>`)
    .join("");
  els.capacityUserOptions.innerHTML = options;
}

function openPlanningDrawer(kind) {
  if (!els.planningDrawer || !els.planningLayout) return;
  els.planningLayout.classList.add("drawer-open");
  els.planningDrawer.classList.add("open");
  if (els.planningAllocationDrawer) {
    els.planningAllocationDrawer.classList.toggle("hidden", kind !== "allocation");
  }
  if (els.planningWindowDrawer) {
    els.planningWindowDrawer.classList.toggle("hidden", kind !== "window");
  }
}

function closePlanningDrawer() {
  if (!els.planningDrawer || !els.planningLayout) return;
  els.planningLayout.classList.remove("drawer-open");
  els.planningDrawer.classList.remove("open");
  els.planningAllocationDrawer?.classList.add("hidden");
  els.planningWindowDrawer?.classList.add("hidden");
}

function renderActiveView() {
  switch (state.currentView) {
    case "master":
      renderMasterFilters();
      renderMasterTable();
      break;
    case "subcomponents-workbench":
      renderSubcomponentsWorkbench();
      break;
    case "dashboard":
      renderDashboard();
      break;
    case "pm-dashboard":
      renderPMDashboard();
      break;
    case "kanban":
      renderKanban();
      break;
    case "calendar":
      renderCalendar();
      break;
    case "planning":
      renderPlanning();
      break;
    case "team-capacity":
      renderTeamCapacity();
      break;
    case "spaces":
      renderSpaces();
      break;
    case "access":
      renderAccess();
      break;
    default:
      renderMasterFilters();
      renderMasterTable();
  }
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && els.solutionModal && !els.solutionModal.classList.contains("hidden")) {
    renderSolutionSubcomponents(openSolutionId);
    renderSolutionActivity(openSolutionId);
    renderSolutionPhases(openSolutionId);
  }
}

function liveUrl() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${location.host}/api/ws`;
}

function initLiveSync() {
  let socket;
  let backoff = 1000;

  const connect = () => {
    socket = new WebSocket(liveUrl());

    socket.addEventListener("open", () => {
      backoff = 1000;
      setStatus("Online", "positive");
    });

    socket.addEventListener("message", (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "refresh") {
          refreshFromServer(msg.entity || "all");
        }
      } catch (err) {
        console.warn("Live message parse failed", err);
      }
    });

    const retry = () => {
      socket = null;
      backoff = Math.min(backoff * 1.5, 5000);
      setTimeout(connect, backoff);
    };

    socket.addEventListener("close", retry);
    socket.addEventListener("error", retry);
  };

  connect();
}

function restoreSelections(projectId, solutionId, subcomponentId) {
  if (projectId && els.projectForm) {
    const proj = state.projects.find((p) => p.project_id === projectId);
    if (proj) {
      els.projectForm.querySelector('[name="project_id"]').value = proj.project_id;
      els.projectForm.querySelector('[name="project_name"]').value = proj.project_name || "";
      els.projectForm.querySelector('[name="status"]').value = proj.status || "";
      els.projectForm.querySelector('[name="description"]').value = proj.description || "";
      els.projectForm.querySelector('[name="success_criteria"]').value = proj.success_criteria || "";
      els.projectForm.querySelector('[name="sponsor"]').value = proj.sponsor || "";
      els.projectForm.querySelector('[name="sponsor_user_soeid"]').value = proj.sponsor_user_soeid || "";
      els.projectForm.querySelector('[name="strategic_objective"]').value = proj.strategic_objective || "";
      els.projectForm.querySelector('[name="priority"]').value = proj.priority ?? 3;
    }
  }

	  if (solutionId && els.solutionForm) {
	    const sol = state.solutions.find((s) => s.solution_id === solutionId);
	    if (sol) {
	      els.solutionForm.querySelector('[name="solution_id"]').value = sol.solution_id;
	      els.solutionForm.querySelector('[name="project_id"]').value = sol.project_id;
	      els.solutionForm.querySelector('[name="solution_name"]').value = sol.solution_name || "";
	      els.solutionForm.querySelector('[name="version"]').value = sol.version || "";
	      els.solutionForm.querySelector('[name="status"]').value = sol.status || "";
	      els.solutionForm.querySelector('[name="rag_status"]').value = sol.rag_status || "green";
	      els.solutionForm.querySelector('[name="rag_reason"]').value = sol.rag_reason || "";
	      els.solutionForm.querySelector('[name="priority"]').value = sol.priority ?? "";
	      els.solutionForm.querySelector('[name="due_date"]').value = sol.due_date || "";
        els.solutionForm.querySelector('[name="planned_start_date"]').value = sol.planned_start_date || "";
	      els.solutionForm.querySelector('[name="description"]').value = sol.description || "";
        els.solutionForm.querySelector('[name="problem_statement"]').value = sol.problem_statement || "";
	      els.solutionForm.querySelector('[name="success_criteria"]').value = sol.success_criteria || "";
        els.solutionForm.querySelector('[name="impact_confidence"]').value = sol.impact_confidence || "";
	      els.solutionForm.querySelector('[name="owner"]').value = sol.owner || "";
        els.solutionForm.querySelector('[name="owner_user_soeid"]').value = sol.owner_user_soeid || "";
      els.solutionForm.querySelector('[name="assignee"]').value = sol.assignee || "";
        els.solutionForm.querySelector('[name="assignee_user_soeid"]').value = sol.assignee_user_soeid || "";
      els.solutionForm.querySelector('[name="approver"]').value = sol.approver || "";
        els.solutionForm.querySelector('[name="approver_user_soeid"]').value = sol.approver_user_soeid || "";
      els.solutionForm.querySelector('[name="key_stakeholder"]').value = sol.key_stakeholder || "";
        els.solutionForm.querySelector('[name="rag_confidence"]').value = sol.rag_confidence ?? "";
      els.solutionForm.querySelector('[name="blockers"]').value = sol.blockers || "";
      els.solutionForm.querySelector('[name="risks"]').value = sol.risks || "";
	      updateCurrentPhaseOptions(sol.solution_id);
	      els.solutionForm.querySelector('[name="current_phase"]').value = sol.current_phase || "";
	      renderSolutionPhases(sol.solution_id);
	    }
	  }

  if (subcomponentId && els.subcomponentForm) {
    const sub = state.subcomponents.find((s) => s.subcomponent_id === subcomponentId);
    if (sub) {
      els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = sub.subcomponent_id;
      els.subcomponentForm.querySelector('[name="project_id"]').value = sub.project_id;
      updateSubcomponentSolutionOptions(sub.project_id);
      els.subcomponentForm.querySelector('[name="solution_id"]').value = sub.solution_id;
      els.subcomponentForm.querySelector('[name="subcomponent_name"]').value = sub.subcomponent_name || "";
      els.subcomponentForm.querySelector('[name="priority"]').value = sub.priority ?? "";
      els.subcomponentForm.querySelector('[name="due_date"]').value = sub.due_date || "";
      els.subcomponentForm.querySelector('[name="status"]').value = sub.status || "";
      els.subcomponentForm.querySelector('[name="assignee"]').value = resolveAssigneeSelectValue(sub.assignee_user_soeid, sub.assignee);
      els.subcomponentForm.querySelector('[name="assignee_user_soeid"]').value = sub.assignee_user_soeid || "";
      els.subcomponentForm.querySelector('[name="estimate_hours"]').value =
        sub.estimate_hours != null ? fteFromHoursForInput(sub.estimate_hours, 0) : "";
      els.subcomponentForm.querySelector('[name="blocked"]').checked = !!sub.blocked;
      els.subcomponentForm.querySelector('[name="blocker_note"]').value = sub.blocker_note || "";
      els.subcomponentForm.querySelector('[name="done_criteria"]').value = sub.done_criteria || "";
    }
  }
}

function deliverableKey(type, id) {
  return `${type}:${id}`;
}

function updatePresetButtons() {
  const preset = state.deliverablesPreset || "";
  [els.presetMy, els.presetOverdue, els.presetBlocked].forEach((btn) => {
    if (!btn) return;
    const match = btn.id === `preset-${preset}`;
    btn.classList.toggle("active", match);
  });
}

function clearDeliverablesFilters() {
  state.filters = {};
  state.deliverablesPreset = "";
  state.deliverableSelection.clear();
  updatePresetButtons();
  renderMasterFilters();
  renderMasterTable();
  renderKanban();
  renderCalendar();
}

function setDeliverablesPreset(preset) {
  state.deliverablesPreset = preset || "";
  updatePresetButtons();
  renderMasterTable();
}

function renderMasterFilters() {
  const mod = getRouteModule("master");
  if (!mod || typeof mod.renderMasterFilters !== "function") {
    ensureRouteModule("master").then((loaded) => {
      if (loaded && state.currentView === "master") renderMasterFilters();
    });
    return;
  }
  mod.renderMasterFilters({
    state,
    els,
    escapeAttr,
    deliverableKey,
    updateBulkSelectionCount,
    renderMasterTable,
    renderKanban,
    renderCalendar,
    clearDeliverablesFilters,
  });
}

function isCompletedSubcomponentStatus(statusValue) {
  const status = normalize(statusValue);
  return status === "complete" || status === "abandoned";
}

function deriveSubcomponentActionability(subcomponent) {
  const hasServerFields =
    Object.prototype.hasOwnProperty.call(subcomponent || {}, "is_overdue") &&
    Object.prototype.hasOwnProperty.call(subcomponent || {}, "is_due_soon") &&
    Object.prototype.hasOwnProperty.call(subcomponent || {}, "is_stale") &&
    Object.prototype.hasOwnProperty.call(subcomponent || {}, "urgency_score");
  if (hasServerFields) {
    return {
      is_overdue: !!subcomponent.is_overdue,
      is_due_soon: !!subcomponent.is_due_soon,
      is_stale: !!subcomponent.is_stale,
      urgency_score: numberOr(subcomponent.urgency_score, 0),
    };
  }

  const done = isCompletedSubcomponentStatus(subcomponent?.status);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dueDate = subcomponent?.due_date ? new Date(`${subcomponent.due_date}T00:00:00`) : null;
  const updated = subcomponent?.updated_at ? new Date(subcomponent.updated_at) : null;

  const is_overdue = !!(dueDate && dueDate < today && !done);
  const dueSoonDays = dueDate ? Math.ceil((dueDate.getTime() - today.getTime()) / (24 * 60 * 60 * 1000)) : null;
  const is_due_soon = !!(dueSoonDays != null && dueSoonDays >= 0 && dueSoonDays <= 14 && !done);
  const staleDays =
    updated && Number.isFinite(updated.getTime())
      ? Math.floor((today.getTime() - updated.getTime()) / (24 * 60 * 60 * 1000))
      : 0;
  const is_stale = !done && staleDays > 7;

  let urgency = 0;
  if (!done) {
    const priority = Math.max(1, Math.min(5, Number(subcomponent?.priority || 3)));
    const priorityScore = (6 - priority) * 15;
    const dueScore = dueSoonDays == null ? 0 : dueSoonDays < 0 ? 45 : Math.max(0, (15 - dueSoonDays) * 2);
    const blockedScore = subcomponent?.blocked ? 18 : 0;
    const staleScore = is_stale ? 10 : 0;
    urgency = Math.min(100, priorityScore + dueScore + blockedScore + staleScore);
  }

  return {
    is_overdue,
    is_due_soon,
    is_stale,
    urgency_score: urgency,
  };
}

function subcomponentsWorkbenchRows() {
  const wb = state.subcomponentsWorkbench;
  const rows = (state.subcomponents || []).map((subcomponent) => {
    const project = state.projects.find((p) => p.project_id === subcomponent.project_id);
    const solution = state.solutions.find((s) => s.solution_id === subcomponent.solution_id);
    return {
      ...subcomponent,
      ...deriveSubcomponentActionability(subcomponent),
      project_name: project?.project_name || "",
      solution_name: solution?.solution_name || "",
    };
  });

  const filters = wb.filters || {};
  const search = normalize(filters.search);
  const userName = normalize(state.user?.display_name);
  const userSoeid = normalize(state.user?.soeid);

  const visible = rows.filter((row) => {
    if (filters.project_id && row.project_id !== filters.project_id) return false;
    if (filters.solution_id && row.solution_id !== filters.solution_id) return false;
    if (filters.status && row.status !== filters.status) return false;
    if (filters.priority_max && Number(row.priority || 999) > Number(filters.priority_max)) return false;
    if (filters.assignee) {
      if (filters.assignee === "__unassigned__") {
        if ((row.assignee || "").trim() || row.assignee_user_soeid) return false;
      } else {
        const assigneeId = normalize(row.assignee_user_soeid);
        const assigneeName = normalize(row.assignee);
        if (assigneeId !== normalize(filters.assignee) && assigneeName !== normalize(filters.assignee_name)) return false;
      }
    }

    if (search) {
      const blob = [
        row.subcomponent_name,
        row.project_name,
        row.solution_name,
        row.assignee,
        row.status,
      ]
        .map((val) => normalize(val))
        .join(" ");
      if (!blob.includes(search)) return false;
    }

    switch (wb.preset) {
      case "my": {
        const assigneeId = normalize(row.assignee_user_soeid);
        const assigneeName = normalize(row.assignee);
        const matchesSelf = (userSoeid && assigneeId === userSoeid) || (userName && assigneeName === userName);
        if (!matchesSelf) return false;
        break;
      }
      case "due_soon":
        if (!row.is_due_soon) return false;
        break;
      case "overdue":
        if (!row.is_overdue) return false;
        break;
      case "blocked":
        if (!row.blocked) return false;
        break;
      case "unassigned":
        if ((row.assignee || "").trim() || row.assignee_user_soeid) return false;
        break;
      case "stale":
        if (!row.is_stale) return false;
        break;
      default:
        break;
    }
    return true;
  });

  visible.sort((a, b) => {
    const urgencyDiff = numberOr(b.urgency_score, 0) - numberOr(a.urgency_score, 0);
    if (urgencyDiff !== 0) return urgencyDiff;
    const dueA = a.due_date ? new Date(`${a.due_date}T00:00:00`).getTime() : Number.POSITIVE_INFINITY;
    const dueB = b.due_date ? new Date(`${b.due_date}T00:00:00`).getTime() : Number.POSITIVE_INFINITY;
    if (dueA !== dueB) return dueA - dueB;
    const priorityDiff = numberOr(a.priority, 99) - numberOr(b.priority, 99);
    if (priorityDiff !== 0) return priorityDiff;
    return (a.subcomponent_name || "").localeCompare(b.subcomponent_name || "");
  });

  wb.visibleIds = visible.map((row) => row.subcomponent_id);
  return { allRows: rows, visibleRows: visible };
}

function subcomponentsWorkbenchSummary(allRows, visibleRows) {
  const rows = allRows || [];
  return {
    total: rows.length,
    visible: (visibleRows || []).length,
    overdue: rows.filter((row) => row.is_overdue).length,
    dueSoon: rows.filter((row) => row.is_due_soon).length,
    blocked: rows.filter((row) => row.blocked).length,
    unassigned: rows.filter((row) => !(row.assignee || "").trim() && !row.assignee_user_soeid).length,
  };
}

function updateSubcomponentsWorkbenchPresetButtons() {
  const wb = state.subcomponentsWorkbench;
  document.querySelectorAll(".scwb-preset").forEach((btn) => {
    const preset = btn.getAttribute("data-preset") || "";
    const active = preset === wb.preset;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function updateSubcomponentsWorkbenchSelectionCount() {
  if (!els.subcomponentsWorkbenchSelectionCount) return;
  const count = state.subcomponentsWorkbench.selected.size;
  els.subcomponentsWorkbenchSelectionCount.textContent = `${count} selected`;
}

function syncSubcomponentsWorkbenchDrawer() {
  const wb = state.subcomponentsWorkbench;
  const drawerOpen = wb.drawerOpen !== false;
  if (els.subcomponentsWorkbenchDrawer) {
    els.subcomponentsWorkbenchDrawer.classList.toggle("hidden", !drawerOpen);
  }
  if (els.subcomponentsWorkbenchLayout) {
    els.subcomponentsWorkbenchLayout.classList.toggle("sub-workbench-layout-drawer-hidden", !drawerOpen);
  }
}

function openSubcomponentsWorkbenchDrawer(preferredSubcomponentId = "") {
  const wb = state.subcomponentsWorkbench;
  if (wb.drawerOpen === false) {
    const anchorId =
      preferredSubcomponentId || wb.activeSubcomponentId || (Array.isArray(wb.visibleIds) ? wb.visibleIds[0] : "") || "";
    wb.drawerReturnSubcomponentId = anchorId;
    wb.drawerReturnScrollY = window.scrollY || window.pageYOffset || 0;
  }
  if (preferredSubcomponentId) {
    wb.activeSubcomponentId = preferredSubcomponentId;
  } else if (!wb.activeSubcomponentId && Array.isArray(wb.visibleIds) && wb.visibleIds.length) {
    wb.activeSubcomponentId = wb.visibleIds[0];
  }
  wb.drawerOpen = true;
  renderSubcomponentsWorkbench();
}

function closeSubcomponentsWorkbenchDrawer() {
  const wb = state.subcomponentsWorkbench;
  const returnSubcomponentId = wb.activeSubcomponentId || wb.drawerReturnSubcomponentId || "";
  wb.activeSubcomponentId = returnSubcomponentId;
  wb.drawerOpen = false;
  wb.drawerReturnSubcomponentId = "";
  wb.drawerReturnScrollY = null;
  wb.suppressAutoScrollOnce = true;
  renderSubcomponentsWorkbench();
  window.requestAnimationFrame(() => {
    if (!returnSubcomponentId || !els.subcomponentsWorkbenchTable) return;
    const row = Array.from(els.subcomponentsWorkbenchTable.querySelectorAll("tr[data-id]")).find(
      (node) => node.getAttribute("data-id") === returnSubcomponentId
    );
    if (row && typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest" });
    }
    const target = row || row?.querySelector(".scwb-edit-btn") || row?.querySelector(".scwb-select-row");
    if (!target || typeof target.focus !== "function") return;
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  });
}

function subcomponentsWorkbenchStorageKey() {
  const userKey = normalize(state.user?.soeid || state.user?.user_id || "anon");
  const spaceKey = normalize(activeSpaceId() || "no-space");
  return `${SUBCOMPONENTS_WORKBENCH_SAVED_VIEWS_KEY_PREFIX}:${userKey}:${spaceKey}`;
}

function setSubcomponentsWorkbenchSavedStatus(text) {
  if (!els.subcomponentsWorkbenchSavedStatus) return;
  els.subcomponentsWorkbenchSavedStatus.textContent = text || "";
}

function loadSubcomponentsWorkbenchSavedViews() {
  const wb = state.subcomponentsWorkbench;
  wb.savedViews = [];
  wb.selectedSavedViewId = "";
  if (!state.authed) return;
  try {
    const raw = localStorage.getItem(subcomponentsWorkbenchStorageKey()) || "[]";
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return;
    wb.savedViews = parsed
      .filter((row) => row && typeof row === "object" && typeof row.name === "string")
      .map((row) => ({
        view_id: String(row.view_id || `sv_${Math.random().toString(36).slice(2, 10)}`),
        name: String(row.name || "").trim(),
        preset: String(row.preset || "all"),
        filters: {
          search: String(row.filters?.search || ""),
          project_id: String(row.filters?.project_id || ""),
          solution_id: String(row.filters?.solution_id || ""),
          assignee: String(row.filters?.assignee || ""),
          assignee_name: String(row.filters?.assignee_name || ""),
          status: String(row.filters?.status || ""),
          priority_max: String(row.filters?.priority_max || ""),
        },
        updated_at: String(row.updated_at || ""),
      }))
      .filter((row) => row.name);
  } catch (err) {
    console.warn("Unable to load subcomponent workbench saved views", err);
  }
}

function persistSubcomponentsWorkbenchSavedViews() {
  if (!state.authed) return;
  try {
    localStorage.setItem(
      subcomponentsWorkbenchStorageKey(),
      JSON.stringify(state.subcomponentsWorkbench.savedViews || [])
    );
  } catch (err) {
    console.warn("Unable to persist subcomponent workbench saved views", err);
  }
}

function updateSubcomponentsWorkbenchSavedViewsUI() {
  const wb = state.subcomponentsWorkbench;
  if (!els.subcomponentsWorkbenchSavedSelect) return;
  const options = (wb.savedViews || [])
    .slice()
    .sort((a, b) => (a.name || "").localeCompare(b.name || ""))
    .map((row) => `<option value="${row.view_id}">${escapeHtml(row.name)}</option>`)
    .join("");
  els.subcomponentsWorkbenchSavedSelect.innerHTML = `<option value="">Select</option>${options}`;
  if (wb.selectedSavedViewId && wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId)) {
    els.subcomponentsWorkbenchSavedSelect.value = wb.selectedSavedViewId;
  } else if (els.subcomponentsWorkbenchSavedSelect.value) {
    wb.selectedSavedViewId = els.subcomponentsWorkbenchSavedSelect.value;
  }
  if (
    els.subcomponentsWorkbenchSavedName &&
    wb.selectedSavedViewId &&
    document.activeElement !== els.subcomponentsWorkbenchSavedName
  ) {
    const saved = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId);
    if (saved) els.subcomponentsWorkbenchSavedName.value = saved.name || "";
  }
}

function captureSubcomponentsWorkbenchCurrentView(name) {
  const wb = state.subcomponentsWorkbench;
  return {
    view_id: `sv_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
    name: String(name || "").trim(),
    preset: wb.preset || "all",
    filters: {
      search: wb.filters.search || "",
      project_id: wb.filters.project_id || "",
      solution_id: wb.filters.solution_id || "",
      assignee: wb.filters.assignee || "",
      assignee_name: wb.filters.assignee_name || "",
      status: wb.filters.status || "",
      priority_max: wb.filters.priority_max || "",
    },
    updated_at: new Date().toISOString(),
  };
}

function applySubcomponentsWorkbenchSavedView(savedView) {
  if (!savedView) return;
  const wb = state.subcomponentsWorkbench;
  wb.preset = savedView.preset || "all";
  wb.filters = {
    search: savedView.filters?.search || "",
    project_id: savedView.filters?.project_id || "",
    solution_id: savedView.filters?.solution_id || "",
    assignee: savedView.filters?.assignee || "",
    assignee_name: savedView.filters?.assignee_name || "",
    status: savedView.filters?.status || "",
    priority_max: savedView.filters?.priority_max || "",
  };
  wb.selected.clear();
  wb.activeSubcomponentId = "";
  wb.selectedSavedViewId = "";
  setSubcomponentsWorkbenchSavedStatus("");
  if (els.subcomponentsWorkbenchSavedName) els.subcomponentsWorkbenchSavedName.value = "";

  if (els.subcomponentsWorkbenchSearch) els.subcomponentsWorkbenchSearch.value = wb.filters.search || "";
  if (els.subcomponentsWorkbenchProject) els.subcomponentsWorkbenchProject.value = wb.filters.project_id || "";
  updateSubcomponentsWorkbenchSolutionOptions(wb.filters.project_id || "");
  if (els.subcomponentsWorkbenchSolution) {
    els.subcomponentsWorkbenchSolution.value = wb.filters.solution_id || "";
  }
  if (els.subcomponentsWorkbenchAssignee) {
    els.subcomponentsWorkbenchAssignee.value = wb.filters.assignee || "";
  }
  if (els.subcomponentsWorkbenchStatus) {
    els.subcomponentsWorkbenchStatus.value = wb.filters.status || "";
  }
  if (els.subcomponentsWorkbenchPriority) {
    els.subcomponentsWorkbenchPriority.value = wb.filters.priority_max || "";
  }
  renderSubcomponentsWorkbench();
}

function isTypingInputTarget(target) {
  if (!target) return false;
  const tag = (target.tagName || "").toLowerCase();
  if (["input", "textarea", "select", "button"].includes(tag)) return true;
  if (target.isContentEditable) return true;
  return false;
}

function setActiveSubcomponentByOffset(offset) {
  const wb = state.subcomponentsWorkbench;
  const ids = wb.visibleIds || [];
  if (!ids.length) return;
  const rawIndex = ids.indexOf(wb.activeSubcomponentId);
  if (rawIndex === -1) {
    wb.activeSubcomponentId = offset >= 0 ? ids[0] : ids[ids.length - 1];
    renderSubcomponentsWorkbench();
    return;
  }
  const currentIndex = rawIndex;
  const nextIndex = Math.min(ids.length - 1, Math.max(0, currentIndex + offset));
  const nextId = ids[nextIndex];
  if (!nextId) return;
  wb.activeSubcomponentId = nextId;
  renderSubcomponentsWorkbench();
}

function scrollActiveSubcomponentIntoView() {
  const wb = state.subcomponentsWorkbench;
  if (!wb.activeSubcomponentId || !els.subcomponentsWorkbenchTable) return;
  const row = els.subcomponentsWorkbenchTable.querySelector(`tr[data-id="${wb.activeSubcomponentId}"]`);
  if (row && typeof row.scrollIntoView === "function") {
    row.scrollIntoView({ block: "nearest" });
  }
}

async function renderSubcomponentsWorkbenchActivity(subcomponentId) {
  const activityEl = els.subcomponentsWorkbenchActivity;
  const wb = state.subcomponentsWorkbench;
  if (!activityEl) return;
  const reqId = (wb.activityRequestId || 0) + 1;
  wb.activityRequestId = reqId;
  if (!subcomponentId) {
    activityEl.innerHTML = "<p class='muted'>Select a subcomponent to see activity.</p>";
    return;
  }
  activityEl.innerHTML = "<p class='muted'>Loading activity…</p>";
  try {
    const rows = await api(`/subcomponents/${encodeURIComponent(subcomponentId)}/activity?limit=12`);
    if (wb.activityRequestId !== reqId) return;
    if (!rows?.length) {
      activityEl.innerHTML = "<p class='muted'>No activity yet.</p>";
      return;
    }
    activityEl.innerHTML = rows
      .map((row) => {
        const action = escapeHtml(row.action || "update");
        const field = row.field ? ` • ${escapeHtml(row.field)}` : "";
        const change = row.new_value ? ` → ${escapeHtml(String(row.new_value).slice(0, 90))}` : "";
        const when = row.created_at ? new Date(row.created_at).toLocaleString() : "";
        return `<div class="activity-item">
          <div class="activity-title">${action}${field}${change}</div>
          <div class="activity-meta">${escapeHtml(row.user_id || "system")} • ${escapeHtml(when)}</div>
        </div>`;
      })
      .join("");
  } catch (err) {
    if (wb.activityRequestId !== reqId) return;
    activityEl.innerHTML = "<p class='muted'>Activity unavailable for this role.</p>";
  }
}

function fillSubcomponentsWorkbenchForm(subcomponent) {
  if (!els.subcomponentsWorkbenchForm) return;
  const form = els.subcomponentsWorkbenchForm;
  const idInput = form.querySelector('[name="subcomponent_id"]');
  const saveButton = form.querySelector('button[type="submit"]');
  const setValue = (name, value) => {
    const el = form.querySelector(`[name="${name}"]`);
    if (el) el.value = value == null ? "" : value;
  };
  if (!subcomponent) {
    form.reset();
    if (idInput) idInput.value = "";
    if (els.subcomponentsWorkbenchContext) {
      els.subcomponentsWorkbenchContext.textContent = "Select a subcomponent to edit.";
    }
    if (saveButton) saveButton.disabled = true;
    renderSubcomponentsWorkbenchActivity("");
    return;
  }
  if (saveButton) saveButton.disabled = false;
  if (idInput) idInput.value = subcomponent.subcomponent_id || "";
  setValue("subcomponent_name", subcomponent.subcomponent_name || "");
  setValue("status", subcomponent.status || "to_do");
  setValue("priority", subcomponent.priority ?? "");
  setValue("due_date", subcomponent.due_date || "");
  setValue("blocker_note", subcomponent.blocker_note || "");
  const blocked = form.querySelector('[name="blocked"]');
  if (blocked) blocked.checked = !!subcomponent.blocked;

  const assigneeSelect = form.querySelector('[name="assignee"]');
  const assigneeUserInput = form.querySelector('[name="assignee_user_soeid"]');
  const assigneeValue = resolveAssigneeSelectValue(subcomponent.assignee_user_soeid, subcomponent.assignee);
  if (assigneeSelect) assigneeSelect.value = assigneeValue || "";
  if (assigneeUserInput) assigneeUserInput.value = assigneeValue || "";

  if (els.subcomponentsWorkbenchContext) {
    const project = state.projects.find((p) => p.project_id === subcomponent.project_id)?.project_name || "Unknown project";
    const solution = state.solutions.find((s) => s.solution_id === subcomponent.solution_id)?.solution_name || "Unknown solution";
    els.subcomponentsWorkbenchContext.textContent = `${project} / ${solution}`;
  }
  renderSubcomponentsWorkbenchActivity(subcomponent.subcomponent_id);
}

function renderSubcomponentsWorkbench() {
  const mod = getRouteModule("subcomponents-workbench");
  if (!mod || typeof mod.renderSubcomponentsWorkbench !== "function") {
    if (state.currentView === "subcomponents-workbench" && els.subcomponentsWorkbenchTable) {
      els.subcomponentsWorkbenchTable.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("subcomponents-workbench").then((loaded) => {
      if (loaded && state.currentView === "subcomponents-workbench") renderSubcomponentsWorkbench();
    });
    return;
  }

  const wb = state.subcomponentsWorkbench;
  const { allRows, visibleRows } = subcomponentsWorkbenchRows();
  const allIds = new Set((state.subcomponents || []).map((row) => row.subcomponent_id));
  Array.from(wb.selected).forEach((subId) => {
    if (!allIds.has(subId)) wb.selected.delete(subId);
  });

  if (wb.activeSubcomponentId) {
    const exists = visibleRows.find((row) => row.subcomponent_id === wb.activeSubcomponentId);
    if (!exists) wb.activeSubcomponentId = "";
  }
  if (wb.drawerOpen !== false && !wb.activeSubcomponentId && visibleRows.length) {
    wb.activeSubcomponentId = visibleRows[0].subcomponent_id;
  }

  mod.renderSubcomponentsWorkbench({
    els,
    rows: visibleRows,
    activeSubcomponentId: wb.activeSubcomponentId,
    selectedIds: wb.selected,
    formatStatus,
    summary: subcomponentsWorkbenchSummary(allRows, visibleRows),
  });

  const active = wb.drawerOpen !== false && wb.activeSubcomponentId
    ? (state.subcomponents || []).find((row) => row.subcomponent_id === wb.activeSubcomponentId) || null
    : null;
  syncSubcomponentsWorkbenchDrawer();
  fillSubcomponentsWorkbenchForm(active);
  updateSubcomponentsWorkbenchPresetButtons();
  updateSubcomponentsWorkbenchSelectionCount();
  updateSubcomponentsWorkbenchSavedViewsUI();
  if (wb.suppressAutoScrollOnce) {
    wb.suppressAutoScrollOnce = false;
  } else {
    window.setTimeout(scrollActiveSubcomponentIntoView, 0);
  }
}

function filteredSolutions() {
  const f = state.filters || {};
  if (f.type && f.type !== "solution") return [];
  const preset = state.deliverablesPreset || "";
  const userName = (state.user?.display_name || state.user?.soeid || "").toLowerCase();
  return state.solutions.filter((s) => {
    // Deliverables filters for every column
    const project = state.projects.find((p) => p.project_id === s.project_id);
    if (f.project && !(project?.project_name || "").toLowerCase().includes(f.project.toLowerCase())) return false;
    if (f.sponsor && !(project?.sponsor || "").toLowerCase().includes(f.sponsor.toLowerCase())) return false;
    if (f.solution && !(s.solution_name || "").toLowerCase().includes(f.solution.toLowerCase())) return false;
    if (f.version && !(s.version || "").toLowerCase().includes(f.version.toLowerCase())) return false;
    if (f.owner && !(s.owner || "").toLowerCase().includes(f.owner.toLowerCase())) return false;
    if (f.current_phase && !(s.current_phase || "").toLowerCase().includes(f.current_phase.toLowerCase())) return false;
    if (f.priority && Number(s.priority) > Number(f.priority)) return false;
    if (f.due && !(s.due_date || "").toLowerCase().includes(f.due.toLowerCase())) return false;
    if (f.rag && !(s.rag_status || "").toLowerCase().includes(f.rag.toLowerCase())) return false;
    if (f.status && !(s.status || "").toLowerCase().includes(f.status.toLowerCase())) return false;
    if (f.progress && solutionProgress(s) > Number(f.progress)) return false;
    if (preset === "my") {
      const ownerMatch = (s.owner || "").toLowerCase().includes(userName);
      const assigneeMatch = (s.assignee || "").toLowerCase().includes(userName);
      if (!ownerMatch && !assigneeMatch) return false;
    }
    if (preset === "overdue") {
      if (!s.due_date) return false;
      if (s.status === "complete" || s.status === "abandoned") return false;
      if (new Date(s.due_date) >= new Date()) return false;
    }
    if (preset === "blocked") {
      const hasBlockers = (s.blockers || "").trim().length > 0;
      const hasRisks = (s.risks || "").trim().length > 0;
      if (!hasBlockers && !hasRisks && s.status !== "on_hold") return false;
    }
    return true;
  });
}

function projectMatchesDeliverablesFilters(project, filters, preset) {
  const f = filters || {};
  if (f.project && !(project?.project_name || "").toLowerCase().includes(f.project.toLowerCase())) return false;
  if (f.sponsor && !(project?.sponsor || "").toLowerCase().includes(f.sponsor.toLowerCase())) return false;
  if (f.priority && Number(project?.priority) > Number(f.priority)) return false;
  if (f.status && !formatStatus(project?.status).toLowerCase().includes(f.status.toLowerCase())) return false;
  if (preset === "my") {
    const userName = (state.user?.display_name || state.user?.soeid || "").toLowerCase();
    if (!userName || !(project?.sponsor || "").toLowerCase().includes(userName)) return false;
  }
  if (preset === "overdue" || preset === "blocked") return false;
  return true;
}

function filteredDeliverables() {
  const f = state.filters || {};
  const preset = state.deliverablesPreset || "";
  const rows = [];
  const includeProjectRows = f.type !== "solution";
  const includeSolutionRows = f.type !== "project";
  const hasSolutionColumnFilters = Boolean(
    f.solution || f.version || f.owner || f.current_phase || f.due || f.rag || f.progress
  );
  const projectById = new Map((state.projects || []).map((project) => [project.project_id, project]));
  const groupedSolutions = new Map();
  const orphanSolutions = [];

  if (includeSolutionRows) {
    filteredSolutions().forEach((solution) => {
      const project = projectById.get(solution.project_id) || null;
      if (!project || !project.project_id) {
        orphanSolutions.push({ type: "solution", project: null, solution });
        return;
      }
      const bucket = groupedSolutions.get(project.project_id) || [];
      bucket.push({ type: "solution", project, solution });
      groupedSolutions.set(project.project_id, bucket);
    });
  }

  const sortedProjects = [...(state.projects || [])].sort((a, b) =>
    (a.project_name || "").localeCompare(b.project_name || "")
  );

  sortedProjects.forEach((project) => {
    const solutionRows = (groupedSolutions.get(project.project_id) || []).sort((a, b) =>
      (a.solution?.solution_name || "").localeCompare(b.solution?.solution_name || "")
    );
    const projectMatches = projectMatchesDeliverablesFilters(project, f, preset);
    const showProjectRow = includeProjectRows && projectMatches && (!hasSolutionColumnFilters || solutionRows.length > 0);
    if (showProjectRow) rows.push({ type: "project", project, solution: null });
    solutionRows.forEach((row) => rows.push(row));
  });

  orphanSolutions
    .sort((a, b) => (a.solution?.solution_name || "").localeCompare(b.solution?.solution_name || ""))
    .forEach((row) => rows.push(row));

  return rows;
}

function filteredSolutionsForKanban() {
  const base = filteredSolutions();
  const { project, owner } = state.kanbanFilters || {};
  return base.filter((s) => {
    const proj = state.projects.find((p) => p.project_id === s.project_id);
    if (project && s.project_id !== project) return false;
    if (owner && !(s.owner || "").toLowerCase().includes(owner.toLowerCase())) return false;
    return true;
  });
}

function filteredSolutionsForCalendar() {
  const base = filteredSolutions();
  const { project, owner } = state.calendarFilters || {};
  return base.filter((s) => {
    if (project && s.project_id !== project) return false;
    if (owner && !(s.owner || "").toLowerCase().includes(owner.toLowerCase())) return false;
    return true;
  });
}

function filteredSubcomponentsForCalendar() {
  const { project, owner } = state.calendarFilters || {};
  const ownerNorm = (owner || "").toLowerCase();
  return (state.subcomponents || []).filter((sc) => {
    if (!sc?.due_date) return false;
    if (project && sc.project_id !== project) return false;
    if (ownerNorm) {
      const assigneeName = (sc.assignee || "").toLowerCase();
      const assigneeSoeid = (sc.assignee_user_soeid || "").toLowerCase();
      if (!assigneeName.includes(ownerNorm) && !assigneeSoeid.includes(ownerNorm)) return false;
    }
    return true;
  });
}

function orderedPhases(solutionId) {
  const enabled = (state.solutionPhases[solutionId] || []).filter((p) => p.is_enabled);
  return enabled.sort((a, b) => {
    const aSeq = a.sequence_override ?? state.phases.find((p) => p.phase_id === a.phase_id)?.sequence ?? 0;
    const bSeq = b.sequence_override ?? state.phases.find((p) => p.phase_id === b.phase_id)?.sequence ?? 0;
    return aSeq - bSeq;
  });
}

function updateCurrentPhaseOptions(solutionId) {
  const sel = els.solutionForm?.querySelector('[name="current_phase"]');
  if (!sel) return;

  const enabledPhaseIds = orderedPhases(solutionId).map((p) => p.phase_id);
  const phases = enabledPhaseIds.length
    ? enabledPhaseIds
        .map((id) => state.phases.find((p) => p.phase_id === id) || { phase_id: id, phase_name: id })
        .filter(Boolean)
    : state.phases;

  const opts = phases
    .map((p) => `<option value="${p.phase_id}">${phaseDisplayName(p.phase_id) || p.phase_id}</option>`)
    .join("");
  sel.innerHTML = `<option value="">None</option>${opts}`;
}

function solutionProgress(solution) {
  if (!solution) return 0;
  if (solution.status === "complete") return 100;
  if (!state.phases.length || !solution.current_phase) return 0;
  const phases = [...state.phases].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
  const idx = phases.findIndex((p) => p.phase_id === solution.current_phase);
  if (idx === -1) return 0;
  return Math.round(((idx + 1) / phases.length) * 100);
}

function computeScoreNumbers(item) {
  const basePriority = Number(item.priority ?? 3) || 3;
  const due = item.due_date ? new Date(item.due_date) : null;
  const daysToDue = due ? Math.max(0, Math.ceil((due.getTime() - Date.now()) / (1000 * 60 * 60 * 24))) : null;
  const timeCriticality = daysToDue == null ? 1 : Math.max(1, 30 - Math.min(30, daysToDue));
  const jobSize = Math.max(1, 6 - Math.min(5, basePriority)); // higher priority -> smaller job size
  const businessValue = Math.max(1, basePriority * 1.5);
  const riskReduction = Math.max(1, (item.risks ? 2 : 1) + (item.blockers ? 1 : 0));
  const impact = Math.max(1, basePriority);
  const confidence = 0.5 + Math.min(0.5, (item.owner ? 0.2 : 0) + (item.assignee ? 0.3 : 0));
  const effort = Math.max(1, jobSize);
  const wsjf = Number((((businessValue + timeCriticality + riskReduction) / jobSize).toFixed(2)));
  const ice = Number(((impact * confidence) / effort).toFixed(2));
  return { wsjf, ice, businessValue, timeCriticality, riskReduction, jobSize, impact, confidence, effort };
}

function formatStatus(status) {
  if (!status) return "—";
  return status
    .toString()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function escapeAttr(value) {
  if (value == null) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function ragPill(ragStatus, ragReason) {
  if (!ragStatus) return "—";
  const status = String(ragStatus);
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  const cls = status === "red" ? "rag-red" : status === "green" ? "rag-green" : "rag-amber";
  const title = ragReason ? `Reason: ${ragReason}` : label;
  return `<span class="pill rag-pill ${cls}" title="${escapeAttr(title)}">${label}</span>`;
}

function phaseDisplayName(phaseId) {
  if (!phaseId) return "";
  const phase = state.phases.find((p) => p.phase_id === phaseId);
  const name = phase?.phase_name || phaseId;
  if (phaseId === "poc" || name.toLowerCase() === "poc") return "Proof of Concept";
  return name;
}

function hasActiveDeliverableFilters() {
  const filterValues = Object.values(state.filters || {});
  const hasFieldFilters = filterValues.some((value) => {
    if (value == null) return false;
    if (typeof value === "number") return !Number.isNaN(value);
    return String(value).trim() !== "";
  });
  return hasFieldFilters || Boolean(state.deliverablesPreset);
}

function renderMasterQuickstart(rowCount = 0) {
  if (!els.masterQuickstart) return;

  const hasRows = Number(rowCount) > 0;
  const hasDeliverableData = (state.projects?.length || 0) > 0 || (state.solutions?.length || 0) > 0;
  const hasFilters = hasActiveDeliverableFilters();

  if (hasRows) {
    els.masterQuickstart.classList.add("hidden");
    els.masterQuickstart.innerHTML = "";
    return;
  }

  if (!hasDeliverableData) {
    els.masterQuickstart.classList.remove("hidden");
    els.masterQuickstart.innerHTML = `
      <div class="quickstart-head">
        <h3>Quick Start</h3>
        <p class="muted">No deliverables in this space yet. Start with one project, then add solutions.</p>
      </div>
      <div class="quickstart-actions">
        <button type="button" class="primary" data-quick-action="create-project">Create first project</button>
        <button type="button" class="secondary" data-quick-action="create-solution">Create first solution</button>
      </div>
      <ol class="quickstart-steps">
        <li>Create a project with sponsor and objective.</li>
        <li>Add 1-3 solutions, then assign owners and due dates.</li>
        <li>Use Planning to allocate work and Dashboard to track progress.</li>
      </ol>
    `;
    return;
  }

  if (hasFilters) {
    els.masterQuickstart.classList.remove("hidden");
    els.masterQuickstart.innerHTML = `
      <div class="quickstart-head">
        <h3>No Matches</h3>
        <p class="muted">Current filters returned zero deliverables in this space.</p>
      </div>
      <div class="quickstart-actions">
        <button type="button" class="secondary" data-quick-action="clear-filters">Clear filters</button>
      </div>
    `;
    return;
  }

  els.masterQuickstart.classList.remove("hidden");
  els.masterQuickstart.innerHTML = `
    <div class="quickstart-head">
      <h3>No Deliverables Yet</h3>
      <p class="muted">This space is ready, but no projects or solutions have been added.</p>
    </div>
    <div class="quickstart-actions">
      <button type="button" class="primary" data-quick-action="create-project">Create project</button>
      <button type="button" class="secondary" data-quick-action="create-solution">Create solution</button>
    </div>
  `;
}

function renderMasterTable() {
  const mod = getRouteModule("master");
  if (!mod || typeof mod.renderMasterTable !== "function") {
    ensureRouteModule("master").then((loaded) => {
      if (loaded && state.currentView === "master") renderMasterTable();
    });
    return;
  }
  mod.renderMasterTable({
    state,
    els,
    filteredDeliverables,
    deliverableKey,
    phaseDisplayName,
    solutionProgress,
    updateBulkSelectionCount,
    renderMasterQuickstart,
    renderKanban,
    renderCalendar,
    clearDeliverablesFilters,
  });
}

function updateBulkSelectionCount() {
  if (!els.bulkSelectedCount) return;
  els.bulkSelectedCount.textContent = `${state.deliverableSelection.size} selected`;
  if (els.bulkApply) {
    els.bulkApply.disabled = !state.deliverableSelection.size || !els.bulkAction?.value;
  }
  syncSelectAllCheckbox();
}

function syncBulkInputs() {
  const action = els.bulkAction?.value || "";
  if (els.bulkStatus) els.bulkStatus.classList.toggle("hidden", action !== "status");
  if (els.bulkOwner) els.bulkOwner.classList.toggle("hidden", action !== "owner");
  updateBulkSelectionCount();
}

async function applyBulkAction() {
  const action = els.bulkAction?.value || "";
  if (!action || !state.deliverableSelection.size) return;
  const status = els.bulkStatus?.value || "";
  const owner = (els.bulkOwner?.value || "").trim();
  if (action === "status" && !status) {
    alert("Select a status first.");
    return;
  }
  if (action === "owner" && !owner) {
    alert("Enter an owner name.");
    return;
  }
  const updates = Array.from(state.deliverableSelection);
  try {
    setStatus("Updating deliverables…");
    for (const key of updates) {
      const [type, id] = key.split(":");
      if (action === "status") {
        if (type === "project") {
          const updated = await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
          upsertById(state.projects, updated, "project_id");
        } else if (type === "solution") {
          const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
          upsertById(state.solutions, updated, "solution_id");
        }
      } else if (action === "owner" && type === "solution") {
        const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify({ owner }) });
        upsertById(state.solutions, updated, "solution_id");
      }
    }
    state.deliverableSelection.clear();
    renderMasterTable();
    renderDashboard();
    renderKanban();
    renderCalendar();
    setStatus("Deliverables updated", "positive");
  } catch (err) {
    alert(`Bulk update failed: ${err.message}`);
  }
}

async function updateDeliverableField(type, id, field, value) {
  try {
    if (type === "project") {
      const payload = { [field]: field === "priority" ? Number(value) : value };
      const updated = await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      upsertById(state.projects, updated, "project_id");
    } else {
      const payload = { [field]: field === "priority" ? Number(value) : value };
      if (field === "rag_status") {
        payload.rag_reason = "";
      }
      const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      upsertById(state.solutions, updated, "solution_id");
    }
    renderMasterTable();
    renderDashboard();
    renderKanban();
    renderCalendar();
  } catch (err) {
    alert(`Update failed: ${err.message}`);
  }
}

function setRagSelectVisualState(fieldEl, value) {
  if (!fieldEl || !fieldEl.classList?.contains("rag-select")) return;
  const normalized = String(value || "").toLowerCase();
  const rag = normalized === "red" || normalized === "amber" ? normalized : "green";
  fieldEl.dataset.ragState = rag;
  fieldEl.classList.remove("rag-red", "rag-amber", "rag-green");
  fieldEl.classList.add(`rag-${rag}`);
}

function bindDeliverablesTable() {
  if (!els.masterTable || els.masterTable._bound) return;
  els.masterTable.addEventListener("change", (e) => {
    const select = e.target.closest(".deliverable-select");
    if (select) {
      const type = select.getAttribute("data-type");
      const id = select.getAttribute("data-id");
      const key = deliverableKey(type, id);
      if (select.checked) state.deliverableSelection.add(key);
      else state.deliverableSelection.delete(key);
      updateBulkSelectionCount();
      return;
    }
    const fieldEl = e.target.closest("[data-field]");
    if (fieldEl) {
      const type = fieldEl.getAttribute("data-type");
      const id = fieldEl.getAttribute("data-id");
      const field = fieldEl.getAttribute("data-field");
      const value = fieldEl.value;
      if (field === "rag_status") setRagSelectVisualState(fieldEl, value);
      updateDeliverableField(type, id, field, value);
    }
  });
  els.masterTable.addEventListener("click", (e) => {
    const actionBtn = e.target.closest("[data-action]");
    if (!actionBtn) return;
    const action = actionBtn.getAttribute("data-action");
    const type = actionBtn.getAttribute("data-type");
    const id = actionBtn.getAttribute("data-id");
    if (action === "edit") {
      if (type === "project") {
        const proj = state.projects.find((p) => p.project_id === id);
        openProjectForm(proj);
      } else if (type === "solution") {
        const sol = state.solutions.find((s) => s.solution_id === id);
        openSolutionModal(sol, "details");
      }
    }
    if (action === "add-subcomponent" && type === "solution") {
      const sol = state.solutions.find((s) => s.solution_id === id);
      openSolutionModal(sol, "subcomponents");
      showSubcomponentForm(sol);
    }
  });
  els.masterTable._bound = true;
}

function syncSelectAllCheckbox() {
  const selectAll = document.getElementById("deliverables-select-all");
  if (!selectAll) return;
  const boxes = els.masterTable?.querySelectorAll('input.deliverable-select') || [];
  const total = boxes.length;
  if (!total) {
    selectAll.checked = false;
    selectAll.indeterminate = false;
    return;
  }
  const checkedCount = Array.from(boxes).filter((box) => box.checked).length;
  selectAll.checked = checkedCount === total;
  selectAll.indeterminate = checkedCount > 0 && checkedCount < total;
}

function bindDebouncedInput(element, onChange, delayMs = 180) {
  if (!element || typeof onChange !== "function") return;
  let timerId = 0;
  element.addEventListener("input", () => {
    if (timerId) window.clearTimeout(timerId);
    timerId = window.setTimeout(() => {
      onChange(element.value || "");
    }, delayMs);
  });
}

function bindDeliverablesControls() {
  els.createProjectBtn?.addEventListener("click", () => openProjectForm(null));
  els.createSolutionBtn?.addEventListener("click", () => openSolutionModal(null, "details"));
  els.presetMy?.addEventListener("click", () => setDeliverablesPreset("my"));
  els.presetOverdue?.addEventListener("click", () => setDeliverablesPreset("overdue"));
  els.presetBlocked?.addEventListener("click", () => setDeliverablesPreset("blocked"));
  els.presetClear?.addEventListener("click", clearDeliverablesFilters);
  els.bulkAction?.addEventListener("change", syncBulkInputs);
  els.bulkApply?.addEventListener("click", applyBulkAction);
  if (els.masterQuickstart && !els.masterQuickstart._bound) {
    els.masterQuickstart.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-quick-action]");
      if (!btn) return;
      const action = (btn.getAttribute("data-quick-action") || "").trim();
      if (action === "create-project") {
        openProjectForm(null);
      } else if (action === "create-solution") {
        openSolutionModal(null, "details");
      } else if (action === "clear-filters") {
        clearDeliverablesFilters();
      }
    });
    els.masterQuickstart._bound = true;
  }
  syncBulkInputs();
  updatePresetButtons();
}

function clearSubcomponentsWorkbenchFilters() {
  const wb = state.subcomponentsWorkbench;
  wb.preset = "all";
  wb.filters = {
    search: "",
    project_id: "",
    solution_id: "",
    assignee: "",
    assignee_name: "",
    status: "",
    priority_max: "",
  };
  wb.selected.clear();
  wb.activeSubcomponentId = "";
  if (els.subcomponentsWorkbenchSearch) els.subcomponentsWorkbenchSearch.value = "";
  if (els.subcomponentsWorkbenchProject) els.subcomponentsWorkbenchProject.value = "";
  if (els.subcomponentsWorkbenchSolution) {
    updateSubcomponentsWorkbenchSolutionOptions("");
    els.subcomponentsWorkbenchSolution.value = "";
  }
  if (els.subcomponentsWorkbenchAssignee) els.subcomponentsWorkbenchAssignee.value = "";
  if (els.subcomponentsWorkbenchStatus) els.subcomponentsWorkbenchStatus.value = "";
  if (els.subcomponentsWorkbenchPriority) els.subcomponentsWorkbenchPriority.value = "";
  renderSubcomponentsWorkbench();
}

function syncSubcomponentsWorkbenchBulkInputs() {
  if (!els.subcomponentsWorkbenchBulkAction) return;
  const action = els.subcomponentsWorkbenchBulkAction.value || "";
  if (els.subcomponentsWorkbenchBulkStatus) {
    els.subcomponentsWorkbenchBulkStatus.classList.toggle("hidden", action !== "status");
  }
  if (els.subcomponentsWorkbenchBulkAssignee) {
    els.subcomponentsWorkbenchBulkAssignee.classList.toggle("hidden", action !== "assignee");
  }
  if (els.subcomponentsWorkbenchBulkShift) {
    els.subcomponentsWorkbenchBulkShift.classList.toggle("hidden", action !== "shift_due");
  }
}

async function applySubcomponentsWorkbenchBulkAction() {
  const wb = state.subcomponentsWorkbench;
  const selectedIds = Array.from(wb.selected);
  if (!selectedIds.length) {
    alert("Select at least one subcomponent.");
    return;
  }
  const action = els.subcomponentsWorkbenchBulkAction?.value || "";
  if (!action) {
    alert("Choose a bulk action.");
    return;
  }
  const payload = { subcomponent_ids: selectedIds };
  if (action === "status") {
    payload.status = els.subcomponentsWorkbenchBulkStatus?.value || "";
    if (!payload.status) {
      alert("Select a status value.");
      return;
    }
  } else if (action === "assignee") {
    const assigneeUserId = els.subcomponentsWorkbenchBulkAssignee?.value || "";
    if (assigneeUserId) {
      const user = findUserBySoeid(assigneeUserId);
      payload.assignee_user_soeid = assigneeUserId;
      payload.assignee = user?.display_name || assigneeUserId;
    } else {
      payload.clear_assignee = true;
    }
  } else if (action === "shift_due") {
    const shift = Number(els.subcomponentsWorkbenchBulkShift?.value || "");
    if (!Number.isFinite(shift) || Math.abs(shift) < 1) {
      alert("Enter a due date shift in whole days (e.g. 3 or -2).");
      return;
    }
    payload.due_date_shift_days = Math.trunc(shift);
  } else {
    alert("Unsupported bulk action.");
    return;
  }

  try {
    const updated = await api("/subcomponents/actions/batch", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    (Array.isArray(updated) ? updated : []).forEach((row) => {
      upsertById(state.subcomponents, row, "subcomponent_id");
    });
    renderSubcomponentsWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionSubcomponents(openSolutionId);
    }
  } catch (err) {
    alert(`Bulk update failed: ${err.message || err}`);
  }
}

function bindSubcomponentsWorkbenchControls() {
  const wb = state.subcomponentsWorkbench;
  const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");
  presetButtons.forEach((btn) => {
    if (btn._bound) return;
    btn.addEventListener("click", () => {
      wb.preset = btn.getAttribute("data-preset") || "all";
      wb.selected.clear();
      renderSubcomponentsWorkbench();
    });
    btn._bound = true;
  });

  if (els.subcomponentsWorkbenchSavedSelect && !els.subcomponentsWorkbenchSavedSelect._bound) {
    els.subcomponentsWorkbenchSavedSelect.addEventListener("change", () => {
      const nextId = els.subcomponentsWorkbenchSavedSelect.value || "";
      wb.selectedSavedViewId = nextId;
      if (!nextId) {
        setSubcomponentsWorkbenchSavedStatus("");
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === nextId);
      if (!saved) return;
      if (els.subcomponentsWorkbenchSavedName) {
        els.subcomponentsWorkbenchSavedName.value = saved.name || "";
      }
      setSubcomponentsWorkbenchSavedStatus(`Applied "${saved.name}"`);
      applySubcomponentsWorkbenchSavedView(saved);
    });
    els.subcomponentsWorkbenchSavedSelect._bound = true;
  }

  if (els.subcomponentsWorkbenchSavedSave && !els.subcomponentsWorkbenchSavedSave._bound) {
    els.subcomponentsWorkbenchSavedSave.addEventListener("click", () => {
      const rawName = (els.subcomponentsWorkbenchSavedName?.value || "").trim();
      if (!rawName) {
        alert("Enter a view name before saving.");
        return;
      }
      let existing = null;
      if (wb.selectedSavedViewId) {
        existing = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId) || null;
      }
      if (!existing) {
        existing = wb.savedViews.find((row) => normalize(row.name) === normalize(rawName)) || null;
      }
      const captured = captureSubcomponentsWorkbenchCurrentView(rawName);
      if (existing) {
        existing.name = captured.name;
        existing.preset = captured.preset;
        existing.filters = captured.filters;
        existing.updated_at = captured.updated_at;
        wb.selectedSavedViewId = existing.view_id;
      } else {
        wb.savedViews.push(captured);
        wb.selectedSavedViewId = captured.view_id;
      }
      persistSubcomponentsWorkbenchSavedViews();
      updateSubcomponentsWorkbenchSavedViewsUI();
      setSubcomponentsWorkbenchSavedStatus(`Saved "${rawName}"`);
    });
    els.subcomponentsWorkbenchSavedSave._bound = true;
  }

  if (els.subcomponentsWorkbenchSavedDelete && !els.subcomponentsWorkbenchSavedDelete._bound) {
    els.subcomponentsWorkbenchSavedDelete.addEventListener("click", () => {
      const selectedId = wb.selectedSavedViewId || els.subcomponentsWorkbenchSavedSelect?.value || "";
      if (!selectedId) {
        alert("Select a saved view to delete.");
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === selectedId);
      if (!saved) return;
      if (!confirm(`Delete saved view "${saved.name}"?`)) return;
      wb.savedViews = wb.savedViews.filter((row) => row.view_id !== selectedId);
      wb.selectedSavedViewId = "";
      persistSubcomponentsWorkbenchSavedViews();
      updateSubcomponentsWorkbenchSavedViewsUI();
      setSubcomponentsWorkbenchSavedStatus(`Deleted "${saved.name}"`);
    });
    els.subcomponentsWorkbenchSavedDelete._bound = true;
  }

  bindDebouncedInput(els.subcomponentsWorkbenchSearch, (value) => {
    wb.filters.search = value || "";
    renderSubcomponentsWorkbench();
  });

  if (els.subcomponentsWorkbenchProject && !els.subcomponentsWorkbenchProject._bound) {
    els.subcomponentsWorkbenchProject.addEventListener("change", () => {
      wb.filters.project_id = els.subcomponentsWorkbenchProject.value || "";
      wb.filters.solution_id = "";
      updateSubcomponentsWorkbenchSolutionOptions(wb.filters.project_id);
      if (els.subcomponentsWorkbenchSolution) {
        els.subcomponentsWorkbenchSolution.value = "";
      }
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchProject._bound = true;
  }

  if (els.subcomponentsWorkbenchSolution && !els.subcomponentsWorkbenchSolution._bound) {
    els.subcomponentsWorkbenchSolution.addEventListener("change", () => {
      wb.filters.solution_id = els.subcomponentsWorkbenchSolution.value || "";
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchSolution._bound = true;
  }

  if (els.subcomponentsWorkbenchAssignee && !els.subcomponentsWorkbenchAssignee._bound) {
    els.subcomponentsWorkbenchAssignee.addEventListener("change", () => {
      const value = els.subcomponentsWorkbenchAssignee.value || "";
      wb.filters.assignee = value;
      const user = findUserBySoeid(value);
      wb.filters.assignee_name = user?.display_name || "";
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchAssignee._bound = true;
  }

  if (els.subcomponentsWorkbenchStatus && !els.subcomponentsWorkbenchStatus._bound) {
    els.subcomponentsWorkbenchStatus.addEventListener("change", () => {
      wb.filters.status = els.subcomponentsWorkbenchStatus.value || "";
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchStatus._bound = true;
  }

  if (els.subcomponentsWorkbenchPriority && !els.subcomponentsWorkbenchPriority._bound) {
    bindDebouncedInput(els.subcomponentsWorkbenchPriority, (value) => {
      wb.filters.priority_max = value || "";
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchPriority._bound = true;
  }

  if (els.subcomponentsWorkbenchClearFilters && !els.subcomponentsWorkbenchClearFilters._bound) {
    els.subcomponentsWorkbenchClearFilters.addEventListener("click", clearSubcomponentsWorkbenchFilters);
    els.subcomponentsWorkbenchClearFilters._bound = true;
  }

  if (els.subcomponentsWorkbenchBulkAction && !els.subcomponentsWorkbenchBulkAction._bound) {
    els.subcomponentsWorkbenchBulkAction.addEventListener("change", syncSubcomponentsWorkbenchBulkInputs);
    els.subcomponentsWorkbenchBulkAction._bound = true;
  }
  if (els.subcomponentsWorkbenchBulkApply && !els.subcomponentsWorkbenchBulkApply._bound) {
    els.subcomponentsWorkbenchBulkApply.addEventListener("click", () => {
      applySubcomponentsWorkbenchBulkAction();
    });
    els.subcomponentsWorkbenchBulkApply._bound = true;
  }
  syncSubcomponentsWorkbenchBulkInputs();

  if (els.subcomponentsWorkbenchTable && !els.subcomponentsWorkbenchTable._bound) {
    els.subcomponentsWorkbenchTable.addEventListener("change", (e) => {
      const rowCheck = e.target.closest(".scwb-select-row");
      if (rowCheck) {
        const subId = rowCheck.getAttribute("data-id") || "";
        if (!subId) return;
        if (rowCheck.checked) wb.selected.add(subId);
        else wb.selected.delete(subId);
        updateSubcomponentsWorkbenchSelectionCount();
        return;
      }
      if (e.target.id === "scwb-select-all") {
        const checked = !!e.target.checked;
        (wb.visibleIds || []).forEach((subId) => {
          if (checked) wb.selected.add(subId);
          else wb.selected.delete(subId);
        });
        renderSubcomponentsWorkbench();
      }
    });
    els.subcomponentsWorkbenchTable.addEventListener("click", (e) => {
      const editBtn = e.target.closest(".scwb-edit-btn");
      if (editBtn) {
        const subId = editBtn.getAttribute("data-id") || "";
        openSubcomponentsWorkbenchDrawer(subId);
        return;
      }
      const row = e.target.closest("tr[data-id]");
      if (!row) return;
      if (e.target.closest("button,input,select,textarea,label")) return;
      wb.activeSubcomponentId = row.getAttribute("data-id") || "";
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchTable._bound = true;
  }

  if (els.subcomponentsWorkbenchForm && !els.subcomponentsWorkbenchForm._bound) {
    els.subcomponentsWorkbenchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.subcomponentsWorkbenchForm);
      const subId = data.get("subcomponent_id");
      if (!subId) {
        alert("Select a subcomponent first.");
        return;
      }
      const assigneeUserId = data.get("assignee") || "";
      const assigneeUser = findUserBySoeid(assigneeUserId);
      const payload = {
        subcomponent_name: data.get("subcomponent_name") || "",
        status: data.get("status") || "to_do",
        priority: Number(data.get("priority") || 3),
        due_date: data.get("due_date") || null,
        assignee: assigneeUser?.display_name || "",
        assignee_user_soeid: assigneeUserId || null,
        blocked: !!data.get("blocked"),
        blocker_note: data.get("blocker_note") || null,
      };
      try {
        const updated = await api(`/subcomponents/${subId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        upsertById(state.subcomponents, updated, "subcomponent_id");
        wb.activeSubcomponentId = updated.subcomponent_id;
        renderSubcomponentsWorkbench();
        const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
          renderSolutionSubcomponents(openSolutionId);
        }
      } catch (err) {
        alert(`Save failed: ${err.message || err}`);
      }
    });
    els.subcomponentsWorkbenchForm._bound = true;
  }

  if (els.subcomponentsWorkbenchReset && !els.subcomponentsWorkbenchReset._bound) {
    els.subcomponentsWorkbenchReset.addEventListener("click", () => {
      wb.activeSubcomponentId = "";
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchReset._bound = true;
  }

  if (els.subcomponentsWorkbenchClose && !els.subcomponentsWorkbenchClose._bound) {
    els.subcomponentsWorkbenchClose.addEventListener("click", () => closeSubcomponentsWorkbenchDrawer());
    els.subcomponentsWorkbenchClose._bound = true;
  }

  if (!document._scwbShortcutsBound) {
    document.addEventListener("keydown", (event) => {
      if (state.currentView !== "subcomponents-workbench") return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const key = (event.key || "").toLowerCase();
      const inWorkbenchTable = !!event.target?.closest?.("#subcomponents-workbench-table");
      const typingContext = isTypingInputTarget(event.target) && !inWorkbenchTable;

      if (key === "/" && !typingContext) {
        event.preventDefault();
        els.subcomponentsWorkbenchSearch?.focus();
        return;
      }
      if (key === "escape") {
        const isDrawerOpen = wb.drawerOpen !== false;
        if (isDrawerOpen) {
          event.preventDefault();
          closeSubcomponentsWorkbenchDrawer();
        }
        return;
      }
      if (typingContext) return;

      if (key === "arrowdown" || key === "arrowup") {
        event.preventDefault();
        setActiveSubcomponentByOffset(key === "arrowdown" ? 1 : -1);
        return;
      }
      if (key === "e") {
        event.preventDefault();
        openSubcomponentsWorkbenchDrawer();
        window.setTimeout(() => {
          const target = els.subcomponentsWorkbenchForm?.querySelector('[name="subcomponent_name"]');
          if (target) target.focus();
        }, 0);
        return;
      }
    });
    document._scwbShortcutsBound = true;
  }
}

function renderDashboard() {
  const mod = getRouteModule("dashboard");
  if (!mod || typeof mod.renderDashboard !== "function") {
    if (state.currentView === "dashboard" && els.dashboardSpaceCapacity) {
      els.dashboardSpaceCapacity.innerHTML = "<p class='muted'>Loading...</p>";
    }
    if (state.currentView === "dashboard" && els.dashboardTopProjects) {
      els.dashboardTopProjects.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("dashboard").then((loaded) => {
      if (loaded && state.currentView === "dashboard") renderDashboard();
    });
    return;
  }
  mod.renderDashboard({ state, els, formatStatus });
}

function renderPMDashboard() {
  const mod = getRouteModule("pm-dashboard");
  if (!mod || typeof mod.renderPMDashboard !== "function") {
    if (state.currentView === "pm-dashboard") {
      if (els.pmDashboardSummary) {
        els.pmDashboardSummary.innerHTML = "<p class='muted'>Loading...</p>";
      }
      if (els.pmDashboardHealth) {
        els.pmDashboardHealth.innerHTML = "<p class='muted'>Loading...</p>";
      }
    }
    ensureRouteModule("pm-dashboard").then((loaded) => {
      if (loaded && state.currentView === "pm-dashboard") renderPMDashboard();
    });
    return;
  }
  mod.renderPMDashboard({
    state,
    els,
    formatStatus,
    assigneeKeyFromAlloc,
    assigneeLabelFromKey,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
  });
}

function closeConfirmModal(result = false) {
  const resolver = pendingConfirmResolve;
  pendingConfirmResolve = null;
  if (els.confirmModal) {
    els.confirmModal.classList.add("hidden");
  }
  if (confirmReturnFocusEl && typeof confirmReturnFocusEl.focus === "function") {
    confirmReturnFocusEl.focus();
  }
  confirmReturnFocusEl = null;
  if (resolver) {
    resolver(result);
  }
}

function showConfirmModal(options = {}) {
  const title = String(options.title || "Confirm Action");
  const message = String(options.message || "Are you sure you want to continue?");
  const confirmLabel = String(options.confirmLabel || "Confirm");
  const cancelLabel = String(options.cancelLabel || "Cancel");
  if (!els.confirmModal || !els.confirmModalTitle || !els.confirmModalMessage || !els.confirmModalConfirm || !els.confirmModalCancel) {
    return Promise.resolve(confirm(message));
  }
  if (pendingConfirmResolve) {
    const staleResolver = pendingConfirmResolve;
    pendingConfirmResolve = null;
    staleResolver(false);
  }
  confirmReturnFocusEl = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  els.confirmModalTitle.textContent = title;
  els.confirmModalMessage.textContent = message;
  els.confirmModalConfirm.textContent = confirmLabel;
  els.confirmModalCancel.textContent = cancelLabel;
  els.confirmModal.classList.remove("hidden");
  window.setTimeout(() => {
    els.confirmModalConfirm?.focus();
  }, 0);
  return new Promise((resolve) => {
    pendingConfirmResolve = resolve;
  });
}

function bindConfirmModal() {
  if (!els.confirmModal || els.confirmModal._bound) return;
  const cancel = () => closeConfirmModal(false);
  const approve = () => closeConfirmModal(true);
  els.confirmModalClose?.addEventListener("click", cancel);
  els.confirmModalCancel?.addEventListener("click", cancel);
  els.confirmModalConfirm?.addEventListener("click", approve);
  els.confirmModal.querySelector(".modal-backdrop")?.addEventListener("click", cancel);
  els.confirmModal._bound = true;
}

function setProjectFormVisibility(show) {
  if (!els.projectModal) return;
  els.projectModal.classList.toggle("hidden", !show);
}

function setProjectActionButtonLabel(isEditing) {
  if (els.projectModalTitle) {
    els.projectModalTitle.textContent = isEditing ? "Edit Project" : "Create Project";
  }
  if (els.projectSubmitBtn) {
    els.projectSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Project";
  }
}

function fillProjectForm(project = null) {
  if (!els.projectForm) return;
  els.projectForm.reset();
  clearDeliverableFormNotice(els.projectFormStatus);
  const setVal = (name, value = "") => {
    const field = els.projectForm.querySelector(`[name="${name}"]`);
    if (field) field.value = value ?? "";
  };
  setVal("project_id", project?.project_id || "");
  setVal("project_name", project?.project_name || "");
  setVal("status", project?.status || "not_started");
  setVal("description", project?.description || "");
  setVal("success_criteria", project?.success_criteria || "");
  setVal("sponsor", project?.sponsor || "");
  setVal("sponsor_user_soeid", project?.sponsor_user_soeid || "");
  setVal("strategic_objective", project?.strategic_objective || "");
  setVal("priority", project?.priority ?? 3);
  if (els.deleteProjectBtn) {
    els.deleteProjectBtn.disabled = !project?.project_id;
  }
}

function openProjectForm(project = null) {
  fillProjectForm(project);
  setProjectFormVisibility(true);
  setProjectActionButtonLabel(!!project?.project_id);
}

function closeProjectForm() {
  fillProjectForm(null);
  setProjectFormVisibility(false);
  setProjectActionButtonLabel(false);
}

function bindProjectForm() {
  if (!els.projectForm) return;
  els.projectModalClose?.addEventListener("click", () => closeProjectForm());
  els.projectModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => closeProjectForm());
  els.projectForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(els.projectForm);
    const id = (data.get("project_id") || "").toString().trim();
    const isEditing = !!id;
    const payload = {
      project_name: data.get("project_name"),
      status: data.get("status"),
      description: data.get("description"),
      success_criteria: data.get("success_criteria") || null,
      sponsor: data.get("sponsor"),
      sponsor_user_soeid: data.get("sponsor_user_soeid") || null,
      strategic_objective: data.get("strategic_objective") || null,
      priority: Number(data.get("priority") || 3),
    };
    try {
      if (isEditing) {
        setDeliverableFormNotice(els.projectFormStatus, "Saving project...");
      } else {
        setDeliverableFormNotice(els.projectFormStatus, "Creating project...");
      }
      markIgnoreRefresh("projects");
      const saved = isEditing
        ? await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await api("/projects", { method: "POST", body: JSON.stringify(payload) });
      upsertById(state.projects, saved, "project_id");
      fillProjectForm(saved);
      setProjectActionButtonLabel(true);
      populateSelects();
      renderMasterTable();
      renderDashboard();
      renderKanban();
      renderCalendar();
      const successMessage = isEditing
        ? `Saved project at ${timestampLabel()}.`
        : `Created project at ${timestampLabel()}.`;
      setDeliverableFormNotice(
        els.projectFormStatus,
        successMessage,
        "success",
        3200
      );
    } catch (err) {
      ignoreNextRefresh.delete("projects");
      setDeliverableFormNotice(
        els.projectFormStatus,
        `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
        "error"
      );
      alert(`${isEditing ? "Save" : "Create"} failed: ${err.message}`);
    }
  });
  els.projectForm.addEventListener("reset", () => {
    clearDeliverableFormNotice(els.projectFormStatus);
    fillProjectForm(null);
    setProjectActionButtonLabel(false);
  });
  if (els.deleteProjectBtn) {
    els.deleteProjectBtn.addEventListener("click", async () => {
      const id = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
      if (!id) return;
      const projectName = els.projectForm?.querySelector('[name="project_name"]')?.value || "this project";
      const confirmed = await showConfirmModal({
        title: "Delete Project?",
        message: `Delete project "${projectName}"? This cannot be undone.`,
        confirmLabel: "Delete Project",
      });
      if (!confirmed) return;
      try {
        markIgnoreRefresh("projects");
        await api(`/projects/${id}`, { method: "DELETE" });
        removeById(state.projects, id, "project_id");
        closeProjectForm();
        populateSelects();
        renderMasterTable();
        renderDashboard();
        renderKanban();
        renderCalendar();
      } catch (err) {
        ignoreNextRefresh.delete("projects");
        alert(`Delete failed: ${err.message}`);
      }
    });
  }
}

function bindSolutionForm() {
  if (!els.solutionForm) return;
  els.solutionModalClose?.addEventListener("click", () => closeSolutionModal());
  els.solutionModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => closeSolutionModal());

  const saveHandler = async () => {
    const data = new FormData(els.solutionForm);
    const id = (data.get("solution_id") || "").toString().trim();
    const isEditing = !!id;
    const projectId = (data.get("project_id") || "").toString().trim();
    if (!isEditing && !projectId) {
      alert("Project is required.");
      return;
    }
    const payload = buildSolutionPayload(data);
    try {
      if (isEditing) {
        setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...");
      } else {
        setDeliverableFormNotice(els.solutionFormStatus, "Creating solution...");
      }
      markIgnoreRefresh("solutions");
      const saved = isEditing
        ? await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await api(`/projects/${projectId}/solutions`, { method: "POST", body: JSON.stringify(payload) });
      upsertById(state.solutions, saved, "solution_id");
      populateSelects();
      fillSolutionForm(saved);
      setSolutionActionButtonLabel(true);
      renderActiveView();
      renderSolutionPhases(saved.solution_id);
      renderSolutionSubcomponents(saved.solution_id);
      renderSolutionActivity(saved.solution_id);
      const successMessage = isEditing
        ? `Saved solution at ${timestampLabel()}.`
        : `Created solution at ${timestampLabel()}.`;
      setDeliverableFormNotice(
        els.solutionFormStatus,
        successMessage,
        "success",
        3200
      );
    } catch (err) {
      ignoreNextRefresh.delete("solutions");
      setDeliverableFormNotice(
        els.solutionFormStatus,
        `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
        "error"
      );
      alert(`${isEditing ? "Save" : "Create"} failed: ${err.message}`);
    }
  };

  els.solutionForm.addEventListener("submit", (e) => {
    e.preventDefault();
    saveHandler();
  });
  els.solutionForm.addEventListener("reset", () => {
    clearDeliverableFormNotice(els.solutionFormStatus);
    fillSolutionForm(null);
    setSolutionActionButtonLabel(false);
    updateCurrentPhaseOptions("");
    renderSolutionPhases();
  });
  if (els.deleteSolutionBtn) {
    els.deleteSolutionBtn.addEventListener("click", async () => {
      const id = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      if (!id) return;
      const solutionName = els.solutionForm?.querySelector('[name="solution_name"]')?.value || "this solution";
      const confirmed = await showConfirmModal({
        title: "Delete Solution?",
        message: `Delete solution "${solutionName}"? This cannot be undone.`,
        confirmLabel: "Delete Solution",
      });
      if (!confirmed) return;
      try {
        markIgnoreRefresh("solutions");
        await api(`/solutions/${id}`, { method: "DELETE" });
        removeById(state.solutions, id, "solution_id");
        delete state.solutionPhases[id];
        closeSolutionModal();
        populateSelects();
        renderMasterTable();
        renderDashboard();
        renderKanban();
        renderCalendar();
      } catch (err) {
        ignoreNextRefresh.delete("solutions");
        alert(`Delete failed: ${err.message}`);
      }
    });
  }
}

function buildSolutionPayload(data) {
  const payload = {
    solution_name: data.get("solution_name"),
    version: data.get("version"),
    status: data.get("status"),
    priority: Number(data.get("priority") || 3),
    due_date: data.get("due_date") || null,
    planned_start_date: data.get("planned_start_date") || null,
    current_phase: data.get("current_phase") || null,
    description: data.get("description"),
    problem_statement: data.get("problem_statement") || null,
    success_criteria: data.get("success_criteria") || null,
    impact_confidence: data.get("impact_confidence") || null,
    owner: data.get("owner"),
    owner_user_soeid: data.get("owner_user_soeid") || null,
    assignee: data.get("assignee") || "",
    assignee_user_soeid: data.get("assignee_user_soeid") || (data.get("assignee") || null),
    approver: data.get("approver") || null,
    approver_user_soeid: data.get("approver_user_soeid") || null,
    key_stakeholder: data.get("key_stakeholder"),
    rag_confidence: data.get("rag_confidence") ? Number(data.get("rag_confidence")) : null,
    blockers: data.get("blockers") || null,
    risks: data.get("risks") || null,
    capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
    capacity_fte_months: numberOr(data.get("capacity_hours"), 0),
    rag_status: data.get("rag_status") || "green",
    rag_reason: data.get("rag_reason") || null,
  };
  return payload;
}

function fillSolutionForm(solution = null) {
  if (!els.solutionForm) return;
  els.solutionForm.reset();
  clearDeliverableFormNotice(els.solutionFormStatus);
  els.solutionForm.querySelector('[name="solution_id"]').value = solution?.solution_id || "";
  els.solutionForm.querySelector('[name="project_id"]').value = solution?.project_id || "";
  els.solutionForm.querySelector('[name="solution_name"]').value = solution?.solution_name || "";
  els.solutionForm.querySelector('[name="version"]').value = solution?.version || "0.1.0";
  els.solutionForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(solution?.capacity_hours, 0);
  els.solutionForm.querySelector('[name="status"]').value = solution?.status || "not_started";
  els.solutionForm.querySelector('[name="rag_status"]').value = solution?.rag_status || "green";
  els.solutionForm.querySelector('[name="rag_reason"]').value = solution?.rag_reason || "";
  els.solutionForm.querySelector('[name="priority"]').value = solution?.priority ?? 3;
  els.solutionForm.querySelector('[name="due_date"]').value = solution?.due_date || "";
  els.solutionForm.querySelector('[name="planned_start_date"]').value = solution?.planned_start_date || "";
  els.solutionForm.querySelector('[name="description"]').value = solution?.description || "";
  els.solutionForm.querySelector('[name="problem_statement"]').value = solution?.problem_statement || "";
  els.solutionForm.querySelector('[name="success_criteria"]').value = solution?.success_criteria || "";
  els.solutionForm.querySelector('[name="impact_confidence"]').value = solution?.impact_confidence || "";
  els.solutionForm.querySelector('[name="owner"]').value = solution?.owner || "";
  els.solutionForm.querySelector('[name="owner_user_soeid"]').value = solution?.owner_user_soeid || "";
  els.solutionForm.querySelector('[name="assignee"]').value = solution?.assignee || "";
  els.solutionForm.querySelector('[name="assignee_user_soeid"]').value = solution?.assignee_user_soeid || "";
  els.solutionForm.querySelector('[name="approver"]').value = solution?.approver || "";
  els.solutionForm.querySelector('[name="approver_user_soeid"]').value = solution?.approver_user_soeid || "";
  els.solutionForm.querySelector('[name="key_stakeholder"]').value = solution?.key_stakeholder || "";
  els.solutionForm.querySelector('[name="rag_confidence"]').value = solution?.rag_confidence ?? "";
  els.solutionForm.querySelector('[name="blockers"]').value = solution?.blockers || "";
  els.solutionForm.querySelector('[name="risks"]').value = solution?.risks || "";
  updateCurrentPhaseOptions(solution?.solution_id || "");
  els.solutionForm.querySelector('[name="current_phase"]').value = solution?.current_phase || "";
  if (els.deleteSolutionBtn) {
    els.deleteSolutionBtn.disabled = !solution?.solution_id;
  }
}

function setSolutionActionButtonLabel(isEditing) {
  if (els.solutionModalTitle) {
    els.solutionModalTitle.textContent = isEditing ? "Edit Solution" : "Create Solution";
  }
  if (els.solutionSubmitBtn) {
    els.solutionSubmitBtn.textContent = isEditing ? "Save Solution" : "Create Solution";
  }
}

function openSolutionModal(solution = null, tab = "details") {
  if (!els.solutionModal) return;
  fillSolutionForm(solution);
  setSolutionActionButtonLabel(!!solution?.solution_id);
  els.solutionModal.classList.remove("hidden");
  if (els.subcomponentViewToggle) {
    els.subcomponentViewToggle.textContent = state.subcomponentView === "table" ? "Swimlane View" : "Table View";
  }
  setSolutionTab(tab);
  if (solution?.solution_id) {
    renderSolutionPhases(solution.solution_id);
    renderSolutionSubcomponents(solution.solution_id);
    renderSolutionActivity(solution.solution_id);
  } else {
    if (els.phasesTable) els.phasesTable.innerHTML = "<p class='muted'>Save the solution to manage phases.</p>";
    if (els.solutionSubcomponentTable) els.solutionSubcomponentTable.innerHTML = "<p class='muted'>Save the solution to add subcomponents.</p>";
    if (els.solutionActivity) els.solutionActivity.innerHTML = "<p class='muted'>Save the solution to see activity.</p>";
  }
}

function closeSolutionModal() {
  if (!els.solutionModal) return;
  fillSolutionForm(null);
  setSolutionActionButtonLabel(false);
  els.solutionModal.classList.add("hidden");
  setSolutionTab("details");
  if (els.subcomponentForm) els.subcomponentForm.classList.add("hidden");
}

function setSolutionTab(tab) {
  const tabButtons = els.solutionModal?.querySelectorAll(".modal-tabs .tab") || [];
  const panels = els.solutionModal?.querySelectorAll(".modal-tab") || [];
  tabButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab));
  panels.forEach((panel) => panel.classList.toggle("active", panel.dataset.tabPanel === tab));
  if (tab === "activity") {
    const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (solutionId) renderSolutionActivity(solutionId);
  }
  if (tab === "subcomponents") {
    const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (solutionId) renderSolutionSubcomponents(solutionId);
  }
  if (tab === "phases") {
    const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (solutionId) renderSolutionPhases(solutionId);
  }
}

function bindSolutionTabs() {
  if (!els.solutionModal) return;
  const tabs = els.solutionModal.querySelector(".modal-tabs");
  if (!tabs || tabs._bound) return;
  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    setSolutionTab(btn.dataset.tab);
  });
  tabs._bound = true;
}

function showSubcomponentForm(solution) {
  if (!els.subcomponentForm) return;
  const sol = solution || state.solutions.find((s) => s.solution_id === els.solutionForm?.querySelector('[name="solution_id"]')?.value);
  if (!sol) return;
  els.subcomponentForm.classList.remove("hidden");
  els.subcomponentForm.reset();
  clearDeliverableFormNotice(els.subcomponentFormStatus);
  els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
  els.subcomponentForm.querySelector('[name="project_id"]').value = sol.project_id;
  els.subcomponentForm.querySelector('[name="solution_id"]').value = sol.solution_id;
  if (els.deleteSubcomponentBtn) {
    els.deleteSubcomponentBtn.disabled = true;
  }
}

function fillSubcomponentForm(sub) {
  if (!els.subcomponentForm || !sub) return;
  els.subcomponentForm.classList.remove("hidden");
  els.subcomponentForm.reset();
  clearDeliverableFormNotice(els.subcomponentFormStatus);
  els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = sub.subcomponent_id;
  els.subcomponentForm.querySelector('[name="project_id"]').value = sub.project_id;
  els.subcomponentForm.querySelector('[name="solution_id"]').value = sub.solution_id;
  els.subcomponentForm.querySelector('[name="subcomponent_name"]').value = sub.subcomponent_name || "";
  els.subcomponentForm.querySelector('[name="priority"]').value = sub.priority ?? "";
  els.subcomponentForm.querySelector('[name="due_date"]').value = sub.due_date || "";
  els.subcomponentForm.querySelector('[name="status"]').value = sub.status || "to_do";
  els.subcomponentForm.querySelector('[name="assignee"]').value = resolveAssigneeSelectValue(sub.assignee_user_soeid, sub.assignee);
  els.subcomponentForm.querySelector('[name="assignee_user_soeid"]').value = sub.assignee_user_soeid || "";
  els.subcomponentForm.querySelector('[name="estimate_hours"]').value =
    sub.estimate_hours != null ? fteFromHoursForInput(sub.estimate_hours, 0) : "";
  els.subcomponentForm.querySelector('[name="blocked"]').checked = !!sub.blocked;
  els.subcomponentForm.querySelector('[name="blocker_note"]').value = sub.blocker_note || "";
  els.subcomponentForm.querySelector('[name="done_criteria"]').value = sub.done_criteria || "";
  els.subcomponentForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(sub.capacity_hours, 0);
  if (els.deleteSubcomponentBtn) {
    els.deleteSubcomponentBtn.disabled = !sub.subcomponent_id;
  }
}

function renderSolutionSubcomponents(solutionId) {
  if (!els.solutionSubcomponentTable) return;
  if (!solutionId) {
    els.solutionSubcomponentTable.innerHTML = "<p class='muted'>Select a solution to see subcomponents.</p>";
    return;
  }
  const subs = state.subcomponents.filter((s) => s.solution_id === solutionId);
  if (state.subcomponentView === "swimlane") {
    const grouped = {
      to_do: [],
      in_progress: [],
      on_hold: [],
      complete: [],
      abandoned: [],
    };
    subs.forEach((s) => grouped[s.status || "to_do"]?.push(s));
    const columns = Object.entries(grouped)
      .map(([status, items]) => {
        const cards = items.length
          ? items
              .map(
                (s) =>
                  `<div class="swimlane-card" data-id="${s.subcomponent_id}">
                    <div class="swimlane-title">${s.subcomponent_name}</div>
                    <div class="swimlane-meta">${s.assignee || "—"} • P${s.priority ?? "–"}</div>
                    <div class="swimlane-meta">Due ${s.due_date || "—"}</div>
                  </div>`
              )
              .join("")
          : "<p class='muted'>Empty</p>";
        return `<div class="swimlane-column"><h4>${formatStatus(status)}</h4>${cards}</div>`;
      })
      .join("");
    els.solutionSubcomponentTable.innerHTML = `<div class="swimlane-board">${columns}</div>`;
  } else {
    const rows = subs
      .map(
        (s) =>
          `<tr data-id="${s.subcomponent_id}">
            <td><button class="icon-btn edit-subcomponent-btn" data-id="${s.subcomponent_id}" title="Edit">✎</button></td>
            <td>${s.subcomponent_name || "—"}</td>
            <td>${formatStatus(s.status)}</td>
            <td>${s.assignee || "—"}</td>
            <td>${s.priority ?? "—"}</td>
            <td>${s.due_date || ""}</td>
          </tr>`
      )
      .join("");
    els.solutionSubcomponentTable.innerHTML = `
      <table class="subcomponent-table">
        <thead>
          <tr>
            <th></th>
            <th>Task</th>
            <th>Status</th>
            <th>Assignee</th>
            <th>Priority</th>
            <th>Due</th>
          </tr>
        </thead>
        <tbody>${rows || "<tr><td colspan='6' class='muted'>No subcomponents</td></tr>"}</tbody>
      </table>`;
  }
}

function bindSolutionSubcomponentControls() {
  if (els.subcomponentViewToggle && !els.subcomponentViewToggle._bound) {
    els.subcomponentViewToggle.addEventListener("click", () => {
      state.subcomponentView = state.subcomponentView === "table" ? "swimlane" : "table";
      els.subcomponentViewToggle.textContent = state.subcomponentView === "table" ? "Swimlane View" : "Table View";
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      renderSolutionSubcomponents(solutionId);
    });
    els.subcomponentViewToggle._bound = true;
  }
  if (els.solutionSubcomponentTable && !els.solutionSubcomponentTable._bound) {
    els.solutionSubcomponentTable.addEventListener("click", (e) => {
      const btn = e.target.closest(".edit-subcomponent-btn");
      const card = e.target.closest(".swimlane-card");
      const id = btn?.getAttribute("data-id") || card?.getAttribute("data-id");
      if (!id) return;
      const sub = state.subcomponents.find((s) => s.subcomponent_id === id);
      if (!sub) return;
      fillSubcomponentForm(sub);
    });
    els.solutionSubcomponentTable._bound = true;
  }
}

function bindModalShortcuts() {
  if (document._jiraLiteModalBound) return;
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (els.confirmModal && !els.confirmModal.classList.contains("hidden")) {
      closeConfirmModal(false);
      return;
    }
    if (els.solutionModal && !els.solutionModal.classList.contains("hidden")) {
      closeSolutionModal();
      return;
    }
    if (els.projectModal && !els.projectModal.classList.contains("hidden")) {
      closeProjectForm();
    }
  });
  document._jiraLiteModalBound = true;
}

async function renderSolutionActivity(solutionId) {
  if (!els.solutionActivity) return;
  if (!solutionId) {
    els.solutionActivity.innerHTML = "<p class='muted'>Select a solution to see activity.</p>";
    return;
  }
  els.solutionActivity.innerHTML = "<p class='muted'>Loading activity…</p>";
  try {
    const rows = await api(`/audit?entity_type=solution&entity_id=${solutionId}`);
    if (!rows?.length) {
      els.solutionActivity.innerHTML = "<p class='muted'>No activity yet.</p>";
      return;
    }
    const html = rows
      .map((row) => {
        const when = row.created_at ? new Date(row.created_at).toLocaleString() : "";
        const field = row.field ? ` • ${row.field}` : "";
        const change = row.new_value ? ` → ${row.new_value}` : "";
        return `<div class="activity-item">
          <div class="activity-title">${row.action}${field}${change}</div>
          <div class="activity-meta">${row.user_id || "system"} • ${when}</div>
        </div>`;
      })
      .join("");
    els.solutionActivity.innerHTML = html;
  } catch (err) {
    els.solutionActivity.innerHTML = `<p class='muted'>Unable to load activity.</p>`;
  }
}

async function renderSolutionPhases(selectedId) {
  if (!els.phasesTable) return;
  const solutionId = selectedId || els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (!solutionId) {
    els.phasesTable.innerHTML = "<p class='muted'>Select a solution to edit phases.</p>";
    return;
  }

  if (!state.solutionPhases[solutionId]) {
    els.phasesTable.innerHTML = "<p class='muted'>Loading phases…</p>";
    try {
      state.solutionPhases[solutionId] = await api(`/solutions/${solutionId}/phases`);
    } catch (err) {
      alert(`Load failed: ${err.message}`);
      return;
    }
  }
  updateCurrentPhaseOptions(solutionId);

  const enabled = new Set((state.solutionPhases[solutionId] || []).filter((p) => p.is_enabled).map((p) => p.phase_id));
  const grouped = {};
  state.phases.forEach((p) => {
    grouped[p.phase_group] = grouped[p.phase_group] || [];
    grouped[p.phase_group].push(p);
  });
  const groupHtml = Object.entries(grouped)
    .map(([groupName, phases]) => {
      const cards = phases
        .map((p) => {
          const checked = enabled.has(p.phase_id) ? "checked" : "";
          return `<div class="phase-cell">
            <div class="phase-title">${phaseDisplayName(p.phase_id)}</div>
            <div class="phase-meta">${groupName}</div>
            <label class="phase-toggle">
              <input type="checkbox" data-phase-id="${p.phase_id}" ${checked}>
              <span>Enabled</span>
            </label>
          </div>`;
        })
        .join("");
      return `<div class="phase-group"><div class="phase-group-title">${groupName}</div><div class="phase-grid">${cards}</div></div>`;
    })
    .join("");
  els.phasesTable.innerHTML = groupHtml;
  els.phasesTable.querySelectorAll('input[data-phase-id]').forEach((box) => {
    box.addEventListener("change", async () => {
      const phases = state.phases.map((ph) => ({
        phase_id: ph.phase_id,
        is_enabled: !!els.phasesTable.querySelector(`input[data-phase-id="${ph.phase_id}"]`)?.checked,
      }));
      try {
        markIgnoreRefresh("solutions");
        await api(`/solutions/${solutionId}/phases`, { method: "POST", body: JSON.stringify({ phases }) });
        const [updated, updatedSolution] = await Promise.all([
          api(`/solutions/${solutionId}/phases`),
          api(`/solutions/${solutionId}`),
        ]);
        state.solutionPhases[solutionId] = updated;
        const idx = state.solutions.findIndex((s) => s.solution_id === solutionId);
        if (idx !== -1) state.solutions[idx] = updatedSolution;

        updateCurrentPhaseOptions(solutionId);
        if (els.solutionForm?.querySelector('[name="solution_id"]')?.value === solutionId) {
          els.solutionForm.querySelector('[name="current_phase"]').value = updatedSolution.current_phase || "";
        }
        renderSolutionPhases(solutionId);
        renderMasterTable();
        renderDashboard();
        renderKanban();
        renderCalendar();
      } catch (err) {
        ignoreNextRefresh.delete("solutions");
        alert(`Save failed: ${err.message}`);
      }
    });
  });
}

function bindSubcomponentForm() {
  if (!els.subcomponentForm) return;
  if (els.showSubcomponentFormBtn) {
    els.showSubcomponentFormBtn.onclick = () => {
      if (els.subcomponentForm.classList.contains("hidden")) {
        const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        const solution = state.solutions.find((s) => s.solution_id === solutionId);
        showSubcomponentForm(solution);
      } else {
        els.subcomponentForm.classList.add("hidden");
      }
    };
  }
  els.subcomponentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(els.subcomponentForm);
    const id = data.get("subcomponent_id");
    if (!id) {
      alert("Select a subcomponent or use Create Subcomponent to add one.");
      return;
    }
    const assigneeUserId = data.get("assignee") || "";
    const assigneeUser = findUserBySoeid(assigneeUserId);
    const assigneeName = assigneeUser?.display_name || "";
    const payload = {
      subcomponent_name: data.get("subcomponent_name"),
      status: data.get("status"),
      priority: Number(data.get("priority") || 3),
      due_date: data.get("due_date") || null,
      assignee: assigneeName,
      assignee_user_soeid: assigneeUserId || null,
      estimate_hours: hoursFromNullableFteInput(data.get("estimate_hours")),
      estimate_fte_months: numberOr(data.get("estimate_hours"), 0),
      blocked: data.get("blocked") ? true : false,
      blocker_note: data.get("blocker_note") || null,
      done_criteria: data.get("done_criteria") || null,
      capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
      capacity_fte_months: numberOr(data.get("capacity_hours"), 0),
    };
    try {
      setDeliverableFormNotice(els.subcomponentFormStatus, "Saving subcomponent...");
      markIgnoreRefresh("subcomponents");
      const updated = await api(`/subcomponents/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      upsertById(state.subcomponents, updated, "subcomponent_id");
      renderSolutionSubcomponents(updated.solution_id);
      renderDashboard();
      setDeliverableFormNotice(
        els.subcomponentFormStatus,
        `Saved subcomponent at ${timestampLabel()}.`,
        "success",
        3200
      );
    } catch (err) {
      ignoreNextRefresh.delete("subcomponents");
      setDeliverableFormNotice(els.subcomponentFormStatus, `Save failed: ${err.message}`, "error");
      alert(`Save failed: ${err.message}`);
    }
  });
  els.subcomponentForm.addEventListener("reset", () => {
    clearDeliverableFormNotice(els.subcomponentFormStatus);
    els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
    if (els.deleteSubcomponentBtn) {
      els.deleteSubcomponentBtn.disabled = true;
    }
  });
  if (els.newSubcomponentBtn) {
    els.newSubcomponentBtn.addEventListener("click", async () => {
      const data = new FormData(els.subcomponentForm);
      const solutionId = data.get("solution_id");
      const projectId = data.get("project_id");
      const name = data.get("subcomponent_name");
      const assigneeUserId = data.get("assignee") || "";
      const assigneeUser = findUserBySoeid(assigneeUserId);
      const assignee = assigneeUser?.display_name || "";
      if (!projectId || !solutionId || !name) {
        alert("Project, solution, and task name are required to create.");
        return;
      }
      const payload = {
        subcomponent_name: name,
        status: data.get("status"),
        priority: Number(data.get("priority") || 3),
        due_date: data.get("due_date") || null,
        assignee,
        assignee_user_soeid: assigneeUserId || null,
        estimate_hours: hoursFromNullableFteInput(data.get("estimate_hours")),
        estimate_fte_months: numberOr(data.get("estimate_hours"), 0),
        blocked: data.get("blocked") ? true : false,
        blocker_note: data.get("blocker_note") || null,
        done_criteria: data.get("done_criteria") || null,
        capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
        capacity_fte_months: numberOr(data.get("capacity_hours"), 0),
      };
      try {
        markIgnoreRefresh("subcomponents");
        const created = await api(`/solutions/${solutionId}/subcomponents`, { method: "POST", body: JSON.stringify(payload) });
        upsertById(state.subcomponents, created, "subcomponent_id");
        els.subcomponentForm.reset();
        els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
        if (els.deleteSubcomponentBtn) {
          els.deleteSubcomponentBtn.disabled = true;
        }
        renderSolutionSubcomponents(solutionId);
        renderDashboard();
      } catch (err) {
        ignoreNextRefresh.delete("subcomponents");
        alert(`Create failed: ${err.message}`);
      }
    });
  }
  if (els.deleteSubcomponentBtn) {
    els.deleteSubcomponentBtn.addEventListener("click", async () => {
      const id = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";
      if (!id) return;
      const solutionId = els.subcomponentForm?.querySelector('[name="solution_id"]')?.value || "";
      const subcomponentName = els.subcomponentForm?.querySelector('[name="subcomponent_name"]')?.value || "this subcomponent";
      if (!confirm(`Delete subcomponent "${subcomponentName}"?`)) return;
      try {
        markIgnoreRefresh("subcomponents");
        await api(`/subcomponents/${id}`, { method: "DELETE" });
        removeById(state.subcomponents, id, "subcomponent_id");
        const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
        if (solution) {
          showSubcomponentForm(solution);
        } else {
          els.subcomponentForm.reset();
          els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
          if (els.deleteSubcomponentBtn) els.deleteSubcomponentBtn.disabled = true;
        }
        renderSolutionSubcomponents(solutionId);
        renderDashboard();
      } catch (err) {
        ignoreNextRefresh.delete("subcomponents");
        alert(`Delete failed: ${err.message}`);
      }
    });
  }
}

function populateSelects() {
  const projectOpts = state.projects.map((p) => `<option value="${p.project_id}">${p.project_name}</option>`).join("");
  const projSelects = [
    els.solutionForm?.querySelector('[name="project_id"]'),
  ].filter(Boolean);
  projSelects.forEach((sel) => {
    if (sel.tagName === "SELECT") {
      sel.innerHTML = `<option value="">Select</option>${projectOpts}`;
    }
  });
  if (els.solutionForm) {
    const projSel = els.solutionForm.querySelector('[name="project_id"]');
    if (projSel && projSel.innerHTML.indexOf("Select") === -1) {
      projSel.innerHTML = `<option value="">Select</option>${projectOpts}`;
    }
    updateCurrentPhaseOptions(els.solutionForm.querySelector('[name="solution_id"]')?.value || "");
  }
  if (els.kanbanFilterProject) {
    els.kanbanFilterProject.innerHTML = `<option value="">All</option>${projectOpts}`;
    els.kanbanFilterProject.value = state.kanbanFilters.project || "";
  }
  if (els.calendarFilterProject) {
    els.calendarFilterProject.innerHTML = `<option value="">All</option>${projectOpts}`;
    els.calendarFilterProject.value = state.calendarFilters.project || "";
  }
  if (els.subcomponentsWorkbenchProject) {
    const wb = state.subcomponentsWorkbench;
    els.subcomponentsWorkbenchProject.innerHTML = `<option value="">All Projects</option>${projectOpts}`;
    els.subcomponentsWorkbenchProject.value = wb.filters.project_id || "";
    updateSubcomponentsWorkbenchSolutionOptions(wb.filters.project_id || "");
    if (wb.filters.solution_id) {
      els.subcomponentsWorkbenchSolution.value = wb.filters.solution_id;
    }
  }
  const teamOpts = state.teams.map((t) => `<option value="${t.team_id}">${t.name}</option>`).join("");
  const teamSelects = [els.teamMemberForm?.querySelector('[name="team_id"]')].filter(Boolean);
  teamSelects.forEach((sel) => (sel.innerHTML = `<option value="">Unassigned</option>${teamOpts}`));
  if (els.teamMemberForm && els.teamMemberForm.querySelector('[name="team_id"]') && state.teams.length && !els.teamMemberForm.querySelector('[name="team_id"]').value) {
    els.teamMemberForm.querySelector('[name="team_id"]').value = state.teams[0].team_id;
  }
  // planning view uses team tags, not team ids
  if (els.planningWindowSelect) {
    const winOpts = state.planningWindows
      .map((w) => `<option value="${w.window_id}">${w.name} (${w.start_date} → ${w.end_date})</option>`)
      .join("");
    const prev = els.planningWindowSelect.value;
    els.planningWindowSelect.innerHTML = `<option value="">Select window</option>${winOpts}`;
    if (prev && state.planningWindows.find((w) => w.window_id === prev)) {
      els.planningWindowSelect.value = prev;
    } else if (!prev && state.planningWindows.length) {
      els.planningWindowSelect.value = state.planningWindows[0].window_id;
    }
    const selectedWin = state.planningWindows.find((w) => w.window_id === els.planningWindowSelect.value);
    if (selectedWin) {
      if (els.planningFrom) els.planningFrom.value = selectedWin.start_date;
      if (els.planningTo) els.planningTo.value = selectedWin.end_date;
      const monthStartInput = els.allocationForm?.querySelector('[name="month_start"]');
      if (monthStartInput && !monthStartInput.value) {
        monthStartInput.value = (normalizeMonthStart(selectedWin.start_date) || "").slice(0, 7);
      }
    }
    updateAllocationWindowHint();
    renderPlanningWindowSummary();
    renderPlanningRoster();
  }

  populateCapacityUserOptions();

  // Assignee dropdown for subcomponents from team members
  if (els.subcomponentForm) {
    const assigneeSel = els.subcomponentForm.querySelector('[name="assignee"]');
    const assigneeUserInput = els.subcomponentForm.querySelector('[name="assignee_user_soeid"]');
    if (assigneeSel) {
      const users = state.users.filter((u) => u.display_name && u.soeid);
      assigneeSel.innerHTML =
        users.length > 0
          ? `<option value="">Select</option>${users.map((u) => `<option value="${u.soeid}">${u.display_name}</option>`).join("")}`
          : `<option value="">No users configured</option>`;
      assigneeSel.onchange = () => {
        if (assigneeUserInput) assigneeUserInput.value = assigneeSel.value || "";
      };
      if (assigneeUserInput) assigneeUserInput.value = assigneeSel.value || "";
    }
  }
  if (els.subcomponentsWorkbenchAssignee || els.subcomponentsWorkbenchBulkAssignee || els.subcomponentsWorkbenchForm) {
    const wb = state.subcomponentsWorkbench;
    const users = state.users
      .filter((u) => u.display_name && u.soeid)
      .sort((a, b) => (a.display_name || "").localeCompare(b.display_name || ""));
    const userOptions = users.map((u) => `<option value="${u.soeid}">${u.display_name}</option>`).join("");

    if (els.subcomponentsWorkbenchAssignee) {
      const prior = wb.filters.assignee || "";
      els.subcomponentsWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;
      els.subcomponentsWorkbenchAssignee.value = prior;
    }
    if (els.subcomponentsWorkbenchBulkAssignee) {
      const prior = els.subcomponentsWorkbenchBulkAssignee.value || "";
      els.subcomponentsWorkbenchBulkAssignee.innerHTML = `<option value="">Unassigned</option>${userOptions}`;
      if (prior && users.find((u) => u.soeid === prior)) {
        els.subcomponentsWorkbenchBulkAssignee.value = prior;
      }
    }
    if (els.subcomponentsWorkbenchForm) {
      const assigneeSel = els.subcomponentsWorkbenchForm.querySelector('[name="assignee"]');
      const assigneeUserInput = els.subcomponentsWorkbenchForm.querySelector('[name="assignee_user_soeid"]');
      if (assigneeSel) {
        const prior = assigneeSel.value || "";
        assigneeSel.innerHTML = `<option value="">Unassigned</option>${userOptions}`;
        if (prior && users.find((u) => u.soeid === prior)) {
          assigneeSel.value = prior;
        }
        assigneeSel.onchange = () => {
          if (assigneeUserInput) assigneeUserInput.value = assigneeSel.value || "";
        };
      }
    }
  }
  if (els.allocationForm) {
    const assigneeSel = els.allocationForm.querySelector('[name="assignee"]');
    const itemSel = els.allocationForm.querySelector('[name="work_item_id"]');
    const typeSel = els.allocationForm.querySelector('[name="work_item_type"]');
    if (assigneeSel) {
      const users = state.users.filter((u) => u.display_name && u.soeid);
      assigneeSel.innerHTML =
        users.length > 0
          ? `<option value="">Select</option>${users.map((u) => `<option value="${u.soeid}">${u.display_name}</option>`).join("")}`
          : `<option value="">No users configured</option>`;
    }
    typeSel?.addEventListener("change", updateAllocationItems);
    itemSel?.addEventListener("change", applyAllocationDefaults);
    updateAllocationItems();
  }

  if (els.aiEntityType && els.aiEntityId) {
    const type = els.aiEntityType.value;
    let options = "";
    if (type === "project") {
      options =
        `<option value=\"\">New project</option>` +
        state.projects.map((p) => `<option value="${p.project_id}">${p.project_name}</option>`).join("");
    } else if (type === "solution") {
      options = state.solutions.map((s) => `<option value="${s.solution_id}">${s.solution_name}</option>`).join("");
    } else {
      options = state.subcomponents.map((sc) => `<option value="${sc.subcomponent_id}">${sc.subcomponent_name}</option>`).join("");
    }
    els.aiEntityId.innerHTML = options || `<option value=\"\">No items</option>`;
  }
}

function updateAllocationItems() {
  if (!els.allocationForm) return;
  const itemSel = els.allocationForm.querySelector('[name="work_item_id"]');
  const typeSel = els.allocationForm.querySelector('[name="work_item_type"]');
  if (!itemSel || !typeSel) return;
  const type = typeSel.value;
  let options = "";
  if (type === "project") {
    options = state.projects.map((p) => `<option value="${p.project_id}">${p.project_name}</option>`).join("");
  } else if (type === "solution") {
    options = state.solutions.map((s) => `<option value="${s.solution_id}">${s.solution_name}</option>`).join("");
  } else {
    options = state.subcomponents.map((sc) => `<option value="${sc.subcomponent_id}">${sc.subcomponent_name}</option>`).join("");
  }
  itemSel.innerHTML = `<option value="">Select</option>${options}`;
  applyAllocationDefaults();
}

function updateAllocationWindowHint() {
  if (!els.allocationWindowHint) return;
  const selectedId = els.planningWindowSelect?.value;
  const win = state.planningWindows.find((w) => w.window_id === selectedId);
  if (win) {
    els.allocationWindowHint.textContent = "";
    els.allocationWindowHint.classList.add("hidden");
    els.allocationWindowHint.classList.remove("warn");
  } else {
    els.allocationWindowHint.textContent = "Select or create a planning window first.";
    els.allocationWindowHint.classList.remove("hidden");
    els.allocationWindowHint.classList.add("warn");
  }
}

function updateSubcomponentSolutionOptions(projectId) {
  const solSel = els.subcomponentForm?.querySelector('[name="solution_id"]');
  if (!solSel || solSel.tagName !== "SELECT") return;
  if (!projectId) {
    solSel.innerHTML = `<option value="">Select project first</option>`;
    return;
  }
  const filteredSolutions = state.solutions.filter((s) => s.project_id === projectId);
  const solutionOpts = filteredSolutions.map((s) => `<option value="${s.solution_id}">${s.solution_name}</option>`).join("");
  solSel.innerHTML = `<option value="">Select</option>${solutionOpts}`;
}

function updateSubcomponentsWorkbenchSolutionOptions(projectId) {
  if (!els.subcomponentsWorkbenchSolution) return;
  const prior = els.subcomponentsWorkbenchSolution.value || "";
  const filteredSolutions = projectId
    ? state.solutions.filter((s) => s.project_id === projectId)
    : state.solutions;
  const opts = filteredSolutions
    .sort((a, b) => (a.solution_name || "").localeCompare(b.solution_name || ""))
    .map((s) => `<option value="${s.solution_id}">${s.solution_name}</option>`)
    .join("");
  els.subcomponentsWorkbenchSolution.innerHTML = `<option value="">All Solutions</option>${opts}`;
  if (prior && filteredSolutions.find((s) => s.solution_id === prior)) {
    els.subcomponentsWorkbenchSolution.value = prior;
  }
}

function renderKanban() {
  const mod = getRouteModule("kanban");
  if (!mod || typeof mod.renderKanban !== "function") {
    if (state.currentView === "kanban" && els.kanbanBoard) {
      els.kanbanBoard.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("kanban").then((loaded) => {
      if (loaded && state.currentView === "kanban") renderKanban();
    });
    return;
  }
  mod.renderKanban({
    state,
    els,
    filteredSolutionsForKanban,
    phaseDisplayName,
    formatStatus,
  });
}

function renderCalendar() {
  const mod = getRouteModule("calendar");
  if (!mod || typeof mod.renderCalendar !== "function") {
    if (state.currentView === "calendar" && els.calendarGrid) {
      els.calendarGrid.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("calendar").then((loaded) => {
      if (loaded && state.currentView === "calendar") renderCalendar();
    });
    return;
  }
  mod.renderCalendar({
    state,
    els,
    filteredSolutionsForCalendar,
    filteredSubcomponentsForCalendar,
    formatStatus,
  });
}

function formatMonthInputValue(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function setCalendarMonth(date) {
  if (!date || Number.isNaN(date)) return;
  state.calendarMonth = new Date(date.getFullYear(), date.getMonth(), 1);
  if (els.calendarMonthInput) {
    els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth);
  }
  renderCalendar();
}

function openCalendarModal(day) {
  const mod = getRouteModule("calendar");
  if (!mod || typeof mod.openCalendarModal !== "function") {
    ensureRouteModule("calendar").then((loaded) => {
      if (loaded && typeof loaded.openCalendarModal === "function") {
        openCalendarModal(day);
      }
    });
    return;
  }
  mod.openCalendarModal(day, {
    state,
    els,
    filteredSolutionsForCalendar,
    filteredSubcomponentsForCalendar,
    formatStatus,
  });
}

async function downloadCsv(kind, filename, resultEl) {
  try {
    const headers = {};
    if (state.activeSpace?.space_id) {
      headers["X-Space-Id"] = state.activeSpace.space_id;
    }
    const res = await fetch(`${API_BASE}/${kind}/export`, {
      credentials: "include",
      headers,
    });
    if (res.status === 401) {
      handleAuthError({ status: 401 });
      setImportResult(resultEl, "Sign in required", true);
      return;
    }
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setImportResult(resultEl, `Downloaded ${filename}`);
  } catch (err) {
    setImportResult(resultEl, `Download failed: ${err.message}`, true);
  }
}

function csvImportResultElement(kind) {
  if (kind === "projects") return els.projectsImportResult;
  if (kind === "solutions") return els.solutionsImportResult;
  if (kind === "users") return els.rosterImportResult;
  return null;
}

function csvTemplateConfig(kind) {
  if (kind === "projects") {
    return {
      filename: "projects-template.csv",
      content: [
        "project_name,status,description,success_criteria,sponsor,sponsor_user_soeid,strategic_objective,priority",
        "Example Project,not_started,Simple project description,Deliver one small milestone,Example Sponsor,,,3",
      ].join("\n"),
    };
  }
  if (kind === "solutions") {
    return {
      filename: "solutions-template.csv",
      content: [
        "project_name,solution_name,version,status,owner,assignee,priority,due_date,current_phase",
        "Example Project,Example Solution,0.1.0,not_started,Example Owner,Example Owner,3,,",
      ].join("\n"),
    };
  }
  return null;
}

function downloadCsvTemplate(kind, resultEl) {
  const config = csvTemplateConfig(kind);
  if (!config) return;
  try {
    const blob = new Blob([config.content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = config.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    if (resultEl) setImportResult(resultEl, `Downloaded ${config.filename}`);
  } catch (err) {
    if (resultEl) setImportResult(resultEl, `Template download failed: ${err.message}`, true);
  }
}

function setCsvUploadStatus(message, tone = "") {
  if (!els.csvUploadStatus) return;
  els.csvUploadStatus.textContent = message || "";
  els.csvUploadStatus.classList.toggle("error", tone === "error");
  els.csvUploadStatus.classList.toggle("success", tone === "success");
}

function setCsvUploadFile(file) {
  const fileNameEl = els.csvUploadFileName;
  const resetSelection = () => {
    csvUploadState.file = null;
    if (els.csvUploadFile) els.csvUploadFile.value = "";
    if (fileNameEl) fileNameEl.textContent = "No file selected";
  };

  if (!file) {
    resetSelection();
    return false;
  }
  const fileName = String(file.name || "").trim();
  if (!fileName.toLowerCase().endsWith(".csv")) {
    resetSelection();
    setCsvUploadStatus("Please choose a .csv file.", "error");
    return false;
  }
  csvUploadState.file = file;
  if (fileNameEl) fileNameEl.textContent = `Selected: ${fileName}`;
  setCsvUploadStatus("");
  return true;
}

function openCsvUploadModal(kind) {
  if (!els.csvUploadModal) return;
  const normalizedKind = kind === "solutions" ? "solutions" : "projects";
  csvUploadState.kind = normalizedKind;
  csvUploadState.file = null;
  if (els.csvUploadTitle) {
    els.csvUploadTitle.textContent = normalizedKind === "projects" ? "Upload Projects CSV" : "Upload Solutions CSV";
  }
  if (els.csvUploadDescription) {
    els.csvUploadDescription.textContent = normalizedKind === "projects"
      ? "Upload a Projects CSV. Use the template if you need the expected columns."
      : "Upload a Solutions CSV. Use the template if you need the expected columns.";
  }
  if (els.csvDropzone) {
    els.csvDropzone.classList.remove("drag-over");
  }
  if (els.csvUploadFile) {
    els.csvUploadFile.value = "";
  }
  if (els.csvUploadFileName) {
    els.csvUploadFileName.textContent = "No file selected";
  }
  setCsvUploadStatus("");
  els.csvUploadModal.classList.remove("hidden");
}

function closeCsvUploadModal() {
  if (!els.csvUploadModal) return;
  els.csvUploadModal.classList.add("hidden");
  csvUploadState.file = null;
  if (els.csvUploadFile) els.csvUploadFile.value = "";
  if (els.csvUploadFileName) els.csvUploadFileName.textContent = "No file selected";
  if (els.csvDropzone) els.csvDropzone.classList.remove("drag-over");
  setCsvUploadStatus("");
}

async function uploadCsvFile(kind, file, resultEl) {
  if (!file) {
    const msg = "Choose a CSV file first";
    setImportResult(resultEl, msg, true);
    return { ok: false, message: msg, partial: false };
  }
  try {
    const csvText = await file.text();
    const headers = { "Content-Type": "text/csv" };
    if (state.activeSpace?.space_id) {
      headers["X-Space-Id"] = state.activeSpace.space_id;
    }
    const res = await fetch(`${API_BASE}/${kind}/import`, {
      method: "POST",
      headers,
      body: csvText,
      credentials: "include",
    });
    if (res.status === 401) {
      handleAuthError({ status: 401 });
      const msg = "Sign in required";
      setImportResult(resultEl, msg, true);
      return { ok: false, message: msg, partial: false };
    }
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const errs = data.errors || [];
    const parts = [
      `Created ${data.created || 0}`,
      `Updated ${data.updated || 0}`,
    ];
    if (data.projects_created !== undefined) parts.push(`Projects created ${data.projects_created}`);
    if (data.solutions_created !== undefined) parts.push(`Solutions created ${data.solutions_created}`);
    const msg = parts.join(", ");
    const errorSnippet = errs.length ? ` Errors (${errs.length}): ${errs.slice(0, 3).join(" | ")}` : "";
    const detail = errs.length ? `${msg}.${errorSnippet}` : msg;
    setImportResult(
      resultEl,
      detail,
      errs.length > 0
    );
    if (errs.length) console.warn("Import errors:", errs);
    if (kind === "users") {
      await loadTeamCapacityData({ force: true });
    } else {
      await loadData();
    }
    return { ok: errs.length === 0, message: detail, partial: errs.length > 0 };
  } catch (err) {
    const msg = `Import failed: ${err.message}`;
    setImportResult(resultEl, msg, true);
    return { ok: false, message: msg, partial: false };
  }
}

async function uploadCsv(kind, fileInput, resultEl) {
  const file = fileInput?.files?.[0];
  try {
    return await uploadCsvFile(kind, file, resultEl);
  } finally {
    if (fileInput) fileInput.value = "";
  }
}

function bindCsvControls() {
  const csvMenuItems = () => Array.from(els.csvActionsMenu?.querySelectorAll("[role='menuitem']") || []);
  const openCsvMenu = () => {
    if (!els.csvActionsMenu || !els.csvActionsToggle) return;
    els.csvActionsMenu.classList.remove("hidden");
    els.csvActionsToggle.setAttribute("aria-expanded", "true");
    csvMenuItems()[0]?.focus();
  };
  const closeCsvMenu = () => {
    if (!els.csvActionsMenu || !els.csvActionsToggle) return;
    els.csvActionsMenu.classList.add("hidden");
    els.csvActionsToggle.setAttribute("aria-expanded", "false");
    els.csvActionsToggle.focus();
  };
  const toggleCsvMenu = () => {
    if (!els.csvActionsMenu || !els.csvActionsToggle) return;
    const isHidden = els.csvActionsMenu.classList.contains("hidden");
    if (isHidden) {
      openCsvMenu();
    } else {
      closeCsvMenu();
    }
  };

  if (els.csvActionsToggle && !els.csvActionsToggle._bound) {
    els.csvActionsToggle.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " " && event.key !== "ArrowDown") return;
      event.preventDefault();
      openCsvMenu();
    });
    els.csvActionsToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleCsvMenu();
    });
    els.csvActionsToggle._bound = true;
  }
  if (els.csvActionsMenu && !els.csvActionsMenu._bound) {
    els.csvActionsMenu.addEventListener("keydown", (event) => {
      const items = csvMenuItems();
      if (!items.length) return;

      const first = items[0];
      const last = items[items.length - 1];
      const activeIndex = items.indexOf(document.activeElement);

      if (event.key === "Escape") {
        event.preventDefault();
        closeCsvMenu();
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        items[(activeIndex + 1) % items.length]?.focus();
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        items[(activeIndex - 1 + items.length) % items.length]?.focus();
        return;
      }
      if (event.key === "Home") {
        event.preventDefault();
        first.focus();
        return;
      }
      if (event.key === "End") {
        event.preventDefault();
        last.focus();
        return;
      }
    });
    els.csvActionsMenu.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    els.csvActionsMenu._bound = true;
  }
  if (!document._csvMenuCloseBound) {
    document.addEventListener("click", (event) => {
      const menu = els.csvActionsMenu;
      const toggle = els.csvActionsToggle;
      if (!menu || !toggle) return;
      if (menu.classList.contains("hidden")) return;
      if (menu.contains(event.target) || toggle.contains(event.target)) return;
      closeCsvMenu();
    });
    document._csvMenuCloseBound = true;
  }

  if (els.projectsDownload && !els.projectsDownload._bound) {
    els.projectsDownload.addEventListener("click", () => {
      closeCsvMenu();
      downloadCsv("projects", "projects.csv", els.projectsImportResult);
    });
    els.projectsDownload._bound = true;
  }
  if (els.projectsUpload && !els.projectsUpload._bound) {
    els.projectsUpload.addEventListener("click", () => {
      closeCsvMenu();
      openCsvUploadModal("projects");
    });
    els.projectsUpload._bound = true;
  }

  if (els.solutionsDownload && !els.solutionsDownload._bound) {
    els.solutionsDownload.addEventListener("click", () => {
      closeCsvMenu();
      downloadCsv("solutions", "solutions.csv", els.solutionsImportResult);
    });
    els.solutionsDownload._bound = true;
  }
  if (els.solutionsUpload && !els.solutionsUpload._bound) {
    els.solutionsUpload.addEventListener("click", () => {
      closeCsvMenu();
      openCsvUploadModal("solutions");
    });
    els.solutionsUpload._bound = true;
  }

  if (els.csvUploadClose && !els.csvUploadClose._bound) {
    els.csvUploadClose.addEventListener("click", closeCsvUploadModal);
    els.csvUploadClose._bound = true;
  }
  if (els.csvUploadBackdrop && !els.csvUploadBackdrop._bound) {
    els.csvUploadBackdrop.addEventListener("click", closeCsvUploadModal);
    els.csvUploadBackdrop._bound = true;
  }
  if (els.csvDropzone && !els.csvDropzone._bound) {
    els.csvDropzone.addEventListener("click", () => els.csvUploadFile?.click());
    els.csvDropzone.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      els.csvUploadFile?.click();
    });
    const preventDropDefaults = (event) => {
      event.preventDefault();
      event.stopPropagation();
    };
    ["dragenter", "dragover"].forEach((eventName) => {
      els.csvDropzone.addEventListener(eventName, (event) => {
        preventDropDefaults(event);
        els.csvDropzone.classList.add("drag-over");
      });
    });
    ["dragleave", "drop"].forEach((eventName) => {
      els.csvDropzone.addEventListener(eventName, (event) => {
        preventDropDefaults(event);
        els.csvDropzone.classList.remove("drag-over");
      });
    });
    els.csvDropzone.addEventListener("drop", (event) => {
      const file = event.dataTransfer?.files?.[0] || null;
      setCsvUploadFile(file);
    });
    els.csvDropzone._bound = true;
  }
  if (els.csvUploadFile && !els.csvUploadFile._bound) {
    els.csvUploadFile.addEventListener("change", () => {
      const file = els.csvUploadFile?.files?.[0] || null;
      setCsvUploadFile(file);
    });
    els.csvUploadFile._bound = true;
  }
  if (els.csvDownloadTemplate && !els.csvDownloadTemplate._bound) {
    els.csvDownloadTemplate.addEventListener("click", () => {
      const kind = csvUploadState.kind || "projects";
      downloadCsvTemplate(kind, csvImportResultElement(kind));
      setCsvUploadStatus("Template downloaded.", "success");
    });
    els.csvDownloadTemplate._bound = true;
  }
  if (els.csvSubmitUpload && !els.csvSubmitUpload._bound) {
    els.csvSubmitUpload.addEventListener("click", async () => {
      const kind = csvUploadState.kind || "";
      if (!kind) return;
      const file = csvUploadState.file;
      const resultEl = csvImportResultElement(kind);
      const result = await uploadCsvFile(kind, file, resultEl);
      setCsvUploadStatus(result.message, result.ok ? "success" : "error");
      if (result.ok) {
        closeCsvUploadModal();
      }
    });
    els.csvSubmitUpload._bound = true;
  }
  if (els.csvUploadModal && !els.csvUploadModal._escapeBound) {
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (els.csvActionsMenu && !els.csvActionsMenu.classList.contains("hidden")) {
        closeCsvMenu();
        return;
      }
      if (els.csvUploadModal.classList.contains("hidden")) return;
      closeCsvUploadModal();
    });
    els.csvUploadModal._escapeBound = true;
  }
  if (els.rosterDownload) {
    els.rosterDownload.addEventListener("click", () =>
      downloadCsv("users", "roster.csv", els.rosterImportResult)
    );
  }
  if (els.rosterUpload && els.rosterFile) {
    els.rosterUpload.addEventListener("click", () => els.rosterFile?.click());
    els.rosterFile.addEventListener("change", () =>
      uploadCsv("users", els.rosterFile, els.rosterImportResult)
    );
  }
}

function bindSpaceSwitcher() {
  if (!els.spaceSwitcher) return;
  els.spaceSwitcher.addEventListener("change", async () => {
    const targetSpaceId = els.spaceSwitcher.value || "";
    const currentSpaceId = state.activeSpace?.space_id || "";
    if (!targetSpaceId || targetSpaceId === currentSpaceId || !state.authed) return;
    try {
      setStatus("Switching space...", "warn");
      const switched = await api("/auth/active-space", {
        method: "POST",
        body: JSON.stringify({ space_id: targetSpaceId }),
      });
      state.activeSpace = switched || state.activeSpace;
      state.spaceMembershipSpaceId = state.activeSpace?.space_id || state.spaceMembershipSpaceId;
      renderSpaceSwitcher();
      clearDataState();
      if (state.currentView === "team-capacity") {
        await loadTeamCapacityData({ force: true, preserveSelection: false });
      } else {
        await loadData({ force: true });
      }
      setStatus("Online", "positive");
    } catch (err) {
      console.warn("Space switch failed", err);
      alert(`Space switch failed: ${err.message || err}`);
      try {
        await refreshSpaceContext();
      } catch (refreshErr) {
        console.warn("Space context refresh failed", refreshErr);
      }
    }
  });
}

function bindNav() {
  els.navButtons.forEach((btn) =>
    btn.addEventListener("click", () => {
      setView(btn.dataset.view);
    })
  );
  window.addEventListener("hashchange", () => {
    if (suppressHashChange) return;
    setView(viewFromHash(), { fromHash: true });
  });
}

function bindCalendarControls() {
  if (els.calendarMonthInput) {
    els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth || new Date());
    els.calendarMonthInput.addEventListener("change", () => {
      const val = els.calendarMonthInput.value;
      if (!val) return;
      const [year, month] = val.split("-").map(Number);
      setCalendarMonth(new Date(year, (month || 1) - 1, 1));
    });
  }
  const shiftMonth = (delta) => {
    const base = state.calendarMonth || new Date();
    const next = new Date(base.getFullYear(), base.getMonth() + delta, 1);
    setCalendarMonth(next);
  };
  els.calendarPrev?.addEventListener("click", () => shiftMonth(-1));
  els.calendarNext?.addEventListener("click", () => shiftMonth(1));
  if (els.calendarGrid) {
    els.calendarGrid.addEventListener("click", (e) => {
      const cell = e.target.closest(".calendar-cell[data-day]");
      if (!cell) return;
      const day = Number(cell.getAttribute("data-day"));
      if (Number.isFinite(day)) openCalendarModal(day);
    });
  }
  els.calendarModalClose?.addEventListener("click", () => els.calendarModal?.classList.add("hidden"));
  els.calendarModal?.addEventListener("click", (e) => {
    if (e.target === els.calendarModal || e.target.classList.contains("modal-backdrop")) {
      els.calendarModal.classList.add("hidden");
    }
  });

  els.kanbanFilterProject?.addEventListener("change", () => {
    state.kanbanFilters.project = els.kanbanFilterProject.value || "";
    renderKanban();
  });
  bindDebouncedInput(els.kanbanFilterOwner, (value) => {
    state.kanbanFilters.owner = value;
    renderKanban();
  });
  els.calendarFilterProject?.addEventListener("change", () => {
    state.calendarFilters.project = els.calendarFilterProject.value || "";
    renderCalendar();
  });
  bindDebouncedInput(els.calendarFilterOwner, (value) => {
    state.calendarFilters.owner = value;
    renderCalendar();
  });

  if (els.planningWindowSelect) {
    els.planningWindowSelect.addEventListener("change", () => {
      const win = state.planningWindows.find((w) => w.window_id === els.planningWindowSelect.value);
      if (win) {
        if (els.planningFrom) els.planningFrom.value = win.start_date;
        if (els.planningTo) els.planningTo.value = win.end_date;
        const monthStartInput = els.allocationForm?.querySelector('[name="month_start"]');
        if (monthStartInput) monthStartInput.value = (normalizeMonthStart(win.start_date) || "").slice(0, 7);
      }
      updateAllocationWindowHint();
      renderPlanningWindowSummary();
      renderPlanningRoster();
      renderPlanning();
    });
  }

  if (els.editWindowBtn) {
    els.editWindowBtn.addEventListener("click", () => {
      const selectedId = els.planningWindowSelect?.value;
      const win = state.planningWindows.find((w) => w.window_id === selectedId);
      if (!els.planningWindowForm) return;
      if (win) {
        els.planningWindowForm.querySelector('[name="window_id_edit"]').value = win.window_id;
        els.planningWindowForm.querySelector('[name="window_name"]').value = win.name || "";
        els.planningWindowForm.querySelector('[name="window_start"]').value = win.start_date || "";
        els.planningWindowForm.querySelector('[name="window_end"]').value = win.end_date || "";
        if (els.saveWindowBtn) els.saveWindowBtn.textContent = "Save Window";
      } else {
        els.planningWindowForm.reset();
        if (els.saveWindowBtn) els.saveWindowBtn.textContent = "Create Window";
      }
      openPlanningDrawer("window");
    });
  }

  if (els.planningAddAllocation) {
    els.planningAddAllocation.addEventListener("click", () => {
      openPlanningDrawer("allocation");
      applyAllocationDefaults();
    });
  }

  if (els.planningCloseAllocation) {
    els.planningCloseAllocation.addEventListener("click", closePlanningDrawer);
  }

  if (els.planningCloseWindow) {
    els.planningCloseWindow.addEventListener("click", closePlanningDrawer);
  }

  bindDebouncedInput(els.planningSearch, () => renderPlanning());
  bindDebouncedInput(els.planningTeamTagFilter, () => renderPlanning());
  els.planningFilterOver?.addEventListener("change", renderPlanning);
  els.planningFilterUnder?.addEventListener("change", renderPlanning);

  if (els.planningBoard) {
    els.planningBoard.addEventListener("click", async (e) => {
      if (!(e.target instanceof Element)) return;
      if (e.target.closest(".wab-shell") || e.target.closest(".wab-toolbar") || e.target.closest(".wab-inline-forms")) {
        return;
      }
      const groupBtn = e.target.closest(".group-toggle");
      if (groupBtn) {
        const group = groupBtn.getAttribute("data-group") || "";
        if (group) {
          if (state.planningGroupCollapsed.has(group)) state.planningGroupCollapsed.delete(group);
          else state.planningGroupCollapsed.add(group);
          renderPlanning();
        }
        return;
      }
      const rowAdd = e.target.closest(".row-add");
      if (rowAdd) {
        const assigneeKey = rowAdd.getAttribute("data-assignee") || "";
        if (els.allocationForm) {
          const assigneeSel = els.allocationForm.querySelector('[name="assignee"]');
          const assigneeUser = els.allocationForm.querySelector('[name="assignee_user_soeid"]');
          if (assigneeSel) assigneeSel.value = assigneeKey;
          if (assigneeUser) assigneeUser.value = assigneeKey;
          applyAllocationDefaults();
          openPlanningDrawer("allocation");
        }
        return;
      }
      const btn = e.target.closest(".chip-delete");
      if (btn) {
        if (!userCanAccessAdminViews()) {
          return;
        }
        const allocId = btn.getAttribute("data-alloc-id");
        if (!allocId) return;
        const confirmDelete = confirm("Delete this allocation?");
        if (!confirmDelete) return;
        try {
          await api(`/resource-allocations/${allocId}`, { method: "DELETE" });
          state.allocations = state.allocations.filter((a) => a.allocation_id !== allocId);
          renderPlanning();
        } catch (err) {
          alert(`Delete failed: ${err.message}`);
        }
        return;
      }
      const chip = e.target.closest(".alloc-chip");
      if (chip) {
        const allocId = chip.getAttribute("data-alloc-id");
        const alloc = state.allocations.find((a) => a.allocation_id === allocId);
        if (!alloc) return;
        const item = allocationLabel(alloc);
        const teamName = alloc.team_id ? state.teams.find((t) => t.team_id === alloc.team_id)?.name : "";
        const win = alloc.window_id ? state.planningWindows.find((w) => w.window_id === alloc.window_id) : null;
        const fteMonths = allocationFteMonths(alloc);
        const monthStart = allocationMonthStart(alloc);
        const details = `
          <div class="modal-item">
            <div class="modal-item-title">${item || alloc.work_item_id}</div>
            <div class="modal-item-meta">
              ${alloc.work_item_type || ""} • ${formatFte(fteMonths)} FTE-mo • ${monthStart || "—"}
            </div>
            <div class="modal-item-meta">Assignee: ${assigneeLabelFromKey(assigneeKeyFromAlloc(alloc)) || "—"}</div>
            <div class="modal-item-meta">Team: ${teamName || "Unassigned"}</div>
            ${win ? `<div class="modal-item-meta">Window: ${win.name} (${win.start_date} → ${win.end_date})</div>` : ""}
          </div>
        `;
        if (els.planningModalTitle) els.planningModalTitle.textContent = "Allocation Details";
        if (els.planningModalBody) els.planningModalBody.innerHTML = details;
        els.planningModal?.classList.remove("hidden");
      }
    });
  }
  if (els.planningModal) {
    els.planningModal.addEventListener("click", (e) => {
      if (e.target === els.planningModal || e.target.classList.contains("modal-backdrop")) {
        els.planningModal.classList.add("hidden");
      }
    });
  }
  els.planningModalClose?.addEventListener("click", () => els.planningModal?.classList.add("hidden"));

  if (els.planningWindowForm) {
    els.planningWindowForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.planningWindowForm);
      const editId = data.get("window_id_edit");
      const name = data.get("window_name");
      const start = data.get("window_start");
      const end = data.get("window_end");
      if (!name || !start || !end) {
        alert("Name, start, and end are required to create a planning window.");
        return;
      }
      try {
        let savedWin;
        if (editId) {
          savedWin = await api(`/planning/windows/${editId}`, {
            method: "PATCH",
            body: JSON.stringify({ name, start_date: start, end_date: end }),
          });
          const idx = state.planningWindows.findIndex((w) => w.window_id === savedWin.window_id);
          if (idx === -1) state.planningWindows.push(savedWin);
          else state.planningWindows[idx] = savedWin;
        } else {
          savedWin = await api("/planning/windows", {
            method: "POST",
            body: JSON.stringify({ name, start_date: start, end_date: end }),
          });
          state.planningWindows.push(savedWin);
        }
        populateSelects();
        if (els.planningWindowSelect) {
          els.planningWindowSelect.value = savedWin.window_id;
        }
        if (els.planningFrom) els.planningFrom.value = savedWin.start_date;
        if (els.planningTo) els.planningTo.value = savedWin.end_date;
        const monthStartInput = els.allocationForm?.querySelector('[name="month_start"]');
        if (monthStartInput) monthStartInput.value = (normalizeMonthStart(savedWin.start_date) || "").slice(0, 7);
        updateAllocationWindowHint();
        renderPlanningWindowSummary();
        renderPlanningRoster();
        renderPlanning();
        els.planningWindowForm.reset();
        els.planningWindowForm.querySelector('[name="window_id_edit"]').value = "";
        if (els.saveWindowBtn) els.saveWindowBtn.textContent = "Create Window";
        closePlanningDrawer();
      } catch (err) {
        alert(`Window create failed: ${err.message}`);
      }
    });

    els.planningWindowForm.addEventListener("reset", () => {
      if (els.saveWindowBtn) els.saveWindowBtn.textContent = "Create Window";
      els.planningWindowForm.querySelector('[name="window_id_edit"]').value = "";
    });
  }

  if (els.allocationForm) {
    const typeSel = els.allocationForm.querySelector('[name="work_item_type"]');
    const itemSel = els.allocationForm.querySelector('[name="work_item_id"]');
    els.allocationForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.allocationForm);
      const windowId = els.planningWindowSelect?.value || "";
      const selectedWindow = windowId ? state.planningWindows.find((w) => w.window_id === windowId) : null;
      const providedMonthStart = monthInputToDate(data.get("month_start"));
      const resolvedMonthStart =
        providedMonthStart || normalizeMonthStart(selectedWindow?.start_date) || normalizeMonthStart(els.planningFrom?.value) || null;
      const assigneeUserId = data.get("assignee") || "";
      const assigneeUser = findUserBySoeid(assigneeUserId);
      const fteMonths = numberOr(data.get("fte_months"), 0);
      const payload = {
        work_item_type: data.get("work_item_type"),
        work_item_id: data.get("work_item_id"),
        assignee: assigneeUser?.display_name || "",
        assignee_user_soeid: assigneeUserId || null,
        team_id: deriveTeamForItem(data.get("work_item_type"), data.get("work_item_id")),
        month_start: resolvedMonthStart,
        fte_months: fteMonths,
        week_start: resolvedMonthStart,
        hours: Math.round(fteMonths * HOURS_PER_FTE_MONTH),
        window_id: windowId || null,
      };
      if (!payload.window_id) {
        if (els.allocationStatus) els.allocationStatus.textContent = "Select or create a planning window first.";
        return;
      }
      if (!payload.work_item_type || !payload.work_item_id || !payload.assignee || !payload.month_start || !payload.fte_months) {
        if (els.allocationStatus) els.allocationStatus.textContent = "Type, item, assignee, month, and FTE-months are required.";
        return;
      }
      try {
        const created = await api("/resource-allocations", { method: "POST", body: JSON.stringify(payload) });
        state.allocations.push(created);
        if (els.allocationStatus) els.allocationStatus.textContent = "Saved.";
        applyAllocationDefaults();
        renderPlanningWindowSummary();
        renderPlanningRoster();
        renderPlanning();
      } catch (err) {
        alert(`Save failed: ${err.message || err}`);
      }
    });

    els.allocationForm.addEventListener("reset", () => {
      if (els.allocationStatus) els.allocationStatus.textContent = "";
      applyAllocationDefaults();
    });
  }
}

function normalizeCapacityLookup(value) {
  return String(value || "").trim().toLowerCase();
}

function findCapacityUserBySoeid(soeid) {
  const norm = normalizeCapacityLookup(soeid);
  if (!norm) return null;
  return state.users.find((u) => normalizeCapacityLookup(u.soeid) === norm) || null;
}

function findCapacityUserByValue(value) {
  const norm = normalizeCapacityLookup(value);
  if (!norm) return null;
  return (
    findCapacityUserBySoeid(norm) ||
    state.users.find((u) => normalizeCapacityLookup(u.display_name) === norm) ||
    null
  );
}

function selectCapacityUser(user, options = {}) {
  const form = els.capacityUserForm;
  if (!form) return;
  const preserveName = !!options.preserveName;
  const shouldRender = options.render !== false;
  const next = user || null;
  state.capacitySelectedSoeid = next?.soeid || "";
  form.querySelector('[name="soeid"]').value = next?.soeid || "";
  if (!preserveName) {
    form.querySelector('[name="display_name"]').value = next?.display_name || "";
  }
  form.querySelector('[name="team_tag"]').value = next?.team_tag || "";
  form.querySelector('[name="capacity_fte_month"]').value = formatFte(next ? userCapacityFteMonth(next) : 1);
  if (shouldRender && state.currentView === "team-capacity") {
    renderTeamCapacity();
  }
}

function clearCapacityUserForm(options = {}) {
  if (!els.capacityUserForm) return;
  const shouldRender = options.render !== false;
  els.capacityUserForm.reset();
  state.capacitySelectedSoeid = "";
  els.capacityUserForm.querySelector('[name="soeid"]').value = "";
  const fteField = els.capacityUserForm.querySelector('[name="capacity_fte_month"]');
  if (fteField) fteField.value = "1.00";
  if (shouldRender && state.currentView === "team-capacity") {
    renderTeamCapacity();
  }
}

async function loadTeamCapacityData(options = {}) {
  if (!state.authed) return;
  const force = !!options.force;
  const preserveSelection = options.preserveSelection !== false;
  if (!force && state.teamCapacity.loading) return;
  const requestedSpaceId = state.activeSpace?.space_id || "";
  const requestedSpaceName = state.activeSpace?.space_name || "";
  if (!requestedSpaceId) {
    state.teamCapacity.error = "No active space selected.";
    state.teamCapacity.lastLoadedAt = "";
    applyEntityData("users", []);
    applyEntityData("allocations", []);
    if (state.currentView === "team-capacity") renderTeamCapacity();
    return;
  }

  const requestId = (state.teamCapacity.requestId || 0) + 1;
  state.teamCapacity.requestId = requestId;
  state.teamCapacity.loading = true;
  state.teamCapacity.error = "";
  if (state.currentView === "team-capacity") renderTeamCapacity();

  try {
    const spaceHeaders = { "X-Space-Id": requestedSpaceId };
    const [usersResult, allocationsResult] = await Promise.allSettled([
      api("/users?active_only=true", { timeoutMs: 45000, headers: spaceHeaders }),
      api("/resource-allocations", { timeoutMs: 45000, headers: spaceHeaders }),
    ]);
    if (state.teamCapacity.requestId !== requestId) return;
    if ((state.activeSpace?.space_id || "") !== requestedSpaceId) return;

    const loadErrors = [];
    if (usersResult.status === "fulfilled") {
      applyEntityData("users", usersResult.value);
    } else {
      if (handleAuthError(usersResult.reason)) return;
      loadErrors.push(`roster: ${usersResult.reason?.message || "failed"}`);
    }
    if (allocationsResult.status === "fulfilled") {
      applyEntityData("allocations", allocationsResult.value);
    } else {
      if (handleAuthError(allocationsResult.reason)) return;
      loadErrors.push(`allocations: ${allocationsResult.reason?.message || "failed"}`);
      // Keep table usable even if allocation fetch fails.
      applyEntityData("allocations", []);
    }

    if (loadErrors.length) {
      state.teamCapacity.error = `Partial load: ${loadErrors.join(" | ")}`;
    }
    state.teamCapacity.lastLoadedAt = new Date().toISOString();
    state.teamCapacity.lastLoadedSpaceId = requestedSpaceId;
    state.teamCapacity.lastLoadedSpaceName = requestedSpaceName;
    populateSelects();
    if (preserveSelection && state.capacitySelectedSoeid) {
      const selected = findCapacityUserBySoeid(state.capacitySelectedSoeid);
      if (selected) selectCapacityUser(selected, { render: false });
      else clearCapacityUserForm({ render: false });
    }
  } catch (err) {
    if (state.teamCapacity.requestId !== requestId) return;
    if (handleAuthError(err)) return;
    state.teamCapacity.error = err?.message || "Failed to load team capacity data.";
  } finally {
    if (state.teamCapacity.requestId === requestId) {
      state.teamCapacity.loading = false;
      if (state.currentView === "team-capacity") renderTeamCapacity();
    }
  }
}

function bindCapacityUsers() {
  if (els.capacityUserForm) {
    const nameInput = els.capacityUserForm.querySelector('[name="display_name"]');
    if (nameInput) {
      nameInput.addEventListener("input", () => {
        const match = findCapacityUserByValue(nameInput.value || "");
        els.capacityUserForm.querySelector('[name="soeid"]').value = match?.soeid || "";
        if (match) {
          state.capacitySelectedSoeid = match.soeid || "";
          els.capacityUserForm.querySelector('[name="team_tag"]').value = match.team_tag || "";
          els.capacityUserForm.querySelector('[name="capacity_fte_month"]').value = formatFte(userCapacityFteMonth(match));
          if (state.currentView === "team-capacity") renderTeamCapacity();
        } else if (state.capacitySelectedSoeid) {
          state.capacitySelectedSoeid = "";
          renderTeamCapacity();
        }
      });
      nameInput.addEventListener("blur", () => {
        const match = findCapacityUserByValue(nameInput.value || "");
        if (match) {
          selectCapacityUser(match);
        }
      });
    }
    els.capacityUserForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.capacityUserForm);
      const soeid = normalizeCapacityLookup(data.get("soeid")) || normalizeCapacityLookup(findCapacityUserByValue(data.get("display_name"))?.soeid);
      if (!soeid) {
        alert("Select a member from the roster (or type an exact SOEID/name match) first.");
        return;
      }
      const payload = {
        team_tag: data.get("team_tag") || null,
        capacity_fte_month: numberOr(data.get("capacity_fte_month"), 0),
      };
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify(payload) });
        await loadTeamCapacityData({ force: true, preserveSelection: false });
        const refreshed = findCapacityUserBySoeid(soeid);
        if (refreshed) selectCapacityUser(refreshed);
        else clearCapacityUserForm();
      } catch (err) {
        alert(`Save failed: ${err.message}`);
      }
    });
    els.capacityUserForm.addEventListener("reset", () => {
      clearCapacityUserForm();
    });
  }
  if (els.capacityUserDelete) {
    els.capacityUserDelete.addEventListener("click", async () => {
      const soeid = els.capacityUserForm?.querySelector('[name="soeid"]')?.value;
      if (!soeid) {
        alert("Select a member first.");
        return;
      }
      if (!confirm("Deactivate this member? They will be hidden from the roster.")) return;
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify({ is_active: false }) });
        clearCapacityUserForm({ render: false });
        await loadTeamCapacityData({ force: true, preserveSelection: false });
      } catch (err) {
        alert(`Delete failed: ${err.message}`);
      }
    });
  }
  if (els.capacityUserList) {
    els.capacityUserList.addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-soeid]");
      if (!row) return;
      const soeid = row.getAttribute("data-soeid");
      const user = state.users.find((u) => u.soeid === soeid);
      if (!user) return;
      selectCapacityUser(user);
    });
  }
  bindDebouncedInput(els.capacityTeamFilter, () => renderTeamCapacity());
  bindDebouncedInput(els.capacityNameFilter, () => renderTeamCapacity());
  if (els.capacityReload) {
    els.capacityReload.addEventListener("click", async () => {
      await loadTeamCapacityData({ force: true });
    });
  }
  if (els.capacityClearFilters) {
    els.capacityClearFilters.addEventListener("click", () => {
      if (els.capacityTeamFilter) els.capacityTeamFilter.value = "";
      if (els.capacityNameFilter) els.capacityNameFilter.value = "";
      renderTeamCapacity();
    });
  }
}

function userIsGlobalAdmin() {
  return !!state.activeSpace?.is_global_admin;
}

function activeSpaceId() {
  return state.activeSpace?.space_id || "";
}

function renderSpaceAdminPanel() {
  if (!els.spaceList) return;
  const isGlobalAdmin = userIsGlobalAdmin();
  if (els.spaceAdminNote) {
    els.spaceAdminNote.textContent = isGlobalAdmin ? "Global admin controls enabled" : "Read-only: only global admins can create/archive spaces";
  }
  if (els.spaceCreateForm) {
    els.spaceCreateForm.classList.toggle("hidden", !isGlobalAdmin);
    const controls = Array.from(els.spaceCreateForm.querySelectorAll("input, button"));
    controls.forEach((control) => {
      control.disabled = !isGlobalAdmin;
    });
  }
  const currentSpaceId = activeSpaceId();
  const rows = (state.spaces || [])
    .map((space) => {
      const isCurrent = space.space_id === currentSpaceId;
      const statusLabel = space.is_active ? "active" : "archived";
      return `<tr data-space-id="${space.space_id}">
        <td>${space.name || space.space_id}</td>
        <td>${space.slug || "—"}</td>
        <td>${statusLabel}</td>
        <td>${isCurrent ? "<span class='pill'>current</span>" : ""}</td>
        <td>
          <button type="button" class="secondary" data-action="switch-space" data-space-id="${space.space_id}">Switch</button>
          ${isGlobalAdmin ? `<button type="button" class="secondary" data-action="toggle-space-active" data-space-id="${space.space_id}" data-next-active="${space.is_active ? "false" : "true"}">${space.is_active ? "Archive" : "Reactivate"}</button>` : ""}
        </td>
      </tr>`;
    })
    .join("");
  els.spaceList.innerHTML = `<h3>Available Spaces</h3><div class="table"><table><thead><tr><th>Name</th><th>Slug</th><th>Status</th><th>Active</th><th>Actions</th></tr></thead><tbody>${rows || "<tr><td colspan='5' class='muted'>No spaces available</td></tr>"}</tbody></table></div>`;
}

function canManageSpaceMembership(spaceId) {
  if (!spaceId) return false;
  if (userIsGlobalAdmin()) return true;
  return isSpaceAdminRole(state.activeSpace?.space_role) && activeSpaceId() === spaceId;
}

function memberLabel(member) {
  const row = member || {};
  const userId = row.user_id || "";
  const soeid = row.user_soeid || "";
  const displayName = row.user_display_name || "";
  const email = row.user_email || "";
  if (displayName && soeid) return `${displayName} (${soeid})`;
  if (displayName) return displayName;
  if (soeid) return soeid;
  if (email) return email;
  const user = state.users.find((item) => item.user_id === userId);
  if (!user) return userId;
  const title = user.display_name || user.soeid || user.user_id;
  if (user.soeid) return `${title} (${user.soeid})`;
  return title;
}

function renderSpaceMembershipPanel() {
  if (!els.spaceMembershipList || !els.spaceMembershipSpaceSelect) return;
  const spaces = state.spaces || [];
  if (!state.spaceMembershipSpaceId || !spaces.some((s) => s.space_id === state.spaceMembershipSpaceId)) {
    state.spaceMembershipSpaceId = state.activeSpace?.space_id || spaces[0]?.space_id || "";
  }
  const selectedSpaceId = state.spaceMembershipSpaceId || "";
  const canManage = canManageSpaceMembership(selectedSpaceId);

  els.spaceMembershipSpaceSelect.innerHTML = spaces
    .map((space) => `<option value="${space.space_id}">${space.name || space.space_id}</option>`)
    .join("");
  if (selectedSpaceId) els.spaceMembershipSpaceSelect.value = selectedSpaceId;
  els.spaceMembershipSpaceSelect.disabled = !spaces.length;

  if (els.spaceMembershipNote) {
    if (!selectedSpaceId) {
      els.spaceMembershipNote.textContent = "No available space selected";
    } else if (canManage) {
      els.spaceMembershipNote.textContent = "Membership management enabled";
    } else {
      els.spaceMembershipNote.textContent = "Read-only: you can manage memberships only as global_admin or space_admin for the selected active space";
    }
  }

  if (els.spaceMembershipForm) {
    const controls = Array.from(els.spaceMembershipForm.querySelectorAll("input[name='soeid'], select[name='role'], select[name='status'], button"));
    controls.forEach((control) => {
      control.disabled = !canManage || !selectedSpaceId;
    });
  }

  if (!selectedSpaceId) {
    els.spaceMembershipList.innerHTML = "<p class='muted'>Select a space to view memberships.</p>";
    return;
  }
  if (!state.spaceMembersLoadedBySpace[selectedSpaceId]) {
    els.spaceMembershipList.innerHTML = "<p class='muted'>Loading memberships...</p>";
    refreshSpaceMembers(selectedSpaceId).catch((err) => {
      console.warn("Failed to load space memberships", err);
      els.spaceMembershipList.innerHTML = `<p class='muted'>Failed to load memberships: ${err.message || err}</p>`;
    });
    return;
  }
  const members = state.spaceMembersBySpace[selectedSpaceId] || [];
  const rows = members
    .map((row) => {
      const nextRole = row.role === "space_admin" ? "member" : "space_admin";
      const nextStatus = row.status === "active" ? "inactive" : "active";
      const roleActionLabel = nextRole === "space_admin" ? "Promote" : "Demote";
      const statusActionLabel = nextStatus === "active" ? "Activate" : "Deactivate";
      const actions = canManage
        ? `<button type="button" class="secondary" data-action="toggle-space-member-role" data-membership-id="${row.membership_id}" data-next-role="${nextRole}">${roleActionLabel}</button>
          <button type="button" class="secondary" data-action="toggle-space-member-status" data-membership-id="${row.membership_id}" data-next-status="${nextStatus}">${statusActionLabel}</button>
          <button type="button" class="secondary" data-action="delete-space-member" data-membership-id="${row.membership_id}">Remove</button>`
        : "<span class='muted'>Read-only</span>";
      return `<tr data-membership-id="${row.membership_id}">
        <td>${memberLabel(row)}</td>
        <td>${row.role}</td>
        <td>${row.status}</td>
        <td>
          ${actions}
        </td>
      </tr>`;
    })
    .join("");
  els.spaceMembershipList.innerHTML = `<h3>Memberships</h3><div class="table"><table><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows || "<tr><td colspan='4' class='muted'>No memberships</td></tr>"}</tbody></table></div>`;
}

function renderGlobalAdminPanel() {
  if (!els.globalAdminList) return;
  const isGlobalAdmin = userIsGlobalAdmin();
  if (els.globalAdminNote) {
    els.globalAdminNote.textContent = isGlobalAdmin ? "Manage platform-level admins" : "Read-only: only global admins can grant/revoke global admin";
  }
  if (els.globalAdminForm) {
    const controls = Array.from(els.globalAdminForm.querySelectorAll("input, button"));
    controls.forEach((control) => {
      control.disabled = !isGlobalAdmin;
    });
  }
  if (!isGlobalAdmin) {
    els.globalAdminList.innerHTML = "<p class='muted'>You do not have access to global admin management.</p>";
    return;
  }
  if (!state.globalAdminsLoaded) {
    els.globalAdminList.innerHTML = "<p class='muted'>Loading global admins...</p>";
    refreshGlobalAdmins().catch((err) => {
      console.warn("Failed to load global admins", err);
      els.globalAdminList.innerHTML = `<p class='muted'>Failed to load global admins: ${err.message || err}</p>`;
    });
    return;
  }
  const rows = (state.globalAdmins || [])
    .map((user) => {
      const statusText = user.is_active ? "active" : "inactive";
      return `<tr data-user-id="${user.user_id}" data-soeid="${user.soeid}">
        <td>${user.display_name || user.soeid || user.user_id}</td>
        <td>${user.soeid || "—"}</td>
        <td>${statusText}</td>
        <td><button type="button" class="secondary" data-action="revoke-global-admin" data-soeid="${user.soeid}">Revoke</button></td>
      </tr>`;
    })
    .join("");
  els.globalAdminList.innerHTML = `<h3>Current Global Admins</h3><div class="table"><table><thead><tr><th>Name</th><th>SOEID</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows || "<tr><td colspan='4' class='muted'>No global admins found</td></tr>"}</tbody></table></div>`;
}

async function refreshGlobalAdmins() {
  if (!userIsGlobalAdmin()) {
    state.globalAdmins = [];
    state.globalAdminsLoaded = false;
    return;
  }
  if (refreshGlobalAdmins._inFlight) return refreshGlobalAdmins._inFlight;
  refreshGlobalAdmins._inFlight = api("/users/global-admins?active_only=false")
    .then((rows) => {
      state.globalAdmins = Array.isArray(rows) ? rows : [];
      state.globalAdminsLoaded = true;
      renderGlobalAdminPanel();
      return state.globalAdmins;
    })
    .finally(() => {
      refreshGlobalAdmins._inFlight = null;
    });
  return refreshGlobalAdmins._inFlight;
}

async function refreshSpaceMembers(spaceId, options = {}) {
  const targetSpaceId = (spaceId || "").toString().trim();
  if (!targetSpaceId) return [];
  const force = !!options.force;
  if (!force && state.spaceMembersLoadedBySpace[targetSpaceId]) {
    return state.spaceMembersBySpace[targetSpaceId] || [];
  }
  refreshSpaceMembers._inFlight = refreshSpaceMembers._inFlight || {};
  if (refreshSpaceMembers._inFlight[targetSpaceId]) {
    return refreshSpaceMembers._inFlight[targetSpaceId];
  }
  refreshSpaceMembers._inFlight[targetSpaceId] = api(`/spaces/${encodeURIComponent(targetSpaceId)}/members`)
    .then((rows) => {
      state.spaceMembersBySpace[targetSpaceId] = Array.isArray(rows) ? rows : [];
      state.spaceMembersLoadedBySpace[targetSpaceId] = true;
      if (state.currentView === "spaces" && state.spaceMembershipSpaceId === targetSpaceId) {
        renderSpaceMembershipPanel();
      }
      return state.spaceMembersBySpace[targetSpaceId];
    })
    .finally(() => {
      delete refreshSpaceMembers._inFlight[targetSpaceId];
    });
  return refreshSpaceMembers._inFlight[targetSpaceId];
}

function bindSpaceAdminControls() {
  if (els.spaceCreateForm) {
    els.spaceCreateForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!userIsGlobalAdmin()) return;
      const data = new FormData(els.spaceCreateForm);
      const name = (data.get("name") || "").toString().trim();
      const slug = (data.get("slug") || "").toString().trim();
      if (!name) {
        alert("Space name is required.");
        return;
      }
      try {
        await api("/spaces", {
          method: "POST",
          body: JSON.stringify({ name, slug: slug || null }),
        });
        await refreshSpaceContext();
        renderSpaceAdminPanel();
        els.spaceCreateForm.reset();
      } catch (err) {
        alert(`Space create failed: ${err.message || err}`);
      }
    });
  }

  if (els.spaceList) {
    els.spaceList.addEventListener("click", async (e) => {
      const button = e.target.closest("button[data-action]");
      if (!button) return;
      const action = button.getAttribute("data-action");
      const spaceId = button.getAttribute("data-space-id") || "";
      if (!spaceId) return;
      if (action === "switch-space") {
        if (!state.authed || spaceId === activeSpaceId()) return;
        try {
          const switched = await api("/auth/active-space", {
            method: "POST",
            body: JSON.stringify({ space_id: spaceId }),
          });
          state.activeSpace = switched || state.activeSpace;
          state.spaceMembershipSpaceId = state.activeSpace?.space_id || state.spaceMembershipSpaceId;
          renderSpaceSwitcher();
          clearDataState();
          await loadData({ force: true });
          renderSpaceAdminPanel();
          renderSpaceMembershipPanel();
        } catch (err) {
          alert(`Space switch failed: ${err.message || err}`);
        }
        return;
      }
      if (action === "toggle-space-active" && userIsGlobalAdmin()) {
        const nextActive = (button.getAttribute("data-next-active") || "").toLowerCase() === "true";
        try {
          await api(`/spaces/${encodeURIComponent(spaceId)}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: nextActive }),
          });
          await refreshSpaceContext();
          renderSpaceAdminPanel();
          renderSpaceMembershipPanel();
        } catch (err) {
          alert(`Space update failed: ${err.message || err}`);
        }
      }
    });
  }

  if (els.globalAdminForm) {
    els.globalAdminForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!userIsGlobalAdmin()) return;
      const data = new FormData(els.globalAdminForm);
      const soeid = (data.get("soeid") || "").toString().trim().toLowerCase();
      if (!soeid) {
        alert("SOEID is required.");
        return;
      }
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "POST" });
        state.globalAdminsLoaded = false;
        await refreshGlobalAdmins();
        await refreshFromServer("users");
      } catch (err) {
        alert(`Grant failed: ${err.message || err}`);
      }
    });
  }

  if (els.globalAdminRevoke) {
    els.globalAdminRevoke.addEventListener("click", async () => {
      if (!userIsGlobalAdmin()) return;
      const soeid = (els.globalAdminForm?.querySelector('[name="soeid"]')?.value || "").toString().trim().toLowerCase();
      if (!soeid) {
        alert("Enter an SOEID to revoke.");
        return;
      }
      if (!confirm(`Revoke global admin from ${soeid}?`)) return;
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "DELETE" });
        state.globalAdminsLoaded = false;
        await refreshGlobalAdmins();
        await refreshFromServer("users");
      } catch (err) {
        alert(`Revoke failed: ${err.message || err}`);
      }
    });
  }

  if (els.globalAdminList) {
    els.globalAdminList.addEventListener("click", async (e) => {
      const button = e.target.closest('button[data-action="revoke-global-admin"]');
      if (!button || !userIsGlobalAdmin()) return;
      const soeid = (button.getAttribute("data-soeid") || "").trim().toLowerCase();
      if (!soeid) return;
      if (!confirm(`Revoke global admin from ${soeid}?`)) return;
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "DELETE" });
        state.globalAdminsLoaded = false;
        await refreshGlobalAdmins();
        await refreshFromServer("users");
      } catch (err) {
        alert(`Revoke failed: ${err.message || err}`);
      }
    });
  }

  if (els.spaceMembershipSpaceSelect) {
    els.spaceMembershipSpaceSelect.addEventListener("change", () => {
      state.spaceMembershipSpaceId = els.spaceMembershipSpaceSelect.value || "";
      renderSpaceMembershipPanel();
    });
  }

  if (els.spaceMembershipForm) {
    els.spaceMembershipForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const spaceId = state.spaceMembershipSpaceId || "";
      if (!spaceId) {
        alert("Select a space first.");
        return;
      }
      if (!canManageSpaceMembership(spaceId)) {
        alert("You do not have permission to manage memberships for this space.");
        return;
      }
      const data = new FormData(els.spaceMembershipForm);
      const soeid = (data.get("soeid") || "").toString().trim().toLowerCase();
      const role = (data.get("role") || "member").toString();
      const status = (data.get("status") || "active").toString();
      if (!soeid) {
        alert("SOEID is required.");
        return;
      }
      try {
        await api(`/spaces/${encodeURIComponent(spaceId)}/members/by-soeid`, {
          method: "POST",
          body: JSON.stringify({ soeid, role, status }),
        });
        state.spaceMembersLoadedBySpace[spaceId] = false;
        await refreshSpaceMembers(spaceId, { force: true });
        const soeidInput = els.spaceMembershipForm.querySelector('[name="soeid"]');
        if (soeidInput) soeidInput.value = "";
      } catch (err) {
        alert(`Add member failed: ${err.message || err}`);
      }
    });
  }

  if (els.spaceMembershipList) {
    els.spaceMembershipList.addEventListener("click", async (e) => {
      const button = e.target.closest("button[data-action]");
      if (!button) return;
      const action = button.getAttribute("data-action");
      if (!action) return;
      const membershipId = (button.getAttribute("data-membership-id") || "").trim();
      const spaceId = state.spaceMembershipSpaceId || "";
      if (!membershipId || !spaceId) return;
      if (!canManageSpaceMembership(spaceId)) {
        alert("You do not have permission to manage memberships for this space.");
        return;
      }
      try {
        if (action === "toggle-space-member-role") {
          const nextRole = (button.getAttribute("data-next-role") || "").trim();
          if (!nextRole) return;
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
            method: "PATCH",
            body: JSON.stringify({ role: nextRole }),
          });
        } else if (action === "toggle-space-member-status") {
          const nextStatus = (button.getAttribute("data-next-status") || "").trim();
          if (!nextStatus) return;
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
            method: "PATCH",
            body: JSON.stringify({ status: nextStatus }),
          });
        } else if (action === "delete-space-member") {
          if (!confirm("Remove this member from the space?")) return;
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
            method: "DELETE",
          });
        } else {
          return;
        }
        state.spaceMembersLoadedBySpace[spaceId] = false;
        await refreshSpaceMembers(spaceId, { force: true });
      } catch (err) {
        alert(`Membership update failed: ${err.message || err}`);
      }
    });
  }
}

function renderPlanning() {
  const mod = getRouteModule("planning");
  if (!mod || typeof mod.renderPlanning !== "function") {
    if (state.currentView === "planning" && els.planningBoard) {
      els.planningBoard.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("planning").then((loaded) => {
      if (loaded && state.currentView === "planning") renderPlanning();
    });
    return;
  }
  mod.renderPlanning({
    state,
    els,
    api,
    refreshFromServer,
    setStatus,
    canDeleteAllocations: userCanAccessAdminViews(),
    assigneeKeyFromAlloc,
    findUserBySoeid,
    assigneeLabelFromKey,
    allocationLabel,
    allocationMonthStart,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
    renderPlanningWindowSummary,
    renderPlanningRoster,
  });
}

function renderTeamCapacity() {
  const mod = getRouteModule("team-capacity");
  if (!mod || typeof mod.renderTeamCapacity !== "function") {
    ensureRouteModule("team-capacity").then((loaded) => {
      if (loaded && state.currentView === "team-capacity") renderTeamCapacity();
    });
    return;
  }
  mod.renderTeamCapacity({
    state,
    els,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
    teamCapacityState: state.teamCapacity,
    selectedSoeid: state.capacitySelectedSoeid,
  });
}

function renderSpaces() {
  const mod = getRouteModule("spaces");
  if (!mod || typeof mod.renderSpaces !== "function") {
    ensureRouteModule("spaces").then((loaded) => {
      if (loaded && state.currentView === "spaces") renderSpaces();
    });
    return;
  }
  mod.renderSpaces({
    renderSpaceAdminPanel,
    renderSpaceMembershipPanel,
  });
}

function renderAccess() {
  const mod = getRouteModule("access");
  if (!mod || typeof mod.renderAccess !== "function") {
    ensureRouteModule("access").then((loaded) => {
      if (loaded && state.currentView === "access") renderAccess();
    });
    return;
  }
  mod.renderAccess({
    renderGlobalAdminPanel,
  });
}

function getSelectedWindow() {
  const id = els.planningWindowSelect?.value || "";
  return id ? state.planningWindows.find((w) => w.window_id === id) : null;
}

function renderPlanningWindowSummary() {
  if (!els.planningWindowSummary) return;
  const win = getSelectedWindow();
  if (!win) {
    els.planningWindowSummary.textContent = "Select or create a planning window.";
    return;
  }
  const allocs = state.allocations.filter((a) => a.window_id === win.window_id);
  const totalFte = allocs.reduce((sum, a) => sum + allocationFteMonths(a), 0);
  const totalCapacity = state.users.reduce((sum, u) => sum + userCapacityFteMonth(u), 0);
  const gap = totalCapacity - totalFte;
  els.planningWindowSummary.innerHTML =
    `<strong>${win.name}</strong> • ${win.start_date} → ${win.end_date} • ${allocs.length} allocations • ` +
    `${formatFte(totalFte)} FTE-mo allocated • ${gap >= 0 ? formatFte(gap) : `-${formatFte(Math.abs(gap))}`} FTE-mo ${gap >= 0 ? "remaining" : "over"}`;
}

function allocationFteDefault(type, itemId) {
  if (type === "solution") {
    const sol = state.solutions.find((s) => s.solution_id === itemId);
    if (sol) {
      if (Number.isFinite(Number(sol.capacity_fte_months))) return Number(sol.capacity_fte_months);
      if (Number.isFinite(Number(sol.capacity_hours))) return Number(sol.capacity_hours) / HOURS_PER_FTE_MONTH;
    }
  }
  if (type === "subcomponent") {
    const sc = state.subcomponents.find((s) => s.subcomponent_id === itemId);
    if (sc) {
      if (Number.isFinite(Number(sc.estimate_fte_months))) return Number(sc.estimate_fte_months);
      if (Number.isFinite(Number(sc.capacity_fte_months))) return Number(sc.capacity_fte_months);
      if (Number.isFinite(Number(sc.estimate_hours))) return Number(sc.estimate_hours) / HOURS_PER_FTE_MONTH;
      if (Number.isFinite(Number(sc.capacity_hours))) return Number(sc.capacity_hours) / HOURS_PER_FTE_MONTH;
    }
  }
  return 0.25;
}

function allocationLabel(allocation) {
  if (!allocation) return "";
  if (allocation.work_item_type === "project") {
    return state.projects.find((p) => p.project_id === allocation.work_item_id)?.project_name || allocation.work_item_id;
  }
  if (allocation.work_item_type === "solution") {
    return state.solutions.find((s) => s.solution_id === allocation.work_item_id)?.solution_name || allocation.work_item_id;
  }
  if (allocation.work_item_type === "subcomponent") {
    return state.subcomponents.find((sc) => sc.subcomponent_id === allocation.work_item_id)?.subcomponent_name || allocation.work_item_id;
  }
  return allocation.work_item_id || "";
}

function deriveTeamForItem(type, itemId) {
  if (!type || !itemId) return null;
  return null;
}

function applyAllocationDefaults() {
  if (!els.allocationForm) return;
  const typeSel = els.allocationForm.querySelector('[name="work_item_type"]');
  const itemSel = els.allocationForm.querySelector('[name="work_item_id"]');
  const fteInput = els.allocationForm.querySelector('[name="fte_months"]');
  const monthStart = els.allocationForm.querySelector('[name="month_start"]');
  const win = getSelectedWindow();
  if (win && monthStart && !monthStart.value) {
    monthStart.value = (normalizeMonthStart(win.start_date) || "").slice(0, 7);
  }
  if (typeSel && itemSel && fteInput) {
    const defaultFte = allocationFteDefault(typeSel.value, itemSel.value);
    fteInput.value = defaultFte.toFixed(2);
  }
}

function renderPlanningRoster() {
  if (!els.planningRoster) return;
  const win = getSelectedWindow();
  if (!win) {
    els.planningRoster.innerHTML = "<p class='muted'>Select a planning window to see roster.</p>";
    return;
  }
  const searchTerm = (els.planningSearch?.value || "").toLowerCase();
  const teamTagFilter = (els.planningTeamTagFilter?.value || "").toLowerCase();
  const allocs = state.allocations.filter((a) => a.window_id === win.window_id);
  const fteByAssignee = new Map();
  state.users.forEach((u) => {
    if (u.soeid) fteByAssignee.set(u.soeid, 0);
  });
  allocs.forEach((a) => {
    const key = assigneeKeyFromAlloc(a);
    fteByAssignee.set(key, (fteByAssignee.get(key) || 0) + allocationFteMonths(a));
  });
  const memberCap = new Map();
  state.users.forEach((u) => {
    if (u.soeid) memberCap.set(u.soeid, userCapacityFteMonth(u));
  });
  const rows = Array.from(fteByAssignee.entries())
    .filter(([key]) => key && key !== "unassigned")
    .map(([key, fte]) => {
      const cap = memberCap.get(key);
      const remaining = cap != null ? Math.max(cap - fte, 0) : null;
      return { key, fte, cap, remaining };
    })
    .filter((r) => {
      const user = findUserBySoeid(r.key);
      if (teamTagFilter && !(user?.team_tag || "").toLowerCase().includes(teamTagFilter)) return false;
      if (searchTerm) {
        const label = assigneeLabelFromKey(r.key).toLowerCase();
        if (!label.includes(searchTerm) && !r.key.toLowerCase().includes(searchTerm)) return false;
      }
      return true;
    })
    .sort((a, b) => (b.cap || 0) - (a.cap || 0));
  const pill = (val, cls = "") => `<span class="pill ${cls}">${val}</span>`;
  const html = rows.length
    ? rows
        .map(
          (r) =>
            `<div class="roster-row" data-assignee="${r.key}">
              <div class="roster-main">
                <strong>${assigneeLabelFromKey(r.key)}</strong>
                <div class="roster-meta">${pill(`${formatFte(r.fte)} FTE`, "warn")} ${
              r.cap != null ? pill(`${formatFte(r.cap)} cap`) : pill("no capacity", "muted")
            } ${r.remaining !== null ? pill(`${formatFte(r.remaining)} left`, r.remaining <= 0.1 ? "warn" : "") : ""}</div>
              </div>
              <div class="roster-actions">
                <button type="button" class="secondary roster-add" data-assignee="${r.key}">+ add</button>
              </div>
            </div>`
        )
        .join("")
    : "<p class='muted'>No allocations yet.</p>";
  els.planningRoster.innerHTML = `<h3>Roster (${win.name})</h3>${html}`;
  els.planningRoster.querySelectorAll(".roster-add").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!els.allocationForm) return;
      const assignee = btn.getAttribute("data-assignee") || "";
      const assigneeSel = els.allocationForm.querySelector('[name="assignee"]');
      const assigneeUser = els.allocationForm.querySelector('[name="assignee_user_soeid"]');
      if (assigneeSel) assigneeSel.value = assignee !== "unassigned" ? assignee : "";
      if (assigneeUser) assigneeUser.value = assignee !== "unassigned" ? assignee : "";
      applyAllocationDefaults();
      openPlanningDrawer("allocation");
    });
  });
}

function init() {
  initTheme();
  bindAuthUI();
  bindCsvControls();
  bindSpaceSwitcher();
  bindNav();
  bindConfirmModal();
  renderSpaceSwitcher();
  bindDeliverablesControls();
  bindDeliverablesTable();
  bindProjectForm();
  bindSolutionForm();
  bindSubcomponentForm();
  bindSolutionTabs();
  bindSolutionSubcomponentControls();
  bindModalShortcuts();
  bindCalendarControls();
  bindCapacityUsers();
  bindSpaceAdminControls();
  initSubcomponentsWorkbench();
  const initialView = viewFromHash();
  setView(initialView, { fromHash: true });
  if (!window.location.hash) {
    syncHashForView(initialView, true);
  }
  bootstrapAuth();
}

init();
