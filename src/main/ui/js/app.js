import {
  API_BASE,
  APP_ASSET_VERSION,
  buildApiUrl,
  buildAppUrl,
  buildResetPageUrl,
  buildWsUrl,
  formatDateTime,
  refreshStylesheetVersion,
} from "./shell/paths.js";
import { createShellContext } from "./shell/context.js";
import { createRouterController } from "./shell/router.js";
import { createDataStoreController } from "./shell/data-store.js";
import { createSessionController } from "./shell/session.js";
import {
  LIVE_SYNC_CLOSE_AUTH,
  LIVE_SYNC_CLOSE_BUSY,
  LIVE_SYNC_CLOSE_LIMIT,
  LIVE_SYNC_CLOSE_SPACE,
  createLiveSyncController,
} from "./shell/live-sync.js";

const HOURS_PER_FTE_MONTH = 160;
const HOURS_PER_FTE_CAPACITY = 40;
refreshStylesheetVersion();

async function copyText(value) {
  const text = String(value || "");
  if (!text) throw new Error("Nothing to copy.");
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = text;
  helper.setAttribute("readonly", "readonly");
  helper.style.position = "fixed";
  helper.style.opacity = "0";
  helper.style.pointerEvents = "none";
  document.body.appendChild(helper);
  helper.select();
  helper.setSelectionRange(0, helper.value.length);
  const copied = document.execCommand("copy");
  document.body.removeChild(helper);
  if (!copied) throw new Error("Clipboard copy is not available in this browser.");
}

