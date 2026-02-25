const API_BASE = "/api";
// LLM-backed endpoints can exceed typical UI timeouts; keep this >= backend wall/model timeout.
const AI_CHAT_TIMEOUT_MS = 75000;
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
  aiEntityType: document.getElementById("ai-entity-type"),
  aiEntityId: document.getElementById("ai-entity-id"),
  aiAutoApprove: document.getElementById("ai-auto-approve"),
  aiNewChat: document.getElementById("ai-new-chat"),
  aiChat: document.getElementById("ai-chat"),
  aiChatForm: document.getElementById("ai-chat-form"),
  aiChatInput: document.getElementById("ai-chat-input"),
  aiStatus: document.getElementById("ai-status"),

  workbenchProject: document.getElementById("workbench-project"),
  workbenchAssist: document.getElementById("workbench-assist-level"),
  workbenchLoadTemplate: document.getElementById("workbench-load-template"),
  workbenchValidate: document.getElementById("workbench-validate"),
  workbenchDownloadRendered: document.getElementById("workbench-download-rendered"),
  workbenchRefine: document.getElementById("workbench-refine"),
  workbenchSave: document.getElementById("workbench-save"),
  workbenchFinalize: document.getElementById("workbench-finalize"),
  workbenchDocState: document.getElementById("workbench-doc-state"),
  workbenchRevisionId: document.getElementById("workbench-revision-id"),
  workbenchRevisions: document.getElementById("workbench-revisions"),
  workbenchTitle: document.getElementById("workbench-title"),
  workbenchContent: document.getElementById("workbench-content"),
  workbenchStatus: document.getElementById("workbench-status"),
  workbenchSummary: document.getElementById("workbench-summary"),
  workbenchQuestions: document.getElementById("workbench-questions"),
  workbenchWarnings: document.getElementById("workbench-warnings"),
  workbenchApply: document.getElementById("workbench-apply"),
  workbenchChecklistControls: document.getElementById("workbench-checklist-controls"),
  workbenchMonth: document.getElementById("workbench-month"),
  workbenchGenerateChecklist: document.getElementById("workbench-generate-checklist"),
  workbenchSowApproval: document.getElementById("workbench-sow-approval"),
  workbenchSowApprovalState: document.getElementById("workbench-sow-approval-state"),
  workbenchSowRequest: document.getElementById("workbench-sow-request"),
  workbenchSowApprove: document.getElementById("workbench-sow-approve"),
  workbenchSowReject: document.getElementById("workbench-sow-reject"),
  workbenchSowNote: document.getElementById("workbench-sow-note"),

  structureProject: document.getElementById("structure-project"),
  structureDecompositionLevel: document.getElementById("structure-decomposition-level"),
  structureGrid: document.getElementById("structure-grid"),
  structureSourcesResizer: document.getElementById("structure-sources-resizer"),
  structureGenerate: document.getElementById("structure-generate"),
  structureCommit: document.getElementById("structure-commit"),
  structureStatus: document.getElementById("structure-status"),
  structureRefineBusy: document.getElementById("structure-refine-busy"),
  structureRefineBusyText: document.getElementById("structure-refine-busy-text"),
  structureSufficiency: document.getElementById("structure-sufficiency"),
  structureMissing: document.getElementById("structure-missing"),
  structureCharterMeta: document.getElementById("structure-charter-meta"),
  structureCharterContent: document.getElementById("structure-charter-content"),
  structurePlanMeta: document.getElementById("structure-plan-meta"),
  structurePlanContent: document.getElementById("structure-plan-content"),
  structureDraftList: document.getElementById("structure-draft-list"),
  structureItemName: document.getElementById("structure-item-name"),
  structureItemDescription: document.getElementById("structure-item-description"),
  structureAccept: document.getElementById("structure-accept"),
  structureDiscard: document.getElementById("structure-discard"),
  structureRefineSelected: document.getElementById("structure-refine-selected"),
  structureBulkSelectionCount: document.getElementById("structure-bulk-selection-count"),
  structureBulkSelectAll: document.getElementById("structure-bulk-select-all"),
  structureBulkClear: document.getElementById("structure-bulk-clear"),
  structureBulkAccept: document.getElementById("structure-bulk-accept"),
  structureBulkDiscard: document.getElementById("structure-bulk-discard"),
  structureChat: document.getElementById("structure-chat"),
  structureChatForm: document.getElementById("structure-chat-form"),
  structureChatInput: document.getElementById("structure-chat-input"),
  structureRefineModal: document.getElementById("structure-refine-modal"),
  structureRefineModalTitle: document.getElementById("structure-refine-modal-title"),
  structureRefineModalClose: document.getElementById("structure-refine-modal-close"),
  structureRefineForm: document.getElementById("structure-refine-form"),
  structureRefineInput: document.getElementById("structure-refine-input"),
  structureRefineSubmit: document.getElementById("structure-refine-submit"),
  structureRefineCancel: document.getElementById("structure-refine-cancel"),
  structureRefineModalBusy: document.getElementById("structure-refine-modal-busy"),
  structureRefineModalBusyText: document.getElementById("structure-refine-modal-busy-text"),
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
  "workbench",
  "structure-studio",
  "team-capacity",
  "spaces",
  "access",
  "ai",
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
  workbench: ["projects"],
  "structure-studio": ["projects"],
  "team-capacity": ["users", "allocations"],
  spaces: [],
  access: [],
  ai: ["projects", "solutions", "subcomponents"],
};
const VIEW_PREFETCH_TARGET = {
  master: "dashboard",
  "subcomponents-workbench": "planning",
  dashboard: "pm-dashboard",
  "pm-dashboard": "kanban",
  kanban: "planning",
  calendar: "planning",
  planning: "team-capacity",
  workbench: "structure-studio",
  "structure-studio": "workbench",
  "team-capacity": "spaces",
  spaces: "access",
  access: "planning",
  ai: "master",
};
const ROUTE_MODULE_LOADERS = {
  master: () => import(`./routes/master.js?v=${APP_ASSET_VERSION}`),
  "subcomponents-workbench": () => import(`./routes/subcomponents-workbench.js?v=${APP_ASSET_VERSION}`),
  ai: () => import(`./routes/ai.js?v=${APP_ASSET_VERSION}`),
  workbench: () => import(`./routes/workbench.js?v=${APP_ASSET_VERSION}`),
  "structure-studio": () => import(`./routes/structure-studio.js?v=${APP_ASSET_VERSION}`),
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
  if (typeof state.aiRefreshGreeting === "function") {
    state.aiRefreshGreeting();
  }
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

function bindGenAIUI() {
  if (!els.aiChat || !els.aiChatForm || !els.aiChatInput) return;
  const AUTO_APPROVE_KEY = "jiraLiteAiAutoApprove";
  const aiState = {
    pending: null,
    history: [],
    followup: null,
    sessionId: null,
    inFlight: false,
    lastAssistantWasQuestion: false,
    awaitingFollowup: false,
    threadStartIndex: 0,
    autoApprove: localStorage.getItem(AUTO_APPROVE_KEY) === "1",
  };
  const autoRefreshTypes = new Set([
    "autofill",
    "sow",
    "checklist",
    "subcomponents",
    "project_create",
    "solution_create",
    "charter_create",
    "plan_create",
    "decision_log_create",
  ]);

  const setStatusText = (text) => {
    if (els.aiStatus) els.aiStatus.textContent = text || "";
  };

  const greetingText = () => {
    const userName = (state.user?.display_name || state.user?.soeid || "").toString().trim();
    return userName ? `Hi ${userName}, what can I do for you?` : "What can I do for you?";
  };

  const addMessage = (role, text, options = {}) => {
    const div = document.createElement("div");
    div.className = `ai-message ${role}`;
    div.textContent = text;
    els.aiChat.appendChild(div);
    els.aiChat.scrollTop = els.aiChat.scrollHeight;
    const record = options.record !== false;
    if (record) {
      aiState.history.push({ role, content: text });
      if (aiState.history.length > 50) {
        aiState.history = aiState.history.slice(-50);
      }
    }
    if (role === "assistant" && record) {
      aiState.lastAssistantWasQuestion = !!(text && text.trim().endsWith("?"));
    }
  };

  const resetChat = () => {
    aiState.pending = null;
    aiState.history = [];
    aiState.sessionId = null;
    aiState.lastAssistantWasQuestion = false;
    aiState.awaitingFollowup = false;
    aiState.threadStartIndex = 0;
    els.aiChat.innerHTML = "";
    setStatusText("");
    addMessage(
      "assistant",
      greetingText(),
      { record: false }
    );
  };

  const refreshGreeting = () => {
    if (!els.aiChat) return;
    if (aiState.history.length !== 0) return;
    const messages = els.aiChat.querySelectorAll(".ai-message");
    if (messages.length !== 1) return;
    const first = messages[0];
    if (!first.classList.contains("assistant")) return;
    first.textContent = greetingText();
  };

  state.aiRefreshGreeting = refreshGreeting;
  state.aiResetChat = resetChat;

  const isNoisyAssistantMessage = (text) => {
    if (!text) return true;
    const trimmed = String(text).trim();
    if (!trimmed) return true;
    if (trimmed.startsWith("DEBUG SUMMARY") || trimmed.startsWith("DEBUG TRACE")) return true;
    if (trimmed.startsWith("# Fields") || trimmed.startsWith("# Checklist") || trimmed.startsWith("# Subcomponents")) return true;
    if (trimmed.startsWith("Would you like me to save this?")) return true;
    return false;
  };

  const buildContextHistory = () => {
    // Keep model context small and focused; UI transcript can be longer.
    const MAX_MESSAGES = 6;
    const MAX_CHARS = 500;
    const compact = [];
    for (const msg of aiState.history.slice(aiState.threadStartIndex)) {
      if (!msg || !msg.content) continue;
      const role = msg.role || "user";
      const content = String(msg.content || "");
      if (role === "assistant" && isNoisyAssistantMessage(content)) continue;
      // Only keep assistant messages that are questions or short confirmations.
      if (role === "assistant") {
        const isQuestion = content.trim().endsWith("?");
        if (!isQuestion && content.length > 240) continue;
      }
      const clipped = content.length > MAX_CHARS ? content.slice(0, MAX_CHARS - 3) + "..." : content;
      compact.push({ role, content: clipped });
      if (compact.length > MAX_MESSAGES) compact.shift();
    }
    return compact;
  };

  const autosizeInput = () => {
    const el = els.aiChatInput;
    if (!el || el.tagName !== "TEXTAREA") return;
    el.style.height = "0px";
    const next = Math.min(el.scrollHeight, 180);
    el.style.height = `${Math.max(next, 44)}px`;
  };

  const extractQuestion = (output) => {
    if (!output) return "";
    try {
      const parsed = JSON.parse(output);
      if (parsed && typeof parsed === "object") {
        if (typeof parsed.question === "string" && parsed.question.trim()) {
          return parsed.question.trim();
        }
        if (Array.isArray(parsed.questions)) {
          const joined = parsed.questions.map((q) => String(q || "").trim()).filter(Boolean).join(" ");
          if (joined) return joined;
        }
      }
    } catch (_) {}
    const lines = output.split("\n").map((line) => line.trim());
    for (const line of lines) {
      if (line.toLowerCase().startsWith("question:")) {
        return line.replace(/^question:\s*/i, "").trim();
      }
    }
    let inQuestions = false;
    const questions = [];
    for (const line of lines) {
      if (line.toLowerCase().startsWith("# questions")) {
        inQuestions = true;
        continue;
      }
      if (line.startsWith("# ")) {
        inQuestions = false;
      }
      if (inQuestions && line && !line.startsWith("# ")) {
        questions.push(line.replace(/^[-*]\s*/, ""));
      }
    }
    if (questions.length) return questions.join(" ");
    const hasFields = lines.some((line) => line.toLowerCase().startsWith("# fields"));
    if (!hasFields && output.trim().endsWith("?")) {
      return output.trim();
    }
    return "";
  };

  const renderOutputForChat = (output) => {
    if (!output) return "";
    let parsed = null;
    try {
      parsed = JSON.parse(output);
    } catch (_) {
      return output;
    }
    if (!parsed || typeof parsed !== "object") return output;
    if (typeof parsed.content === "string" && parsed.content.trim()) {
      return parsed.content.trim();
    }
    if (parsed.fields && typeof parsed.fields === "object") {
      const lines = ["# Fields"];
      Object.entries(parsed.fields).forEach(([key, value]) => {
        lines.push(`- ${key}: ${typeof value === "string" ? `"${value}"` : value}`);
      });
      return lines.join("\n");
    }
    if (Array.isArray(parsed.checklist)) {
      const lines = ["# Checklist"];
      parsed.checklist.forEach((item) => {
        if (item) lines.push(`- ${item}`);
      });
      return lines.join("\n");
    }
    if (Array.isArray(parsed.subcomponents)) {
      const lines = ["# Subcomponents"];
      parsed.subcomponents.forEach((item) => {
        if (!item || !item.name) return;
        const priority = item.priority != null ? item.priority : 3;
        const assignee = item.assignee || "";
        lines.push(`- name: "${item.name}" | priority: ${priority} | assignee: "${assignee}"`);
      });
      return lines.join("\n");
    }
    if (typeof parsed.summary === "string" && parsed.summary.trim()) {
      return parsed.summary.trim();
    }
    return output;
  };

  const parseJsonObject = (raw) => {
    if (!raw) return null;
    if (typeof raw === "object") return raw;
    if (typeof raw !== "string") return null;
    const trimmed = raw.trim();
    if (!trimmed) return null;
    let candidate = trimmed;
    const fenced = candidate.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
    if (fenced && fenced[1]) {
      candidate = fenced[1].trim();
    }
    try {
      return JSON.parse(candidate);
    } catch (_) {
      return null;
    }
  };

  const normalizeAiEntityType = (entityType) => {
    const key = String(entityType || "").trim().toLowerCase();
    if (!key) return "";
    if (key === "project" || key === "projects") return "project";
    if (key === "solution" || key === "solutions") return "solution";
    if (
      key === "subcomponent" ||
      key === "subcomponents" ||
      key === "task" ||
      key === "tasks" ||
      key === "sub-component"
    ) {
      return "subcomponent";
    }
    return key;
  };

  const normalizeUpdateDraft = (rawUpdate, fallbackEntityType, fallbackEntityId) => {
    if (!rawUpdate || typeof rawUpdate !== "object") return null;
    const raw = rawUpdate;

    let entityType = normalizeAiEntityType(raw.entity_type || fallbackEntityType || "");
    let entityId = String(raw.entity_id || fallbackEntityId || "").trim();
    if (!entityId || !entityType) {
      if (raw.solution_id) {
        entityType = entityType || "solution";
        entityId = String(raw.solution_id || "").trim();
      } else if (raw.subcomponent_id || raw.task_id) {
        entityType = entityType || "subcomponent";
        entityId = String(raw.subcomponent_id || raw.task_id || "").trim();
      } else if (raw.project_id) {
        entityType = entityType || "project";
        entityId = String(raw.project_id || "").trim();
      }
    }
    if (!entityType || !entityId) return null;

    let fields = null;
    if (raw.fields && typeof raw.fields === "object" && !Array.isArray(raw.fields)) {
      fields = { ...raw.fields };
    } else {
      const reserved = new Set([
        "entity_type",
        "entity_id",
        "project_id",
        "solution_id",
        "subcomponent_id",
        "task_id",
        "project_name",
        "solution_name",
        "subcomponent_name",
        "label",
      ]);
      const pairs = Object.entries(raw).filter(([key]) => !reserved.has(key));
      if (pairs.length) fields = Object.fromEntries(pairs);
    }
    if (!fields || !Object.keys(fields).length) return null;

    return { entityType, entityId, fields };
  };

  const extractUpdatesForLocalState = (output, fallbackEntityType, fallbackEntityId) => {
    const parsed = parseJsonObject(output);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return [];

    const updates = [];
    if (Array.isArray(parsed.updates)) {
      parsed.updates.forEach((candidate) => {
        const normalized = normalizeUpdateDraft(candidate, fallbackEntityType, fallbackEntityId);
        if (normalized) updates.push(normalized);
      });
    } else {
      const normalized = normalizeUpdateDraft(parsed, fallbackEntityType, fallbackEntityId);
      if (normalized) updates.push(normalized);
      if (
        !normalized &&
        parsed.fields &&
        typeof parsed.fields === "object" &&
        !Array.isArray(parsed.fields)
      ) {
        const entityType = normalizeAiEntityType(fallbackEntityType);
        const entityId = String(fallbackEntityId || "").trim();
        if (entityType && entityId) {
          updates.push({ entityType, entityId, fields: { ...parsed.fields } });
        }
      }
    }

    const merged = new Map();
    updates.forEach((item) => {
      const key = `${item.entityType}:${item.entityId}`;
      const existing = merged.get(key);
      if (!existing) {
        merged.set(key, item);
        return;
      }
      merged.set(key, {
        ...existing,
        fields: { ...existing.fields, ...item.fields },
      });
    });
    return Array.from(merged.values());
  };

  const applyUpdatesToLocalState = (updates) => {
    if (!Array.isArray(updates) || !updates.length) return false;
    const configByType = {
      project: { list: state.projects, idKey: "project_id" },
      solution: { list: state.solutions, idKey: "solution_id" },
      subcomponent: { list: state.subcomponents, idKey: "subcomponent_id" },
    };
    let changed = false;
    updates.forEach((update) => {
      const cfg = configByType[update.entityType];
      if (!cfg || !Array.isArray(cfg.list)) return;
      const idx = cfg.list.findIndex((row) => row && row[cfg.idKey] === update.entityId);
      if (idx === -1) return;
      cfg.list[idx] = {
        ...cfg.list[idx],
        ...update.fields,
        [cfg.idKey]: update.entityId,
      };
      changed = true;
    });
    return changed;
  };

  const rerenderDeliverablesIfVisible = () => {
    if (state.currentView === "master") renderMasterTable();
    if (state.currentView === "dashboard") renderDashboard();
    if (state.currentView === "pm-dashboard") renderPMDashboard();
    if (state.currentView === "kanban") renderKanban();
    if (state.currentView === "calendar") renderCalendar();
  };

  const syncUIAfterAISave = async (output, fallbackEntityType, fallbackEntityId) => {
    const updates = extractUpdatesForLocalState(output, fallbackEntityType, fallbackEntityId);
    if (applyUpdatesToLocalState(updates)) {
      rerenderDeliverablesIfVisible();
    }
    await refreshFromServer("all");
    if (applyUpdatesToLocalState(updates)) {
      rerenderDeliverablesIfVisible();
    }
  };

  const getProjectId = (entityType, entityId) => {
    void entityType;
    void entityId;
    return null;
  };

  const runAgentic = async (message) => {
    if (aiState.inFlight) return;
    aiState.inFlight = true;
    els.aiChatInput.disabled = true;
    setStatusText("Thinking...");
    try {
      const entityType = null;
      const entityId = null;
      const continueThread = aiState.awaitingFollowup || aiState.lastAssistantWasQuestion;
      const threadHistory = continueThread ? buildContextHistory() : [];
      // The backend appends the current user message; avoid duplicating it in history.
      if (continueThread && threadHistory.length && threadHistory[threadHistory.length - 1].role === "user") {
        threadHistory.pop();
      }
      const payload = {
        message,
        entity_type: entityType,
        entity_id: entityId,
        project_id: getProjectId(entityType, entityId),
        history: continueThread ? threadHistory : [],
        current_date: new Date().toISOString().slice(0, 10),
        session_id: continueThread ? aiState.sessionId || null : null,
      };
      const result = await api("/ai/chat", {
        method: "POST",
        body: JSON.stringify(payload),
        timeoutMs: AI_CHAT_TIMEOUT_MS,
      });
      setStatusText("");
      if (result.session_id) aiState.sessionId = result.session_id;
      // Prefer the server's explicit next_action so follow-up turns work even when the assistant
      // doesn't end with a literal question mark.
      const nextAction = result.next_action || "";
      const serverAwaiting = nextAction ? nextAction === "answer_question" : null;
      const reply = result.reply || "";
      if (reply) addMessage("assistant", reply);
      aiState.awaitingFollowup = serverAwaiting != null ? serverAwaiting : aiState.lastAssistantWasQuestion;
      if (result.debug) {
        const renderedOutput = renderOutputForChat(result.output || "");
        const userVisible = reply || renderedOutput || "";
        const summary = {
          user_visible_reply: userVisible,
          requires_approval: !!result.requires_approval,
          request_type: result.request_type || null,
          next_action: result.requires_approval
            ? "approve_or_discard"
            : userVisible && userVisible.trim().endsWith("?")
            ? "answer_question"
            : "done",
        };
        addMessage("assistant", `DEBUG SUMMARY\n${JSON.stringify(summary, null, 2)}`, { record: false });
        addMessage("assistant", `DEBUG TRACE\n${JSON.stringify(result.debug, null, 2)}`, { record: false });
      }
      // If the backend auto-saved (no approval step), still show the saved payload for transparency.
      if (!result.requires_approval && autoRefreshTypes.has(result.request_type) && result.output) {
        const renderedSaved = renderOutputForChat(result.output || "");
        if (renderedSaved && renderedSaved !== reply) {
          addMessage("assistant", renderedSaved, { record: false });
        }
      }
      const resultEntityType = result.entity_type || payload.entity_type;
      const resultEntityId = result.entity_id || payload.entity_id;
      const hasLocalUpdates = extractUpdatesForLocalState(result.output, resultEntityType, resultEntityId).length > 0;
      if (!result.requires_approval && (autoRefreshTypes.has(result.request_type) || hasLocalUpdates)) {
        await syncUIAfterAISave(result.output, resultEntityType, resultEntityId);
      }
      if (result.requires_approval) {
        const output = result.output || reply;
        const question = extractQuestion(output);
        if (question) {
          addMessage("assistant", question);
          aiState.awaitingFollowup = true;
          return;
        }
        aiState.awaitingFollowup = false;
        const rendered = renderOutputForChat(output);
        if (rendered && rendered !== reply) {
          // Keep transcripts readable without polluting follow-up context.
          addMessage("assistant", rendered, { record: false });
        }
        aiState.pending = {
          request_type: result.request_type,
          entity_type: result.entity_type || payload.entity_type,
          entity_id: result.entity_id || payload.entity_id,
          output,
        };
        // Ensure approve payload is always valid (some create flows don't have an entity_type in context).
        if (!aiState.pending.entity_type) {
          const rt = aiState.pending.request_type || "";
          if (rt === "project_create") aiState.pending.entity_type = "project";
          else if (rt === "solution_create") aiState.pending.entity_type = "project";
          else if (rt === "subcomponent_create") aiState.pending.entity_type = "solution";
          else if (rt === "charter_create" || rt === "plan_create" || rt === "decision_log_create") {
            aiState.pending.entity_type = "project";
          }
        }

        if (aiState.autoApprove) {
          setStatusText("Saving...");
          try {
            const pendingSnapshot = { ...aiState.pending };
            const saved = await api("/ai/approve", {
              method: "POST",
              body: JSON.stringify({ ...aiState.pending }),
              timeoutMs: AI_CHAT_TIMEOUT_MS,
            });
            addMessage("assistant", saved?.reply || "Saved.");
            aiState.pending = null;
            setStatusText("");
            await syncUIAfterAISave(
              saved?.output || pendingSnapshot.output,
              saved?.entity_type || pendingSnapshot.entity_type,
              saved?.entity_id || pendingSnapshot.entity_id
            );
          } catch (err) {
            addMessage("assistant", err.message || "Auto-save failed.");
            setStatusText("");
          }
          return;
        }

        addMessage("assistant", "Would you like me to save this? Reply “yes” to approve or “no” to discard.");
        setStatusText("Awaiting approval.");
      }
    } catch (err) {
      setStatusText("");
      console.warn("AI chat failed", err);
      addMessage("assistant", err.message || "Request failed.");
    } finally {
      aiState.inFlight = false;
      els.aiChatInput.disabled = false;
      autosizeInput();
    }
  };

  const handleApproval = async (message) => {
    const response = normalize(message);
    if (!aiState.pending) return false;
    const hasNegativeApproval = /\b(do not|don't|dont|not)\b[\s\S]{0,24}\b(approve|save)\b/.test(response);
    const wantsReject =
      response === "no" ||
      response === "n" ||
      response.includes("discard") ||
      response.includes("reject") ||
      response.includes("cancel") ||
      hasNegativeApproval;
    const wantsApprove =
      !wantsReject &&
      (response === "yes" || response === "y" || response.includes("approve") || response.includes("save"));

    if (wantsApprove) {
      setStatusText("Saving...");
      const payload = { ...aiState.pending };
      try {
        const result = await api("/ai/approve", { method: "POST", body: JSON.stringify(payload) });
        addMessage("assistant", result?.reply || "Saved.");
        aiState.pending = null;
        setStatusText("");
        await syncUIAfterAISave(
          result?.output || payload.output,
          result?.entity_type || payload.entity_type,
          result?.entity_id || payload.entity_id
        );
      } catch (err) {
        addMessage("assistant", err.message || "Save failed.");
        setStatusText("");
      }
      return true;
    }
    if (wantsReject) {
      addMessage("assistant", "Discarded.");
      aiState.pending = null;
      setStatusText("");
      return true;
    }
    return false;
  };

  els.aiNewChat?.addEventListener("click", () => resetChat());
  if (els.aiAutoApprove) {
    els.aiAutoApprove.checked = aiState.autoApprove;
    els.aiAutoApprove.addEventListener("change", () => {
      aiState.autoApprove = !!els.aiAutoApprove.checked;
      localStorage.setItem(AUTO_APPROVE_KEY, aiState.autoApprove ? "1" : "0");
      setStatusText(aiState.autoApprove ? "Auto-save enabled." : "");
      if (aiState.autoApprove) setTimeout(() => setStatusText(""), 1200);
    });
  }

  if (els.aiChatInput && els.aiChatInput.tagName === "TEXTAREA") {
    els.aiChatInput.addEventListener("input", autosizeInput);
    els.aiChatInput.addEventListener("keydown", (e) => {
      // ChatGPT-style: Enter sends, Shift+Enter inserts a newline.
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        els.aiChatForm.requestSubmit();
      }
    });
    autosizeInput();
  }

  els.aiChatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = els.aiChatInput.value.trim();
    if (!message) return;
    els.aiChatInput.value = "";
    autosizeInput();
    addMessage("user", message);

    try {
      if (await handleApproval(message)) return;
      // New request: isolate model context from earlier tasks.
      if (!(aiState.awaitingFollowup || aiState.lastAssistantWasQuestion)) {
        aiState.threadStartIndex = Math.max(aiState.history.length - 1, 0);
      }
      await runAgentic(message);
    } catch (err) {
      console.warn("AI chat submit failed", err);
      addMessage("assistant", err.message || "Request failed.");
    }
  });

  resetChat();
}