const els = {
  navButtons: document.querySelectorAll(".nav-btn[data-view]"),
  navAdminSection: document.getElementById("nav-admin-section"),
  views: document.querySelectorAll(".view"),
  status: document.getElementById("connection-status"),
  topbarCreateShell: document.getElementById("topbar-create-shell"),
  topbarCreateToggle: document.getElementById("topbar-create-toggle"),
  topbarCreatePanel: document.getElementById("topbar-create-panel"),
  topbarCreateProject: document.getElementById("topbar-create-project"),
  topbarCreateSolution: document.getElementById("topbar-create-solution"),
  topbarCreateSubcomponent: document.getElementById("topbar-create-subcomponent"),
  spaceSwitcherShell: document.getElementById("space-switcher-shell"),
  spaceSwitcherTrigger: document.getElementById("space-switcher-trigger"),
  spaceSwitcherCurrent: document.getElementById("space-switcher-current"),
  spaceSwitcherMeta: document.getElementById("space-switcher-meta"),
  spaceSwitcherPanel: document.getElementById("space-switcher-panel"),
  spaceSwitcherClose: document.getElementById("space-switcher-close"),
  spaceSwitcherSearch: document.getElementById("space-switcher-search"),
  spaceSwitcherFeedback: document.getElementById("space-switcher-feedback"),
  spaceSwitcherCurrentList: document.getElementById("space-switcher-current-list"),
  spaceSwitcherRecentList: document.getElementById("space-switcher-recent-list"),
  spaceSwitcherAllList: document.getElementById("space-switcher-all-list"),
  currentUser: document.getElementById("current-user"),
  completedVisibilityToggle: document.getElementById("completed-visibility-toggle"),
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
  subcomponentsWorkbenchBulkFeedback: document.getElementById("subcomponents-workbench-bulk-feedback"),
  subcomponentsWorkbenchForm: document.getElementById("subcomponents-workbench-form"),
  subcomponentsWorkbenchFormStatus: document.getElementById("subcomponents-workbench-form-status"),
  subcomponentsWorkbenchDelete: document.getElementById("subcomponents-workbench-delete"),
  subcomponentsWorkbenchReset: document.getElementById("subcomponents-workbench-reset"),
  subcomponentsWorkbenchClose: document.getElementById("subcomponents-workbench-close"),
  subcomponentsWorkbenchContext: document.getElementById("subcomponents-workbench-context"),
  subcomponentsWorkbenchActivity: document.getElementById("subcomponents-workbench-activity"),
  subcomponentsWorkbenchLayout: document.getElementById("subcomponents-workbench-layout"),
  subcomponentsWorkbenchDrawer: document.getElementById("subcomponents-workbench-drawer"),
  projectModal: document.getElementById("project-modal"),
  projectModalClose: document.getElementById("project-modal-close"),
  projectModalTitle: document.getElementById("project-modal-title"),
  solutionModal: document.getElementById("solution-modal"),
  solutionModalClose: document.getElementById("solution-modal-close"),
  solutionModalTitle: document.getElementById("solution-modal-title"),
  subcomponentCreatePickerModal: document.getElementById("subcomponent-create-picker-modal"),
  subcomponentCreatePickerClose: document.getElementById("subcomponent-create-picker-close"),
  subcomponentCreatePickerCancel: document.getElementById("subcomponent-create-picker-cancel"),
  subcomponentCreatePickerForm: document.getElementById("subcomponent-create-picker-form"),
  subcomponentCreatePickerSelect: document.getElementById("subcomponent-create-picker-select"),
  subcomponentCreatePickerStatus: document.getElementById("subcomponent-create-picker-status"),
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
  presetEngineering: document.getElementById("preset-engineering"),
  presetClear: document.getElementById("preset-clear"),
  bulkSelectedCount: document.getElementById("bulk-selected-count"),
  bulkAction: document.getElementById("bulk-action"),
  bulkStatus: document.getElementById("bulk-status"),
  bulkOwner: document.getElementById("bulk-owner"),
  bulkApply: document.getElementById("bulk-apply"),
  bulkFeedback: document.getElementById("bulk-feedback"),
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
  capacityUserFormStatus: document.getElementById("capacity-user-form-status"),
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
  spaceGovernanceShell: document.getElementById("space-governance-shell"),
  spaceCreateModal: document.getElementById("space-create-modal"),
  spaceCreateModalClose: document.getElementById("space-create-modal-close"),
  spaceCreateModalForm: document.getElementById("space-create-modal-form"),
  spaceCreateStatus: document.getElementById("space-create-status"),
  spaceMemberModal: document.getElementById("space-member-modal"),
  spaceMemberModalClose: document.getElementById("space-member-modal-close"),
  spaceMemberModalForm: document.getElementById("space-member-modal-form"),
  spaceMemberModalContext: document.getElementById("space-member-modal-context"),
  spaceMemberStatus: document.getElementById("space-member-status"),
  spaceDirectoryModal: document.getElementById("space-directory-modal"),
  spaceDirectoryModalClose: document.getElementById("space-directory-modal-close"),
  spaceDirectoryModalBody: document.getElementById("space-directory-modal-body"),
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
  subcomponentFormFooter: document.getElementById("subcomponent-form-footer"),
  subcomponentSubmitBtn: document.getElementById("subcomponent-submit-btn"),
  subcomponentFormStatus: document.getElementById("subcomponent-form-status"),
  subcomponentRepoPreview: document.getElementById("subcomponent-repo-preview"),
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

const esc = escapeHtml;

function repoDisplayUrl(value) {
  return String(value || "").trim();
}

function effectiveSubcomponentRepoInfo(solutionId, overrideUrl) {
  const override = repoDisplayUrl(overrideUrl);
  if (override) {
    return { url: override, source: "override" };
  }
  const solution = (state.solutions || []).find((row) => row.solution_id === solutionId);
  const inherited = repoDisplayUrl(solution?.github_repo_url);
  if (inherited) {
    return { url: inherited, source: "inherited" };
  }
  return { url: "", source: "none" };
}

function renderExternalRepoLink(url, { label = "Open Repo", className = "" } = {}) {
  const targetUrl = repoDisplayUrl(url);
  if (!targetUrl) return "";
  const classes = ["repo-external-link", className].filter(Boolean).join(" ");
  return `<a class="${classes}" href="${escapeAttr(targetUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function updateSubcomponentRepoPreview(solutionId, overrideUrl) {
  if (!els.subcomponentRepoPreview) return;
  const { url, source } = effectiveSubcomponentRepoInfo(solutionId, overrideUrl);
  if (!url) {
    els.subcomponentRepoPreview.textContent = "No solution repo set.";
    return;
  }
  const sourceLabel = source === "override" ? "Override repo" : "Inherited repo";
  els.subcomponentRepoPreview.innerHTML = `${escapeHtml(sourceLabel)}: ${renderExternalRepoLink(url, { label: url, className: "repo-external-link-inline" })}`;
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
  spaceSwitching: false,
  spaceSwitcherOpen: false,
  spaceSwitcherQuery: "",
  spaceRecentIds: [],
  spaceFeedback: { text: "", tone: "", timeoutId: null },
  spaceGovernanceNotice: { text: "", tone: "", timeoutId: null },
  spaceAdminSection: "",
  spaceDirectoryQuery: "",
  spaceDirectoryShowArchived: false,
  spaceMembershipActionMenuId: "",
  archivedSpacesById: {},
  spaceMembershipSpaceId: "",
  spaceDirectoryModalOpen: false,
  spaceMembersBySpace: {},
  spaceMembersLoadedBySpace: {},
  globalAdmins: [],
  globalAdminsLoaded: false,
  platformPasswordReset: null,
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
  planningWindowSelectedId: "",
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
  workspacePrefs: { showCompleted: false },
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
  shellStatus: { text: "Loading…", tone: "" },
  liveSync: {
    phase: "idle",
    statusText: "",
    statusTone: "",
    socketSpaceId: "",
    pausedForHidden: false,
  },
  structureStudio: null,
  loadedEntities: new Set(),
};

const IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const IDLE_WARN_MS = 55 * 60 * 1000;
const ACCESS_REFRESH_INTERVAL_MS = 4 * 60 * 1000;
const MASTER_VIEW_STATE_KEY_PREFIX = "sipm-master-filters-v1";
const WORKSPACE_VIEW_PREFS_KEY_PREFIX = "sipm-workspace-prefs-v1";
const CALENDAR_VIEW_STATE_KEY_PREFIX = "sipm-calendar-view-state-v1";
const KANBAN_VIEW_STATE_KEY_PREFIX = "sipm-kanban-view-state-v1";
const TEAM_CAPACITY_VIEW_STATE_KEY_PREFIX = "sipm-team-capacity-view-state-v1";
const PLANNING_WINDOW_VIEW_STATE_KEY_PREFIX = "sipm-planning-window-state-v1";
const SPACE_RECENTS_KEY_PREFIX = "sipm-space-recents-v1";
const SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX = "sipm-subcomponents-workbench-state-v1";
const SUBCOMPONENTS_WORKBENCH_SAVED_VIEWS_KEY_PREFIX = "sipm-subcomponents-workbench-views";
const VALID_DELIVERABLE_PRESETS = new Set(["", "my", "overdue", "blocked", "engineering"]);
const VALID_DELIVERABLE_TYPES = new Set(["", "project", "solution"]);
const VALID_DELIVERABLE_REPO_PRESENCE = new Set(["", "has_repo", "missing_repo"]);
const MASTER_TEXT_FILTER_KEYS = ["project", "sponsor", "solution", "version", "owner", "current_phase", "due", "rag", "status"];
const MASTER_ENGINEERING_HIDDEN_FILTER_KEYS = ["sponsor", "version", "current_phase", "priority", "progress"];
const VALID_SUBCOMPONENTS_WORKBENCH_PRESETS = new Set([
  "all",
  "my",
  "due_soon",
  "overdue",
  "blocked",
  "unassigned",
  "stale",
]);
const RECENT_SPACES_LIMIT = 5;
let idleLastActive = Date.now();
let idleWarned = false;
let idleInterval = null;
let idleListenersBound = false;
let pendingConfirmResolve = null;
let confirmReturnFocusEl = null;
const csvUploadState = {
  kind: "",
  file: null,
};

let routerController = null;
let dataStoreController = null;
let sessionController = null;
let liveSyncController = null;
const ignoreNextRefresh = {
  delete(entity) {
    return dataStoreController.clearIgnoredRefresh(entity);
  },
};

function getRouteModule(view) {
  return routerController.getRouteModule(view);
}

async function ensureRouteModule(view) {
  return routerController.ensureRouteModule(view);
}

function normalizeView(view) {
  return routerController.normalizeView(view);
}

function isAdminView(view) {
  return routerController.isAdminView(view);
}

function userCanAccessAdminViews() {
  return routerController.userCanAccessAdminViews();
}

function canAccessView(view) {
  return routerController.canAccessView(view);
}

function resolveAccessibleView(view) {
  return routerController.resolveAccessibleView(view);
}

function appRelativePath(pathname = window.location.pathname) {
  return routerController.appRelativePath(pathname);
}

function routePathForView(view) {
  return routerController.routePathForView(view);
}

function viewHref(view) {
  return routerController.viewHref(view);
}

function isResetPathname(pathname = window.location.pathname) {
  return routerController.isResetPathname(pathname);
}

function viewFromLocationPath(pathname = window.location.pathname) {
  return routerController.viewFromLocationPath(pathname);
}

function syncPathForView(view, replace = false) {
  return routerController.syncPathForView(view, replace);
}

function viewDomIdForRoute(view) {
  return routerController.viewDomIdForRoute(view);
}

function navViewForRoute(view) {
  return routerController.navViewForRoute(view);
}

function isSpaceGovernanceView(view) {
  return routerController.isSpaceGovernanceView(view);
}

function entitiesForView(view) {
  return routerController.entitiesForView(view);
}

function isKnownEntity(entity) {
  return routerController.isKnownEntity(entity);
}

function clearDataState() {
  return dataStoreController.clearDataState();
}

function markIgnoreRefresh(entity) {
  return dataStoreController.markIgnoreRefresh(entity);
}

async function fetchEntityData(entity) {
  return dataStoreController.fetchEntityData(entity);
}

function applyEntityData(entity, data) {
  return dataStoreController.applyEntityData(entity, data);
}

function scheduleViewPrefetch(view) {
  return dataStoreController.scheduleViewPrefetch(view);
}

async function refreshFromServer(entity = "all") {
  return dataStoreController.refreshFromServer(entity);
}

function renderTopbarStatus() {
  if (!els.status) return;
  const source = state.authed && state.liveSync.statusText
    ? state.liveSync
    : state.shellStatus;
  const text = source?.statusText ?? source?.text ?? "Loading…";
  const tone = source?.statusTone ?? source?.tone ?? "";
  els.status.textContent = text || "Loading…";
  els.status.className = `pill ${tone}`.trim();
}

function setStatus(text, type = "") {
  state.shellStatus = { text, tone: type };
  renderTopbarStatus();
}

function initShellControllers() {
  routerController = createRouterController({
    state,
    els,
    renderActiveView,
    userIsGlobalAdmin,
    isSpaceAdminRole,
    loadData: (...args) => dataStoreController.loadData(...args),
    loadTeamCapacityData,
  });
  dataStoreController = createDataStoreController({
    state,
    els,
    api: (...args) => sessionController.api(...args),
    setStatus,
    setAuthVisible,
    renderActiveView,
    populateSelects,
    restoreSelections,
    handleAuthError: (...args) => sessionController.handleAuthError(...args),
    loadTeamCapacityData,
    entitiesForView: (...args) => routerController.entitiesForView(...args),
    isKnownEntity: (...args) => routerController.isKnownEntity(...args),
    dataEntities: routerController.DATA_ENTITIES,
    viewPrefetchTarget: routerController.VIEW_PREFETCH_TARGET,
  });
  sessionController = createSessionController({
    state,
    els,
    apiBase: API_BASE,
    accessRefreshIntervalMs: ACCESS_REFRESH_INTERVAL_MS,
    buildAppUrl,
    isResetPathname,
    setAuthMode,
    setAuthed,
    setStatus,
    setAuthVisible,
    setResetVisible,
    showAuthError,
    showAuthNotice,
    showResetError,
    showResetSuccess,
    resetIdleTimer,
    hideIdleModal,
    refreshSpaceContext,
    reloadCurrentViewData: (...args) => dataStoreController.reloadCurrentViewData(...args),
    startLiveSync: (...args) => liveSyncController.startLiveSync(...args),
    stopLiveSync: (...args) => liveSyncController.stopLiveSync(...args),
  });
  liveSyncController = createLiveSyncController({
    state,
    buildWsUrl,
    isResetPath: (...args) => sessionController.isResetPath(...args),
    refreshSessionTokens: (...args) => sessionController.refreshSessionTokens(...args),
    refreshSpaceContext,
    reloadCurrentViewData: (...args) => dataStoreController.reloadCurrentViewData(...args),
    refreshFromServer: (...args) => dataStoreController.refreshFromServer(...args),
    handleAuthError: (...args) => sessionController.handleAuthError(...args),
    handleSessionExpired: (...args) => sessionController.handleSessionExpired(...args),
    renderTopbarStatus,
    setSpaceFeedback,
    spaceNameForId,
    clearDataState: (...args) => dataStoreController.clearDataState(...args),
  });
}

function setLiveSyncPhase(phase, options = {}) {
  return liveSyncController.setLiveSyncPhase(phase, options);
}

initShellControllers();

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


function currentSpaceRoleLabel(ctx = state.activeSpace) {
  if (!ctx) return "";
  if (ctx.is_global_admin) return "Global Admin";
  const role = normalizeSpaceRole(ctx.space_role || "member")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
  return role || "Member";
}

function clearSpaceFeedback() {
  if (state.spaceFeedback?.timeoutId) {
    clearTimeout(state.spaceFeedback.timeoutId);
  }
  state.spaceFeedback = { text: "", tone: "", timeoutId: null };
}

function setSpaceFeedback(message, tone = "info", autoClearMs = 0) {
  clearSpaceFeedback();
  if (!message) {
    renderSpaceSwitcher();
    return;
  }
  state.spaceFeedback = { text: message, tone, timeoutId: null };
  if (autoClearMs > 0) {
    state.spaceFeedback.timeoutId = setTimeout(() => {
      clearSpaceFeedback();
      renderSpaceSwitcher();
    }, autoClearMs);
  }
  renderSpaceSwitcher();
}

function clearSpaceGovernanceNotice() {
  if (state.spaceGovernanceNotice?.timeoutId) {
    clearTimeout(state.spaceGovernanceNotice.timeoutId);
  }
  state.spaceGovernanceNotice = { text: "", tone: "", timeoutId: null };
}

function setSpaceGovernanceNotice(message, tone = "info", autoClearMs = 5000) {
  clearSpaceGovernanceNotice();
  if (!message) {
    renderGovernanceHub();
    return;
  }
  state.spaceGovernanceNotice = { text: message, tone, timeoutId: null };
  if (autoClearMs > 0) {
    state.spaceGovernanceNotice.timeoutId = setTimeout(() => {
      clearSpaceGovernanceNotice();
      renderGovernanceHub();
    }, autoClearMs);
  }
  renderGovernanceHub();
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
    setView("master", { replacePath: true });
  }
}


function renderSpaceSwitcher() {
  const active = state.activeSpace;
  if (els.spaceSwitcherTrigger) {
    els.spaceSwitcherTrigger.disabled = !state.authed || state.spaceSwitching || !(state.spaces || []).length;
    els.spaceSwitcherTrigger.setAttribute("aria-expanded", state.spaceSwitcherOpen ? "true" : "false");
    els.spaceSwitcherTrigger.classList.toggle("is-busy", !!state.spaceSwitching);
  }
  if (els.spaceSwitcherCurrent) {
    els.spaceSwitcherCurrent.textContent = state.authed
      ? (active?.space_name || active?.space_id || "No active space")
      : "Sign in";
  }
  if (els.spaceSwitcherMeta) {
    const meta = !state.authed
      ? ""
      : (state.spaceSwitching ? "Switching" : (active ? currentSpaceRoleLabel(active) : ""));
    els.spaceSwitcherMeta.textContent = meta || "Role";
    els.spaceSwitcherMeta.classList.toggle("hidden", !meta);
  }
  if (els.spaceSwitcherPanel) {
    els.spaceSwitcherPanel.classList.toggle("hidden", !state.spaceSwitcherOpen || !state.authed);
  }
  if (els.spaceSwitcherFeedback) {
    els.spaceSwitcherFeedback.textContent = state.spaceFeedback?.text || "";
    els.spaceSwitcherFeedback.className = "form-notice";
    if (state.spaceFeedback?.tone === "success") els.spaceSwitcherFeedback.classList.add("notice-success");
    if (state.spaceFeedback?.tone === "error") els.spaceSwitcherFeedback.classList.add("notice-error");
  }
  const renderList = (container, spaces, { emptyText = "No spaces available", currentId = active?.space_id || "" } = {}) => {
    if (!container) return;
    if (!spaces.length) {
      container.innerHTML = `<p class="muted space-switcher-empty">${emptyText}</p>`;
      return;
    }
    container.innerHTML = spaces.map((space) => {
      const isCurrent = space.space_id === currentId;
      const roleLabel = isCurrent
        ? currentSpaceRoleLabel(active)
        : (userIsGlobalAdmin() ? "Global Admin" : "Accessible");
      return `<button
        type="button"
        class="space-switcher-option${isCurrent ? " is-current" : ""}"
        data-space-switch="${escapeAttr(space.space_id)}"
        ${isCurrent || state.spaceSwitching ? "disabled" : ""}
      >
        <span class="space-switcher-option-main">
          <strong>${esc(space.name || space.space_id)}</strong>
          <span class="space-switcher-option-meta">${esc(space.slug || "Workspace")}</span>
        </span>
        <span class="space-switcher-option-side">
          <span class="pill ${isCurrent ? "" : "muted"}">${esc(roleLabel)}</span>
          ${isCurrent ? "<span class='pill positive'>Current</span>" : ""}
        </span>
      </button>`;
    }).join("");
  };
  const query = normalize(state.spaceSwitcherQuery);
  const activeId = active?.space_id || "";
  const visibleSpaces = (state.spaces || []).filter((space) => {
    if (!query) return true;
    return [space.name, space.slug, space.space_id].some((value) => normalize(value).includes(query));
  });
  const recentSpaceIds = state.spaceRecentIds.filter((spaceId) => spaceId && spaceId !== activeId);
  const recentSpaces = recentSpaceIds
    .map((spaceId) => (state.spaces || []).find((space) => space.space_id === spaceId))
    .filter(Boolean)
    .filter((space, index, list) => list.findIndex((item) => item.space_id === space.space_id) === index)
    .filter((space) => !query || [space.name, space.slug, space.space_id].some((value) => normalize(value).includes(query)));
  renderList(els.spaceSwitcherCurrentList, active ? [{
    space_id: active.space_id,
    name: active.space_name || active.space_id,
    slug: "",
  }] : [], { emptyText: "No active space", currentId: activeId });
  renderList(els.spaceSwitcherRecentList, recentSpaces, { emptyText: "No recent spaces yet", currentId: activeId });
  renderList(els.spaceSwitcherAllList, visibleSpaces, { emptyText: "No matching spaces", currentId: activeId });
  syncRoleAwareNavigation();
}


function spaceNameForId(spaceId) {
  const id = String(spaceId || "").trim();
  if (!id) return "";
  const match = (state.spaces || []).find((space) => space.space_id === id);
  if (match?.name) return match.name;
  if ((state.activeSpace?.space_id || "") === id) return state.activeSpace?.space_name || id;
  return id;
}


async function switchActiveSpace(targetSpaceId) {
  const target = String(targetSpaceId || "").trim();
  const current = state.activeSpace?.space_id || "";
  if (!state.authed || !target) return false;
  if (target === current) return true;
  if (state.spaceSwitching) return false;

  state.spaceSwitching = true;
  state.spaceMembershipActionMenuId = "";
  setSpaceFeedback(`Switching to ${spaceNameForId(target) || target}...`, "info");
  renderSpaceSwitcher();
  if (isSpaceGovernanceView(state.currentView)) {
    renderGovernanceHub();
  }

  const targetName = spaceNameForId(target);
  try {
    const switched = await api("/auth/active-space", {
      method: "POST",
      body: JSON.stringify({ space_id: target }),
    });
    if (current) {
      recordRecentSpace(current);
    }
    state.activeSpace = switched || state.activeSpace;
    state.spaceMembershipSpaceId = state.activeSpace?.space_id || state.spaceMembershipSpaceId;
    stopLiveSync({ phase: "reconnecting" });
    clearDataState();
    await reloadCurrentViewData({ force: true, preserveCapacitySelection: false });
    startLiveSync({ force: true });
    state.spaceSwitcherOpen = false;
    setSpaceFeedback(`Now working in ${state.activeSpace?.space_name || targetName || target}.`, "success", 4200);
    return true;
  } catch (err) {
    console.warn("Space switch failed", err);
    setSpaceFeedback(err?.message ? `Space switch failed: ${err.message}` : "Space switch failed.", "error", 7000);
    try {
      await refreshSpaceContext();
    } catch (refreshErr) {
      console.warn("Space context refresh failed", refreshErr);
    }
    return false;
  } finally {
    state.spaceSwitching = false;
    renderSpaceSwitcher();
    if (isSpaceGovernanceView(state.currentView)) {
      renderGovernanceHub();
    }
  }
}


async function refreshSpaceContext(options = {}) {
  const apiOptions = options.apiOptions || {};
  const suppressLiveSyncRestart = !!options.suppressLiveSyncRestart;
  const previousActiveSpaceId = state.activeSpace?.space_id || "";
  if (!state.authed) {
    state.spaces = [];
    state.activeSpace = null;
    state.spaceSwitching = false;
    state.spaceSwitcherOpen = false;
    state.spaceSwitcherQuery = "";
    state.spaceRecentIds = [];
    clearSpaceFeedback();
    clearSpaceGovernanceNotice();
    state.spaceAdminSection = "";
    state.spaceDirectoryQuery = "";
    state.spaceDirectoryShowArchived = false;
    state.spaceMembershipActionMenuId = "";
    state.archivedSpacesById = {};
    state.spaceMembershipSpaceId = "";
    state.spaceDirectoryModalOpen = false;
    state.spaceMembersBySpace = {};
    state.spaceMembersLoadedBySpace = {};
    state.globalAdmins = [];
    state.globalAdminsLoaded = false;
    state.subcomponentsWorkbench.savedViews = [];
    state.subcomponentsWorkbench.selectedSavedViewId = "";
    state.filters = {};
    state.deliverablesPreset = "";
    closeSpaceCreateModal();
    closeSpaceMemberModal();
    closeSpaceDirectoryModal();
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
  state.spaceRecentIds = readRecentSpaceIds().filter((spaceId) => visibleSpaceIds.has(spaceId));
  persistRecentSpaceIds();
  restoreWorkspaceViewPreferences();
  restoreMasterViewState();
  restoreCalendarViewState();
  restoreKanbanViewState();
  restoreTeamCapacityViewState();
  restorePlanningWindowViewState();
  restoreSubcomponentsWorkbenchUiState();
  renderSpaceSwitcher();
  loadSubcomponentsWorkbenchSavedViews();
  updateSubcomponentsWorkbenchSavedViewsUI();
  const nextActiveSpaceId = state.activeSpace?.space_id || "";
  if (
    !suppressLiveSyncRestart
    && state.authed
    && previousActiveSpaceId
    && nextActiveSpaceId
    && previousActiveSpaceId !== nextActiveSpaceId
  ) {
    startLiveSync({ force: true });
  }
}


function setAuthed(user) {
  state.user = user;
  state.authed = !!user;
  sessionController.onAuthedChange(user);
  if (!user) stopLiveSync();
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
    state.spaceRecentIds = readRecentSpaceIds();
  } else {
    state.workspacePrefs = { showCompleted: false };
    clearDataState();
    state.spaces = [];
    state.activeSpace = null;
    state.spaceSwitching = false;
    state.spaceSwitcherOpen = false;
    state.spaceSwitcherQuery = "";
    state.spaceRecentIds = [];
    clearSpaceFeedback();
    clearSpaceGovernanceNotice();
    state.spaceAdminSection = "";
    state.spaceDirectoryQuery = "";
    state.spaceDirectoryShowArchived = false;
    state.spaceMembershipActionMenuId = "";
    state.archivedSpacesById = {};
    state.spaceMembershipSpaceId = "";
    state.spaceDirectoryModalOpen = false;
    state.spaceMembersBySpace = {};
    state.spaceMembersLoadedBySpace = {};
    state.globalAdmins = [];
    state.globalAdminsLoaded = false;
    state.subcomponentsWorkbench.savedViews = [];
    state.subcomponentsWorkbench.selectedSavedViewId = "";
    closeSpaceCreateModal();
    closeSpaceMemberModal();
    closeSpaceDirectoryModal();
    stopIdleWatch();
    setLiveSyncPhase("idle", { clear: true });
  }
  setAuthVisible(!state.authed);
  if (!state.authed) {
    setStatus("Sign in required", "warn");
  }
  renderSpaceSwitcher();
  renderCompletedVisibilityToggle();
  updateSubcomponentsWorkbenchSavedViewsUI();
  renderTopbarStatus();
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
  return sessionController.refreshSessionTokens(options);
}

function maybeRefreshSessionOnActivity() {
  return sessionController.maybeRefreshSessionOnActivity();
}

async function api(path, options = {}) {
  return sessionController.api(path, options);
}

function handleAuthError(err) {
  return sessionController.handleAuthError(err);
}

function handleSessionExpired() {
  return sessionController.handleSessionExpired();
}

async function fetchCurrentUser() {
  return sessionController.fetchCurrentUser();
}

async function performLogin(email, password) {
  return sessionController.performLogin(email, password);
}

async function performRegister(display_name, email, password) {
  return sessionController.performRegister(display_name, email, password);
}

function isResetPath() {
  return sessionController.isResetPath();
}

function bindAuthUI() {
  return sessionController.bindAuthUI();
}

function clearLiveSyncRetry() {
  if (liveSyncRetryTimer) {
    clearTimeout(liveSyncRetryTimer);
    liveSyncRetryTimer = null;
  }
}

function resetLiveSyncRecoveryFlags() {
  liveSyncReconnectAttempt = 0;
  liveSyncAuthRecoveryUsed = false;
  liveSyncSpaceRecoveryUsed = false;
}

function closeLiveSyncSocket(closeCode = 1000, reason = "") {
  const socket = liveSyncSocket;
  liveSyncSocket = null;
  state.liveSync.socketSpaceId = "";
  if (!socket) return;
  try {
    if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
      socket.close(closeCode, reason);
    }
  } catch (err) {
    console.warn("Live sync close failed", err);
  }
}

function stopLiveSync(options = {}) {
  return liveSyncController.stopLiveSync(options);
}

function liveUrl() {
  const url = new URL(buildWsUrl("/ws"));
  if (state.activeSpace?.space_id) {
    url.searchParams.set("space_id", state.activeSpace.space_id);
  }
  return url.toString();
}

function liveSyncRetryDelayMs() {
  const idx = Math.min(liveSyncReconnectAttempt, LIVE_SYNC_RETRY_DELAYS_MS.length - 1);
  const base = LIVE_SYNC_RETRY_DELAYS_MS[idx];
  const jitter = 0.85 + (Math.random() * 0.3);
  return Math.round(base * jitter);
}

function scheduleLiveSyncRetry() {
  if (!state.authed) return;
  if (document.hidden) {
    stopLiveSync({ phase: "paused", pausedForHidden: true });
    return;
  }
  clearLiveSyncRetry();
  const delay = liveSyncRetryDelayMs();
  liveSyncReconnectAttempt += 1;
  setLiveSyncPhase("reconnecting");
  liveSyncRetryTimer = window.setTimeout(() => {
    liveSyncRetryTimer = null;
    startLiveSync({ force: true, preserveRecovery: true });
  }, delay);
}

async function recoverLiveSyncAuth() {
  if (liveSyncRecoveryPromise) return liveSyncRecoveryPromise;
  if (liveSyncAuthRecoveryUsed) {
    handleSessionExpired();
    return false;
  }
  liveSyncAuthRecoveryUsed = true;
  setLiveSyncPhase("reconnecting");
  liveSyncRecoveryPromise = (async () => {
    const refreshed = await refreshSessionTokens({
      force: true,
      silentFailure: true,
      suppressLiveSyncRestart: true,
    });
    if (!refreshed) {
      handleSessionExpired();
      return false;
    }
    startLiveSync({ force: true, preserveRecovery: true });
    return true;
  })();
  try {
    return await liveSyncRecoveryPromise;
  } finally {
    liveSyncRecoveryPromise = null;
  }
}

async function recoverLiveSyncSpace() {
  if (liveSyncRecoveryPromise) return liveSyncRecoveryPromise;
  if (liveSyncSpaceRecoveryUsed) {
    setSpaceFeedback(
      "Live sync lost access to the active space. Refresh this tab or switch to another space to restore sync.",
      "error",
      9000,
    );
    stopLiveSync({ phase: "attention", text: "Space attention", tone: "warn", preserveRecovery: true });
    return false;
  }
  liveSyncSpaceRecoveryUsed = true;
  setLiveSyncPhase("reconnecting");
  liveSyncRecoveryPromise = (async () => {
    const previousSpaceId = state.activeSpace?.space_id || "";
    try {
      await refreshSpaceContext({
        apiOptions: { skipAuthRefresh: true },
        suppressLiveSyncRestart: true,
      });
    } catch (err) {
      if (handleAuthError(err)) return false;
      console.warn("Live sync space recovery failed", err);
    }
    if (!state.authed) return false;
    const nextSpaceId = state.activeSpace?.space_id || "";
    if (!nextSpaceId) {
      setSpaceFeedback("Unable to restore the active space for live sync.", "error", 9000);
      stopLiveSync({ phase: "attention", text: "Space attention", tone: "warn", preserveRecovery: true });
      return false;
    }
    if (nextSpaceId !== previousSpaceId) {
      setSpaceFeedback(`Live sync moved to ${spaceNameForId(nextSpaceId) || nextSpaceId}.`, "info", 4200);
    }
    clearDataState();
    try {
      await reloadCurrentViewData({ force: true, silent: true, preserveCapacitySelection: false });
    } catch (err) {
      console.warn("Live sync space recovery failed to reload current view", err);
      if (handleAuthError(err)) return false;
    }
    startLiveSync({ force: true, preserveRecovery: true });
    return true;
  })();
  try {
    return await liveSyncRecoveryPromise;
  } finally {
    liveSyncRecoveryPromise = null;
  }
}

async function handleLiveSyncClose(event) {
  if (!state.authed) return;
  if (document.hidden) {
    stopLiveSync({ phase: "paused", pausedForHidden: true });
    return;
  }
  if (event.code === LIVE_SYNC_CLOSE_AUTH) {
    await recoverLiveSyncAuth();
    return;
  }
  if (event.code === LIVE_SYNC_CLOSE_SPACE) {
    await recoverLiveSyncSpace();
    return;
  }
  if (event.code === LIVE_SYNC_CLOSE_LIMIT) {
    setSpaceFeedback(
      "Live sync paused because this account already has the maximum number of connected tabs.",
      "info",
      9000,
    );
    stopLiveSync({ phase: "paused", text: "Sync paused", tone: "warn", preserveRecovery: true });
    return;
  }
  if (event.code === LIVE_SYNC_CLOSE_BUSY || event.code === 1006 || event.code === 1011 || event.code === 1001) {
    scheduleLiveSyncRetry();
    return;
  }
  scheduleLiveSyncRetry();
}

function startLiveSync(options = {}) {
  return liveSyncController.startLiveSync(options);
}

async function handleLiveSyncVisibilityChange() {
  return liveSyncController.handleLiveSyncVisibilityChange();
}

function initSubcomponentsWorkbench() {
  bindSubcomponentsWorkbenchControls();
}

async function bootstrapAuth() {
  return sessionController.bootstrapAuth();
}

async function loadData(options = {}) {
  return dataStoreController.loadData(options);
}

async function reloadCurrentViewData(options = {}) {
  return dataStoreController.reloadCurrentViewData(options);
}

function setView(view, options = {}) {
  return routerController.setView(view, options);
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

function bindWorkspaceViewPreferences() {
  renderCompletedVisibilityToggle();
  if (els.completedVisibilityToggle && !els.completedVisibilityToggle._bound) {
    els.completedVisibilityToggle.addEventListener("click", () => {
      if (!state.authed) return;
      state.workspacePrefs.showCompleted = !state.workspacePrefs.showCompleted;
      persistWorkspaceViewPreferences();
      renderCompletedVisibilityToggle();
      renderActiveView();
    });
    els.completedVisibilityToggle._bound = true;
  }
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
  const routeDispatch = {
    master: () => {
      renderMasterFilters();
      renderMasterTable();
    },
    "subcomponents-workbench": () => renderSubcomponentsWorkbench(),
    dashboard: () => renderDashboard(),
    "pm-dashboard": () => renderPMDashboard(),
    kanban: () => renderKanban(),
    calendar: () => renderCalendar(),
    planning: () => renderPlanning(),
    "team-capacity": () => renderTeamCapacity(),
    spaces: () => renderSpaces(),
    access: () => renderAccess(),
  };
  const renderRoute = routeDispatch[state.currentView] || routeDispatch.master;
  renderRoute();
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && els.solutionModal && !els.solutionModal.classList.contains("hidden")) {
    renderSolutionSubcomponents(openSolutionId);
    renderSolutionActivity(openSolutionId);
    renderSolutionPhases(openSolutionId);
  }
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
      els.subcomponentForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(sub.capacity_hours, 0);
      if (els.deleteSubcomponentBtn) {
        els.deleteSubcomponentBtn.disabled = !sub.subcomponent_id;
      }
      setSubcomponentActionButtonLabel(true);
    }
  }
}

function deliverableKey(type, id) {
  return `${type}:${id}`;
}

function updatePresetButtons() {
  const preset = state.deliverablesPreset || "";
  [els.presetMy, els.presetOverdue, els.presetBlocked, els.presetEngineering].forEach((btn) => {
    if (!btn) return;
    const match = btn.id === `preset-${preset}`;
    btn.classList.toggle("active", match);
  });
}

function normalizeMasterPriorityFilter(value) {
  if (value === null || value === undefined) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 && n <= 5 ? String(n) : "";
}

function normalizeMasterProgressFilter(value) {
  if (value === null || value === undefined) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 && n <= 100 ? String(n) : "";
}

function normalizeMasterFilters(filters = {}, preset = "") {
  const source = filters && typeof filters === "object" ? filters : {};
  const next = {};
  let changed = filters !== source;
  MASTER_TEXT_FILTER_KEYS.forEach((key) => {
    const value = source[key];
    if (typeof value === "string") {
      next[key] = value;
      return;
    }
    next[key] = "";
    if (value !== null && value !== undefined && value !== "") changed = true;
  });
  const type = String(source.type || "");
  next.type = VALID_DELIVERABLE_TYPES.has(type) ? type : "";
  if (next.type !== type) changed = true;
  const repoPresence = String(source.repo_presence || "");
  next.repo_presence = VALID_DELIVERABLE_REPO_PRESENCE.has(repoPresence) ? repoPresence : "";
  if (next.repo_presence !== repoPresence) changed = true;
  const priority = normalizeMasterPriorityFilter(source.priority);
  const progress = normalizeMasterProgressFilter(source.progress);
  if (priority !== String(source.priority || "")) changed = true;
  if (progress !== String(source.progress || "")) changed = true;
  next.priority = priority;
  next.progress = progress;

  if (preset === "engineering") {
    MASTER_ENGINEERING_HIDDEN_FILTER_KEYS.forEach((key) => {
      if (!next[key]) return;
      next[key] = "";
      changed = true;
    });
    if (next.type === "project") {
      next.type = "";
      changed = true;
    }
  } else if (next.repo_presence) {
    next.repo_presence = "";
    changed = true;
  }

  return { filters: next, changed };
}

function clearDeliverablesFilters() {
  state.filters = {};
  state.deliverablesPreset = "";
  state.deliverableSelection.clear();
  persistMasterViewState();
  updatePresetButtons();
  renderMasterFilters();
  renderMasterTable();
  renderKanban();
  renderCalendar();
}

function setDeliverablesPreset(preset) {
  state.deliverablesPreset = preset || "";
  const normalized = normalizeMasterFilters(state.filters, state.deliverablesPreset);
  state.filters = normalized.filters;
  persistMasterViewState();
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
  mod.renderMasterFilters(createShellContext({
    state,
    els,
    escapeAttr,
    deliverableKey,
    updateBulkSelectionCount,
    renderMasterTable,
    renderKanban,
    renderCalendar,
    clearDeliverablesFilters,
  }, { view: "master" }));
}

function isClosedLifecycleStatus(statusValue) {
  const status = normalize(statusValue);
  return status === "complete" || status === "abandoned";
}

function isClosedProjectStatus(statusValue) {
  return isClosedLifecycleStatus(statusValue);
}

function isClosedSolutionStatus(statusValue) {
  return isClosedLifecycleStatus(statusValue);
}

function isCompletedSubcomponentStatus(statusValue) {
  return isClosedLifecycleStatus(statusValue);
}

function showCompletedOperationalWork() {
  return !!state.workspacePrefs?.showCompleted;
}

function requestsClosedStatuses(filterValue) {
  const status = normalize(filterValue);
  if (!status) return false;
  return status.includes("complete") || status.includes("abandoned");
}

function hideClosedDeliverables() {
  return !showCompletedOperationalWork() && !requestsClosedStatuses(state.filters?.status);
}

function hideClosedSubcomponentsWorkbench() {
  return !showCompletedOperationalWork() && !requestsClosedStatuses(state.subcomponentsWorkbench?.filters?.status);
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
    if (hideClosedSubcomponentsWorkbench() && isCompletedSubcomponentStatus(row.status)) return false;
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
    hiddenClosed: hideClosedSubcomponentsWorkbench()
      ? rows.filter((row) => isCompletedSubcomponentStatus(row.status)).length
      : 0,
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
  if (els.subcomponentsWorkbenchBulkApply) {
    const action = els.subcomponentsWorkbenchBulkAction?.value || "";
    const hasActiveDeleteTarget = action === "delete" && !!state.subcomponentsWorkbench.activeSubcomponentId;
    els.subcomponentsWorkbenchBulkApply.disabled = !action || (!count && !hasActiveDeleteTarget);
  }
}

function describeSubcomponentsForDelete(subcomponentIds) {
  const uniqueIds = Array.from(new Set((subcomponentIds || []).map((id) => String(id || "").trim()).filter(Boolean)));
  const names = uniqueIds.map((id) => {
    const row = state.subcomponents.find((item) => item.subcomponent_id === id);
    return row?.subcomponent_name || "";
  }).filter(Boolean);
  const preview = names.slice(0, 3).map((name) => `"${name}"`);
  const remainder = Math.max(names.length - preview.length, 0);
  const listed = preview.join(", ");
  const suffix = remainder > 0 ? `${listed ? ", " : ""}and ${remainder} more` : "";
  return {
    ids: uniqueIds,
    names,
    previewText: `${listed}${suffix}`,
  };
}

async function deleteSubcomponentsById(subcomponentIds, options = {}) {
  const details = describeSubcomponentsForDelete(subcomponentIds);
  const { ids } = details;
  if (!ids.length) {
    return { cancelled: false, deletedIds: [], failed: [] };
  }

  const count = ids.length;
  const defaultTitle = count === 1 ? "Delete Subcomponent?" : "Delete Subcomponents?";
  const defaultConfirm = count === 1 ? "Delete Subcomponent" : `Delete ${count} Subcomponents`;
  const defaultMessage = count === 1
    ? `Delete ${details.previewText || "this subcomponent"}? This cannot be undone.`
    : `Delete ${count} subcomponents${details.previewText ? ` (${details.previewText})` : ""}? This cannot be undone.`;

  const confirmed = await showConfirmModal({
    title: options.title || defaultTitle,
    message: options.message || defaultMessage,
    confirmLabel: options.confirmLabel || defaultConfirm,
  });
  if (!confirmed) {
    return { cancelled: true, deletedIds: [], failed: [] };
  }

  const deletedIds = [];
  const failed = [];
  for (const id of ids) {
    try {
      await api(`/subcomponents/${encodeURIComponent(id)}`, { method: "DELETE" });
      deletedIds.push(id);
    } catch (err) {
      failed.push({ id, error: err });
    }
  }

  deletedIds.forEach((id) => removeById(state.subcomponents, id, "subcomponent_id"));
  const wb = state.subcomponentsWorkbench;
  deletedIds.forEach((id) => wb.selected.delete(id));
  if (deletedIds.includes(wb.activeSubcomponentId)) {
    wb.activeSubcomponentId = "";
  }

  return { cancelled: false, deletedIds, failed };
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
  persistSubcomponentsWorkbenchUiState();
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
  persistSubcomponentsWorkbenchUiState();
  renderSubcomponentsWorkbench();
  window.requestAnimationFrame(() => {
    if (!returnSubcomponentId || !els.subcomponentsWorkbenchTable) return;
    const row = Array.from(els.subcomponentsWorkbenchTable.querySelectorAll("tr[data-id]")).find(
      (node) => node.getAttribute("data-id") === returnSubcomponentId
    );
    if (row && typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest" });
    }
    const target = row || row?.querySelector(".scwb-select-row");
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

function clearSubcomponentsWorkbenchBulkFeedback() {
  clearDeliverableFormNotice(els.subcomponentsWorkbenchBulkFeedback);
}

function setSubcomponentsWorkbenchBulkFeedback(message, tone = "info", autoClearMs = 0) {
  setDeliverableFormNotice(els.subcomponentsWorkbenchBulkFeedback, message, tone, autoClearMs);
}

function loadSubcomponentsWorkbenchSavedViews() {
  const wb = state.subcomponentsWorkbench;
  wb.savedViews = [];
  wb.selectedSavedViewId = "";
  if (!state.authed) return;
  let recovered = false;
  let parsed = [];
  try {
    const raw = localStorage.getItem(subcomponentsWorkbenchStorageKey()) || "[]";
    const candidate = JSON.parse(raw);
    if (Array.isArray(candidate)) {
      parsed = candidate;
    } else {
      recovered = true;
    }
  } catch (err) {
    recovered = true;
    console.warn("Unable to load subcomponent workbench saved views", err);
  }
  const normalizedViews = parsed
      .filter((row) => row && typeof row === "object" && typeof row.name === "string")
      .map((row) => ({
        view_id: String(row.view_id || `sv_${Math.random().toString(36).slice(2, 10)}`),
        name: String(row.name || "").trim(),
        preset: VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(row.preset || "all"))
          ? String(row.preset || "all")
          : "all",
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
  wb.savedViews = normalizedViews;
  if (recovered || JSON.stringify(parsed) !== JSON.stringify(normalizedViews)) {
    persistSubcomponentsWorkbenchSavedViews();
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
  let selectionChanged = false;
  if (wb.selectedSavedViewId && wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId)) {
    els.subcomponentsWorkbenchSavedSelect.value = wb.selectedSavedViewId;
  } else if (wb.selectedSavedViewId) {
    wb.selectedSavedViewId = "";
    els.subcomponentsWorkbenchSavedSelect.value = "";
    selectionChanged = true;
  } else if (els.subcomponentsWorkbenchSavedSelect.value) {
    wb.selectedSavedViewId = els.subcomponentsWorkbenchSavedSelect.value;
    selectionChanged = true;
  }
  if (
    els.subcomponentsWorkbenchSavedName &&
    wb.selectedSavedViewId &&
    document.activeElement !== els.subcomponentsWorkbenchSavedName
  ) {
    const saved = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId);
    if (saved) els.subcomponentsWorkbenchSavedName.value = saved.name || "";
  }
  if (selectionChanged) persistSubcomponentsWorkbenchUiState();
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
  wb.selectedSavedViewId = savedView.view_id || wb.selectedSavedViewId || "";
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
  normalizeSubcomponentsWorkbenchUiState({ persist: true });
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
  const deleteButton = els.subcomponentsWorkbenchDelete;
  const previousId = form.dataset.activeSubcomponentId || "";
  const setValue = (name, value) => {
    const el = form.querySelector(`[name="${name}"]`);
    if (el) el.value = value == null ? "" : value;
  };
  if (!subcomponent) {
    form.dataset.activeSubcomponentId = "";
    form.reset();
    if (idInput) idInput.value = "";
    if (els.subcomponentsWorkbenchContext) {
      els.subcomponentsWorkbenchContext.textContent = "Select a subcomponent to edit.";
    }
    if (saveButton) saveButton.disabled = true;
    if (deleteButton) deleteButton.disabled = true;
    clearDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus);
    renderSubcomponentsWorkbenchActivity("");
    return;
  }
  const currentId = subcomponent.subcomponent_id || "";
  if (previousId !== currentId) {
    clearDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus);
  }
  form.dataset.activeSubcomponentId = currentId;
  if (saveButton) saveButton.disabled = false;
  if (deleteButton) deleteButton.disabled = !currentId;
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
    els.subcomponentsWorkbenchContext.innerHTML = `
      <span class="sub-workbench-context-primary">${renderSubcomponentsWorkbenchDrawerProjectLink(project, subcomponent.project_id)} / ${renderSubcomponentsWorkbenchDrawerSolutionLink(solution, subcomponent.solution_id)}</span>
      ${renderSubcomponentsWorkbenchDrawerRepoContext(subcomponent)}
    `;
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
  persistSubcomponentsWorkbenchUiState();

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
    if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;
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
    if (preset === "engineering") {
      const hasRepo = !!repoDisplayUrl(s.github_repo_url);
      if (f.repo_presence === "has_repo" && !hasRepo) return false;
      if (f.repo_presence === "missing_repo" && hasRepo) return false;
    }
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
  if (hideClosedDeliverables() && isClosedProjectStatus(project?.status)) return false;
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
  const includeProjectRows = preset !== "engineering" && f.type !== "solution";
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
  const { project, owner } = state.kanbanFilters || {};
  const ownerNorm = (owner || "").toLowerCase();
  return (state.solutions || []).filter((s) => {
    if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;
    if (project && s.project_id !== project) return false;
    if (ownerNorm && !(s.owner || "").toLowerCase().includes(ownerNorm)) return false;
    return true;
  });
}

function filteredSolutionsForCalendar() {
  const { project, owner } = state.calendarFilters || {};
  const ownerNorm = (owner || "").toLowerCase();
  return (state.solutions || []).filter((s) => {
    if (hideClosedDeliverables() && isClosedSolutionStatus(s.status)) return false;
    if (project && s.project_id !== project) return false;
    if (ownerNorm && !(s.owner || "").toLowerCase().includes(ownerNorm)) return false;
    return true;
  });
}

function filteredSubcomponentsForCalendar() {
  const { project, owner } = state.calendarFilters || {};
  const ownerNorm = (owner || "").toLowerCase();
  return (state.subcomponents || []).filter((sc) => {
    if (!showCompletedOperationalWork() && isCompletedSubcomponentStatus(sc.status)) return false;
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
  const hiddenClosedDeliverables = !showCompletedOperationalWork()
    ? (state.projects || []).filter((project) => isClosedProjectStatus(project.status)).length
      + (state.solutions || []).filter((solution) => isClosedSolutionStatus(solution.status)).length
    : 0;

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

  if (hiddenClosedDeliverables > 0) {
    els.masterQuickstart.classList.remove("hidden");
    els.masterQuickstart.innerHTML = `
      <div class="quickstart-head">
        <h3>Completed Work Hidden</h3>
        <p class="muted">${hiddenClosedDeliverables} completed or abandoned deliverable${hiddenClosedDeliverables === 1 ? "" : "s"} are hidden from the workspace.</p>
      </div>
      <div class="quickstart-actions">
        <button type="button" class="secondary" data-quick-action="show-completed">Show completed work</button>
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
    persistMasterViewState,
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
  clearBulkFeedback();
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
    setBulkFeedback("Select a status first.", "error");
    return;
  }
  if (action === "owner" && !owner) {
    setBulkFeedback("Enter an owner name.", "error");
    return;
  }
  const updates = Array.from(state.deliverableSelection);
  try {
    setBulkFeedback("Updating deliverables…");
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
    setBulkFeedback("Deliverables updated.", "success", 3200);
  } catch (err) {
    setBulkFeedback(`Bulk update failed: ${err.message}`, "error");
  }
}

async function updateDeliverableField(type, id, field, value) {
  clearBulkFeedback();
  setBulkFeedback("Saving deliverable change…");
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
    setBulkFeedback("Deliverable updated.", "success", 2200);
  } catch (err) {
    setBulkFeedback(`Update failed: ${err.message}`, "error");
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
      clearBulkFeedback();
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

function closeTopbarCreateMenu({ restoreFocus = true } = {}) {
  if (!els.topbarCreatePanel || !els.topbarCreateToggle) return;
  els.topbarCreatePanel.classList.add("hidden");
  els.topbarCreateToggle.setAttribute("aria-expanded", "false");
  if (restoreFocus) els.topbarCreateToggle.focus();
}

function subcomponentCreateCandidateSolutions() {
  return [...(state.solutions || [])].sort((a, b) => {
    const projectA = state.projects.find((project) => project.project_id === a.project_id)?.project_name || "";
    const projectB = state.projects.find((project) => project.project_id === b.project_id)?.project_name || "";
    const projectDiff = projectA.localeCompare(projectB);
    if (projectDiff !== 0) return projectDiff;
    return String(a.solution_name || "").localeCompare(String(b.solution_name || ""));
  });
}

function subcomponentCreateSolutionLabel(solution) {
  const projectName = state.projects.find((project) => project.project_id === solution?.project_id)?.project_name || "";
  const solutionName = String(solution?.solution_name || "").trim() || "Untitled Solution";
  return projectName ? `${projectName} / ${solutionName}` : solutionName;
}

function closeSubcomponentCreatePicker() {
  if (!els.subcomponentCreatePickerModal) return;
  els.subcomponentCreatePickerModal.classList.add("hidden");
  clearDeliverableFormNotice(els.subcomponentCreatePickerStatus);
}

function continueSubcomponentCreateForSolution(solution) {
  if (!solution?.solution_id) return;
  closeSubcomponentCreatePicker();
  openSolutionModal(solution, "subcomponents");
  showSubcomponentForm(solution);
}

function populateSubcomponentCreatePickerOptions(selectedSolutionId = "") {
  if (!els.subcomponentCreatePickerSelect) return;
  const solutions = subcomponentCreateCandidateSolutions();
  const options = solutions
    .map((solution) => {
      const selected = solution.solution_id === selectedSolutionId ? "selected" : "";
      return `<option value="${escapeHtml(solution.solution_id)}" ${selected}>${escapeHtml(subcomponentCreateSolutionLabel(solution))}</option>`;
    })
    .join("");
  els.subcomponentCreatePickerSelect.innerHTML = options;
  if (selectedSolutionId) {
    els.subcomponentCreatePickerSelect.value = selectedSolutionId;
  }
}

function openSubcomponentCreatePicker(selectedSolutionId = "") {
  if (!els.subcomponentCreatePickerModal) return;
  populateSubcomponentCreatePickerOptions(selectedSolutionId);
  clearDeliverableFormNotice(els.subcomponentCreatePickerStatus);
  els.subcomponentCreatePickerModal.classList.remove("hidden");
  window.setTimeout(() => {
    els.subcomponentCreatePickerSelect?.focus();
  }, 0);
}

function handleTopbarSubcomponentCreate() {
  closeTopbarCreateMenu({ restoreFocus: false });
  const currentOpenSolutionId = !els.solutionModal?.classList.contains("hidden")
    ? (els.solutionForm?.querySelector('[name="solution_id"]')?.value || "")
    : "";
  const currentOpenSolution = currentOpenSolutionId
    ? state.solutions.find((solution) => solution.solution_id === currentOpenSolutionId)
    : null;
  if (currentOpenSolution?.solution_id) {
    continueSubcomponentCreateForSolution(currentOpenSolution);
    return;
  }
  const solutions = subcomponentCreateCandidateSolutions();
  if (!solutions.length) {
    openSolutionModal(null, "details");
    setDeliverableFormNotice(els.solutionFormStatus, "Create a solution first, then add subcomponents.", "error");
    return;
  }
  if (solutions.length === 1) {
    continueSubcomponentCreateForSolution(solutions[0]);
    return;
  }
  openSubcomponentCreatePicker(currentOpenSolutionId);
}

function openTopbarCreateMenu() {
  if (!els.topbarCreatePanel || !els.topbarCreateToggle) return;
  if (els.csvActionsMenu && !els.csvActionsMenu.classList.contains("hidden")) {
    els.csvActionsMenu.classList.add("hidden");
    els.csvActionsToggle?.setAttribute("aria-expanded", "false");
  }
  els.topbarCreatePanel.classList.remove("hidden");
  els.topbarCreateToggle.setAttribute("aria-expanded", "true");
  const items = Array.from(els.topbarCreatePanel.querySelectorAll("[role='menuitem']"));
  items[0]?.focus();
}

function bindTopbarCreateMenu() {
  const topbarCreateMenuItems = () => Array.from(els.topbarCreatePanel?.querySelectorAll("[role='menuitem']") || []);
  const toggleTopbarCreateMenu = () => {
    if (!els.topbarCreatePanel || !els.topbarCreateToggle) return;
    const isHidden = els.topbarCreatePanel.classList.contains("hidden");
    if (isHidden) {
      openTopbarCreateMenu();
    } else {
      closeTopbarCreateMenu();
    }
  };

  if (els.topbarCreateToggle && !els.topbarCreateToggle._bound) {
    els.topbarCreateToggle.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " " && event.key !== "ArrowDown") return;
      event.preventDefault();
      openTopbarCreateMenu();
    });
    els.topbarCreateToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleTopbarCreateMenu();
    });
    els.topbarCreateToggle._bound = true;
  }

  if (els.topbarCreatePanel && !els.topbarCreatePanel._bound) {
    els.topbarCreatePanel.addEventListener("keydown", (event) => {
      const items = topbarCreateMenuItems();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const activeIndex = items.indexOf(document.activeElement);

      if (event.key === "Escape") {
        event.preventDefault();
        closeTopbarCreateMenu();
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
    els.topbarCreatePanel.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    els.topbarCreatePanel._bound = true;
  }

  if (!document._topbarCreateMenuCloseBound) {
    document.addEventListener("click", (event) => {
      const menu = els.topbarCreatePanel;
      const toggle = els.topbarCreateToggle;
      if (!menu || !toggle) return;
      if (menu.classList.contains("hidden")) return;
      if (menu.contains(event.target) || toggle.contains(event.target)) return;
      closeTopbarCreateMenu({ restoreFocus: false });
    });
    document._topbarCreateMenuCloseBound = true;
  }

  if (els.topbarCreateProject && !els.topbarCreateProject._bound) {
    els.topbarCreateProject.addEventListener("click", () => {
      closeTopbarCreateMenu({ restoreFocus: false });
      openProjectForm(null);
    });
    els.topbarCreateProject._bound = true;
  }

  if (els.topbarCreateSolution && !els.topbarCreateSolution._bound) {
    els.topbarCreateSolution.addEventListener("click", () => {
      closeTopbarCreateMenu({ restoreFocus: false });
      openSolutionModal(null, "details");
    });
    els.topbarCreateSolution._bound = true;
  }

  if (els.topbarCreateSubcomponent && !els.topbarCreateSubcomponent._bound) {
    els.topbarCreateSubcomponent.addEventListener("click", handleTopbarSubcomponentCreate);
    els.topbarCreateSubcomponent._bound = true;
  }
}

function bindDeliverablesControls() {
  els.presetMy?.addEventListener("click", () => setDeliverablesPreset("my"));
  els.presetOverdue?.addEventListener("click", () => setDeliverablesPreset("overdue"));
  els.presetBlocked?.addEventListener("click", () => setDeliverablesPreset("blocked"));
  els.presetEngineering?.addEventListener("click", () => setDeliverablesPreset("engineering"));
  els.presetClear?.addEventListener("click", clearDeliverablesFilters);
  els.bulkAction?.addEventListener("change", syncBulkInputs);
  els.bulkApply?.addEventListener("click", applyBulkAction);
  els.bulkStatus?.addEventListener("change", clearBulkFeedback);
  els.bulkOwner?.addEventListener("input", clearBulkFeedback);
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
      } else if (action === "show-completed") {
        state.workspacePrefs.showCompleted = true;
        persistWorkspaceViewPreferences();
        renderCompletedVisibilityToggle();
        renderActiveView();
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
  persistSubcomponentsWorkbenchUiState();
  renderSubcomponentsWorkbench();
}

function syncSubcomponentsWorkbenchBulkInputs() {
  clearSubcomponentsWorkbenchBulkFeedback();
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
  updateSubcomponentsWorkbenchSelectionCount();
}

async function applySubcomponentsWorkbenchBulkAction() {
  const wb = state.subcomponentsWorkbench;
  const selectedIds = Array.from(wb.selected);
  const action = els.subcomponentsWorkbenchBulkAction?.value || "";
  if (!action) {
    setSubcomponentsWorkbenchBulkFeedback("Choose a bulk action.", "error");
    return;
  }
  const activeId = wb.activeSubcomponentId || "";
  const allowActiveDelete = action === "delete" && !selectedIds.length && !!activeId;
  if (!selectedIds.length && !allowActiveDelete) {
    setSubcomponentsWorkbenchBulkFeedback("Select at least one subcomponent.", "error");
    return;
  }
  if (action === "delete") {
    const deleteTargets = selectedIds.length ? selectedIds : [activeId];
    setSubcomponentsWorkbenchBulkFeedback(
      deleteTargets.length === 1 ? "Deleting subcomponent…" : `Deleting ${deleteTargets.length} subcomponents…`
    );
    markIgnoreRefresh("subcomponents");
    const result = await deleteSubcomponentsById(deleteTargets, {
      title: deleteTargets.length === 1 ? "Delete Subcomponent?" : "Delete Selected Subcomponents?",
      confirmLabel: deleteTargets.length === 1 ? "Delete Subcomponent" : `Delete ${deleteTargets.length} Subcomponents`,
    });
    if (result.cancelled) return;
    if (!result.deletedIds.length) {
      ignoreNextRefresh.delete("subcomponents");
    }
    renderSubcomponentsWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionSubcomponents(openSolutionId);
    }
    renderDashboard();
    if (result.failed.length) {
      setSubcomponentsWorkbenchBulkFeedback(
        `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,
        "error"
      );
      return;
    }
    setSubcomponentsWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length} subcomponent${result.deletedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
    return;
  }

  const payload = { subcomponent_ids: selectedIds };
  if (action === "status") {
    payload.status = els.subcomponentsWorkbenchBulkStatus?.value || "";
    if (!payload.status) {
      setSubcomponentsWorkbenchBulkFeedback("Select a status value.", "error");
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
      setSubcomponentsWorkbenchBulkFeedback("Enter a due date shift in whole days (e.g. 3 or -2).", "error");
      return;
    }
    payload.due_date_shift_days = Math.trunc(shift);
  } else {
    setSubcomponentsWorkbenchBulkFeedback("Unsupported bulk action.", "error");
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
    setSubcomponentsWorkbenchBulkFeedback(
      `Updated ${selectedIds.length} subcomponent${selectedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
  } catch (err) {
    setSubcomponentsWorkbenchBulkFeedback(`Bulk update failed: ${err.message || err}`, "error");
  }
}

function clearBulkFeedback() {
  clearDeliverableFormNotice(els.bulkFeedback);
}

function setBulkFeedback(message, tone = "info", autoClearMs = 0) {
  setDeliverableFormNotice(els.bulkFeedback, message, tone, autoClearMs);
}

function clearCapacityUserFormStatus() {
  clearDeliverableFormNotice(els.capacityUserFormStatus);
}

function setCapacityUserFormStatus(message, tone = "info", autoClearMs = 0) {
  setDeliverableFormNotice(els.capacityUserFormStatus, message, tone, autoClearMs);
}

function bindSubcomponentsWorkbenchControls() {
  const wb = state.subcomponentsWorkbench;
  const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");
  presetButtons.forEach((btn) => {
    if (btn._bound) return;
    btn.addEventListener("click", () => {
      wb.preset = btn.getAttribute("data-preset") || "all";
      wb.selected.clear();
      persistSubcomponentsWorkbenchUiState();
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
        persistSubcomponentsWorkbenchUiState();
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === nextId);
      if (!saved) return;
      if (els.subcomponentsWorkbenchSavedName) {
        els.subcomponentsWorkbenchSavedName.value = saved.name || "";
      }
      setSubcomponentsWorkbenchSavedStatus(`Applied "${saved.name}"`);
      persistSubcomponentsWorkbenchUiState();
      applySubcomponentsWorkbenchSavedView(saved);
    });
    els.subcomponentsWorkbenchSavedSelect._bound = true;
  }

  if (els.subcomponentsWorkbenchSavedSave && !els.subcomponentsWorkbenchSavedSave._bound) {
    els.subcomponentsWorkbenchSavedSave.addEventListener("click", () => {
      const rawName = (els.subcomponentsWorkbenchSavedName?.value || "").trim();
      if (!rawName) {
        setSubcomponentsWorkbenchSavedStatus("Enter a view name before saving.");
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
      persistSubcomponentsWorkbenchUiState();
      updateSubcomponentsWorkbenchSavedViewsUI();
      setSubcomponentsWorkbenchSavedStatus(`Saved "${rawName}"`);
    });
    els.subcomponentsWorkbenchSavedSave._bound = true;
  }

  if (els.subcomponentsWorkbenchSavedDelete && !els.subcomponentsWorkbenchSavedDelete._bound) {
    els.subcomponentsWorkbenchSavedDelete.addEventListener("click", async () => {
      const selectedId = wb.selectedSavedViewId || els.subcomponentsWorkbenchSavedSelect?.value || "";
      if (!selectedId) {
        setSubcomponentsWorkbenchSavedStatus("Select a saved view to delete.");
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === selectedId);
      if (!saved) return;
      const confirmed = await showConfirmModal({
        title: "Delete Saved View?",
        message: `Delete saved view "${saved.name}"?`,
        confirmLabel: "Delete Saved View",
      });
      if (!confirmed) return;
      wb.savedViews = wb.savedViews.filter((row) => row.view_id !== selectedId);
      wb.selectedSavedViewId = "";
      persistSubcomponentsWorkbenchSavedViews();
      persistSubcomponentsWorkbenchUiState();
      updateSubcomponentsWorkbenchSavedViewsUI();
      setSubcomponentsWorkbenchSavedStatus(`Deleted "${saved.name}"`);
    });
    els.subcomponentsWorkbenchSavedDelete._bound = true;
  }

  bindDebouncedInput(els.subcomponentsWorkbenchSearch, (value) => {
    wb.filters.search = value || "";
    persistSubcomponentsWorkbenchUiState();
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
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchProject._bound = true;
  }

  if (els.subcomponentsWorkbenchSolution && !els.subcomponentsWorkbenchSolution._bound) {
    els.subcomponentsWorkbenchSolution.addEventListener("change", () => {
      wb.filters.solution_id = els.subcomponentsWorkbenchSolution.value || "";
      persistSubcomponentsWorkbenchUiState();
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
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchAssignee._bound = true;
  }

  if (els.subcomponentsWorkbenchStatus && !els.subcomponentsWorkbenchStatus._bound) {
    els.subcomponentsWorkbenchStatus.addEventListener("change", () => {
      wb.filters.status = els.subcomponentsWorkbenchStatus.value || "";
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchStatus._bound = true;
  }

  if (els.subcomponentsWorkbenchPriority && !els.subcomponentsWorkbenchPriority._bound) {
    bindDebouncedInput(els.subcomponentsWorkbenchPriority, (value) => {
      wb.filters.priority_max = value || "";
      persistSubcomponentsWorkbenchUiState();
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
        clearSubcomponentsWorkbenchBulkFeedback();
        updateSubcomponentsWorkbenchSelectionCount();
        return;
      }
      if (e.target.id === "scwb-select-all") {
        const checked = !!e.target.checked;
        (wb.visibleIds || []).forEach((subId) => {
          if (checked) wb.selected.add(subId);
          else wb.selected.delete(subId);
        });
        clearSubcomponentsWorkbenchBulkFeedback();
        persistSubcomponentsWorkbenchUiState();
        renderSubcomponentsWorkbench();
      }
    });
    els.subcomponentsWorkbenchTable.addEventListener("click", (e) => {
      const actionEl = e.target.closest("[data-scwb-action]");
      if (actionEl) {
        const action = actionEl.getAttribute("data-scwb-action") || "";
        if (action === "open-project") {
          openSubcomponentsWorkbenchProjectDrilldown(actionEl.getAttribute("data-project-id"));
        }
        if (action === "open-solution") {
          openSubcomponentsWorkbenchSolutionDrilldown(actionEl.getAttribute("data-solution-id"));
        }
        return;
      }
      const row = e.target.closest("tr[data-id]");
      if (!row) return;
      if (e.target.closest("button,input,select,textarea,label")) return;
      const subId = row.getAttribute("data-id") || "";
      if (!subId) return;
      openSubcomponentsWorkbenchDrawer(subId);
    });
    els.subcomponentsWorkbenchTable._bound = true;
  }

  if (els.subcomponentsWorkbenchForm && !els.subcomponentsWorkbenchForm._bound) {
    els.subcomponentsWorkbenchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.subcomponentsWorkbenchForm);
      const subId = data.get("subcomponent_id");
      if (!subId) {
        setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, "Select a subcomponent first.", "error");
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
        setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, "Saving subcomponent...");
        const updated = await api(`/subcomponents/${subId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        upsertById(state.subcomponents, updated, "subcomponent_id");
        wb.activeSubcomponentId = updated.subcomponent_id;
        persistSubcomponentsWorkbenchUiState();
        renderSubcomponentsWorkbench();
        const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
          renderSolutionSubcomponents(openSolutionId);
        }
        setDeliverableFormNotice(
          els.subcomponentsWorkbenchFormStatus,
          `Saved subcomponent at ${timestampLabel()}.`,
          "success",
          3200
        );
      } catch (err) {
        setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, `Save failed: ${err.message || err}`, "error");
      }
    });
    els.subcomponentsWorkbenchForm._bound = true;
  }

  if (els.subcomponentsWorkbenchContext && !els.subcomponentsWorkbenchContext._bound) {
    els.subcomponentsWorkbenchContext.addEventListener("click", (event) => {
      const actionEl = event.target.closest("[data-scwb-context-action]");
      if (!actionEl) return;
      const action = actionEl.getAttribute("data-scwb-context-action") || "";
      if (action === "open-project") {
        openSubcomponentsWorkbenchProjectDrilldown(actionEl.getAttribute("data-project-id"));
      }
      if (action === "open-solution") {
        openSubcomponentsWorkbenchSolutionDrilldown(actionEl.getAttribute("data-solution-id"));
      }
    });
    els.subcomponentsWorkbenchContext._bound = true;
  }

  if (els.subcomponentsWorkbenchDelete && !els.subcomponentsWorkbenchDelete._bound) {
    els.subcomponentsWorkbenchDelete.addEventListener("click", async () => {
      const subId = els.subcomponentsWorkbenchForm?.querySelector('[name="subcomponent_id"]')?.value || "";
      if (!subId) {
        setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, "Select a subcomponent first.", "error");
        return;
      }
      markIgnoreRefresh("subcomponents");
      const result = await deleteSubcomponentsById([subId], {
        title: "Delete Subcomponent?",
      });
      if (result.cancelled) return;
      if (!result.deletedIds.length) {
        ignoreNextRefresh.delete("subcomponents");
      }
      renderSubcomponentsWorkbench();
      const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
        renderSolutionSubcomponents(openSolutionId);
      }
      renderDashboard();
      if (result.failed.length) {
        setDeliverableFormNotice(
          els.subcomponentsWorkbenchFormStatus,
          `Delete failed for ${result.failed.length} subcomponent(s).`,
          "error"
        );
        return;
      }
      setDeliverableFormNotice(
        els.subcomponentsWorkbenchFormStatus,
        `Deleted subcomponent at ${timestampLabel()}.`,
        "success",
        3200
      );
    });
    els.subcomponentsWorkbenchDelete._bound = true;
  }

  if (els.subcomponentsWorkbenchReset && !els.subcomponentsWorkbenchReset._bound) {
    els.subcomponentsWorkbenchReset.addEventListener("click", () => {
      wb.activeSubcomponentId = "";
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchReset._bound = true;
  }

  if (els.subcomponentsWorkbenchClose && !els.subcomponentsWorkbenchClose._bound) {
    els.subcomponentsWorkbenchClose.addEventListener("click", () => closeSubcomponentsWorkbenchDrawer());
    els.subcomponentsWorkbenchClose._bound = true;
  }

  if (!document._scwbShortcutsBound) {
    document.addEventListener("keydown", async (event) => {
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
      if (key === "delete") {
        const selectedIds = Array.from(wb.selected);
        const targetIds = selectedIds.length
          ? selectedIds
          : (wb.activeSubcomponentId ? [wb.activeSubcomponentId] : []);
        if (!targetIds.length) return;
        event.preventDefault();
        markIgnoreRefresh("subcomponents");
        const result = await deleteSubcomponentsById(targetIds, {
          title: targetIds.length === 1 ? "Delete Subcomponent?" : "Delete Selected Subcomponents?",
        });
        if (result.cancelled) return;
        if (!result.deletedIds.length) {
          ignoreNextRefresh.delete("subcomponents");
        }
        renderSubcomponentsWorkbench();
        const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
          renderSolutionSubcomponents(openSolutionId);
        }
        renderDashboard();
        if (result.failed.length) {
          setSubcomponentsWorkbenchBulkFeedback(
            `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,
            "error"
          );
        } else {
          setSubcomponentsWorkbenchBulkFeedback(
            `Deleted ${result.deletedIds.length} subcomponent${result.deletedIds.length === 1 ? "" : "s"}.`,
            "success",
            3200
          );
        }
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
  mod.renderDashboard({
    state,
    els,
    formatStatus,
    openDashboardSolutionDrilldown,
    openDashboardProjectDrilldown,
  });
}

function openDashboardSolutionDrilldown(solutionId) {
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

function openDashboardProjectDrilldown(projectId) {
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  openProjectForm(project);
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
    viewHref,
    openPMDashboardCapacityDrilldown,
    openPMDashboardProjectDrilldown,
    openPMDashboardSolutionDrilldown,
    openPMDashboardSubcomponentDrilldown,
    assigneeKeyFromAlloc,
    assigneeLabelFromKey,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
  });
}

function openPMDashboardProjectDrilldown(projectId) {
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  openProjectForm(project);
}

function closePlanningModal() {
  if (els.planningModal) {
    els.planningModal.classList.add("hidden");
  }
  if (els.planningModalBody) {
    els.planningModalBody.innerHTML = "";
  }
}

function openPlanningModal(title, bodyHtml) {
  if (els.planningModalTitle) {
    els.planningModalTitle.textContent = title || "Details";
  }
  if (els.planningModalBody) {
    els.planningModalBody.innerHTML = bodyHtml || "";
  }
  els.planningModal?.classList.remove("hidden");
}

function openAllocationWorkItemDrilldown(allocationId) {
  const targetId = String(allocationId || "").trim();
  if (!targetId) return;
  const allocation = state.allocations.find((row) => String(row.allocation_id || "") === targetId);
  if (!allocation) {
    setStatus("Allocation details are no longer available.", "warn");
    return;
  }
  closePlanningModal();
  const workItemId = String(allocation.work_item_id || "").trim();
  if (!workItemId) {
    setStatus("The linked work item is unavailable.", "warn");
    return;
  }
  if (allocation.work_item_type === "project") {
    const project = state.projects.find((row) => row.project_id === workItemId);
    if (!project) {
      setStatus("The linked project is unavailable.", "warn");
      return;
    }
    openProjectForm(project);
    return;
  }
  if (allocation.work_item_type === "solution") {
    const solution = state.solutions.find((row) => row.solution_id === workItemId);
    if (!solution) {
      setStatus("The linked solution is unavailable.", "warn");
      return;
    }
    openSolutionModal(solution, "details");
    return;
  }
  if (allocation.work_item_type === "subcomponent") {
    const subcomponent = state.subcomponents.find((row) => row.subcomponent_id === workItemId);
    if (!subcomponent) {
      setStatus("The linked task is unavailable.", "warn");
      return;
    }
    const solution = state.solutions.find((row) => row.solution_id === subcomponent.solution_id);
    if (!solution) {
      setStatus("The linked solution is unavailable.", "warn");
      return;
    }
    openSolutionModal(solution, "subcomponents");
    fillSubcomponentForm(subcomponent);
    return;
  }
  setStatus("This allocation type does not have a linked drill-down yet.", "warn");
}

function openPMDashboardCapacityDrilldown(detail) {
  const allocations = Array.isArray(detail?.allocations) ? detail.allocations : [];
  const assigneeLabel = String(detail?.label || "Unassigned").trim() || "Unassigned";
  const scopeLabel = String(detail?.scopeLabel || "").trim();
  const allocated = Number(detail?.allocated);
  const capacity = Number(detail?.capacity);
  const utilization = Number(detail?.utilization);
  const summaryBits = [];
  if (scopeLabel) summaryBits.push(scopeLabel);
  if (Number.isFinite(allocated)) summaryBits.push(`${formatFte(allocated)} FTE-mo allocated`);
  if (Number.isFinite(capacity) && capacity > 0) summaryBits.push(`${formatFte(capacity)} FTE-mo capacity`);
  if (Number.isFinite(utilization) && capacity > 0) summaryBits.push(`${Math.round(utilization)}% load`);
  const itemsHtml = allocations.length
    ? allocations
        .map((allocation) => {
          const type = String(allocation.work_item_type || "").trim().toLowerCase();
          const itemTitle = allocationLabel(allocation) || allocation.work_item_id || "Unknown Item";
          const teamName = allocation.team_id ? state.teams.find((team) => team.team_id === allocation.team_id)?.name : "";
          const windowName = allocation.window_id ? state.planningWindows.find((row) => row.window_id === allocation.window_id)?.name : "";
          const actionLabel =
            type === "project" ? "Open Project" : type === "solution" ? "Open Solution" : type === "subcomponent" ? "Open Task" : "Open Item";
          const itemClass = type === "solution" || type === "subcomponent" ? ` ${type}` : "";
          return `<div class="modal-item${itemClass}">
            <div class="modal-item-title">${esc(itemTitle)}</div>
            <div class="modal-item-meta">${esc(allocation.work_item_type || "work item")} • ${formatFte(allocationFteMonths(allocation))} FTE-mo • ${esc(allocationMonthStart(allocation) || "—")}</div>
            <div class="modal-item-meta">Team: ${esc(teamName || "Unassigned")}${windowName ? ` • Window: ${esc(windowName)}` : ""}</div>
            <div class="modal-item-actions">
              <button type="button" class="secondary modal-item-action" data-planning-modal-action="open-allocation-work-item" data-allocation-id="${esc(allocation.allocation_id || "")}">${esc(actionLabel)}</button>
            </div>
          </div>`;
        })
        .join("")
    : '<p class="modal-empty">No allocations in this scope.</p>';
  const bodyHtml = `<div class="modal-section">
    <div class="modal-section-title">Capacity Summary</div>
    <div class="modal-item">
      <div class="modal-item-title">${esc(assigneeLabel)}</div>
      <div class="modal-item-meta">${esc(summaryBits.join(" • ") || "Allocation detail")}</div>
      <div class="modal-item-meta">${allocations.length} allocation${allocations.length === 1 ? "" : "s"} in this scope</div>
    </div>
  </div>
  <div class="modal-section">
    <div class="modal-section-title">Underlying Allocations</div>
    <div class="modal-list">${itemsHtml}</div>
  </div>`;
  openPlanningModal(`${assigneeLabel} Allocation Detail`, bodyHtml);
}

function openPMDashboardSolutionDrilldown(solutionId) {
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

function openKanbanProjectDrilldown(projectId) {
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  openProjectForm(project);
}

function openSubcomponentsWorkbenchProjectDrilldown(projectId) {
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  openProjectForm(project);
}

function openSubcomponentsWorkbenchSolutionDrilldown(solutionId) {
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

function renderSubcomponentsWorkbenchDrawerProjectLink(label, projectId) {
  const text = String(label || "").trim() || "Unknown project";
  const targetId = String(projectId || "").trim();
  if (!targetId) return escapeHtml(text);
  return `<button type="button" class="sub-workbench-context-link" data-scwb-context-action="open-project" data-project-id="${escapeHtml(targetId)}">${escapeHtml(text)}</button>`;
}

function renderSubcomponentsWorkbenchDrawerSolutionLink(label, solutionId) {
  const text = String(label || "").trim() || "Unknown solution";
  const targetId = String(solutionId || "").trim();
  if (!targetId) return escapeHtml(text);
  return `<button type="button" class="sub-workbench-context-link" data-scwb-context-action="open-solution" data-solution-id="${escapeHtml(targetId)}">${escapeHtml(text)}</button>`;
}

function renderSubcomponentsWorkbenchDrawerRepoContext(subcomponent) {
  const { url, source } = effectiveSubcomponentRepoInfo(
    subcomponent?.solution_id,
    subcomponent?.github_repo_url
  );
  if (!url) {
    return `<span class="sub-workbench-context-secondary">Repo: <span class="muted">Not set</span></span>`;
  }
  const sourceLabel = source === "override" ? "override" : "inherited";
  return `<span class="sub-workbench-context-secondary">Repo: ${renderExternalRepoLink(url, {
    label: url,
    className: "repo-external-link-inline",
  })} <span class="sub-workbench-context-source">(${escapeHtml(sourceLabel)})</span></span>`;
}

function openKanbanSolutionDrilldown(solutionId) {
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

function openPMDashboardSubcomponentDrilldown(subcomponentId) {
  const targetId = String(subcomponentId || "").trim();
  if (!targetId) return;
  const subcomponent = state.subcomponents.find((row) => row.subcomponent_id === targetId);
  if (!subcomponent) return;
  const solution = state.solutions.find((row) => row.solution_id === subcomponent.solution_id);
  if (!solution) return;
  openSolutionModal(solution, "subcomponents");
  fillSubcomponentForm(subcomponent);
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
    console.warn("Confirm modal shell missing; canceling action.");
    return Promise.resolve(false);
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
        setDeliverableFormNotice(els.projectFormStatus, "Deleting project...");
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
        setDeliverableFormNotice(
          els.projectFormStatus,
          `Delete failed: ${err.message}`,
          "error"
        );
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
      setDeliverableFormNotice(
        els.solutionFormStatus,
        "Select a project before creating a solution.",
        "error"
      );
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
      if (els.subcomponentForm && !els.subcomponentForm.classList.contains("hidden")) {
        const activeOverride = els.subcomponentForm.querySelector('[name="github_repo_url"]')?.value || "";
        updateSubcomponentRepoPreview(saved.solution_id, activeOverride);
      }
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
        setDeliverableFormNotice(els.solutionFormStatus, "Deleting solution...");
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
        setDeliverableFormNotice(
          els.solutionFormStatus,
          `Delete failed: ${err.message}`,
          "error"
        );
      }
    });
  }
}

function buildSolutionPayload(data) {
  const payload = {
    solution_name: data.get("solution_name"),
    github_repo_url: data.get("github_repo_url") || null,
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

function buildSubcomponentPayload(data) {
  const assigneeUserId = (data.get("assignee") || "").toString().trim();
  const assigneeUser = findUserBySoeid(assigneeUserId);
  return {
    subcomponent_name: data.get("subcomponent_name"),
    github_repo_url: data.get("github_repo_url") || null,
    status: data.get("status"),
    priority: Number(data.get("priority") || 3),
    due_date: data.get("due_date") || null,
    assignee: assigneeUser?.display_name || "",
    assignee_user_soeid: assigneeUserId || null,
    estimate_hours: hoursFromNullableFteInput(data.get("estimate_hours")),
    estimate_fte_months: numberOr(data.get("estimate_hours"), 0),
    blocked: data.get("blocked") ? true : false,
    blocker_note: data.get("blocker_note") || null,
    done_criteria: data.get("done_criteria") || null,
    capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
    capacity_fte_months: numberOr(data.get("capacity_hours"), 0),
  };
}

function fillSolutionForm(solution = null) {
  if (!els.solutionForm) return;
  els.solutionForm.reset();
  clearDeliverableFormNotice(els.solutionFormStatus);
  els.solutionForm.querySelector('[name="solution_id"]').value = solution?.solution_id || "";
  els.solutionForm.querySelector('[name="project_id"]').value = solution?.project_id || "";
  els.solutionForm.querySelector('[name="solution_name"]').value = solution?.solution_name || "";
  els.solutionForm.querySelector('[name="github_repo_url"]').value = solution?.github_repo_url || "";
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

function setSubcomponentActionButtonLabel(isEditing) {
  if (els.subcomponentSubmitBtn) {
    els.subcomponentSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Subcomponent";
  }
}

function setSubcomponentFormVisibility(show) {
  if (els.subcomponentForm) {
    els.subcomponentForm.classList.toggle("hidden", !show);
  }
  if (els.subcomponentFormFooter) {
    els.subcomponentFormFooter.classList.toggle("hidden", !show);
  }
}

function setSubcomponentCreateAvailability(solutionId) {
  if (!els.showSubcomponentFormBtn) return;
  const hasSolution = !!String(solutionId || "").trim();
  els.showSubcomponentFormBtn.disabled = !hasSolution;
  els.showSubcomponentFormBtn.title = hasSolution
    ? "Add a task to this solution"
    : "Save the solution before adding subcomponents.";
}

function openSolutionModal(solution = null, tab = "details") {
  if (!els.solutionModal) return;
  fillSolutionForm(solution);
  setSolutionActionButtonLabel(!!solution?.solution_id);
  setSubcomponentCreateAvailability(solution?.solution_id || "");
  if (els.subcomponentForm) {
    setSubcomponentFormVisibility(false);
    setSubcomponentActionButtonLabel(false);
  }
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
  setSubcomponentCreateAvailability("");
  els.solutionModal.classList.add("hidden");
  setSolutionTab("details");
  if (els.subcomponentForm) {
    setSubcomponentFormVisibility(false);
    setSubcomponentActionButtonLabel(false);
  }
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

function prepareSubcomponentCreateForm(solution, options = {}) {
  if (!els.subcomponentForm) return;
  const { resetForm = true } = options;
  const sol = solution || state.solutions.find((s) => s.solution_id === els.solutionForm?.querySelector('[name="solution_id"]')?.value);
  if (!sol) return;
  setSubcomponentFormVisibility(true);
  if (resetForm) els.subcomponentForm.reset();
  clearDeliverableFormNotice(els.subcomponentFormStatus);
  els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
  els.subcomponentForm.querySelector('[name="project_id"]').value = sol.project_id;
  els.subcomponentForm.querySelector('[name="solution_id"]').value = sol.solution_id;
  els.subcomponentForm.querySelector('[name="github_repo_url"]').value = "";
  els.subcomponentForm.querySelector('[name="priority"]').value = 3;
  els.subcomponentForm.querySelector('[name="status"]').value = "to_do";
  els.subcomponentForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(0, 0);
  updateSubcomponentRepoPreview(sol.solution_id, "");
  if (els.deleteSubcomponentBtn) {
    els.deleteSubcomponentBtn.disabled = true;
  }
  setSubcomponentActionButtonLabel(false);
}

function showSubcomponentForm(solution) {
  prepareSubcomponentCreateForm(solution);
}

function fillSubcomponentForm(sub) {
  if (!els.subcomponentForm || !sub) return;
  setSubcomponentFormVisibility(true);
  els.subcomponentForm.reset();
  clearDeliverableFormNotice(els.subcomponentFormStatus);
  els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = sub.subcomponent_id;
  els.subcomponentForm.querySelector('[name="project_id"]').value = sub.project_id;
  els.subcomponentForm.querySelector('[name="solution_id"]').value = sub.solution_id;
  els.subcomponentForm.querySelector('[name="subcomponent_name"]').value = sub.subcomponent_name || "";
  els.subcomponentForm.querySelector('[name="github_repo_url"]').value = sub.github_repo_url || "";
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
  updateSubcomponentRepoPreview(sub.solution_id, sub.github_repo_url || "");
  if (els.deleteSubcomponentBtn) {
    els.deleteSubcomponentBtn.disabled = !sub.subcomponent_id;
  }
  setSubcomponentActionButtonLabel(!!sub.subcomponent_id);
}

function renderSolutionSubcomponents(solutionId) {
  if (!els.solutionSubcomponentTable) return;
  if (!solutionId) {
    setSubcomponentCreateAvailability("");
    els.solutionSubcomponentTable.innerHTML = "<p class='muted'>Save the solution to add subcomponents.</p>";
    return;
  }
  setSubcomponentCreateAvailability(solutionId);
  const allSubs = state.subcomponents.filter((s) => s.solution_id === solutionId);
  const hiddenClosedCount = !showCompletedOperationalWork()
    ? allSubs.filter((subcomponent) => isCompletedSubcomponentStatus(subcomponent.status)).length
    : 0;
  const subs = showCompletedOperationalWork()
    ? allSubs
    : allSubs.filter((subcomponent) => !isCompletedSubcomponentStatus(subcomponent.status));
  const hiddenNote = hiddenClosedCount
    ? `<p class="form-notice">Completed items are hidden here. Use Show Completed in the top bar to review ${hiddenClosedCount} closed subcomponent${hiddenClosedCount === 1 ? "" : "s"}.</p>`
    : "";
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
    els.solutionSubcomponentTable.innerHTML = `${hiddenNote}<div class="swimlane-board">${columns}</div>`;
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
      ${hiddenNote}
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
        <tbody>${rows || `<tr><td colspan='6' class='muted'>${hiddenClosedCount ? "No open subcomponents in view." : "No subcomponents"}</td></tr>`}</tbody>
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
    if (els.subcomponentCreatePickerModal && !els.subcomponentCreatePickerModal.classList.contains("hidden")) {
      closeSubcomponentCreatePicker();
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

function bindSubcomponentCreatePicker() {
  if (els.subcomponentCreatePickerClose && !els.subcomponentCreatePickerClose._bound) {
    els.subcomponentCreatePickerClose.addEventListener("click", closeSubcomponentCreatePicker);
    els.subcomponentCreatePickerClose._bound = true;
  }
  if (els.subcomponentCreatePickerCancel && !els.subcomponentCreatePickerCancel._bound) {
    els.subcomponentCreatePickerCancel.addEventListener("click", closeSubcomponentCreatePicker);
    els.subcomponentCreatePickerCancel._bound = true;
  }
  if (els.subcomponentCreatePickerModal && !els.subcomponentCreatePickerModal._bound) {
    els.subcomponentCreatePickerModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSubcomponentCreatePicker);
    els.subcomponentCreatePickerModal._bound = true;
  }
  if (els.subcomponentCreatePickerForm && !els.subcomponentCreatePickerForm._bound) {
    els.subcomponentCreatePickerForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const solutionId = (new FormData(els.subcomponentCreatePickerForm).get("solution_id") || "").toString().trim();
      const solution = state.solutions.find((row) => row.solution_id === solutionId);
      if (!solution?.solution_id) {
        setDeliverableFormNotice(els.subcomponentCreatePickerStatus, "Choose a solution first.", "error");
        return;
      }
      continueSubcomponentCreateForSolution(solution);
    });
    els.subcomponentCreatePickerForm._bound = true;
  }
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
      els.phasesTable.innerHTML = "<p class='muted'>Unable to load phases.</p>";
      setDeliverableFormNotice(
        els.solutionFormStatus,
        `Unable to load phases: ${err.message}`,
        "error"
      );
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
        setDeliverableFormNotice(
          els.solutionFormStatus,
          `Phase update failed: ${err.message}`,
          "error"
        );
      }
    });
  });
}

function bindSubcomponentForm() {
  if (!els.subcomponentForm) return;
  if (!els.subcomponentForm._repoPreviewBound) {
    els.subcomponentForm.addEventListener("input", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const repoInput = target.closest('[name="github_repo_url"]');
      if (!repoInput) return;
      const solutionId = els.subcomponentForm?.querySelector('[name="solution_id"]')?.value || "";
      updateSubcomponentRepoPreview(solutionId, repoInput.value || "");
    });
    els.subcomponentForm._repoPreviewBound = true;
  }
  if (els.showSubcomponentFormBtn) {
    els.showSubcomponentFormBtn.onclick = () => {
      if (els.subcomponentForm.classList.contains("hidden")) {
        const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (!solutionId) {
          renderSolutionSubcomponents("");
          return;
        }
        const solution = state.solutions.find((s) => s.solution_id === solutionId);
        showSubcomponentForm(solution);
      } else {
        setSubcomponentFormVisibility(false);
      }
    };
  }
  els.subcomponentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(els.subcomponentForm);
    const id = (data.get("subcomponent_id") || "").toString().trim();
    const solutionId = (data.get("solution_id") || "").toString().trim();
    const isEditing = !!id;
    if (!solutionId) {
      setDeliverableFormNotice(els.subcomponentFormStatus, "Save the solution before adding subcomponents.", "error");
      return;
    }
    const payload = buildSubcomponentPayload(data);
    try {
      if (isEditing) {
        setDeliverableFormNotice(els.subcomponentFormStatus, "Saving subcomponent...");
      } else {
        setDeliverableFormNotice(els.subcomponentFormStatus, "Creating subcomponent...");
      }
      markIgnoreRefresh("subcomponents");
      const saved = isEditing
        ? await api(`/subcomponents/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await api(`/solutions/${solutionId}/subcomponents`, { method: "POST", body: JSON.stringify(payload) });
      upsertById(state.subcomponents, saved, "subcomponent_id");
      fillSubcomponentForm(saved);
      renderSolutionSubcomponents(saved.solution_id);
      renderDashboard();
      const successMessage = isEditing
        ? `Saved subcomponent at ${timestampLabel()}.`
        : `Created subcomponent at ${timestampLabel()}.`;
      setDeliverableFormNotice(
        els.subcomponentFormStatus,
        successMessage,
        "success",
        3200
      );
    } catch (err) {
      ignoreNextRefresh.delete("subcomponents");
      setDeliverableFormNotice(
        els.subcomponentFormStatus,
        `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
        "error"
      );
    }
  });
  els.subcomponentForm.addEventListener("reset", () => {
    clearDeliverableFormNotice(els.subcomponentFormStatus);
    const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
    if (solution) {
      prepareSubcomponentCreateForm(solution, { resetForm: false });
      return;
    }
    els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
    if (els.deleteSubcomponentBtn) {
      els.deleteSubcomponentBtn.disabled = true;
    }
    setSubcomponentActionButtonLabel(false);
  });
  if (els.deleteSubcomponentBtn) {
    els.deleteSubcomponentBtn.addEventListener("click", async () => {
      const id = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";
      if (!id) return;
      const solutionId = els.subcomponentForm?.querySelector('[name="solution_id"]')?.value || "";
      markIgnoreRefresh("subcomponents");
      const result = await deleteSubcomponentsById([id], {
        title: "Delete Subcomponent?",
      });
      if (result.cancelled) return;
      if (!result.deletedIds.length) {
        ignoreNextRefresh.delete("subcomponents");
      }
      const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
      if (solution) {
        showSubcomponentForm(solution);
      } else {
        els.subcomponentForm.reset();
        els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
        if (els.deleteSubcomponentBtn) els.deleteSubcomponentBtn.disabled = true;
        setSubcomponentActionButtonLabel(false);
      }
      renderSolutionSubcomponents(solutionId);
      renderDashboard();
      if (result.failed.length) {
        setDeliverableFormNotice(
          els.subcomponentFormStatus,
          `Delete failed: ${result.failed[0]?.error?.message || "Unable to delete subcomponent."}`,
          "error"
        );
        return;
      }
      setDeliverableFormNotice(
        els.subcomponentFormStatus,
        `Deleted subcomponent at ${timestampLabel()}.`,
        "success",
        3200
      );
    });
  }
}