function startLiveSyncOnce() {
  if (liveSyncStarted) return;
  initLiveSync();
  liveSyncStarted = true;
}

function initAI() {
  bindGenAIUI();
}

function renderAI() {
  const mod = getRouteModule("ai");
  if (!mod || typeof mod.renderAI !== "function") {
    ensureRouteModule("ai").then((loaded) => {
      if (loaded && state.currentView === "ai") renderAI();
    });
    return;
  }
  mod.renderAI({
    state,
  });
}

function initWorkbench() {
  bindWorkbenchUI();
}

function initSubcomponentsWorkbench() {
  bindSubcomponentsWorkbenchControls();
}

function renderWorkbench() {
  const mod = getRouteModule("workbench");
  if (!mod || typeof mod.renderWorkbench !== "function") {
    ensureRouteModule("workbench").then((loaded) => {
      if (loaded && state.currentView === "workbench") renderWorkbench();
    });
    return;
  }
  mod.renderWorkbench({
    state,
  });
}

function initStructureStudio() {
  bindStructureStudioUI();
}

function renderStructureStudio() {
  const mod = getRouteModule("structure-studio");
  if (!mod || typeof mod.renderStructureStudio !== "function") {
    ensureRouteModule("structure-studio").then((loaded) => {
      if (loaded && state.currentView === "structure-studio") renderStructureStudio();
    });
    return;
  }
  mod.renderStructureStudio({
    state,
  });
}