function populateSelects() {
  const projectOpts = state.projects.map((p) => `<option value="${p.project_id}">${p.project_name}</option>`).join("");
  const kanbanProjectFilterChanged = normalizeScopedProjectFilter(state.kanbanFilters);
  const kanbanOwnerFilterChanged = normalizeScopedOwnerFilter(state.kanbanFilters, { includeSolutions: true });
  const calendarProjectFilterChanged = normalizeScopedProjectFilter(state.calendarFilters);
  const calendarOwnerFilterChanged = normalizeScopedOwnerFilter(state.calendarFilters, {
    includeSolutions: true,
    includeSubcomponents: true,
  });
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
  if (els.kanbanFilterOwner) {
    els.kanbanFilterOwner.value = state.kanbanFilters.owner || "";
  }
  if (els.calendarFilterProject) {
    els.calendarFilterProject.innerHTML = `<option value="">All</option>${projectOpts}`;
    els.calendarFilterProject.value = state.calendarFilters.project || "";
  }
  if (els.calendarFilterOwner) {
    els.calendarFilterOwner.value = state.calendarFilters.owner || "";
  }
  if (kanbanProjectFilterChanged) {
    persistKanbanViewState();
  }
  if (kanbanOwnerFilterChanged) {
    persistKanbanViewState();
  }
  if (calendarProjectFilterChanged) {
    persistCalendarViewState();
  }
  if (calendarOwnerFilterChanged) {
    persistCalendarViewState();
  }
  if (els.subcomponentsWorkbenchProject) {
    els.subcomponentsWorkbenchProject.innerHTML = `<option value="">All Projects</option>${projectOpts}`;
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
    const prev = els.planningWindowSelect.value || state.planningWindowSelectedId || "";
    els.planningWindowSelect.innerHTML = `<option value="">Select window</option>${winOpts}`;
    let nextSelectedId = "";
    if (prev && state.planningWindows.find((w) => w.window_id === prev)) {
      nextSelectedId = prev;
    } else if (state.planningWindows.length) {
      nextSelectedId = state.planningWindows[0].window_id;
    }
    els.planningWindowSelect.value = nextSelectedId;
    state.planningWindowSelectedId = nextSelectedId;
    if (prev !== nextSelectedId) persistPlanningWindowViewState();
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
      els.subcomponentsWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;
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
  normalizeSubcomponentsWorkbenchUiState({ persist: true });
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

const VALID_SUBCOMPONENTS_WORKBENCH_STATUSES = new Set([
  "",
  "to_do",
  "in_progress",
  "on_hold",
  "complete",
  "abandoned",
]);

function normalizeSubcomponentsWorkbenchPriorityFilter(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5) return "";
  return String(parsed);
}

function normalizeSubcomponentsWorkbenchFilters(filters = {}) {
  const next = {
    search: String(filters.search || ""),
    project_id: String(filters.project_id || ""),
    solution_id: String(filters.solution_id || ""),
    assignee: String(filters.assignee || ""),
    assignee_name: String(filters.assignee_name || ""),
    status: String(filters.status || ""),
    priority_max: normalizeSubcomponentsWorkbenchPriorityFilter(filters.priority_max),
  };
  let changed = next.priority_max !== String(filters.priority_max || "");

  if (!VALID_SUBCOMPONENTS_WORKBENCH_STATUSES.has(next.status)) {
    next.status = "";
    changed = true;
  }

  if (state.loadedEntities?.has("projects")) {
    const validProjectIds = new Set((state.projects || []).map((project) => project.project_id));
    if (next.project_id && !validProjectIds.has(next.project_id)) {
      next.project_id = "";
      changed = true;
    }
  }

  if (state.loadedEntities?.has("solutions")) {
    const filteredSolutions = next.project_id
      ? (state.solutions || []).filter((solution) => solution.project_id === next.project_id)
      : (state.solutions || []);
    const validSolutionIds = new Set(filteredSolutions.map((solution) => solution.solution_id));
    if (next.solution_id && !validSolutionIds.has(next.solution_id)) {
      next.solution_id = "";
      changed = true;
    }
  }

  if (state.loadedEntities?.has("users")) {
    const usersBySoeid = new Map(
      (state.users || [])
        .filter((user) => user?.soeid && user?.display_name)
        .map((user) => [String(user.soeid), String(user.display_name)])
    );
    if (next.assignee === "__unassigned__") {
      if (next.assignee_name) {
        next.assignee_name = "";
        changed = true;
      }
    } else if (next.assignee) {
      const displayName = usersBySoeid.get(next.assignee) || "";
      if (!displayName) {
        next.assignee = "";
        next.assignee_name = "";
        changed = true;
      } else if (next.assignee_name !== displayName) {
        next.assignee_name = displayName;
        changed = true;
      }
    } else if (next.assignee_name) {
      next.assignee_name = "";
      changed = true;
    }
  }

  return { filters: next, changed };
}

function syncSubcomponentsWorkbenchFilterControls() {
  const wb = state.subcomponentsWorkbench;
  if (els.subcomponentsWorkbenchSearch) els.subcomponentsWorkbenchSearch.value = wb.filters.search || "";
  if (els.subcomponentsWorkbenchProject) els.subcomponentsWorkbenchProject.value = wb.filters.project_id || "";
  updateSubcomponentsWorkbenchSolutionOptions(wb.filters.project_id || "");
  if (els.subcomponentsWorkbenchSolution) els.subcomponentsWorkbenchSolution.value = wb.filters.solution_id || "";
  if (els.subcomponentsWorkbenchAssignee) els.subcomponentsWorkbenchAssignee.value = wb.filters.assignee || "";
  if (els.subcomponentsWorkbenchStatus) els.subcomponentsWorkbenchStatus.value = wb.filters.status || "";
  if (els.subcomponentsWorkbenchPriority) els.subcomponentsWorkbenchPriority.value = wb.filters.priority_max || "";
}

function normalizeSubcomponentsWorkbenchUiState({ persist = false } = {}) {
  const wb = state.subcomponentsWorkbench;
  let changed = false;
  if (!VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(wb.preset || "all"))) {
    wb.preset = "all";
    changed = true;
  }
  const normalized = normalizeSubcomponentsWorkbenchFilters(wb.filters);
  wb.filters = normalized.filters;
  syncSubcomponentsWorkbenchFilterControls();
  if (persist && (normalized.changed || changed)) persistSubcomponentsWorkbenchUiState();
  return normalized.changed || changed;
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
    openKanbanProjectDrilldown,
    openKanbanSolutionDrilldown,
  });
}

function normalizeScopedOwnerFilter(filterState, { includeSolutions = true, includeSubcomponents = false } = {}) {
  if (!filterState || typeof filterState !== "object") return false;
  const currentOwner = String(filterState.owner || "").trim();
  if (!currentOwner) return false;
  const ownerToken = currentOwner.toLowerCase();
  const hasSolutionMatch = includeSolutions
    && (state.solutions || []).some((solution) => String(solution?.owner || "").toLowerCase().includes(ownerToken));
  const hasSubcomponentMatch = includeSubcomponents
    && (state.subcomponents || []).some((subcomponent) => {
      const assigneeName = String(subcomponent?.assignee || "").toLowerCase();
      const assigneeSoeid = String(subcomponent?.assignee_user_soeid || "").toLowerCase();
      return assigneeName.includes(ownerToken) || assigneeSoeid.includes(ownerToken);
    });
  if (hasSolutionMatch || hasSubcomponentMatch) return false;
  filterState.owner = "";
  return true;
}

function normalizeScopedProjectFilter(filterState) {
  if (!filterState || typeof filterState !== "object") return false;
  const validProjectIds = new Set((state.projects || []).map((project) => project.project_id));
  const currentProjectId = String(filterState.project || "");
  if (!currentProjectId || validProjectIds.has(currentProjectId)) return false;
  filterState.project = "";
  return true;
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

function parseMonthInputValue(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}$/.test(raw)) return null;
  const [yearText, monthText] = raw.split("-");
  const year = Number(yearText);
  const monthIndex = Number(monthText) - 1;
  if (!Number.isFinite(year) || !Number.isFinite(monthIndex) || monthIndex < 0 || monthIndex > 11) return null;
  return new Date(year, monthIndex, 1);
}

function setCalendarMonth(date) {
  if (!date || Number.isNaN(date)) return;
  state.calendarMonth = new Date(date.getFullYear(), date.getMonth(), 1);
  if (els.calendarMonthInput) {
    els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth);
  }
  persistCalendarViewState();
  renderCalendar();
}

function closeCalendarModal() {
  els.calendarModal?.classList.add("hidden");
}

function openCalendarSolutionDrilldown(solutionId) {
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  closeCalendarModal();
  openSolutionModal(solution, "details");
}

function openCalendarProjectDrilldown(projectId) {
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  closeCalendarModal();
  openProjectForm(project);
}

function openCalendarSubcomponentDrilldown(subcomponentId) {
  const targetId = String(subcomponentId || "").trim();
  if (!targetId) return;
  const subcomponent = state.subcomponents.find((row) => row.subcomponent_id === targetId);
  if (!subcomponent) return;
  const solution = state.solutions.find((row) => row.solution_id === subcomponent.solution_id);
  if (!solution) return;
  closeCalendarModal();
  openSolutionModal(solution, "subcomponents");
  fillSubcomponentForm(subcomponent);
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
        "project_name,solution_name,version,status,owner,assignee,priority,due_date,current_phase,github_repo_url",
        "Example Project,Example Solution,0.1.0,not_started,Example Owner,Example Owner,3,,,https://github.com/example-org/example-repo",
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
    closeTopbarCreateMenu({ restoreFocus: false });
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
  const closeSwitcher = ({ returnFocus = false } = {}) => {
    if (!state.spaceSwitcherOpen) return;
    state.spaceSwitcherOpen = false;
    state.spaceSwitcherQuery = "";
    if (els.spaceSwitcherSearch) els.spaceSwitcherSearch.value = "";
    renderSpaceSwitcher();
    if (returnFocus) els.spaceSwitcherTrigger?.focus();
  };
  const openSwitcher = () => {
    if (!state.authed || state.spaceSwitching || !(state.spaces || []).length) return;
    state.spaceSwitcherOpen = true;
    renderSpaceSwitcher();
    window.setTimeout(() => {
      els.spaceSwitcherSearch?.focus();
      els.spaceSwitcherSearch?.select();
    }, 0);
  };
  const visibleOptions = () => Array.from(
    els.spaceSwitcherPanel?.querySelectorAll(".space-switcher-option:not([disabled])") || []
  );
  const moveFocus = (delta) => {
    const options = visibleOptions();
    if (!options.length) return;
    const currentIndex = options.indexOf(document.activeElement);
    const nextIndex = currentIndex === -1
      ? (delta > 0 ? 0 : options.length - 1)
      : (currentIndex + delta + options.length) % options.length;
    options[nextIndex]?.focus();
  };

  if (els.spaceSwitcherTrigger && !els.spaceSwitcherTrigger._bound) {
    els.spaceSwitcherTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      if (state.spaceSwitcherOpen) closeSwitcher();
      else openSwitcher();
    });
    els.spaceSwitcherTrigger.addEventListener("keydown", (event) => {
      if (!["Enter", " ", "ArrowDown"].includes(event.key)) return;
      event.preventDefault();
      openSwitcher();
    });
    els.spaceSwitcherTrigger._bound = true;
  }
  if (els.spaceSwitcherClose && !els.spaceSwitcherClose._bound) {
    els.spaceSwitcherClose.addEventListener("click", () => closeSwitcher({ returnFocus: true }));
    els.spaceSwitcherClose._bound = true;
  }
  if (els.spaceSwitcherSearch && !els.spaceSwitcherSearch._bound) {
    els.spaceSwitcherSearch.addEventListener("input", () => {
      state.spaceSwitcherQuery = els.spaceSwitcherSearch.value || "";
      renderSpaceSwitcher();
    });
    els.spaceSwitcherSearch.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeSwitcher({ returnFocus: true });
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveFocus(1);
      }
    });
    els.spaceSwitcherSearch._bound = true;
  }
  if (els.spaceSwitcherPanel && !els.spaceSwitcherPanel._bound) {
    els.spaceSwitcherPanel.addEventListener("click", async (event) => {
      event.stopPropagation();
      const button = event.target.closest("button[data-space-switch]");
      if (!button) return;
      const targetSpaceId = button.getAttribute("data-space-switch") || "";
      if (!targetSpaceId) return;
      await switchActiveSpace(targetSpaceId);
    });
    els.spaceSwitcherPanel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeSwitcher({ returnFocus: true });
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveFocus(1);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        moveFocus(-1);
        return;
      }
      if (event.key === "Home") {
        event.preventDefault();
        visibleOptions()[0]?.focus();
        return;
      }
      if (event.key === "End") {
        event.preventDefault();
        const options = visibleOptions();
        options[options.length - 1]?.focus();
      }
    });
    els.spaceSwitcherPanel._bound = true;
  }
  if (!document._spaceSwitcherCloseBound) {
    document.addEventListener("click", (event) => {
      if (!state.spaceSwitcherOpen) return;
      const shell = els.spaceSwitcherShell;
      if (shell?.contains(event.target)) return;
      closeSwitcher();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (state.spaceSwitcherOpen) {
        event.preventDefault();
        closeSwitcher({ returnFocus: true });
      }
    });
    document._spaceSwitcherCloseBound = true;
  }
}