function bindWorkbenchUI() {
  if (!els.workbenchProject || !els.workbenchContent) return;

  const docTabs = Array.from(document.querySelectorAll('#view-workbench .workbench-tabs .tab'));
  const wb = {
    docType: "charter",
    projectId: "",
    revisionId: "",
    docState: "draft",
    approvalState: "draft",
    templates: new Map(), // docType -> { template, config }
    pendingPatch: null,
    render: null,
  };
  state.workbench = wb;

  const setStatusText = (text) => {
    if (els.workbenchStatus) els.workbenchStatus.textContent = text || "";
  };

  const setMeta = () => {
    if (els.workbenchDocState) {
      const label = wb.docState ? wb.docState.toUpperCase() : "DRAFT";
      els.workbenchDocState.textContent = label;
    }
    if (els.workbenchRevisionId) {
      els.workbenchRevisionId.textContent = wb.revisionId ? `Rev ${wb.revisionId.slice(0, 8)}` : "No revision";
    }
    if (els.workbenchSowApprovalState) {
      els.workbenchSowApprovalState.textContent = wb.approvalState || "draft";
    }
  };

  const clearSuggestions = () => {
    wb.pendingPatch = null;
    if (els.workbenchSummary) els.workbenchSummary.textContent = "";
    if (els.workbenchQuestions) els.workbenchQuestions.innerHTML = "";
    if (els.workbenchWarnings) els.workbenchWarnings.innerHTML = "";
    if (els.workbenchApply) els.workbenchApply.disabled = true;
  };

  const renderQuestions = (questions) => {
    if (!els.workbenchQuestions) return;
    const items = (questions || []).map((q) => String(q || "").trim()).filter(Boolean);
    if (!items.length) {
      els.workbenchQuestions.innerHTML = "";
      return;
    }
    els.workbenchQuestions.innerHTML = `<div class="pill warn">Questions</div><div class="muted">${items
      .map((q) => `<div style="margin-top:6px;">• ${escapeHtml(q)}</div>`)
      .join("")}</div>`;
  };

  const renderWarnings = (warnings, title = "Warnings") => {
    if (!els.workbenchWarnings) return;
    const items = (warnings || []).map((w) => String(w || "").trim()).filter(Boolean);
    if (!items.length) {
      els.workbenchWarnings.innerHTML = "";
      return;
    }
    els.workbenchWarnings.innerHTML = `<div class="pill warn">${escapeHtml(title)}</div><div class="muted">${items
      .map((w) => `<div style="margin-top:6px;">• ${escapeHtml(w)}</div>`)
      .join("")}</div>`;
  };

  const selectedProject = () => state.projects.find((p) => p.project_id === wb.projectId) || null;

  const sanitizeFilePart = (value, fallback = "document") => {
    const cleaned = String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    if (cleaned) return cleaned;
    return fallback;
  };

  const formatInlineMarkdown = (text) => {
    let out = escapeHtml(text || "");
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_m, label, url) => {
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    return out;
  };

  const renderMarkdownToHtml = (rawMarkdown) => {
    const lines = String(rawMarkdown || "").replaceAll("\r\n", "\n").split("\n");
    const html = [];
    let inCodeBlock = false;
    let codeLines = [];
    let paragraphLines = [];
    let listType = ""; // ul|ol
    let listItems = [];
    let tableLines = [];

    const pushParagraph = () => {
      if (!paragraphLines.length) return;
      html.push(`<p>${paragraphLines.map((line) => formatInlineMarkdown(line)).join("<br />")}</p>`);
      paragraphLines = [];
    };

    const pushList = () => {
      if (!listItems.length || !listType) return;
      html.push(`<${listType}>${listItems.map((item) => `<li>${item}</li>`).join("")}</${listType}>`);
      listType = "";
      listItems = [];
    };

    const pushCode = () => {
      if (!codeLines.length) return;
      html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      codeLines = [];
    };

    const pushTable = () => {
      if (!tableLines.length) return;
      const parseRow = (row) =>
        row
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((cell) => formatInlineMarkdown(cell.trim()));
      const rows = tableLines.map(parseRow).filter((cells) => cells.length);
      if (!rows.length) {
        tableLines = [];
        return;
      }
      const sepCells =
        tableLines.length > 1
          ? tableLines[1]
              .trim()
              .replace(/^\|/, "")
              .replace(/\|$/, "")
              .split("|")
              .map((cell) => cell.trim())
          : [];
      const hasHeaderSeparator = sepCells.length > 0 && sepCells.every((cell) => /^:?-{3,}:?$/.test(cell));
      const header = rows[0];
      const body = hasHeaderSeparator ? rows.slice(2) : rows.slice(1);
      const headHtml = `<thead><tr>${header.map((cell) => `<th>${cell || "&nbsp;"}</th>`).join("")}</tr></thead>`;
      const bodyHtml = body.length
        ? `<tbody>${body.map((cells) => `<tr>${cells.map((cell) => `<td>${cell || "&nbsp;"}</td>`).join("")}</tr>`).join("")}</tbody>`
        : "<tbody></tbody>";
      html.push(`<table>${headHtml}${bodyHtml}</table>`);
      tableLines = [];
    };

    for (const rawLine of lines) {
      const line = String(rawLine || "");
      const trimmed = line.trim();

      if (inCodeBlock) {
        if (trimmed.startsWith("```")) {
          pushCode();
          inCodeBlock = false;
        } else {
          codeLines.push(line);
        }
        continue;
      }

      const tableLike = trimmed.startsWith("|") && trimmed.includes("|");
      if (tableLike) {
        pushParagraph();
        pushList();
        tableLines.push(line);
        continue;
      }
      if (tableLines.length) {
        pushTable();
      }

      if (!trimmed) {
        pushParagraph();
        pushList();
        continue;
      }

      if (trimmed.startsWith("```")) {
        pushParagraph();
        pushList();
        inCodeBlock = true;
        codeLines = [];
        continue;
      }

      const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        pushParagraph();
        pushList();
        const level = heading[1].length;
        html.push(`<h${level}>${formatInlineMarkdown(heading[2])}</h${level}>`);
        continue;
      }

      if (/^([-*_])\1{2,}$/.test(trimmed.replaceAll(" ", ""))) {
        pushParagraph();
        pushList();
        html.push("<hr />");
        continue;
      }

      const blockquote = trimmed.match(/^>\s?(.*)$/);
      if (blockquote) {
        pushParagraph();
        pushList();
        html.push(`<blockquote><p>${formatInlineMarkdown(blockquote[1])}</p></blockquote>`);
        continue;
      }

      const unordered = line.match(/^\s*[-*]\s+(.+)$/);
      if (unordered) {
        pushParagraph();
        if (listType && listType !== "ul") pushList();
        listType = "ul";
        listItems.push(formatInlineMarkdown(unordered[1]));
        continue;
      }

      const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
      if (ordered) {
        pushParagraph();
        if (listType && listType !== "ol") pushList();
        listType = "ol";
        listItems.push(formatInlineMarkdown(ordered[1]));
        continue;
      }

      paragraphLines.push(trimmed);
    }

    if (tableLines.length) pushTable();
    if (inCodeBlock) pushCode();
    pushParagraph();
    pushList();
    return html.join("\n");
  };

  const docTypeLabel = (docType) => {
    if (docType === "sow") return "Statement of Work";
    if (docType === "checklist") return "Checklist";
    if (docType === "charter") return "Project Charter";
    if (docType === "plan") return "Project Plan";
    return "Document";
  };

  const renderExportHtml = (content) => {
    const project = selectedProject();
    const projectName = project?.project_name || "Project";
    const title = (els.workbenchTitle?.value || "").trim() || docTypeLabel(wb.docType);
    const renderedBody = renderMarkdownToHtml(content);
    const generatedAt = new Date().toLocaleString();
    const month = wb.docType === "checklist" ? (els.workbenchMonth?.value || "") : "";
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; margin: 0; background: #f5f7fb; color: #122031; }
    .wrap { max-width: 980px; margin: 24px auto; background: #fff; border: 1px solid #d6deea; border-radius: 12px; padding: 24px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .meta { color: #495b73; font-size: 13px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 10px; }
    article { line-height: 1.5; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    th, td { border: 1px solid #d6deea; padding: 8px; vertical-align: top; text-align: left; }
    th { background: #eef3fb; }
    pre { background: #0f1a2b; color: #e7edf7; padding: 12px; border-radius: 8px; overflow: auto; }
    code { background: #eef3fb; padding: 1px 4px; border-radius: 4px; }
    blockquote { margin: 12px 0; padding: 8px 12px; border-left: 4px solid #7e91ab; background: #f7f9fc; }
    hr { border: 0; border-top: 1px solid #d6deea; margin: 16px 0; }
  </style>
</head>
<body>
  <main class="wrap">
    <h1>${escapeHtml(title)}</h1>
    <div class="meta">
      <span><strong>Project:</strong> ${escapeHtml(projectName)}</span>
      <span><strong>Type:</strong> ${escapeHtml(docTypeLabel(wb.docType))}</span>
      ${month ? `<span><strong>Month:</strong> ${escapeHtml(month)}</span>` : ""}
      <span><strong>Generated:</strong> ${escapeHtml(generatedAt)}</span>
    </div>
    <article>${renderedBody}</article>
  </main>
</body>
</html>`;
  };

  const downloadRenderedDoc = () => {
    const content = String(els.workbenchContent?.value || "");
    if (!content.trim()) {
      setStatusText("Nothing to download yet.");
      setTimeout(() => setStatusText(""), 900);
      return;
    }
    const projectName = selectedProject()?.project_name || "project";
    const title = (els.workbenchTitle?.value || "").trim();
    const checklistMonth = wb.docType === "checklist" ? sanitizeFilePart(els.workbenchMonth?.value || "", "") : "";
    const filename = [
      sanitizeFilePart(projectName, "project"),
      sanitizeFilePart(wb.docType, "document"),
      checklistMonth,
      sanitizeFilePart(title, ""),
    ]
      .filter(Boolean)
      .join("-") + ".html";

    const html = renderExportHtml(content);
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "document.html";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatusText(`Downloaded ${filename}.`);
    setTimeout(() => setStatusText(""), 1300);
  };

  const isoMonthKey = (year, monthIndex) => {
    const mm = String(monthIndex + 1).padStart(2, "0");
    return `${year}-${mm}`;
  };

  const currentMonthKey = () => {
    const d = new Date();
    return isoMonthKey(d.getFullYear(), d.getMonth());
  };

  const fillTemplate = (template) => {
    const proj = selectedProject();
    const projectName = proj?.project_name || "Project";
    const sponsor = proj?.sponsor || state.user?.display_name || state.user?.soeid || "Sponsor";
    const currentUser = state.user?.display_name || state.user?.soeid || "User";
    const todayDate = new Date().toISOString().slice(0, 10);

    const solutions = state.solutions.filter((s) => s.project_id === wb.projectId);
    const solutionLines = solutions.length
      ? solutions
          .slice()
          .sort((a, b) => (a.solution_name || "").localeCompare(b.solution_name || ""))
          .map((s) => `- ${s.solution_name || "Solution"} (status: ${s.status || "n/a"})`)
          .join("\n")
      : "- [[TODO]]";

    const subcomponents = state.subcomponents.filter((sc) => sc.project_id === wb.projectId);
    const subLines = subcomponents.length
      ? subcomponents
          .slice()
          .sort((a, b) => (a.subcomponent_name || "").localeCompare(b.subcomponent_name || ""))
          .map((sc) => `- ${sc.subcomponent_name || "Subcomponent"} (status: ${sc.status || "n/a"})`)
          .join("\n")
      : "- [[TODO]]";

    return String(template || "")
      .replaceAll("[[PROJECT_NAME]]", projectName)
      .replaceAll("[[SPONSOR]]", sponsor)
      .replaceAll("[[CURRENT_USER]]", currentUser)
      .replaceAll("[[TODAY_DATE]]", todayDate)
      .replaceAll("[[SOLUTIONS_LIST]]", solutionLines)
      .replaceAll("[[SUBCOMPONENTS_LIST]]", subLines);
  };

  const ensureTemplateLoaded = async (docType) => {
    if (wb.templates.has(docType)) return wb.templates.get(docType);
    const tpl = await api(`/workbench/templates/${docType}`);
    wb.templates.set(docType, tpl);
    return tpl;
  };

  const setDocType = async (docType) => {
    const next = (docType || "charter").toLowerCase();
    wb.docType = next;
    docTabs.forEach((btn) => btn.classList.toggle("active", btn.dataset.doc === next));
    clearSuggestions();

    const isChecklist = next === "checklist";
    if (els.workbenchChecklistControls) els.workbenchChecklistControls.classList.toggle("hidden", !isChecklist);
    if (els.workbenchSowApproval) els.workbenchSowApproval.classList.toggle("hidden", next !== "sow");
    if (els.workbenchFinalize) els.workbenchFinalize.disabled = isChecklist;

    await loadLatest();
  };

  const setProjectId = async (projectId) => {
    wb.projectId = projectId || "";
    clearSuggestions();
    await loadLatest();
  };

  const renderProjectOptions = () => {
    if (!els.workbenchProject) return;
    const prior = els.workbenchProject.value;
    const projects = state.projects.slice().sort((a, b) => (a.project_name || "").localeCompare(b.project_name || ""));
    els.workbenchProject.innerHTML = projects
      .map((p) => `<option value="${p.project_id}">${escapeHtml(p.project_name || "Project")}</option>`)
      .join("");
    if (wb.projectId) {
      els.workbenchProject.value = wb.projectId;
    } else if (prior && projects.some((p) => p.project_id === prior)) {
      els.workbenchProject.value = prior;
      wb.projectId = prior;
    } else if (projects.length) {
      els.workbenchProject.value = projects[0].project_id;
      wb.projectId = projects[0].project_id;
    }
  };

  const renderRevisions = (revisions) => {
    if (!els.workbenchRevisions) return;
    const rows = revisions || [];
    if (!rows.length || wb.docType === "checklist") {
      els.workbenchRevisions.innerHTML = "<p class='muted'>No revisions yet.</p>";
      return;
    }
    els.workbenchRevisions.innerHTML = rows
      .map((r) => {
        const createdAt = r.created_at ? new Date(r.created_at).toLocaleString() : "";
        const title = r.title || "(untitled)";
        const stateTag = r.state ? `<span class="pill muted">${escapeHtml(String(r.state))}</span>` : "";
        const approvalTag =
          wb.docType === "sow" && r.approval_state ? `<span class="pill muted">${escapeHtml(r.approval_state)}</span>` : "";
        return `<div class="workbench-rev" data-revision="${r.revision_id}">
            <strong>${escapeHtml(title)}</strong>
            <div class="muted">${escapeHtml(createdAt)}</div>
            <div style="margin-top:6px; display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
              ${stateTag}${approvalTag}
              <span style="flex:1"></span>
              <button type="button" class="secondary workbench-rev-delete" data-revision="${r.revision_id}">Delete</button>
            </div>
          </div>`;
      })
      .join("");
    els.workbenchRevisions.querySelectorAll(".workbench-rev").forEach((el) => {
      el.addEventListener("click", async () => {
        const rid = el.getAttribute("data-revision") || "";
        if (!rid) return;
        await loadRevision(rid);
      });
    });
    els.workbenchRevisions.querySelectorAll(".workbench-rev-delete").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const rid = btn.getAttribute("data-revision") || "";
        if (!rid) return;
        const ok = confirm("Delete this revision from history? This cannot be undone (but you can re-save from another revision).");
        if (!ok) return;
        setStatusText("Deleting...");
        try {
          await api(`/workbench/docs/${wb.docType}/revisions/${encodeURIComponent(rid)}`, { method: "DELETE" });
          // If we deleted the currently loaded revision, fall back to latest.
          if (wb.revisionId === rid) {
            wb.revisionId = "";
            wb.docState = "draft";
            wb.approvalState = "draft";
            setMeta();
            await loadLatest();
          } else {
            await loadRevisions();
          }
          setStatusText("Deleted.");
          setTimeout(() => setStatusText(""), 900);
        } catch (err) {
          console.warn("Delete revision failed", err);
          setStatusText(err?.message || "Delete failed.");
        }
      });
    });
  };

  const loadRevisions = async () => {
    if (!wb.projectId || wb.docType === "checklist") {
      renderRevisions([]);
      return;
    }
    const data = await api(`/workbench/docs/${wb.docType}/revisions?project_id=${encodeURIComponent(wb.projectId)}`);
    renderRevisions(data?.revisions || []);
  };

  const loadRevision = async (revisionId) => {
    if (!wb.projectId) return;
    setStatusText("Loading revision...");
    try {
      const doc = await api(`/workbench/docs/${wb.docType}/revisions/${encodeURIComponent(revisionId)}`);
      wb.revisionId = doc?.revision_id || "";
      wb.docState = doc?.state || "draft";
      wb.approvalState = doc?.approval_state || "draft";
      if (els.workbenchTitle) els.workbenchTitle.value = doc?.title || "";
      if (els.workbenchContent) els.workbenchContent.value = doc?.content || "";
      setMeta();
      clearSuggestions();
    } finally {
      setStatusText("");
    }
  };

  const loadChecklist = async () => {
    if (!wb.projectId) return;
    if (els.workbenchMonth && !els.workbenchMonth.value) {
      els.workbenchMonth.value = currentMonthKey();
    }
    const monthKey = els.workbenchMonth?.value || currentMonthKey();
    setStatusText("Loading checklist...");
    try {
      const data = await api(
        `/workbench/checklist?project_id=${encodeURIComponent(wb.projectId)}&month_key=${encodeURIComponent(monthKey)}`
      );
      const lines = (data?.items || []).map((it) => it.title).filter(Boolean);
      els.workbenchContent.value = lines.join("\n");
      wb.revisionId = "";
      wb.docState = "draft";
      wb.approvalState = "draft";
      if (els.workbenchTitle) els.workbenchTitle.value = `${selectedProject()?.project_name || "Project"} ${monthKey}`;
      setMeta();
      clearSuggestions();
      await loadRevisions();
    } finally {
      setStatusText("");
    }
  };

  const loadLatest = async () => {
    if (!wb.projectId) return;
    setMeta();

    if (wb.docType === "checklist") {
      await loadChecklist();
      return;
    }

    const tpl = await ensureTemplateLoaded(wb.docType);
    await loadRevisions();

    setStatusText("Loading latest...");
    try {
      const doc = await api(`/workbench/docs/${wb.docType}/latest?project_id=${encodeURIComponent(wb.projectId)}`);
      if (!doc) {
        wb.revisionId = "";
        wb.docState = "draft";
        wb.approvalState = "draft";
        if (els.workbenchTitle) els.workbenchTitle.value = "";
        els.workbenchContent.value = fillTemplate(tpl?.template || "");
      } else {
        wb.revisionId = doc?.revision_id || "";
        wb.docState = doc?.state || "draft";
        wb.approvalState = doc?.approval_state || "draft";
        if (els.workbenchTitle) els.workbenchTitle.value = doc?.title || "";
        els.workbenchContent.value = doc?.content || "";
      }
      setMeta();
      clearSuggestions();
    } finally {
      setStatusText("");
    }
  };

  const extractChecklistItems = (raw) => {
    const text = String(raw || "");
    const lines = text.split("\n");

    const parseTable = (headerMatcher) => {
      const headerIdx = lines.findIndex((l) => headerMatcher(String(l || "").trim()));
      if (headerIdx === -1) return [];
      // Table is expected to be:
      // | ... |
      // |---|---|
      // | row |
      const sepIdx = headerIdx + 1;
      if (sepIdx >= lines.length) return [];
      const sep = String(lines[sepIdx] || "").trim();
      if (!sep.startsWith("|") || !sep.includes("---")) return [];
      const out = [];
      for (let i = sepIdx + 1; i < lines.length; i += 1) {
        const row = String(lines[i] || "").trim();
        if (!row) break;
        if (!row.startsWith("|")) break;
        if (!row.includes("|")) break;
        out.push(row);
      }
      return out;
    };

    const splitRow = (row) =>
      row
        .split("|")
        .map((c) => c.trim())
        .filter((c, idx, arr) => !(idx === 0 || idx === arr.length - 1));

    const normalizedHeader = (line) => String(line || "").trim().toLowerCase().replace(/\s+/g, " ");

    // Prefer the executive control table (accept legacy/new header variants).
    const controlRows = parseTable((l) => {
      const header = normalizedHeader(l);
      return (
        header === "| control id | category | attestation | notes |"
        || header === "| control id | attestation | notes |"
        || header === "| control id | attestation | notes (if false/unknown) |"
      );
    });
    if (controlRows.length) {
      return controlRows
        .map(splitRow)
        .map((cols) => {
          const hasCategory = cols.length >= 4;
          const id = String(cols[0] || "").trim();
          const category = hasCategory ? String(cols[1] || "").trim() : "";
          const attestation = String(cols[hasCategory ? 2 : 1] || "").trim();
          const notes = String(cols[hasCategory ? 3 : 2] || "").trim();
          const parts = [];
          if (id) parts.push(`[${id}]`);
          if (category) parts.push(category);
          if (attestation) parts.push(`=> ${attestation}`);
          if (notes) parts.push(`(${notes})`);
          return parts.join(" ").trim();
        })
        .filter(Boolean);
    }

    // Fall back to a single-column attestation table.
    const attestationRows = parseTable((l) => l.toLowerCase() === "| attestation |");
    if (attestationRows.length) {
      return attestationRows.map(splitRow).map((cols) => String(cols[0] || "").trim()).filter(Boolean);
    }

    // Final fallback: line-per-item (legacy behavior).
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
  };

  const saveDoc = async () => {
    if (!wb.projectId) return;
    const title = (els.workbenchTitle?.value || "").trim() || null;
    const content = els.workbenchContent?.value || "";
    setStatusText("Saving...");
    try {
      if (wb.docType === "checklist") {
        const monthKey = els.workbenchMonth?.value || currentMonthKey();
        const items = extractChecklistItems(content);
        await api("/workbench/checklist/save", {
          method: "POST",
          body: JSON.stringify({ project_id: wb.projectId, month_key: monthKey, items }),
        });
        setStatusText("Saved.");
        setTimeout(() => setStatusText(""), 1200);
        return;
      }

      const doc = await api(`/workbench/docs/${wb.docType}/save`, {
        method: "POST",
        body: JSON.stringify({ project_id: wb.projectId, title, content }),
      });
      wb.revisionId = doc?.revision_id || "";
      wb.docState = doc?.state || "draft";
      wb.approvalState = doc?.approval_state || wb.approvalState;
      setMeta();
      await loadRevisions();
      setStatusText("Saved.");
      setTimeout(() => setStatusText(""), 1200);
    } catch (err) {
      setStatusText("");
      throw err;
    }
  };

  const validateDoc = async () => {
    const content = els.workbenchContent?.value || "";
    const result = await api("/workbench/validate", { method: "POST", body: JSON.stringify({ doc_type: wb.docType, content }) });
    const errs = result?.errors || [];
    if (!errs.length) {
      renderWarnings(["No issues found."], "Validation");
      return true;
    }
    renderWarnings(errs.map((e) => e.message || JSON.stringify(e)), "Validation");
    return false;
  };

  const refineDoc = async () => {
    if (!wb.projectId) return;
    const content = els.workbenchContent?.value || "";
    const assist = els.workbenchAssist?.value || "light";

    if (wb.docType === "checklist") {
      await generateChecklist();
      return;
    }

    clearSuggestions();
    setStatusText("Refining...");
    try {
      const result = await api("/workbench/refine", {
        method: "POST",
        body: JSON.stringify({ doc_type: wb.docType, project_id: wb.projectId, content, assist_level: assist }),
        timeoutMs: AI_CHAT_TIMEOUT_MS,
      });
      if (els.workbenchSummary) els.workbenchSummary.textContent = result?.summary || "";
      renderQuestions(result?.questions || []);
      renderWarnings(result?.warnings || []);
      const patch = Array.isArray(result?.patches) ? result.patches.find((p) => p.op === "replace_document" && p.content) : null;
      if (patch && patch.content) {
        wb.pendingPatch = patch;
        if (els.workbenchApply) els.workbenchApply.disabled = false;
      }
    } catch (err) {
      setStatusText("");
      throw err;
    } finally {
      if (els.workbenchStatus?.textContent === "Refining...") setStatusText("");
    }
  };

  const applySuggestion = () => {
    if (!wb.pendingPatch || !wb.pendingPatch.content) return;
    els.workbenchContent.value = wb.pendingPatch.content;
    clearSuggestions();
    setStatusText("Applied.");
    setTimeout(() => setStatusText(""), 900);
  };

  const finalizeDoc = async () => {
    if (!wb.revisionId) {
      setStatusText("Save before finalizing.");
      setTimeout(() => setStatusText(""), 1200);
      return;
    }
    setStatusText("Finalizing...");
    try {
      const doc = await api(`/workbench/docs/${wb.docType}/finalize`, {
        method: "POST",
        body: JSON.stringify({ revision_id: wb.revisionId }),
      });
      wb.docState = doc?.state || "final";
      wb.approvalState = doc?.approval_state || wb.approvalState;
      setMeta();
      await loadRevisions();
      setStatusText("Final.");
      setTimeout(() => setStatusText(""), 900);
    } catch (err) {
      setStatusText("");
      throw err;
    }
  };

  const sowApproval = async (action) => {
    if (!wb.revisionId) return;
    const note = (els.workbenchSowNote?.value || "").trim() || null;
    setStatusText("Updating approval...");
    try {
      const doc = await api(`/workbench/docs/sow/${action}`, {
        method: "POST",
        body: JSON.stringify({ revision_id: wb.revisionId, note }),
      });
      wb.approvalState = doc?.approval_state || wb.approvalState;
      setMeta();
      await loadRevisions();
    } finally {
      setStatusText("");
    }
  };

  const generateChecklist = async () => {
    if (!wb.projectId) return;
    if (els.workbenchMonth && !els.workbenchMonth.value) els.workbenchMonth.value = currentMonthKey();
    const monthKey = els.workbenchMonth?.value || currentMonthKey();
    clearSuggestions();
    setStatusText("Generating...");
    try {
      const result = await api("/workbench/checklist/generate", {
        method: "POST",
        body: JSON.stringify({ project_id: wb.projectId, month_key: monthKey }),
        timeoutMs: AI_CHAT_TIMEOUT_MS,
      });
      const markdown = typeof result?.markdown === "string" ? result.markdown.trim() : "";
      if (markdown) {
        els.workbenchContent.value = markdown;
      } else {
        const list = result?.checklist || [];
        els.workbenchContent.value = Array.isArray(list) ? list.map((l) => String(l || "").trim()).filter(Boolean).join("\n") : "";
      }
      if (els.workbenchSummary) els.workbenchSummary.textContent = result?.summary || "";
      renderQuestions(result?.questions || []);
      renderWarnings(result?.warnings || []);
      setStatusText("");
    } catch (err) {
      setStatusText("");
      throw err;
    }
  };

  // Events
  els.workbenchProject.addEventListener("change", async () => {
    await setProjectId(els.workbenchProject.value);
  });
  docTabs.forEach((btn) =>
    btn.addEventListener("click", async () => {
      await setDocType(btn.dataset.doc);
    })
  );
  els.workbenchLoadTemplate?.addEventListener("click", async () => {
    if (!wb.projectId || wb.docType === "checklist") return;
    const tpl = await ensureTemplateLoaded(wb.docType);
    wb.revisionId = "";
    wb.docState = "draft";
    wb.approvalState = "draft";
    if (els.workbenchTitle) els.workbenchTitle.value = "";
    els.workbenchContent.value = fillTemplate(tpl?.template || "");
    setMeta();
    clearSuggestions();
  });
  els.workbenchValidate?.addEventListener("click", async () => {
    try {
      await validateDoc();
    } catch (err) {
      console.warn("Workbench validate failed", err);
      setStatusText(err?.message || "Validate failed.");
    }
  });
  els.workbenchDownloadRendered?.addEventListener("click", () => {
    try {
      downloadRenderedDoc();
    } catch (err) {
      console.warn("Workbench rendered download failed", err);
      setStatusText(err?.message || "Rendered download failed.");
    }
  });
  els.workbenchRefine?.addEventListener("click", async () => {
    try {
      await refineDoc();
    } catch (err) {
      console.warn("Workbench refine failed", err);
      setStatusText(err?.message || "Refine failed.");
    }
  });
  els.workbenchSave?.addEventListener("click", async () => {
    try {
      await saveDoc();
    } catch (err) {
      console.warn("Workbench save failed", err);
      setStatusText(err?.message || "Save failed.");
    }
  });
  els.workbenchFinalize?.addEventListener("click", async () => {
    try {
      await finalizeDoc();
    } catch (err) {
      console.warn("Workbench finalize failed", err);
      const detail = err?.message || "Finalize failed.";
      setStatusText(detail === "approval_required" ? "SOW requires approval first." : detail);
    }
  });
  els.workbenchApply?.addEventListener("click", () => applySuggestion());
  els.workbenchGenerateChecklist?.addEventListener("click", async () => {
    try {
      await generateChecklist();
    } catch (err) {
      console.warn("Checklist generate failed", err);
      setStatusText(err?.message || "Generate failed.");
    }
  });
  els.workbenchSowRequest?.addEventListener("click", async () => sowApproval("request-approval"));
  els.workbenchSowApprove?.addEventListener("click", async () => sowApproval("approve"));
  els.workbenchSowReject?.addEventListener("click", async () => sowApproval("reject"));

  // Expose a render hook for view activation / data refresh.
  wb.render = () => {
    renderProjectOptions();
    setMeta();
    // Ensure month defaults are applied even before checklist tab is selected.
    if (els.workbenchMonth && !els.workbenchMonth.value) {
      els.workbenchMonth.value = currentMonthKey();
    }
    // On first render, load the selected doc.
    if (!wb._initialized) {  // eslint-disable-line no-underscore-dangle
      wb._initialized = true;
      setDocType(wb.docType);
    }
  };
}

function bindStructureStudioUI() {
  if (!els.structureProject || !els.structureDraftList) return;

  const makeDraftId = () => `draft-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const studio = {
    projectId: "",
    decompositionLevel: "simple",
    context: null,
    draft: { solutions: [], subcomponents: [] },
    selectedItemId: "",
    bulkSelectedIds: new Set(),
    acceptedSolutionIds: new Set(),
    acceptedSubcomponentIds: new Set(),
    discardedSolutionIds: new Set(),
    discardedSubcomponentIds: new Set(),
    refineTargetId: "",
    userEditedFieldsByItem: {},
    chatHistory: [],
    refining: false,
    render: null,
  };
  state.structureStudio = studio;

  const setStatusText = (text) => {
    if (els.structureStatus) els.structureStatus.textContent = text || "";
  };

  const setRefiningState = (refining, message = "AI Assistant is refining draft items...") => {
    studio.refining = !!refining;
    if (els.structureRefineBusy) {
      els.structureRefineBusy.classList.toggle("hidden", !studio.refining);
    }
    if (els.structureRefineBusyText) {
      els.structureRefineBusyText.textContent = studio.refining ? (message || "AI Assistant is refining draft items...") : "";
    }
    if (els.structureProject) els.structureProject.disabled = studio.refining;
    if (els.structureDecompositionLevel) els.structureDecompositionLevel.disabled = studio.refining;
    if (els.structureGenerate) els.structureGenerate.disabled = studio.refining;
    if (els.structureCommit) els.structureCommit.disabled = studio.refining;
    if (els.structureRefineSubmit) {
      els.structureRefineSubmit.disabled = studio.refining;
      els.structureRefineSubmit.textContent = studio.refining ? "Refining..." : "Run Detailed Refinement";
    }
    if (els.structureRefineInput) {
      els.structureRefineInput.disabled = studio.refining;
    }
    if (els.structureRefineCancel) {
      els.structureRefineCancel.disabled = studio.refining;
    }
    if (els.structureRefineModalBusy) {
      els.structureRefineModalBusy.classList.toggle("hidden", !studio.refining);
    }
    if (els.structureRefineModalBusyText) {
      els.structureRefineModalBusyText.textContent = studio.refining
        ? (message || "AI Assistant is refining your request...")
        : "AI Assistant is refining your request...";
    }
  };

  const setupSourcesResizer = () => {
    const grid = els.structureGrid;
    const resizer = els.structureSourcesResizer;
    if (!grid || !resizer || resizer._bound) return;
    resizer._bound = true;

    const STORAGE_KEY = "jira-lite-structure-sources-width";
    const DEFAULT_WIDTH = 320;
    const MIN_WIDTH = 280;
    const MAX_WIDTH_HARD = 760;
    const MIN_DRAFT_WIDTH = 320;
    const RESIZER_WIDTH = 10;
    const GRID_GAP_ALLOWANCE = 24;

    const isMobileLayout = () => window.matchMedia("(max-width: 980px)").matches;

    const readCurrentWidth = () => {
      const sources = grid.querySelector(".structure-sources");
      if (sources) return Math.round(sources.getBoundingClientRect().width);
      const raw = getComputedStyle(grid).getPropertyValue("--structure-sources-width");
      const parsed = Number(String(raw || "").replace("px", "").trim());
      return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_WIDTH;
    };

    const applyWidth = (requestedWidth, persist = true) => {
      if (isMobileLayout()) return;
      const gridWidth = grid.getBoundingClientRect().width || 0;
      const editor = grid.querySelector(".structure-editor");
      const editorWidth = editor ? Math.round(editor.getBoundingClientRect().width || 360) : 0;
      const availableMax = gridWidth - editorWidth - MIN_DRAFT_WIDTH - RESIZER_WIDTH - GRID_GAP_ALLOWANCE;
      const computedMax = Number.isFinite(availableMax) ? Math.floor(availableMax) : MAX_WIDTH_HARD;
      const maxWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH_HARD, computedMax));
      const numericRequested = Number(requestedWidth);
      const fallback = readCurrentWidth();
      const next = Number.isFinite(numericRequested) ? numericRequested : fallback;
      const clamped = Math.max(MIN_WIDTH, Math.min(maxWidth, Math.round(next)));
      grid.style.setProperty("--structure-sources-width", `${clamped}px`);
      resizer.setAttribute("aria-valuenow", String(clamped));
      if (!persist) return;
      try {
        localStorage.setItem(STORAGE_KEY, String(clamped));
      } catch (error) {
        console.warn("Unable to save Structure Studio pane width", error);
      }
    };

    let storedWidth = DEFAULT_WIDTH;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = Number(raw);
      if (Number.isFinite(parsed) && parsed > 0) {
        storedWidth = parsed;
      }
    } catch (error) {
      console.warn("Unable to read Structure Studio pane width", error);
    }
    applyWidth(storedWidth, false);

    const onWindowResize = () => {
      if (isMobileLayout()) return;
      applyWidth(readCurrentWidth(), false);
    };
    window.addEventListener("resize", onWindowResize);

    resizer.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || isMobileLayout()) return;
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = readCurrentWidth();
      let stopped = false;

      const stopResize = () => {
        if (stopped) return;
        stopped = true;
        document.body.classList.remove("structure-resize-active");
        document.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerup", stopResize);
        document.removeEventListener("pointercancel", stopResize);
        applyWidth(readCurrentWidth(), true);
      };

      const onPointerMove = (moveEvent) => {
        const delta = moveEvent.clientX - startX;
        applyWidth(startWidth + delta, false);
      };

      document.body.classList.add("structure-resize-active");
      document.addEventListener("pointermove", onPointerMove);
      document.addEventListener("pointerup", stopResize);
      document.addEventListener("pointercancel", stopResize);
    });
  };
  setupSourcesResizer();

  const normalizeDraftItem = (item, fallbackKind = "solution") => {
    const kind = (item?.kind || fallbackKind || "solution").toLowerCase() === "subcomponent" ? "subcomponent" : "solution";
    return {
      draft_id: item?.draft_id || makeDraftId(),
      kind,
      name: item?.name || item?.solution_name || item?.subcomponent_name || "",
      description: item?.description || "",
      parent_solution_draft_id: item?.parent_solution_draft_id || null,
      status: "draft",
      user_edited_fields: Array.isArray(item?.user_edited_fields) ? item.user_edited_fields : [],
      assumptions: Array.isArray(item?.assumptions) ? item.assumptions : [],
      evidence: Array.isArray(item?.evidence) ? item.evidence : [],
      confidence: item?.confidence || "",
    };
  };

  const findItem = (draftId) => {
    const inSolutions = studio.draft.solutions.find((item) => item.draft_id === draftId);
    if (inSolutions) return inSolutions;
    return studio.draft.subcomponents.find((item) => item.draft_id === draftId) || null;
  };

  const allDraftItems = () => [...(studio.draft.solutions || []), ...(studio.draft.subcomponents || [])];

  const isAcceptedItem = (item) => {
    if (!item) return false;
    return item.kind === "solution"
      ? studio.acceptedSolutionIds.has(item.draft_id)
      : studio.acceptedSubcomponentIds.has(item.draft_id);
  };

  const isDiscardedItem = (item) => {
    if (!item) return false;
    return item.kind === "solution"
      ? studio.discardedSolutionIds.has(item.draft_id)
      : studio.discardedSubcomponentIds.has(item.draft_id);
  };

  const pruneBulkSelection = () => {
    const validIds = new Set(allDraftItems().map((item) => item.draft_id));
    studio.bulkSelectedIds = new Set(Array.from(studio.bulkSelectedIds).filter((id) => validIds.has(id)));
  };

  const updateCommitCallToAction = () => {
    if (!els.structureCommit) return;
    const acceptedCount = studio.acceptedSolutionIds.size + studio.acceptedSubcomponentIds.size;
    const hasAccepted = acceptedCount > 0;
    if (!els.structureCommit.dataset.baseLabel) {
      els.structureCommit.dataset.baseLabel = (els.structureCommit.textContent || "Commit Selected Items").trim();
    }
    const baseLabel = els.structureCommit.dataset.baseLabel || "Commit Selected Items";
    els.structureCommit.classList.toggle("secondary", !hasAccepted);
    els.structureCommit.classList.toggle("primary", hasAccepted);
    els.structureCommit.classList.toggle("commit-ready", hasAccepted);
    els.structureCommit.textContent = hasAccepted ? `${baseLabel} (${acceptedCount})` : baseLabel;
  };

  const renderBulkSelectionState = () => {
    pruneBulkSelection();
    const refining = !!studio.refining;
    const count = studio.bulkSelectedIds.size;
    if (els.structureBulkSelectionCount) {
      els.structureBulkSelectionCount.textContent = `${count} selected`;
    }
    if (els.structureBulkAccept) els.structureBulkAccept.disabled = refining || count === 0;
    if (els.structureBulkDiscard) els.structureBulkDiscard.disabled = refining || count === 0;
    if (els.structureBulkClear) els.structureBulkClear.disabled = refining || count === 0;
    if (els.structureBulkSelectAll) {
      const total = allDraftItems().length;
      els.structureBulkSelectAll.disabled = refining || total === 0 || count === total;
    }
    updateCommitCallToAction();
  };

  const itemStatusClass = (item) => {
    if (!item) return "";
    const accepted = isAcceptedItem(item);
    const discarded = isDiscardedItem(item);
    if (accepted) return "accepted";
    if (discarded) return "discarded";
    return "";
  };

  const setSelection = (draftId) => {
    studio.selectedItemId = draftId || "";
    renderSelectedItem();
    renderDraftList();
  };

  const markItem = (item, mode, shouldRender = true) => {
    if (!item) return;
    const isAccept = mode === "accept";
    if (item.kind === "solution") {
      if (isAccept) {
        studio.acceptedSolutionIds.add(item.draft_id);
        studio.discardedSolutionIds.delete(item.draft_id);
      } else {
        studio.discardedSolutionIds.add(item.draft_id);
        studio.acceptedSolutionIds.delete(item.draft_id);
      }
    } else {
      if (isAccept) {
        studio.acceptedSubcomponentIds.add(item.draft_id);
        studio.discardedSubcomponentIds.delete(item.draft_id);
      } else {
        studio.discardedSubcomponentIds.add(item.draft_id);
        studio.acceptedSubcomponentIds.delete(item.draft_id);
      }
    }
    studio.bulkSelectedIds.delete(item.draft_id);
    if (shouldRender) {
      renderDraftList();
      renderSelectedItem();
      renderBulkSelectionState();
    }
  };

  const closeRefineModal = () => {
    if (studio.refining) return;
    studio.refineTargetId = "";
    if (els.structureRefineModal) {
      els.structureRefineModal.classList.add("hidden");
    }
    if (els.structureRefineInput) {
      els.structureRefineInput.value = "";
    }
  };

  const openRefineModal = (draftId) => {
    if (studio.refining) return;
    const target = findItem(draftId || studio.selectedItemId);
    if (!target) {
      setStatusText("Select a draft item to refine.");
      return;
    }
    studio.refineTargetId = target.draft_id;
    if (studio.selectedItemId !== target.draft_id) {
      setSelection(target.draft_id);
    }
    if (els.structureRefineModalTitle) {
      const kind = target.kind === "subcomponent" ? "Sub-component" : "Solution";
      const name = (target.name || "").trim() || "Selected item";
      els.structureRefineModalTitle.textContent = `Detailed Refinement · ${kind}: ${name}`;
    }
    if (els.structureRefineInput) {
      const kind = target.kind === "subcomponent" ? "sub-component" : "solution";
      const name = (target.name || "").trim() || "selected item";
      els.structureRefineInput.value = "";
      els.structureRefineInput.placeholder = `Give detailed guidance for ${kind} "${name}"`;
    }
    if (els.structureRefineModal) {
      els.structureRefineModal.classList.remove("hidden");
    }
    setTimeout(() => {
      els.structureRefineInput?.focus();
    }, 0);
  };

  const renderContext = () => {
    const ctx = studio.context || {};
    const suff = ctx.sufficiency || {};
    if (els.structureSufficiency) {
      const label = suff.status ? String(suff.status).toUpperCase() : "NOT EVALUATED";
      els.structureSufficiency.textContent = label;
    }
    if (els.structureMissing) {
      const missing = Array.isArray(suff.missing) ? suff.missing : [];
      if (missing.length) {
        els.structureMissing.innerHTML = missing.map((item) => `<div>• ${escapeHtml(item)}</div>`).join("");
      } else {
        els.structureMissing.innerHTML = "<div>Inputs look sufficient.</div>";
      }
    }

    const charter = ctx?.sources?.charter || null;
    const plan = ctx?.sources?.plan || null;
    if (els.structureCharterMeta) {
      if (!charter) {
        els.structureCharterMeta.textContent = "No charter";
      } else {
        const createdAt = charter.created_at ? new Date(charter.created_at).toLocaleString() : "";
        const rev = charter.revision_id ? `Rev ${String(charter.revision_id).slice(0, 8)}` : "No revision";
        els.structureCharterMeta.textContent = `${rev}${createdAt ? ` • ${createdAt}` : ""}`;
      }
    }
    if (els.structurePlanMeta) {
      if (!plan) {
        els.structurePlanMeta.textContent = "No plan";
      } else {
        const createdAt = plan.created_at ? new Date(plan.created_at).toLocaleString() : "";
        const rev = plan.revision_id ? `Rev ${String(plan.revision_id).slice(0, 8)}` : "No revision";
        els.structurePlanMeta.textContent = `${rev}${createdAt ? ` • ${createdAt}` : ""}`;
      }
    }
    if (els.structureCharterContent) els.structureCharterContent.value = charter?.content || "";
    if (els.structurePlanContent) els.structurePlanContent.value = plan?.content || "";
  };

  const renderProjectOptions = () => {
    const projects = state.projects.slice().sort((a, b) => (a.project_name || "").localeCompare(b.project_name || ""));
    const prior = els.structureProject.value || studio.projectId;
    els.structureProject.innerHTML = projects.map((p) => `<option value="${p.project_id}">${escapeHtml(p.project_name || "Project")}</option>`).join("");
    if (studio.projectId && projects.some((p) => p.project_id === studio.projectId)) {
      els.structureProject.value = studio.projectId;
    } else if (prior && projects.some((p) => p.project_id === prior)) {
      studio.projectId = prior;
      els.structureProject.value = prior;
    } else if (projects.length) {
      studio.projectId = projects[0].project_id;
      els.structureProject.value = studio.projectId;
    } else {
      studio.projectId = "";
    }
  };

  const renderDecompositionLevel = () => {
    const selected = studio.decompositionLevel === "detailed" ? "detailed" : "simple";
    studio.decompositionLevel = selected;
    if (els.structureDecompositionLevel) {
      els.structureDecompositionLevel.value = selected;
    }
  };

  const ensureSelectedItem = () => {
    if (studio.selectedItemId && findItem(studio.selectedItemId)) return;
    const first = studio.draft.solutions[0] || studio.draft.subcomponents[0] || null;
    studio.selectedItemId = first?.draft_id || "";
  };

  const renderDraftList = () => {
    if (!els.structureDraftList) return;
    const solutions = studio.draft.solutions || [];
    const subcomponents = studio.draft.subcomponents || [];
    pruneBulkSelection();
    if (!solutions.length && !subcomponents.length) {
      els.structureDraftList.innerHTML = "<p class='muted'>No draft items yet. Generate a draft structure.</p>";
      renderBulkSelectionState();
      return;
    }

    const renderItemCard = (item, kindLabel, isChild = false) => {
      const refining = !!studio.refining;
      const isSelected = studio.selectedItemId === item.draft_id;
      const statusClass = itemStatusClass(item);
      const selected = isSelected ? "selected" : "";
      const bulkSelected = studio.bulkSelectedIds.has(item.draft_id) ? "bulk-selected" : "";
      const childClass = isChild ? "structure-item-child" : "";
      const checked = studio.bulkSelectedIds.has(item.draft_id) ? "checked" : "";
      const checkboxDisabled = refining ? "disabled" : "";
      const acceptDisabled = isAcceptedItem(item) || refining ? "disabled" : "";
      const discardDisabled = isDiscardedItem(item) || refining ? "disabled" : "";
      const refineDisabled = refining ? "disabled" : "";
      const acceptReadyClass = isSelected && !refining && !isAcceptedItem(item) ? "accept-ready" : "";
      return `<div class="structure-item ${statusClass} ${selected} ${bulkSelected} ${childClass}" data-draft-id="${item.draft_id}">
        <div class="structure-item-head">
          <label class="structure-item-select">
            <input
              type="checkbox"
              data-structure-action="bulk-toggle"
              data-draft-id="${item.draft_id}"
              ${checked}
              ${checkboxDisabled}
              aria-label="Select ${kindLabel}"
            />
            <span class="structure-item-kind">${kindLabel}</span>
          </label>
          <div class="structure-item-actions">
            <button type="button" class="secondary structure-item-action ${acceptReadyClass}" data-structure-action="accept" data-draft-id="${item.draft_id}" ${acceptDisabled}>Accept</button>
            <button type="button" class="secondary structure-item-action" data-structure-action="discard" data-draft-id="${item.draft_id}" ${discardDisabled}>Discard</button>
            <button type="button" class="secondary structure-item-action" data-structure-action="refine" data-draft-id="${item.draft_id}" ${refineDisabled}>Refine</button>
          </div>
        </div>
        <div class="structure-item-title">${escapeHtml(item.name || `(unnamed ${kindLabel.toLowerCase()})`)}</div>
        <div class="structure-item-meta">${escapeHtml(item.description || "")}</div>
      </div>`;
    };

    let html = "";
    const usedSubIds = new Set();
    solutions.forEach((solution) => {
      html += renderItemCard(solution, "Solution");

      const children = subcomponents.filter((sub) => sub.parent_solution_draft_id === solution.draft_id);
      children.forEach((sub) => {
        usedSubIds.add(sub.draft_id);
        html += renderItemCard(sub, "Sub-component", true);
      });
    });

    subcomponents
      .filter((sub) => !usedSubIds.has(sub.draft_id))
      .forEach((sub) => {
        html += renderItemCard(sub, "Sub-component");
      });

    els.structureDraftList.innerHTML = html;
    renderBulkSelectionState();
  };

  const renderSelectedItem = () => {
    ensureSelectedItem();
    const item = findItem(studio.selectedItemId);
    const disabled = !item;
    const refining = !!studio.refining;
    const controlsDisabled = disabled || refining;
    if (els.structureItemName) {
      els.structureItemName.disabled = controlsDisabled;
      els.structureItemName.value = item?.name || "";
    }
    if (els.structureItemDescription) {
      els.structureItemDescription.disabled = controlsDisabled;
      els.structureItemDescription.value = item?.description || "";
    }
    if (els.structureAccept) els.structureAccept.disabled = controlsDisabled;
    if (els.structureDiscard) els.structureDiscard.disabled = controlsDisabled;
    if (els.structureRefineSelected) els.structureRefineSelected.disabled = controlsDisabled;
    if (els.structureChatInput) {
      const kindLabel = item?.kind === "subcomponent" ? "sub-component" : "solution";
      const targetName = (item?.name || "").trim() || "selected item";
      els.structureChatInput.disabled = controlsDisabled;
      els.structureChatInput.placeholder = controlsDisabled
        ? refining
          ? "AI Assistant is refining. Please wait..."
          : "Select a draft item, then submit feedback to refine it."
        : `Refine selected ${kindLabel}: ${targetName}`;
    }
    const chatSubmit = els.structureChatForm?.querySelector('button[type="submit"]');
    if (chatSubmit) {
      chatSubmit.disabled = controlsDisabled;
      if (!chatSubmit.dataset.defaultLabel) {
        chatSubmit.dataset.defaultLabel = chatSubmit.textContent || "Refine";
      }
      chatSubmit.textContent = refining ? "Refining..." : chatSubmit.dataset.defaultLabel;
    }
    if (els.structureDraftList) {
      els.structureDraftList.setAttribute("aria-busy", refining ? "true" : "false");
    }
  };

  const normalizeDraftPayload = (draft) => {
    const solutionsRaw = Array.isArray(draft?.solutions) ? draft.solutions : [];
    const subRaw = Array.isArray(draft?.subcomponents) ? draft.subcomponents : [];
    const solutions = solutionsRaw.map((item) => normalizeDraftItem(item, "solution"));
    const fallbackSolutionId = solutions[0]?.draft_id || null;
    const subcomponents = subRaw
      .map((item) => normalizeDraftItem(item, "subcomponent"))
      .map((item) => ({
        ...item,
        parent_solution_draft_id: item.parent_solution_draft_id || fallbackSolutionId,
      }))
      .filter((item) => !!item.parent_solution_draft_id);
    return { solutions, subcomponents };
  };

  const loadContext = async () => {
    if (!studio.projectId) return;
    setStatusText("Loading source inputs...");
    try {
      const ctx = await api(`/workbench/structure-studio/context?project_id=${encodeURIComponent(studio.projectId)}`);
      studio.context = ctx || null;
      renderContext();
    } catch (err) {
      console.warn("Structure Studio context load failed", err);
      setStatusText(err?.message || "Failed to load source inputs.");
      return;
    }
    setStatusText("");
  };

  const resetDraftState = () => {
    setRefiningState(false);
    studio.draft = { solutions: [], subcomponents: [] };
    studio.selectedItemId = "";
    studio.bulkSelectedIds = new Set();
    studio.acceptedSolutionIds = new Set();
    studio.acceptedSubcomponentIds = new Set();
    studio.discardedSolutionIds = new Set();
    studio.discardedSubcomponentIds = new Set();
    studio.refineTargetId = "";
    studio.userEditedFieldsByItem = {};
    studio.chatHistory = [];
    if (els.structureChat) els.structureChat.innerHTML = "";
    closeRefineModal();
    renderDraftList();
    renderSelectedItem();
    renderBulkSelectionState();
  };

  const generateDraft = async () => {
    if (!studio.projectId) return;
    setStatusText("Generating draft structure...");
    try {
      const result = await api("/workbench/structure-studio/generate", {
        method: "POST",
        body: JSON.stringify({
          project_id: studio.projectId,
          allow_minimal_on_insufficient: true,
          decomposition_level: studio.decompositionLevel,
        }),
        timeoutMs: AI_CHAT_TIMEOUT_MS,
      });
      studio.context = {
        ...(studio.context || {}),
        sufficiency: result?.sufficiency || studio.context?.sufficiency || null,
      };
      renderContext();
      studio.draft = normalizeDraftPayload(result?.draft || {});
      studio.bulkSelectedIds = new Set();
      studio.acceptedSolutionIds = new Set();
      studio.acceptedSubcomponentIds = new Set();
      studio.discardedSolutionIds = new Set();
      studio.discardedSubcomponentIds = new Set();
      studio.userEditedFieldsByItem = {};
      studio.selectedItemId = studio.draft.solutions[0]?.draft_id || studio.draft.subcomponents[0]?.draft_id || "";
      renderDraftList();
      renderSelectedItem();
      renderBulkSelectionState();
      const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
      if (warnings.length) {
        setStatusText(warnings.join(" "));
      } else {
        setStatusText(result?.minimal_draft ? "Minimal draft generated due to limited input detail." : "Draft generated.");
      }
    } catch (err) {
      console.warn("Structure Studio generation failed", err);
      setStatusText(err?.message || "Generate failed.");
    }
  };

  const addChatMessage = (role, text) => {
    if (!els.structureChat) return;
    studio.chatHistory.push({ role, content: text || "" });
    const div = document.createElement("div");
    div.className = `structure-chat-message ${role}`;
    div.textContent = text || "";
    els.structureChat.appendChild(div);
    els.structureChat.scrollTop = els.structureChat.scrollHeight;
  };

  const applyOperations = (operations) => {
    const allItemsById = {};
    studio.draft.solutions.forEach((item) => {
      allItemsById[item.draft_id] = item;
    });
    studio.draft.subcomponents.forEach((item) => {
      allItemsById[item.draft_id] = item;
    });

    const upsertSolution = (item) => {
      const normalized = normalizeDraftItem(item, "solution");
      const idx = studio.draft.solutions.findIndex((row) => row.draft_id === normalized.draft_id);
      if (idx === -1) studio.draft.solutions.push(normalized);
      else studio.draft.solutions[idx] = { ...studio.draft.solutions[idx], ...normalized };
      allItemsById[normalized.draft_id] = normalized;
    };
    const upsertSubcomponent = (item) => {
      const normalized = normalizeDraftItem(item, "subcomponent");
      const fallbackSolutionId = studio.draft.solutions[0]?.draft_id || null;
      normalized.parent_solution_draft_id = normalized.parent_solution_draft_id || fallbackSolutionId;
      if (!normalized.parent_solution_draft_id) return;
      const idx = studio.draft.subcomponents.findIndex((row) => row.draft_id === normalized.draft_id);
      if (idx === -1) studio.draft.subcomponents.push(normalized);
      else studio.draft.subcomponents[idx] = { ...studio.draft.subcomponents[idx], ...normalized };
      allItemsById[normalized.draft_id] = normalized;
    };

    (operations || []).forEach((operation) => {
      const op = String(operation?.op || "").trim();
      if (!op) return;

      if (op === "update_item_fields") {
        const itemId = operation?.item_id || operation?.target_id;
        const fields = operation?.fields || {};
        const target = allItemsById[itemId];
        if (!target || !fields || typeof fields !== "object") return;
        Object.keys(fields).forEach((key) => {
          if (key === "name") target.name = String(fields[key] || "");
          if (key === "description") target.description = String(fields[key] || "");
          if (key === "parent_solution_draft_id") target.parent_solution_draft_id = String(fields[key] || "") || null;
        });
        return;
      }

      if (op === "discard_item") {
        const itemId = operation?.item_id || operation?.target_id;
        const target = allItemsById[itemId];
        if (target) markItem(target, "discard");
        return;
      }

      if (op === "split_solution") {
        const targetId = operation?.target_id || operation?.item_id;
        const target = allItemsById[targetId];
        if (target) markItem(target, "discard");
        const items = Array.isArray(operation?.items) ? operation.items : [];
        items.forEach((item) => upsertSolution(item));
        return;
      }

      if (op === "add_subcomponent") {
        const items = Array.isArray(operation?.items) ? operation.items : [];
        items.forEach((item) => upsertSubcomponent(item));
      }
    });

    ensureSelectedItem();
    renderDraftList();
    renderSelectedItem();
    renderBulkSelectionState();
  };

  const refineDraft = async (instruction, options = {}) => {
    if (!studio.projectId) return false;
    if (!instruction) return false;
    if (studio.refining) return false;
    if (!studio.draft.solutions.length && !studio.draft.subcomponents.length) {
      setStatusText("Generate a draft before refinement.");
      return false;
    }
    const targetId = String(options?.targetId || studio.selectedItemId || "").trim();
    const detailedMode = !!options?.detailed;
    const selectedItem = findItem(targetId);
    if (!selectedItem) {
      setStatusText("Select a draft item to refine.");
      return false;
    }
    if (studio.selectedItemId !== selectedItem.draft_id) {
      setSelection(selectedItem.draft_id);
    }
    const selectedKind = selectedItem.kind === "subcomponent" ? "sub-component" : "solution";
    const selectedName = (selectedItem.name || "").trim() || "selected item";
    addChatMessage("user", `[${selectedKind}] ${selectedName}${detailedMode ? " [detailed]" : ""}: ${instruction}`);
    setRefiningState(
      true,
      detailedMode
        ? `AI Assistant is running detailed refinement for "${selectedName}"...`
        : `AI Assistant is refining "${selectedName}"...`
    );
    renderDraftList();
    renderSelectedItem();
    renderBulkSelectionState();
    setStatusText(detailedMode ? "Applying detailed targeted refinement..." : "Applying targeted refinement...");
    try {
      const locked = studio.userEditedFieldsByItem || {};
      const result = await api("/workbench/structure-studio/refine", {
        method: "POST",
        body: JSON.stringify({
          project_id: studio.projectId,
          instruction,
          draft: studio.draft,
          target_ids: selectedItem.draft_id ? [selectedItem.draft_id] : [],
          allow_full_regeneration: false,
          locked_fields_by_item: locked,
          decomposition_level: detailedMode ? "detailed" : studio.decompositionLevel,
        }),
        timeoutMs: AI_CHAT_TIMEOUT_MS,
      });
      const operations = Array.isArray(result?.operations) ? result.operations : [];
      applyOperations(operations);
      const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
      const touchedSelected = operations.some((operation) => {
        const itemId = operation?.item_id || operation?.target_id || "";
        if (itemId && itemId === selectedItem.draft_id) return true;
        const items = Array.isArray(operation?.items) ? operation.items : [];
        return items.some((draftItem) => {
          if (!draftItem || typeof draftItem !== "object") return false;
          return (
            draftItem.draft_id === selectedItem.draft_id ||
            draftItem.parent_solution_draft_id === selectedItem.draft_id
          );
        });
      });
      const updatedItem = findItem(selectedItem.draft_id);
      const updatedName = (updatedItem?.name || selectedName).trim() || selectedName;
      const reply = warnings.length
        ? `Applied refinement with warnings: ${warnings.join(" ")}`
        : touchedSelected
          ? `Updated "${updatedName}". Review and accept when ready.`
          : `Applied ${operations.length} targeted edit(s).`;
      addChatMessage("assistant", reply);
      setStatusText(
        warnings.length
          ? warnings.join(" ")
          : touchedSelected
            ? `Updated "${updatedName}". Ready for acceptance.`
            : "Refinement applied."
      );
      return true;
    } catch (err) {
      console.warn("Structure Studio refine failed", err);
      addChatMessage("assistant", err?.message || "Refinement failed.");
      setStatusText(err?.message || "Refinement failed.");
      return false;
    } finally {
      setRefiningState(false);
      renderDraftList();
      renderSelectedItem();
      renderBulkSelectionState();
    }
  };

  const toggleBulkSelection = (draftId, checked) => {
    if (!draftId) return;
    if (checked) {
      studio.bulkSelectedIds.add(draftId);
      if (studio.selectedItemId !== draftId) {
        studio.selectedItemId = draftId;
      }
    } else {
      studio.bulkSelectedIds.delete(draftId);
    }
    renderDraftList();
    renderSelectedItem();
    renderBulkSelectionState();
  };

  const selectAllDraftItems = () => {
    const allIds = allDraftItems().map((item) => item.draft_id).filter(Boolean);
    studio.bulkSelectedIds = new Set(allIds);
    if (!studio.selectedItemId && allIds.length) {
      studio.selectedItemId = allIds[0];
    }
    renderDraftList();
    renderSelectedItem();
    renderBulkSelectionState();
  };

  const clearBulkSelection = () => {
    studio.bulkSelectedIds = new Set();
    renderDraftList();
    renderBulkSelectionState();
  };

  const applyBulkMark = (mode) => {
    const ids = Array.from(studio.bulkSelectedIds);
    if (!ids.length) {
      setStatusText("Select at least one draft item first.");
      return;
    }
    let applied = 0;
    ids.forEach((id) => {
      const item = findItem(id);
      if (!item) return;
      markItem(item, mode, false);
      applied += 1;
    });
    studio.bulkSelectedIds = new Set();
    renderDraftList();
    renderSelectedItem();
    renderBulkSelectionState();
    if (applied) {
      setStatusText(`${mode === "accept" ? "Accepted" : "Discarded"} ${applied} item(s).`);
    }
  };

  const commitSelected = async () => {
    if (!studio.projectId) return;
    if (!studio.acceptedSolutionIds.size && !studio.acceptedSubcomponentIds.size) {
      setStatusText("Select at least one item to commit.");
      return;
    }
    setStatusText("Committing accepted items...");
    try {
      const result = await api("/workbench/structure-studio/commit", {
        method: "POST",
        body: JSON.stringify({
          project_id: studio.projectId,
          draft: studio.draft,
          accepted: {
            solution_ids: Array.from(studio.acceptedSolutionIds),
            subcomponent_ids: Array.from(studio.acceptedSubcomponentIds),
          },
        }),
      });
      const createdSolutions = Array.isArray(result?.created_solutions) ? result.created_solutions.length : 0;
      const createdSubcomponents = Array.isArray(result?.created_subcomponents) ? result.created_subcomponents.length : 0;
      setStatusText(`Committed ${createdSolutions} solution(s) and ${createdSubcomponents} sub-component(s).`);
      resetDraftState();
      await refreshFromServer("all");
      await loadContext();
    } catch (err) {
      console.warn("Structure Studio commit failed", err);
      setStatusText(err?.message || "Commit failed.");
    }
  };

  els.structureProject.addEventListener("change", async () => {
    studio.projectId = els.structureProject.value || "";
    resetDraftState();
    await loadContext();
  });

  els.structureDecompositionLevel?.addEventListener("change", () => {
    const level = (els.structureDecompositionLevel?.value || "simple").toLowerCase();
    studio.decompositionLevel = level === "detailed" ? "detailed" : "simple";
  });

  els.structureGenerate?.addEventListener("click", async () => {
    await generateDraft();
  });

  els.structureCommit?.addEventListener("click", async () => {
    await commitSelected();
  });

  els.structureDraftList.addEventListener("click", (event) => {
    if (studio.refining) return;
    const actionBtn = event.target.closest("[data-structure-action]");
    if (actionBtn) {
      event.preventDefault();
      event.stopPropagation();
      const action = actionBtn.getAttribute("data-structure-action") || "";
      const draftId = actionBtn.getAttribute("data-draft-id") || "";
      if (!draftId) return;
      const item = findItem(draftId);
      if (!item) return;
      if (action === "accept") {
        markItem(item, "accept");
        return;
      }
      if (action === "discard") {
        markItem(item, "discard");
        return;
      }
      if (action === "refine") {
        openRefineModal(draftId);
        return;
      }
      return;
    }

    if (event.target.closest('input[type="checkbox"][data-structure-action="bulk-toggle"]')) {
      return;
    }

    const row = event.target.closest(".structure-item[data-draft-id]");
    if (!row) return;
    const draftId = row.getAttribute("data-draft-id") || "";
    if (!draftId) return;
    setSelection(draftId);
  });

  els.structureDraftList.addEventListener("change", (event) => {
    if (studio.refining) return;
    const checkbox = event.target.closest('input[type="checkbox"][data-structure-action="bulk-toggle"]');
    if (!checkbox) return;
    const draftId = checkbox.getAttribute("data-draft-id") || "";
    if (!draftId) return;
    toggleBulkSelection(draftId, !!checkbox.checked);
  });

  const markEditedField = (draftId, field) => {
    if (!draftId || !field) return;
    if (!studio.userEditedFieldsByItem[draftId]) studio.userEditedFieldsByItem[draftId] = [];
    if (!studio.userEditedFieldsByItem[draftId].includes(field)) studio.userEditedFieldsByItem[draftId].push(field);
  };

  els.structureItemName?.addEventListener("input", () => {
    const item = findItem(studio.selectedItemId);
    if (!item) return;
    item.name = els.structureItemName.value || "";
    markEditedField(item.draft_id, "name");
    renderDraftList();
  });

  els.structureItemDescription?.addEventListener("input", () => {
    const item = findItem(studio.selectedItemId);
    if (!item) return;
    item.description = els.structureItemDescription.value || "";
    markEditedField(item.draft_id, "description");
    renderDraftList();
  });

  els.structureAccept?.addEventListener("click", () => {
    const item = findItem(studio.selectedItemId);
    if (!item) return;
    markItem(item, "accept");
  });

  els.structureDiscard?.addEventListener("click", () => {
    const item = findItem(studio.selectedItemId);
    if (!item) return;
    markItem(item, "discard");
  });

  els.structureBulkSelectAll?.addEventListener("click", () => {
    selectAllDraftItems();
  });

  els.structureBulkClear?.addEventListener("click", () => {
    clearBulkSelection();
  });

  els.structureBulkAccept?.addEventListener("click", () => {
    applyBulkMark("accept");
  });

  els.structureBulkDiscard?.addEventListener("click", () => {
    applyBulkMark("discard");
  });

  els.structureRefineSelected?.addEventListener("click", () => {
    openRefineModal(studio.selectedItemId);
  });

  const submitDetailedRefine = async () => {
    if (studio.refining) return;
    const instruction = (els.structureRefineInput?.value || "").trim();
    if (!instruction) {
      setStatusText("Enter feedback for detailed refinement.");
      return;
    }
    const targetId = studio.refineTargetId || studio.selectedItemId;
    const ok = await refineDraft(instruction, { targetId, detailed: true });
    if (ok) closeRefineModal();
  };

  els.structureRefineForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitDetailedRefine();
  });

  els.structureRefineCancel?.addEventListener("click", () => {
    closeRefineModal();
  });

  els.structureRefineModalClose?.addEventListener("click", () => {
    closeRefineModal();
  });

  els.structureRefineModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => {
    closeRefineModal();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!els.structureRefineModal || els.structureRefineModal.classList.contains("hidden")) return;
    closeRefineModal();
  });

  els.structureChatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const instruction = (els.structureChatInput?.value || "").trim();
    if (!instruction) return;
    els.structureChatInput.value = "";
    await refineDraft(instruction);
  });

  if (els.structureChatInput && els.structureChatInput.tagName === "TEXTAREA") {
    els.structureChatInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        els.structureChatForm?.requestSubmit();
      }
    });
  }

  studio.render = () => {
    renderProjectOptions();
    renderDecompositionLevel();
    renderContext();
    renderDraftList();
    renderSelectedItem();
    if (!studio._initialized) {
      studio._initialized = true;
      loadContext();
    }
  };
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
    case "workbench":
      renderWorkbench();
      break;
    case "structure-studio":
      renderStructureStudio();
      break;
    case "ai":
      renderAI();
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
        <button type="button" class="secondary" data-quick-action="open-ai">AI Assistant</button>
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
      } else if (action === "open-ai") {
        setView("ai");
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
        renderWorkbench();
        renderStructureStudio();
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
      if (typeof state.aiResetChat === "function") {
        state.aiResetChat();
      }
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
          if (typeof state.aiResetChat === "function") state.aiResetChat();
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
  initAI();
  initWorkbench();
  initSubcomponentsWorkbench();
  initStructureStudio();
  const initialView = viewFromHash();
  setView(initialView, { fromHash: true });
  if (!window.location.hash) {
    syncHashForView(initialView, true);
  }
  bootstrapAuth();
}

init();