function bindNav() {
  els.navButtons.forEach((btn) =>
    btn.addEventListener("click", () => {
      setView(btn.dataset.view);
    })
  );
  window.addEventListener("popstate", () => {
    if (routerController.isRouteChangeSuppressed()) return;
    setView(viewFromLocationPath(), { fromHistory: true });
  });
  if (!document._appRouteClickBound) {
    document.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!link) return;
      if (link.hasAttribute("download")) return;
      const targetAttr = (link.getAttribute("target") || "").trim().toLowerCase();
      if (targetAttr && targetAttr !== "_self") return;
      const href = link.getAttribute("href") || "";
      if (!href || href.startsWith("#")) return;
      let url;
      try {
        url = new URL(link.href, window.location.origin);
      } catch {
        return;
      }
      if (url.origin !== window.location.origin) return;
      if (isResetPathname(url.pathname)) return;
      const relativePath = appRelativePath(url.pathname);
      if (!relativePath.startsWith("/")) return;
      const candidateView = viewFromLocationPath(url.pathname);
      const canonicalPath = new URL(viewHref(candidateView), window.location.origin).pathname;
      if (url.pathname !== canonicalPath && url.pathname !== canonicalPath.replace(/\/+$/, "")) return;
      event.preventDefault();
      setView(candidateView);
    });
    document._appRouteClickBound = true;
  }
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
      const previewActionEl = e.target.closest("[data-calendar-preview-action]");
      if (previewActionEl) {
        const action = previewActionEl.getAttribute("data-calendar-preview-action") || "";
        if (action === "open-solution") {
          openCalendarSolutionDrilldown(previewActionEl.getAttribute("data-solution-id"));
        }
        return;
      }
      const cell = e.target.closest(".calendar-cell[data-day]");
      if (!cell) return;
      const day = Number(cell.getAttribute("data-day"));
      if (Number.isFinite(day)) openCalendarModal(day);
    });
  }
  els.calendarModalClose?.addEventListener("click", closeCalendarModal);
  els.calendarModalList?.addEventListener("click", (e) => {
    const actionEl = e.target.closest("[data-calendar-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-calendar-action") || "";
    if (action === "open-project") {
      openCalendarProjectDrilldown(actionEl.getAttribute("data-project-id"));
      return;
    }
    if (action === "open-solution") {
      openCalendarSolutionDrilldown(actionEl.getAttribute("data-solution-id"));
      return;
    }
    if (action === "open-subcomponent") {
      openCalendarSubcomponentDrilldown(actionEl.getAttribute("data-subcomponent-id"));
    }
  });
  els.calendarModal?.addEventListener("click", (e) => {
    if (e.target === els.calendarModal || e.target.classList.contains("modal-backdrop")) {
      closeCalendarModal();
    }
  });

  els.kanbanFilterProject?.addEventListener("change", () => {
    state.kanbanFilters.project = els.kanbanFilterProject.value || "";
    persistKanbanViewState();
    renderKanban();
  });
  bindDebouncedInput(els.kanbanFilterOwner, (value) => {
    state.kanbanFilters.owner = value;
    persistKanbanViewState();
    renderKanban();
  });
  els.calendarFilterProject?.addEventListener("change", () => {
    state.calendarFilters.project = els.calendarFilterProject.value || "";
    persistCalendarViewState();
    renderCalendar();
  });
  bindDebouncedInput(els.calendarFilterOwner, (value) => {
    state.calendarFilters.owner = value;
    persistCalendarViewState();
    renderCalendar();
  });

  if (els.planningWindowSelect) {
    els.planningWindowSelect.addEventListener("change", () => {
      state.planningWindowSelectedId = els.planningWindowSelect.value || "";
      persistPlanningWindowViewState();
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
        const confirmed = await showConfirmModal({
          title: "Delete Allocation?",
          message: "Delete this allocation?",
          confirmLabel: "Delete Allocation",
        });
        if (!confirmed) return;
        try {
          await api(`/resource-allocations/${allocId}`, { method: "DELETE" });
          state.allocations = state.allocations.filter((a) => a.allocation_id !== allocId);
          renderPlanning();
        } catch (err) {
          if (els.allocationStatus) els.allocationStatus.textContent = `Delete failed: ${err.message}`;
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
        openPlanningModal("Allocation Details", details);
      }
    });
  }
  if (els.planningModal) {
    els.planningModal.addEventListener("click", (e) => {
      if (!(e.target instanceof Element)) return;
      const actionEl = e.target.closest("[data-planning-modal-action]");
      if (actionEl) {
        const action = actionEl.getAttribute("data-planning-modal-action") || "";
        if (action === "open-allocation-work-item") {
          const allocationId = actionEl.getAttribute("data-allocation-id") || "";
          openAllocationWorkItemDrilldown(allocationId);
        }
        return;
      }
      if (e.target === els.planningModal || e.target.classList.contains("modal-backdrop")) {
        closePlanningModal();
      }
    });
  }
  els.planningModalClose?.addEventListener("click", () => closePlanningModal());

  if (els.planningWindowForm) {
    els.planningWindowForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.planningWindowForm);
      const editId = data.get("window_id_edit");
      const name = data.get("window_name");
      const start = data.get("window_start");
      const end = data.get("window_end");
      if (!name || !start || !end) {
        setStatus("Name, start, and end are required to create a planning window.", "danger");
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
        state.planningWindowSelectedId = savedWin.window_id;
        persistPlanningWindowViewState();
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
        setStatus(`Window create failed: ${err.message}`, "danger");
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
        if (els.allocationStatus) els.allocationStatus.textContent = `Save failed: ${err.message || err}`;
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
  const preserveStatus = !!options.preserveStatus;
  const shouldRender = options.render !== false;
  const next = user || null;
  if (!preserveStatus) clearCapacityUserFormStatus();
  state.capacitySelectedSoeid = next?.soeid || "";
  form.querySelector('[name="soeid"]').value = next?.soeid || "";
  if (!preserveName) {
    form.querySelector('[name="display_name"]').value = next?.display_name || "";
  }
  form.querySelector('[name="team_tag"]').value = next?.team_tag || "";
  form.querySelector('[name="capacity_fte_month"]').value = formatFte(next ? userCapacityFteMonth(next) : 1);
  persistTeamCapacityViewState();
  if (shouldRender && state.currentView === "team-capacity") {
    renderTeamCapacity();
  }
}

function clearCapacityUserForm(options = {}) {
  if (!els.capacityUserForm) return;
  const preserveStatus = !!options.preserveStatus;
  const shouldRender = options.render !== false;
  if (!preserveStatus) clearCapacityUserFormStatus();
  els.capacityUserForm.reset();
  state.capacitySelectedSoeid = "";
  els.capacityUserForm.querySelector('[name="soeid"]').value = "";
  const fteField = els.capacityUserForm.querySelector('[name="capacity_fte_month"]');
  if (fteField) fteField.value = "1.00";
  persistTeamCapacityViewState();
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
    persistTeamCapacityViewState();
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
        clearCapacityUserFormStatus();
        const match = findCapacityUserByValue(nameInput.value || "");
        els.capacityUserForm.querySelector('[name="soeid"]').value = match?.soeid || "";
        if (match) {
          state.capacitySelectedSoeid = match.soeid || "";
          els.capacityUserForm.querySelector('[name="team_tag"]').value = match.team_tag || "";
          els.capacityUserForm.querySelector('[name="capacity_fte_month"]').value = formatFte(userCapacityFteMonth(match));
          persistTeamCapacityViewState();
          if (state.currentView === "team-capacity") renderTeamCapacity();
        } else if (state.capacitySelectedSoeid) {
          state.capacitySelectedSoeid = "";
          persistTeamCapacityViewState();
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
        setCapacityUserFormStatus("Select a member from the roster (or type an exact SOEID/name match) first.", "error");
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
        if (refreshed) selectCapacityUser(refreshed, { preserveStatus: true });
        else clearCapacityUserForm({ preserveStatus: true });
        setCapacityUserFormStatus(`Saved member at ${timestampLabel()}.`, "success", 3200);
      } catch (err) {
        setCapacityUserFormStatus(`Save failed: ${err.message}`, "error");
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
        setCapacityUserFormStatus("Select a member first.", "error");
        return;
      }
      const confirmed = await showConfirmModal({
        title: "Deactivate Member?",
        message: "Deactivate this member? They will be hidden from the roster.",
        confirmLabel: "Deactivate Member",
      });
      if (!confirmed) return;
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify({ is_active: false }) });
        clearCapacityUserForm({ render: false, preserveStatus: true });
        await loadTeamCapacityData({ force: true, preserveSelection: false });
        setCapacityUserFormStatus(`Member deactivated at ${timestampLabel()}.`, "success", 3200);
      } catch (err) {
        setCapacityUserFormStatus(`Delete failed: ${err.message}`, "error");
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
  bindDebouncedInput(els.capacityTeamFilter, () => {
    persistTeamCapacityViewState();
    renderTeamCapacity();
  });
  bindDebouncedInput(els.capacityNameFilter, () => {
    persistTeamCapacityViewState();
    renderTeamCapacity();
  });
  if (els.capacityReload) {
    els.capacityReload.addEventListener("click", async () => {
      await loadTeamCapacityData({ force: true });
    });
  }
  if (els.capacityClearFilters) {
    els.capacityClearFilters.addEventListener("click", () => {
      if (els.capacityTeamFilter) els.capacityTeamFilter.value = "";
      if (els.capacityNameFilter) els.capacityNameFilter.value = "";
      persistTeamCapacityViewState();
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

function activeSpaceScopedStorageKey(prefix, spaceId = activeSpaceId()) {
  const scope = normalize(spaceId || "no-space");
  return `${prefix}:${scope}`;
}

function readStoredJson(key, fallback) {
  return readStoredJsonState(key, fallback).value;
}

function readStoredJsonState(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return { value: fallback, recovered: false };
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return { value: parsed, recovered: false };
    }
    console.warn(`Stored state for ${key} was not an object and will be reset.`);
    return { value: fallback, recovered: true };
  } catch (err) {
    console.warn(`Unable to read stored state for ${key}`, err);
    return { value: fallback, recovered: true };
  }
}

function writeStoredJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (err) {
    console.warn(`Unable to persist state for ${key}`, err);
  }
}

function userScopedStorageKey(prefix) {
  const scope = normalize(state.user?.user_id || state.user?.soeid || state.user?.email || "anon");
  return `${prefix}:${scope}`;
}

function renderCompletedVisibilityToggle() {
  if (!els.completedVisibilityToggle) return;
  const showCompleted = !!state.workspacePrefs?.showCompleted;
  els.completedVisibilityToggle.disabled = !state.authed;
  els.completedVisibilityToggle.textContent = `Show Completed: ${showCompleted ? "On" : "Off"}`;
  els.completedVisibilityToggle.setAttribute("aria-pressed", showCompleted ? "true" : "false");
  els.completedVisibilityToggle.classList.toggle("active", showCompleted);
  els.completedVisibilityToggle.title = showCompleted
    ? "Completed and abandoned work is visible in operational views."
    : "Completed and abandoned work is hidden from operational views.";
}

function readRecentSpaceIds() {
  const storageKey = userScopedStorageKey(SPACE_RECENTS_KEY_PREFIX);
  const { value: stored, recovered } = readStoredJsonState(storageKey, { recent: [] });
  const recent = Array.isArray(stored.recent) ? stored.recent : [];
  const normalizedRecent = recent
    .map((spaceId) => String(spaceId || "").trim())
    .filter(Boolean)
    .filter((spaceId, index, list) => list.indexOf(spaceId) === index)
    .slice(0, RECENT_SPACES_LIMIT);
  if (recovered || JSON.stringify(recent) !== JSON.stringify(normalizedRecent)) {
    writeStoredJson(storageKey, { recent: normalizedRecent });
  }
  return normalizedRecent;
}

function persistRecentSpaceIds() {
  writeStoredJson(userScopedStorageKey(SPACE_RECENTS_KEY_PREFIX), {
    recent: state.spaceRecentIds.slice(0, RECENT_SPACES_LIMIT),
  });
}

function recordRecentSpace(spaceId) {
  const target = String(spaceId || "").trim();
  if (!target) return;
  state.spaceRecentIds = [target, ...state.spaceRecentIds.filter((id) => id !== target)].slice(0, RECENT_SPACES_LIMIT);
  persistRecentSpaceIds();
}

function persistMasterViewState() {
  writeStoredJson(
    activeSpaceScopedStorageKey(MASTER_VIEW_STATE_KEY_PREFIX),
    {
      filters: { ...(state.filters || {}) },
      deliverablesPreset: state.deliverablesPreset || "",
    }
  );
}

function persistWorkspaceViewPreferences() {
  writeStoredJson(
    activeSpaceScopedStorageKey(WORKSPACE_VIEW_PREFS_KEY_PREFIX),
    {
      showCompleted: !!state.workspacePrefs?.showCompleted,
    }
  );
}

function restoreWorkspaceViewPreferences() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(WORKSPACE_VIEW_PREFS_KEY_PREFIX), {});
  const nextShowCompleted = stored.showCompleted === true;
  state.workspacePrefs = {
    showCompleted: nextShowCompleted,
  };
  if (recovered || !Object.keys(stored || {}).length || stored.showCompleted !== nextShowCompleted) {
    persistWorkspaceViewPreferences();
  }
  renderCompletedVisibilityToggle();
}

function restoreMasterViewState() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(MASTER_VIEW_STATE_KEY_PREFIX), {});
  const rawFilters = stored.filters && typeof stored.filters === "object" ? { ...stored.filters } : {};
  state.deliverablesPreset = String(stored.deliverablesPreset || "");
  let changed = recovered;
  if (!VALID_DELIVERABLE_PRESETS.has(state.deliverablesPreset)) {
    state.deliverablesPreset = "";
    changed = true;
  }
  const normalized = normalizeMasterFilters(rawFilters, state.deliverablesPreset);
  state.filters = normalized.filters;
  if (normalized.changed) changed = true;
  if (changed) persistMasterViewState();
}

function persistCalendarViewState() {
  writeStoredJson(
    activeSpaceScopedStorageKey(CALENDAR_VIEW_STATE_KEY_PREFIX),
    {
      month: formatMonthInputValue(state.calendarMonth || new Date()),
      filters: {
        project: state.calendarFilters?.project || "",
        owner: state.calendarFilters?.owner || "",
      },
    }
  );
}

function restoreCalendarViewState() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(CALENDAR_VIEW_STATE_KEY_PREFIX), {});
  const parsedMonth = parseMonthInputValue(stored.month || "");
  state.calendarMonth = parsedMonth || state.calendarMonth || new Date();
  state.calendarFilters = {
    project: String(stored.filters?.project || ""),
    owner: String(stored.filters?.owner || ""),
  };
  if (recovered) persistCalendarViewState();
  if (recovered) return;
  if (recovered || !Object.keys(stored || {}).length || !parsedMonth) persistCalendarViewState();
}

function persistKanbanViewState() {
  writeStoredJson(
    activeSpaceScopedStorageKey(KANBAN_VIEW_STATE_KEY_PREFIX),
    {
      filters: {
        project: state.kanbanFilters?.project || "",
        owner: state.kanbanFilters?.owner || "",
      },
    }
  );
}

function restoreKanbanViewState() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(KANBAN_VIEW_STATE_KEY_PREFIX), {});
  state.kanbanFilters = {
    project: String(stored.filters?.project || ""),
    owner: String(stored.filters?.owner || ""),
  };
  if (recovered) persistKanbanViewState();
  if (recovered) return;
  if (recovered || !Object.keys(stored || {}).length) persistKanbanViewState();
}

function persistTeamCapacityViewState() {
  writeStoredJson(
    activeSpaceScopedStorageKey(TEAM_CAPACITY_VIEW_STATE_KEY_PREFIX),
    {
      team_filter: String(els.capacityTeamFilter?.value || ""),
      name_filter: String(els.capacityNameFilter?.value || ""),
      selected_soeid: String(state.capacitySelectedSoeid || ""),
    }
  );
}

function restoreTeamCapacityViewState() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(TEAM_CAPACITY_VIEW_STATE_KEY_PREFIX), {});
  if (els.capacityTeamFilter) els.capacityTeamFilter.value = String(stored.team_filter || "");
  if (els.capacityNameFilter) els.capacityNameFilter.value = String(stored.name_filter || "");
  state.capacitySelectedSoeid = String(stored.selected_soeid || "");
  if (recovered) persistTeamCapacityViewState();
  if (recovered) return;
  if (recovered || !Object.keys(stored || {}).length) persistTeamCapacityViewState();
}

function persistPlanningWindowViewState() {
  writeStoredJson(
    activeSpaceScopedStorageKey(PLANNING_WINDOW_VIEW_STATE_KEY_PREFIX),
    {
      selected_window_id: String(state.planningWindowSelectedId || ""),
    }
  );
}

function restorePlanningWindowViewState() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(PLANNING_WINDOW_VIEW_STATE_KEY_PREFIX), {});
  state.planningWindowSelectedId = String(stored.selected_window_id || "");
  if (recovered || !Object.keys(stored || {}).length) persistPlanningWindowViewState();
}

function persistSubcomponentsWorkbenchUiState() {
  const wb = state.subcomponentsWorkbench;
  writeStoredJson(
    activeSpaceScopedStorageKey(SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX),
    {
      preset: wb.preset || "all",
      filters: {
        search: wb.filters?.search || "",
        project_id: wb.filters?.project_id || "",
        solution_id: wb.filters?.solution_id || "",
        assignee: wb.filters?.assignee || "",
        assignee_name: wb.filters?.assignee_name || "",
        status: wb.filters?.status || "",
        priority_max: wb.filters?.priority_max || "",
      },
      activeSubcomponentId: wb.activeSubcomponentId || "",
      selectedSavedViewId: wb.selectedSavedViewId || "",
      drawerOpen: wb.drawerOpen !== false,
    }
  );
}

function restoreSubcomponentsWorkbenchUiState() {
  const wb = state.subcomponentsWorkbench;
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(SUBCOMPONENTS_WORKBENCH_UI_STATE_KEY_PREFIX), {});
  wb.preset = String(stored.preset || "all");
  wb.filters = {
    search: String(stored.filters?.search || ""),
    project_id: String(stored.filters?.project_id || ""),
    solution_id: String(stored.filters?.solution_id || ""),
    assignee: String(stored.filters?.assignee || ""),
    assignee_name: String(stored.filters?.assignee_name || ""),
    status: String(stored.filters?.status || ""),
    priority_max: String(stored.filters?.priority_max || ""),
  };
  wb.selected.clear();
  wb.activeSubcomponentId = String(stored.activeSubcomponentId || "");
  wb.selectedSavedViewId = String(stored.selectedSavedViewId || "");
  wb.drawerOpen = stored.drawerOpen !== false;
  normalizeSubcomponentsWorkbenchUiState();
  if (recovered || !Object.keys(stored || {}).length) persistSubcomponentsWorkbenchUiState();
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

function normalizeGovernanceSection(value) {
  const raw = normalize(value).replace(/[\s_]+/g, "-");
  return raw || "current-space";
}

function governanceSections() {
  const sections = [
    { id: "current-space", label: "Current Space" },
    { id: "space-directory", label: "Space Directory" },
  ];
  if (userIsGlobalAdmin()) {
    sections.push({ id: "platform-access", label: "Platform Access" });
  }
  return sections;
}

function resolveGovernanceSection(preferred = "") {
  const allowed = governanceSections().map((section) => section.id);
  const preferredId = normalizeGovernanceSection(preferred);
  if (preferred && allowed.includes(preferredId)) {
    state.spaceAdminSection = preferredId;
  }
  if (!allowed.includes(state.spaceAdminSection)) {
    state.spaceAdminSection = allowed.includes(preferredId) ? preferredId : (allowed[0] || "current-space");
  }
  return state.spaceAdminSection;
}

function effectiveDirectorySpaces() {
  const merged = new Map();
  (state.spaces || []).forEach((space) => {
    if (!space?.space_id) return;
    merged.set(space.space_id, { ...space, is_active: space.is_active !== false });
  });
  if (state.spaceDirectoryShowArchived) {
    Object.values(state.archivedSpacesById || {}).forEach((space) => {
      if (!space?.space_id) return;
      if (!merged.has(space.space_id)) {
        merged.set(space.space_id, { ...space, is_active: false });
      }
    });
  }
  return Array.from(merged.values()).sort((a, b) => (a.name || "").localeCompare(b.name || ""));
}

function directorySpaceById(spaceId) {
  const targetSpaceId = String(spaceId || "").trim();
  if (!targetSpaceId) return null;
  return effectiveDirectorySpaces().find((space) => space.space_id === targetSpaceId)
    || (state.spaces || []).find((space) => space.space_id === targetSpaceId)
    || Object.values(state.archivedSpacesById || {}).find((space) => space?.space_id === targetSpaceId)
    || null;
}

function ensureSelectedDirectorySpace() {
  const spaces = effectiveDirectorySpaces();
  const availableIds = new Set(spaces.map((space) => space.space_id));
  if (!state.spaceMembershipSpaceId || !availableIds.has(state.spaceMembershipSpaceId)) {
    state.spaceMembershipSpaceId = activeSpaceId() || spaces[0]?.space_id || "";
  }
  return spaces.find((space) => space.space_id === state.spaceMembershipSpaceId) || null;
}

function roleBadgeLabelForSpace(space) {
  if (!space) return "";
  if (space.space_id === activeSpaceId()) return currentSpaceRoleLabel(state.activeSpace);
  if (userIsGlobalAdmin()) return "Global Admin";
  return "Accessible";
}

function roleBadgeClass(label) {
  const normalized = normalize(label);
  if (normalized.includes("admin")) return "";
  if (normalized === "accessible") return "muted";
  return "muted";
}

function membershipSummaryForSpace(spaceId) {
  const members = state.spaceMembersBySpace[spaceId] || [];
  return {
    total: members.length,
    active: members.filter((row) => normalize(row.status) === "active").length,
    admins: members.filter((row) => normalizeSpaceRole(row.role) === "space_admin" && normalize(row.status) === "active").length,
    inactive: members.filter((row) => normalize(row.status) === "inactive").length,
  };
}

function openSpaceCreateModal() {
  if (!userIsGlobalAdmin() || !els.spaceCreateModal) return;
  els.spaceCreateModal.classList.remove("hidden");
  els.spaceCreateModalForm?.reset();
  clearDeliverableFormNotice(els.spaceCreateStatus);
  window.setTimeout(() => {
    els.spaceCreateModalForm?.querySelector('[name="name"]')?.focus();
  }, 0);
}

function closeSpaceCreateModal() {
  els.spaceCreateModal?.classList.add("hidden");
}

function openSpaceMemberModal(spaceId = activeSpaceId()) {
  const targetSpaceId = String(spaceId || "").trim();
  if (!targetSpaceId || !canManageSpaceMembership(targetSpaceId) || !els.spaceMemberModalForm) return;
  const targetSpace = effectiveDirectorySpaces().find((space) => space.space_id === targetSpaceId)
    || (state.spaces || []).find((space) => space.space_id === targetSpaceId)
    || null;
  els.spaceMemberModalForm.reset();
  els.spaceMemberModalForm.querySelector('[name="space_id"]').value = targetSpaceId;
  if (els.spaceMemberModalContext) {
    els.spaceMemberModalContext.textContent = `Adding a member to ${targetSpace?.name || targetSpaceId}.`;
  }
  clearDeliverableFormNotice(els.spaceMemberStatus);
  els.spaceMemberModal.classList.remove("hidden");
  window.setTimeout(() => {
    els.spaceMemberModalForm?.querySelector('[name="soeid"]')?.focus();
  }, 0);
}

function closeSpaceMemberModal() {
  els.spaceMemberModal?.classList.add("hidden");
}

function openSpaceDirectoryModal(spaceId) {
  const targetSpaceId = String(spaceId || state.spaceMembershipSpaceId || "").trim();
  if (!targetSpaceId || !els.spaceDirectoryModal) return;
  state.spaceMembershipSpaceId = targetSpaceId;
  state.spaceDirectoryModalOpen = true;
  renderSpaceDirectoryModal();
  els.spaceDirectoryModal.classList.remove("hidden");
  window.setTimeout(() => {
    els.spaceDirectoryModalClose?.focus();
  }, 0);
}

function closeSpaceDirectoryModal() {
  state.spaceDirectoryModalOpen = false;
  els.spaceDirectoryModal?.classList.add("hidden");
}

function renderGovernanceNotice() {
  if (!state.spaceGovernanceNotice?.text) return "";
  const toneClass = state.spaceGovernanceNotice.tone === "error"
    ? " notice-error"
    : (state.spaceGovernanceNotice.tone === "success" ? " notice-success" : "");
  return `<p class="form-notice space-governance-notice${toneClass}" role="status" aria-live="polite">${esc(state.spaceGovernanceNotice.text)}</p>`;
}

function renderMembershipTable(spaceId) {
  const canManage = canManageSpaceMembership(spaceId) && !state.spaceSwitching;
  const members = state.spaceMembersBySpace[spaceId] || [];
  if (!members.length) {
    return `
      <div class="space-empty-card">
        <h3>No members yet</h3>
        <p class="muted">Add people to this space so ownership, planning, and access can be managed without leaving the governance hub.</p>
      </div>
    `;
  }
  const rows = members.map((row) => {
    const nextRole = normalizeSpaceRole(row.role) === "space_admin" ? "member" : "space_admin";
    const nextStatus = normalize(row.status) === "active" ? "inactive" : "active";
    const menuOpen = state.spaceMembershipActionMenuId === row.membership_id;
    const soeid = row.user_soeid ? `<span>${esc(row.user_soeid)}</span>` : "";
    const email = row.user_email ? `<span>${esc(row.user_email)}</span>` : "";
    return `<tr data-membership-id="${escapeAttr(row.membership_id)}">
      <td>
        <div class="space-member-cell">
          <strong>${esc(memberLabel(row))}</strong>
          <div class="space-member-meta">${soeid}${soeid && email ? " • " : ""}${email}</div>
        </div>
      </td>
      <td><span class="pill ${normalizeSpaceRole(row.role) === "space_admin" ? "" : "muted"}">${esc(row.role)}</span></td>
      <td><span class="pill ${normalize(row.status) === "active" ? "positive" : "muted"}">${esc(row.status)}</span></td>
      <td>
        ${canManage ? `
          <div class="space-member-actions">
            <button type="button" class="secondary" data-space-action="toggle-member-menu" data-membership-id="${escapeAttr(row.membership_id)}" aria-expanded="${menuOpen ? "true" : "false"}">Manage</button>
            ${menuOpen ? `
              <div class="space-action-menu" role="menu">
                <button type="button" class="secondary" data-space-action="toggle-space-member-role" data-membership-id="${escapeAttr(row.membership_id)}" data-space-id="${escapeAttr(spaceId)}" data-next-role="${escapeAttr(nextRole)}">${nextRole === "space_admin" ? "Promote to space_admin" : "Demote to member"}</button>
                <button type="button" class="secondary" data-space-action="toggle-space-member-status" data-membership-id="${escapeAttr(row.membership_id)}" data-space-id="${escapeAttr(spaceId)}" data-next-status="${escapeAttr(nextStatus)}">${nextStatus === "active" ? "Activate membership" : "Deactivate membership"}</button>
                <button type="button" class="secondary danger" data-space-action="delete-space-member" data-membership-id="${escapeAttr(row.membership_id)}" data-space-id="${escapeAttr(spaceId)}">Remove from space</button>
              </div>
            ` : ""}
          </div>
        ` : "<span class='muted'>Read-only</span>"}
      </td>
    </tr>`;
  }).join("");
  return `
    <div class="table">
      <table>
        <thead>
          <tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderCurrentSpaceSection() {
  const active = state.activeSpace;
  const currentSpaceId = activeSpaceId();
  if (!active || !currentSpaceId) {
    return "<p class='muted'>Select a space to manage memberships and scoped administration.</p>";
  }
  if (!state.spaceMembersLoadedBySpace[currentSpaceId]) {
    refreshSpaceMembers(currentSpaceId).catch((err) => {
      console.warn("Failed to load active space memberships", err);
      setSpaceGovernanceNotice(err?.message || "Failed to load space memberships.", "error", 7000);
    });
  }
  const loading = !state.spaceMembersLoadedBySpace[currentSpaceId];
  const summary = loading ? { total: 0, active: 0, admins: 0, inactive: 0 } : membershipSummaryForSpace(currentSpaceId);
  return `
    <div class="space-section-stack">
      <div class="space-hero-card">
        <div>
          <p class="space-card-kicker">Active workspace</p>
          <h3>${esc(active.space_name || currentSpaceId)}</h3>
          <p class="muted">This is the space that powers the data, assignments, and membership edits in the rest of the app.</p>
        </div>
        <div class="space-hero-actions">
          <span class="pill">${esc(currentSpaceRoleLabel(active))}</span>
          <button type="button" class="primary" data-space-action="open-member-modal" data-space-id="${escapeAttr(currentSpaceId)}" ${state.spaceSwitching ? "disabled" : ""}>Add Member</button>
        </div>
      </div>
      <div class="space-summary-grid">
        <div class="panel soft space-summary-card"><span class="muted">Members</span><strong>${loading ? "..." : summary.total}</strong></div>
        <div class="panel soft space-summary-card"><span class="muted">Active</span><strong>${loading ? "..." : summary.active}</strong></div>
        <div class="panel soft space-summary-card"><span class="muted">Active Admins</span><strong>${loading ? "..." : summary.admins}</strong></div>
        <div class="panel soft space-summary-card"><span class="muted">Inactive</span><strong>${loading ? "..." : summary.inactive}</strong></div>
      </div>
      <div class="panel soft space-membership-card">
        <div class="panel-header">
          <div>
            <h3>Space Memberships</h3>
            <p class="muted">Manage the people who can work inside ${esc(active.space_name || currentSpaceId)}.</p>
          </div>
        </div>
        ${loading ? "<p class='muted'>Loading memberships...</p>" : renderMembershipTable(currentSpaceId)}
      </div>
    </div>
  `;
}

function renderDirectoryDetailSurface(selectedSpace) {
  if (!selectedSpace) {
    return `
      <div class="space-empty-card">
        <h3>Select a space</h3>
        <p class="muted">Choose a space from the directory to inspect its status, switch into it, or continue governance work.</p>
      </div>
    `;
  }
  const isCurrent = selectedSpace.space_id === activeSpaceId();
  const canManage = canManageSpaceMembership(selectedSpace.space_id);
  const canSwitchToManage = !userIsGlobalAdmin() && isSpaceAdminRole(state.activeSpace?.space_role) && !isCurrent;
  const isArchived = selectedSpace.is_active === false;
  const canToggleActive = userIsGlobalAdmin() && (isArchived || !isCurrent);
  const archiveLabel = isArchived ? "Reactivate" : "Archive";
  const previewMode = isCurrent
    ? "Current workspace"
    : (canManage ? "Ready to manage" : (canSwitchToManage ? "Switch to manage" : "Read-only preview"));
  if (!state.spaceMembersLoadedBySpace[selectedSpace.space_id] && (canManage || userIsGlobalAdmin()) && !state.spaceSwitching) {
    refreshSpaceMembers(selectedSpace.space_id).catch((err) => {
      console.warn("Failed to load directory space memberships", err);
      setSpaceGovernanceNotice(err?.message || "Failed to load selected space details.", "error", 7000);
    });
  }
  const summary = state.spaceMembersLoadedBySpace[selectedSpace.space_id]
    ? membershipSummaryForSpace(selectedSpace.space_id)
    : null;
  return `
    <div class="space-directory-modal-shell">
      <div class="panel soft space-directory-preview space-directory-modal-preview">
        <div class="space-directory-preview-hero">
          <div>
            <p class="space-card-kicker">Space details</p>
            <h3>${esc(selectedSpace.name || selectedSpace.space_id)}</h3>
            <p class="space-directory-preview-id">${esc(selectedSpace.space_id)}</p>
            <p class="muted">Review the current state first, then take the next action from this layer without cluttering the directory.</p>
          </div>
          <div class="space-hero-actions">
            <span class="pill ${roleBadgeClass(roleBadgeLabelForSpace(selectedSpace))}">${esc(roleBadgeLabelForSpace(selectedSpace))}</span>
            ${isCurrent ? "<span class='pill positive'>Current</span>" : ""}
            ${isArchived ? "<span class='pill danger'>Archived</span>" : "<span class='pill muted'>Active</span>"}
          </div>
        </div>
        <div class="space-directory-preview-grid">
          <div class="space-summary-card panel">
            <span class="muted">Slug</span>
            <strong>${esc(selectedSpace.slug || "Not set")}</strong>
          </div>
          <div class="space-summary-card panel">
            <span class="muted">Members</span>
            <strong>${summary ? summary.total : "Preview after load"}</strong>
          </div>
          <div class="space-summary-card panel">
            <span class="muted">Active Admins</span>
            <strong>${summary ? summary.admins : "Preview after load"}</strong>
          </div>
          <div class="space-summary-card panel">
            <span class="muted">Mode</span>
            <strong>${esc(previewMode)}</strong>
          </div>
        </div>
        ${canSwitchToManage ? `
          <div class="space-inline-callout">
            <div>
              <strong>Read-only preview</strong>
              <p class="muted">Switch into ${esc(selectedSpace.name || selectedSpace.space_id)} to manage memberships and work with full governance controls.</p>
            </div>
            <button type="button" class="primary" data-space-action="switch-space" data-space-id="${escapeAttr(selectedSpace.space_id)}">Switch to manage</button>
          </div>
        ` : ""}
        ${isArchived ? `
          <p class="muted">Archived spaces remain visible here for review. Reactivate the space before adding or changing memberships.</p>
        ` : ""}
        ${(canManage || userIsGlobalAdmin()) ? `
          <div class="space-directory-preview-actions">
            <button type="button" class="secondary" data-space-action="switch-space" data-space-id="${escapeAttr(selectedSpace.space_id)}" ${isCurrent || state.spaceSwitching ? "disabled" : ""}>${isCurrent ? "Already current" : "Switch to this space"}</button>
            <button type="button" class="primary" data-space-action="open-member-modal" data-space-id="${escapeAttr(selectedSpace.space_id)}" ${canManage && !isArchived ? "" : "disabled"}>Add Member</button>
            ${userIsGlobalAdmin() ? `<button type="button" class="secondary${!canToggleActive ? " muted-action" : ""}" data-space-action="toggle-space-active" data-space-id="${escapeAttr(selectedSpace.space_id)}" data-next-active="${isArchived ? "true" : "false"}" ${canToggleActive ? "" : "disabled"}>${archiveLabel}</button>` : ""}
          </div>
        ` : ""}
      </div>
      <div class="form-actions space-directory-modal-footer">
        <button type="button" class="secondary" data-space-action="close-directory-space-modal">Close</button>
      </div>
    </div>
  `;
}

function renderSpaceDirectoryModal() {
  if (!els.spaceDirectoryModal || !els.spaceDirectoryModalBody) return;
  if (!state.spaceDirectoryModalOpen) {
    els.spaceDirectoryModal.classList.add("hidden");
    els.spaceDirectoryModalBody.innerHTML = "";
    return;
  }
  const selectedSpace = directorySpaceById(state.spaceMembershipSpaceId);
  if (!selectedSpace) {
    closeSpaceDirectoryModal();
    els.spaceDirectoryModalBody.innerHTML = "";
    return;
  }
  els.spaceDirectoryModalBody.innerHTML = renderDirectoryDetailSurface(selectedSpace);
  els.spaceDirectoryModal.classList.remove("hidden");
}

function renderDirectorySection() {
  const allSpaces = effectiveDirectorySpaces();
  const spaces = allSpaces.filter((space) => {
    const query = normalize(state.spaceDirectoryQuery);
    if (!query) return true;
    return [space.name, space.slug, space.space_id].some((value) => normalize(value).includes(query));
  });
  const totalSpaces = allSpaces.length;
  const activeSpaces = allSpaces.filter((space) => space.is_active !== false).length;
  const archivedSpaces = allSpaces.filter((space) => space.is_active === false).length;
  const ensuredSelected = ensureSelectedDirectorySpace();
  const selectedSpace = spaces.length
    ? (spaces.find((space) => space.space_id === state.spaceMembershipSpaceId) || spaces[0] || ensuredSelected)
    : null;
  if (selectedSpace?.space_id && selectedSpace.space_id !== state.spaceMembershipSpaceId) {
    state.spaceMembershipSpaceId = selectedSpace.space_id;
  }
  const cards = spaces.length
      ? spaces.map((space) => {
        const isCurrent = space.space_id === activeSpaceId();
        const isSelected = space.space_id === state.spaceMembershipSpaceId;
        const isArchived = space.is_active === false;
        const workspaceState = isArchived ? "Archived" : (isCurrent ? "Current" : "Active");
        return `<article class="space-directory-card${isSelected ? " is-selected" : ""}${isCurrent ? " is-current" : ""}${isArchived ? " is-archived" : ""}">
          <div class="space-directory-card-head">
            <div>
              <p class="space-card-kicker">${esc(space.slug || "workspace")}</p>
              <h3>${esc(space.name || space.space_id)}</h3>
            </div>
            <div class="space-card-badges">
              <span class="pill ${roleBadgeClass(roleBadgeLabelForSpace(space))}">${esc(roleBadgeLabelForSpace(space))}</span>
              ${isCurrent ? "<span class='pill positive'>Current</span>" : ""}
              ${isArchived ? "<span class='pill danger'>Archived</span>" : "<span class='pill muted'>Active</span>"}
            </div>
          </div>
          <div class="space-directory-card-body">
            <p class="space-directory-card-id">${esc(space.space_id)}</p>
            <p class="space-directory-card-note muted">Open the space sheet to review status, switch workspaces, and handle space-level actions in one layer.</p>
            <div class="space-directory-card-facts">
              <div class="space-directory-card-fact">
                <span>Mode</span>
                <strong>${esc(workspaceState)}</strong>
              </div>
              <div class="space-directory-card-fact">
                <span>Access</span>
                <strong>${esc(isCurrent ? "Current workspace" : roleBadgeLabelForSpace(space))}</strong>
              </div>
            </div>
          </div>
          <div class="space-directory-card-actions space-directory-card-actions-single">
            <button type="button" class="primary" data-space-action="open-directory-space" data-space-id="${escapeAttr(space.space_id)}">${isSelected ? "Reopen details" : (isCurrent ? "Open current space" : "View details")}</button>
          </div>
        </article>`;
      }).join("")
    : `
      <div class="space-empty-card">
        <h3>No spaces found</h3>
        <p class="muted">${userIsGlobalAdmin() ? "Try a different search or switch off archived filtering to widen the directory." : "Try a different search to widen the directory."}</p>
      </div>
    `;
  return `
    <div class="space-section-stack">
      <div class="panel soft space-directory-overview">
        <div class="space-directory-overview-copy">
          <p class="space-card-kicker">Workspace atlas</p>
          <h3>Space Directory</h3>
          <p class="muted">Scan every space, inspect the current state, and move into the right workspace without losing your governance context.</p>
        </div>
        <div class="space-directory-overview-stats">
          <div class="space-directory-stat">
            <span>Total spaces</span>
            <strong>${totalSpaces}</strong>
          </div>
          <div class="space-directory-stat">
            <span>Active</span>
            <strong>${activeSpaces}</strong>
          </div>
          <div class="space-directory-stat">
            <span>Archived</span>
            <strong>${archivedSpaces}</strong>
          </div>
          <div class="space-directory-stat">
            <span>In view</span>
            <strong>${spaces.length}</strong>
          </div>
        </div>
        <div class="space-directory-toolbar">
          <label class="space-directory-search-field">Search spaces
            <input type="search" id="space-directory-search" placeholder="Name, slug, or ID" value="${escapeAttr(state.spaceDirectoryQuery)}" />
          </label>
          ${userIsGlobalAdmin() ? `<label class="checkbox-row space-directory-toggle"><input type="checkbox" id="space-directory-show-archived" ${state.spaceDirectoryShowArchived ? "checked" : ""} /> Show archived</label>` : ""}
          ${userIsGlobalAdmin() ? `<button type="button" class="primary" data-space-action="open-create-space-modal">Create Space</button>` : ""}
        </div>
      </div>
      <div class="space-directory-layout">
        <div class="space-directory-grid">${cards}</div>
      </div>
    </div>
  `;
}

function renderPlatformPasswordResetResult() {
  const issued = state.platformPasswordReset;
  if (!issued?.temp_password) return "";
  const expiresText = formatDateTime(issued.expires_at) || "Unknown expiration";
  return `
    <div class="panel soft platform-reset-output">
      <div class="platform-reset-output-head">
        <div>
          <p class="space-card-kicker">Temporary password issued</p>
          <h3>Share the temporary password</h3>
          <p class="muted">Issued for ${esc(issued.soeid || "user")} and valid until ${esc(expiresText)}. Send them to the reset page with this temporary password.</p>
        </div>
        <span class="pill positive">Ready</span>
      </div>
      <div class="platform-reset-grid">
        <label class="wide">Temporary password
          <input type="text" readonly value="${escapeAttr(issued.temp_password)}" />
        </label>
        <label class="wide">Reset page
          <input type="text" readonly value="${escapeAttr(issued.reset_url || "")}" />
        </label>
      </div>
      <div class="form-actions">
        <button type="button" class="secondary" data-space-action="copy-temp-password">Copy temp password</button>
        <button type="button" class="secondary" data-space-action="copy-reset-link">Copy reset page</button>
        <button type="button" class="secondary" data-space-action="clear-reset-result">Clear</button>
      </div>
    </div>
  `;
}

function renderPlatformAccessSection() {
  if (!userIsGlobalAdmin()) {
    return `
      <div class="space-empty-card">
        <h3>Platform Access</h3>
        <p class="muted">Global admin access is managed centrally and is only visible to global admins.</p>
      </div>
    `;
  }
  if (!state.globalAdminsLoaded) {
    refreshGlobalAdmins().catch((err) => {
      console.warn("Failed to load global admins", err);
      setSpaceGovernanceNotice(err?.message || "Failed to load platform access.", "error", 7000);
    });
  }
  const rows = state.globalAdminsLoaded
    ? (state.globalAdmins || []).map((user) => {
        const statusText = user.is_active ? "active" : "inactive";
        return `<tr data-user-id="${escapeAttr(user.user_id)}" data-soeid="${escapeAttr(user.soeid)}">
          <td>${esc(user.display_name || user.soeid || user.user_id)}</td>
          <td>${esc(user.soeid || "—")}</td>
          <td><span class="pill ${user.is_active ? "positive" : "muted"}">${esc(statusText)}</span></td>
          <td>
            <div class="platform-access-actions">
              <button type="button" class="secondary" data-space-action="issue-password-reset" data-soeid="${escapeAttr(user.soeid)}">Reset Password</button>
              <button type="button" class="secondary" data-space-action="revoke-global-admin" data-soeid="${escapeAttr(user.soeid)}">Revoke</button>
            </div>
          </td>
        </tr>`;
      }).join("")
    : "<tr><td colspan='4' class='muted'>Loading global admins...</td></tr>";
  return `
    <div class="space-section-stack">
      <div class="space-hero-card">
        <div>
          <p class="space-card-kicker">Platform-wide access</p>
          <h3>Global Admins</h3>
          <p class="muted">Grant platform-wide access, revoke it when needed, or issue password resets without leaving the governance hub.</p>
        </div>
      </div>
      <div class="panel soft">
        <form id="space-platform-access-form" class="form compact inline-form">
          <label class="wide">User SOEID <input name="soeid" placeholder="e.g. lgo12345" /></label>
          <div class="form-actions full-span">
            <button type="submit">Grant Global Admin</button>
          </div>
        </form>
      </div>
      <div class="panel soft">
        <form id="space-password-reset-form" class="form compact inline-form">
          <label class="wide">User SOEID <input name="soeid" placeholder="e.g. lgo12345" /></label>
          <label>Expires in minutes <input type="number" name="expires_minutes" min="5" max="1440" placeholder="30" /></label>
          <p class="muted full-span">Issuing a reset signs the user out, generates a temporary password on this screen, and requires them to choose a new password on the reset page.</p>
          <div class="form-actions full-span">
            <button type="submit">Issue Password Reset</button>
          </div>
        </form>
      </div>
      ${renderPlatformPasswordResetResult()}
      <div class="panel soft">
        <div class="table">
          <table>
            <thead><tr><th>Name</th><th>SOEID</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>${rows || "<tr><td colspan='4' class='muted'>No global admins found</td></tr>"}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderGovernanceHub(preferredSection = "") {
  if (!els.spaceGovernanceShell) return;
  const activeSection = resolveGovernanceSection(
    preferredSection || (state.currentView === "access" ? "platform-access" : state.spaceAdminSection || "current-space")
  );
  const sectionTabs = governanceSections()
    .map((section) => `
      <button
        type="button"
        class="secondary${activeSection === section.id ? " active" : ""}"
        data-space-action="select-section"
        data-section="${escapeAttr(section.id)}"
      >${esc(section.label)}</button>
    `)
    .join("");
  let body = "";
  if (activeSection === "current-space") body = renderCurrentSpaceSection();
  if (activeSection === "space-directory") body = renderDirectorySection();
  if (activeSection === "platform-access") body = renderPlatformAccessSection();
  const introCopy = activeSection === "platform-access"
    ? "Manage platform-wide admins without leaving the same governance hub."
    : "Switch spaces quickly, stay oriented, and handle access work without leaving the current admin context.";
  els.spaceGovernanceShell.innerHTML = `
    <div class="space-governance-header">
      <div>
        <p class="space-card-kicker">Unified admin hub</p>
        <h3>Manage Current Space, Directory, and Platform Access</h3>
        <p class="muted">${esc(introCopy)}</p>
      </div>
      <div class="space-governance-header-actions">
        ${activeSection !== "current-space" && canManageSpaceMembership(activeSpaceId()) ? `<button type="button" class="primary" data-space-action="open-member-modal" data-space-id="${escapeAttr(activeSpaceId())}">Add Member</button>` : ""}
        ${activeSection !== "space-directory" && userIsGlobalAdmin() ? `<button type="button" class="secondary" data-space-action="open-create-space-modal">Create Space</button>` : ""}
      </div>
    </div>
    <div class="space-governance-tabs">${sectionTabs}</div>
    ${renderGovernanceNotice()}
    <div class="space-governance-body">${body}</div>
  `;
  if (activeSection !== "space-directory") {
    closeSpaceDirectoryModal();
  } else {
    renderSpaceDirectoryModal();
  }
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
      if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
      return state.globalAdmins;
    })
    .finally(() => {
      refreshGlobalAdmins._inFlight = null;
    });
  return refreshGlobalAdmins._inFlight;
}

async function issuePasswordResetForSoeid(soeid, expiresMinutes = null) {
  const soeidNorm = String(soeid || "").trim().toLowerCase();
  if (!soeidNorm) {
    throw new Error("SOEID is required.");
  }
  const body = {};
  if (expiresMinutes !== null && expiresMinutes !== undefined && String(expiresMinutes).trim() !== "") {
    body.expires_minutes = Number(expiresMinutes);
  }
  const issued = await api(`/users/by-soeid/${encodeURIComponent(soeidNorm)}/password-reset-request`, {
    method: "POST",
    ...(Object.keys(body).length ? { body: JSON.stringify(body) } : {}),
  });
  state.platformPasswordReset = {
    soeid: soeidNorm,
    temp_password: issued?.temp_password || "",
    expires_at: issued?.expires_at || "",
    reset_url: buildResetPageUrl(),
  };
  if (isSpaceGovernanceView(state.currentView)) {
    renderGovernanceHub();
  }
  return state.platformPasswordReset;
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
      if (isSpaceGovernanceView(state.currentView) && state.spaceMembershipSpaceId === targetSpaceId) {
        renderGovernanceHub();
      } else if (isSpaceGovernanceView(state.currentView) && targetSpaceId === activeSpaceId()) {
        renderGovernanceHub();
      }
      return state.spaceMembersBySpace[targetSpaceId];
    })
    .finally(() => {
      delete refreshSpaceMembers._inFlight[targetSpaceId];
    });
  return refreshSpaceMembers._inFlight[targetSpaceId];
}

async function handleSpaceGovernanceAction(button) {
  if (!button) return false;
  const action = button.getAttribute("data-space-action") || "";
  const spaceId = button.getAttribute("data-space-id") || "";
  const membershipId = button.getAttribute("data-membership-id") || "";
  const soeid = button.getAttribute("data-soeid") || "";
  const launchedFromDirectoryModal = !!button.closest("#space-directory-modal");
  if (action !== "toggle-member-menu") {
    state.spaceMembershipActionMenuId = "";
  }
  if (action === "select-section") {
    state.spaceAdminSection = normalizeGovernanceSection(button.getAttribute("data-section"));
    renderGovernanceHub();
    return true;
  }
  if (action === "open-directory-space") {
    openSpaceDirectoryModal(spaceId);
    return true;
  }
  if (action === "close-directory-space-modal") {
    closeSpaceDirectoryModal();
    return true;
  }
  if (action === "preview-space") {
    state.spaceMembershipSpaceId = spaceId;
    renderGovernanceHub();
    return true;
  }
  if (action === "open-create-space-modal") {
    openSpaceCreateModal();
    return true;
  }
  if (action === "open-member-modal") {
    if (launchedFromDirectoryModal) {
      closeSpaceDirectoryModal();
    }
    openSpaceMemberModal(spaceId || activeSpaceId());
    return true;
  }
  if (action === "switch-space") {
    if (launchedFromDirectoryModal) {
      closeSpaceDirectoryModal();
    }
    await switchActiveSpace(spaceId);
    return true;
  }
  if (action === "toggle-member-menu") {
    state.spaceMembershipActionMenuId = state.spaceMembershipActionMenuId === membershipId ? "" : membershipId;
    renderGovernanceHub();
    return true;
  }
  if (action === "toggle-space-active" && userIsGlobalAdmin()) {
    const nextActive = normalize(button.getAttribute("data-next-active")) === "true";
    const targetName = spaceNameForId(spaceId) || "this space";
    const confirmed = await showConfirmModal({
      title: nextActive ? "Reactivate Space" : "Archive Space",
      message: nextActive
        ? `Reactivate ${targetName}?`
        : `Archive ${targetName}? It will stop appearing in active space lists until reactivated.`,
      confirmLabel: nextActive ? "Reactivate" : "Archive",
    });
    if (!confirmed) return true;
    try {
      const updated = await api(`/spaces/${encodeURIComponent(spaceId)}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: nextActive }),
      });
      if (updated?.is_active === false) {
        state.archivedSpacesById[updated.space_id] = updated;
      } else if (updated?.space_id) {
        delete state.archivedSpacesById[updated.space_id];
      }
      await refreshSpaceContext();
      state.spaceMembershipSpaceId = updated?.space_id || state.spaceMembershipSpaceId;
      state.spaceAdminSection = "space-directory";
      if (launchedFromDirectoryModal) {
        closeSpaceDirectoryModal();
      }
      setSpaceGovernanceNotice(
        `${nextActive ? "Reactivated" : "Archived"} ${updated?.name || targetName}.`,
        "success",
        4500
      );
    } catch (err) {
      setSpaceGovernanceNotice(err?.message || "Space update failed.", "error", 7000);
    }
    return true;
  }
  if (action === "toggle-space-member-role" || action === "toggle-space-member-status" || action === "delete-space-member") {
    if (!membershipId || !spaceId || !canManageSpaceMembership(spaceId)) {
      setSpaceGovernanceNotice("Switch into this space to manage its memberships.", "error", 7000);
      return true;
    }
    try {
      if (action === "toggle-space-member-role") {
        const nextRole = (button.getAttribute("data-next-role") || "").trim();
        await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
          method: "PATCH",
          body: JSON.stringify({ role: nextRole }),
        });
      } else if (action === "toggle-space-member-status") {
        const nextStatus = (button.getAttribute("data-next-status") || "").trim();
        await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
        });
      } else {
        const confirmed = await showConfirmModal({
          title: "Remove Space Member",
          message: "Remove this member from the selected space?",
          confirmLabel: "Remove",
        });
        if (!confirmed) return true;
        await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
          method: "DELETE",
        });
      }
      state.spaceMembersLoadedBySpace[spaceId] = false;
      await refreshSpaceMembers(spaceId, { force: true });
      setSpaceGovernanceNotice("Membership updated.", "success", 3500);
    } catch (err) {
      setSpaceGovernanceNotice(err?.message || "Membership update failed.", "error", 7000);
    }
    return true;
  }
  if (action === "issue-password-reset" && userIsGlobalAdmin()) {
    const confirmed = await showConfirmModal({
      title: "Issue Password Reset",
      message: `Issue a one-time password reset for ${soeid}? This will invalidate their active sessions.`,
      confirmLabel: "Issue Reset",
    });
    if (!confirmed) return true;
    try {
      await issuePasswordResetForSoeid(soeid);
      setSpaceGovernanceNotice(`Issued password reset for ${soeid}.`, "success", 4500);
    } catch (err) {
      setSpaceGovernanceNotice(err?.message || "Password reset failed.", "error", 7000);
    }
    return true;
  }
  if (action === "copy-temp-password" || action === "copy-reset-link") {
    const issued = state.platformPasswordReset;
    const text = action === "copy-temp-password" ? issued?.temp_password : issued?.reset_url;
    try {
      await copyText(text);
      setSpaceGovernanceNotice(action === "copy-temp-password" ? "Temporary password copied." : "Reset page copied.", "success", 3000);
    } catch (err) {
      setSpaceGovernanceNotice(err?.message || "Copy failed.", "error", 5000);
    }
    return true;
  }
  if (action === "clear-reset-result") {
    state.platformPasswordReset = null;
    renderGovernanceHub();
    return true;
  }
  if (action === "revoke-global-admin" && userIsGlobalAdmin()) {
    const confirmed = await showConfirmModal({
      title: "Revoke Global Admin",
      message: `Revoke global admin from ${soeid}?`,
      confirmLabel: "Revoke",
    });
    if (!confirmed) return true;
    try {
      await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "DELETE" });
      state.globalAdminsLoaded = false;
      await refreshGlobalAdmins();
      await refreshFromServer("users");
      setSpaceGovernanceNotice(`Revoked global admin from ${soeid}.`, "success", 4500);
    } catch (err) {
      setSpaceGovernanceNotice(err?.message || "Revoke failed.", "error", 7000);
    }
    return true;
  }
  return false;
}

function bindSpaceAdminControls() {
  if (els.spaceCreateModalClose && !els.spaceCreateModalClose._bound) {
    els.spaceCreateModalClose.addEventListener("click", closeSpaceCreateModal);
    els.spaceCreateModalClose._bound = true;
  }
  if (els.spaceCreateModal && !els.spaceCreateModal._bound) {
    els.spaceCreateModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSpaceCreateModal);
    els.spaceCreateModal._bound = true;
  }
  if (els.spaceCreateModalForm && !els.spaceCreateModalForm._bound) {
    els.spaceCreateModalForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!userIsGlobalAdmin()) return;
      const data = new FormData(els.spaceCreateModalForm);
      const name = (data.get("name") || "").toString().trim();
      const slug = (data.get("slug") || "").toString().trim();
      if (!name) {
        setDeliverableFormNotice(els.spaceCreateStatus, "Space name is required.", "error");
        return;
      }
      try {
        const created = await api("/spaces", {
          method: "POST",
          body: JSON.stringify({ name, slug: slug || null }),
        });
        clearDeliverableFormNotice(els.spaceCreateStatus);
        closeSpaceCreateModal();
        setSpaceGovernanceNotice(`Created ${created?.name || name}.`, "success", 4500);
        await refreshSpaceContext();
        state.spaceMembershipSpaceId = created?.space_id || state.spaceMembershipSpaceId;
        state.spaceAdminSection = "space-directory";
        renderGovernanceHub();
      } catch (err) {
        setDeliverableFormNotice(els.spaceCreateStatus, err?.message || "Space create failed.", "error");
      }
    });
    els.spaceCreateModalForm._bound = true;
  }

  if (els.spaceMemberModalClose && !els.spaceMemberModalClose._bound) {
    els.spaceMemberModalClose.addEventListener("click", closeSpaceMemberModal);
    els.spaceMemberModalClose._bound = true;
  }
  if (els.spaceMemberModal && !els.spaceMemberModal._bound) {
    els.spaceMemberModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSpaceMemberModal);
    els.spaceMemberModal._bound = true;
  }
  if (els.spaceMemberModalForm && !els.spaceMemberModalForm._bound) {
    els.spaceMemberModalForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(els.spaceMemberModalForm);
      const spaceId = String(data.get("space_id") || "").trim();
      const soeid = String(data.get("soeid") || "").trim().toLowerCase();
      const role = String(data.get("role") || "member");
      const status = String(data.get("status") || "active");
      if (!spaceId) {
        setDeliverableFormNotice(els.spaceMemberStatus, "Select a space first.", "error");
        return;
      }
      if (!canManageSpaceMembership(spaceId)) {
        setDeliverableFormNotice(els.spaceMemberStatus, "Switch into this space to manage its memberships.", "error");
        return;
      }
      if (!soeid) {
        setDeliverableFormNotice(els.spaceMemberStatus, "SOEID is required.", "error");
        return;
      }
      try {
        await api(`/spaces/${encodeURIComponent(spaceId)}/members/by-soeid`, {
          method: "POST",
          body: JSON.stringify({ soeid, role, status }),
        });
        state.spaceMembersLoadedBySpace[spaceId] = false;
        await refreshSpaceMembers(spaceId, { force: true });
        closeSpaceMemberModal();
        setSpaceGovernanceNotice(`Added ${soeid} to ${spaceNameForId(spaceId) || "the selected space"}.`, "success", 4500);
      } catch (err) {
        setDeliverableFormNotice(els.spaceMemberStatus, err?.message || "Add member failed.", "error");
      }
    });
    els.spaceMemberModalForm._bound = true;
  }

  if (els.spaceDirectoryModalClose && !els.spaceDirectoryModalClose._bound) {
    els.spaceDirectoryModalClose.addEventListener("click", closeSpaceDirectoryModal);
    els.spaceDirectoryModalClose._bound = true;
  }
  if (els.spaceDirectoryModal && !els.spaceDirectoryModal._bound) {
    els.spaceDirectoryModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSpaceDirectoryModal);
    els.spaceDirectoryModal.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-space-action]");
      if (!button) return;
      await handleSpaceGovernanceAction(button);
    });
    els.spaceDirectoryModal._bound = true;
  }

  if (els.spaceGovernanceShell && !els.spaceGovernanceShell._bound) {
    els.spaceGovernanceShell.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-space-action]");
      if (!button) return;
      await handleSpaceGovernanceAction(button);
    });
    els.spaceGovernanceShell.addEventListener("submit", async (event) => {
      const form = event.target.closest("form");
      if (!form) return;
      if (form.id === "space-platform-access-form") {
        event.preventDefault();
        if (!userIsGlobalAdmin()) return;
        const data = new FormData(form);
        const soeid = String(data.get("soeid") || "").trim().toLowerCase();
        if (!soeid) {
          setSpaceGovernanceNotice("SOEID is required.", "error", 5000);
          return;
        }
        try {
          await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "POST" });
          state.globalAdminsLoaded = false;
          await refreshGlobalAdmins();
          await refreshFromServer("users");
          form.reset();
          setSpaceGovernanceNotice(`Granted global admin to ${soeid}.`, "success", 4500);
        } catch (err) {
          setSpaceGovernanceNotice(err?.message || "Grant failed.", "error", 7000);
        }
      } else if (form.id === "space-password-reset-form") {
        event.preventDefault();
        if (!userIsGlobalAdmin()) return;
        const data = new FormData(form);
        const soeid = String(data.get("soeid") || "").trim().toLowerCase();
        const expiresMinutesRaw = String(data.get("expires_minutes") || "").trim();
        if (!soeid) {
          setSpaceGovernanceNotice("SOEID is required.", "error", 5000);
          return;
        }
        if (expiresMinutesRaw) {
          const expiresMinutes = Number(expiresMinutesRaw);
          if (!Number.isInteger(expiresMinutes) || expiresMinutes < 5 || expiresMinutes > 1440) {
            setSpaceGovernanceNotice("Expiration must be a whole number between 5 and 1440 minutes.", "error", 6000);
            return;
          }
        }
        try {
          await issuePasswordResetForSoeid(soeid, expiresMinutesRaw || null);
          form.reset();
          setSpaceGovernanceNotice(`Issued password reset for ${soeid}.`, "success", 4500);
        } catch (err) {
          setSpaceGovernanceNotice(err?.message || "Password reset failed.", "error", 7000);
        }
      }
    });
    els.spaceGovernanceShell.addEventListener("input", (event) => {
      if (event.target.id === "space-directory-search") {
        const nextValue = event.target.value || "";
        state.spaceDirectoryQuery = nextValue;
        renderGovernanceHub();
        const input = els.spaceGovernanceShell?.querySelector("#space-directory-search");
        if (input) {
          input.focus();
          input.value = nextValue;
          input.setSelectionRange(nextValue.length, nextValue.length);
        }
      }
    });
    els.spaceGovernanceShell.addEventListener("change", (event) => {
      if (event.target.id === "space-directory-show-archived") {
        state.spaceDirectoryShowArchived = !!event.target.checked;
        renderGovernanceHub();
      }
    });
    els.spaceGovernanceShell._bound = true;
  }

  if (!document._spaceGovernanceEscapeBound) {
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (els.spaceCreateModal && !els.spaceCreateModal.classList.contains("hidden")) {
        closeSpaceCreateModal();
        return;
      }
      if (els.spaceDirectoryModal && !els.spaceDirectoryModal.classList.contains("hidden")) {
        closeSpaceDirectoryModal();
        return;
      }
      if (els.spaceMemberModal && !els.spaceMemberModal.classList.contains("hidden")) {
        closeSpaceMemberModal();
      }
    });
    document.addEventListener("click", (event) => {
      if (!state.spaceMembershipActionMenuId) return;
      const eventPath = typeof event.composedPath === "function" ? event.composedPath() : [];
      const clickedInsideMemberActions = eventPath.some((node) => (
        node
        && node.classList
        && (node.classList.contains("space-member-actions") || node.classList.contains("space-action-menu"))
      ));
      if (clickedInsideMemberActions) return;
      state.spaceMembershipActionMenuId = "";
      renderGovernanceHub();
    });
    document._spaceGovernanceEscapeBound = true;
  }
}

function renderSpaceAdminPanel() {
  renderGovernanceHub();
}

function renderSpaceMembershipPanel() {
  renderGovernanceHub();
}

function renderGlobalAdminPanel() {
  renderGovernanceHub("platform-access");
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
  mod.renderPlanning(createShellContext({
    state,
    els,
    api,
    refreshFromServer,
    setStatus,
    showConfirmModal,
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
  }, { view: "planning" }));
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
    renderGovernanceHub,
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
    renderGovernanceHub,
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
  bindWorkspaceViewPreferences();
  bindAuthUI();
  bindTopbarCreateMenu();
  bindSubcomponentCreatePicker();
  bindCsvControls();
  bindSpaceSwitcher();
  bindNav();
  document.addEventListener("visibilitychange", handleLiveSyncVisibilityChange);
  bindConfirmModal();
  renderTopbarStatus();
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
  const initialView = viewFromLocationPath();
  setView(initialView, { fromHistory: true });
  if (!isResetPath()) {
    syncPathForView(initialView, true);
  }
  bootstrapAuth();
}

init();
