import {
  API_BASE,
  APP_CONTEXT_PATH,
  buildAppUrl,
  buildApiUrl,
  buildResetPageUrl,
  buildWsUrl,
  formatDateTime,
} from "./shell/paths.js";
import { createShellContext } from "./shell/context.js";
import { queryShellElements } from "./shell/dom.js";
import { createRouterController } from "./shell/router.js";
import { createDataStoreController } from "./shell/data-store.js";
import { createSessionController } from "./shell/session.js";
import { createActivitySessionController } from "./shell/activity-session.js";
import { createTelemetryController } from "./shell/telemetry.js";
import {
  createLiveSyncController,
} from "./shell/live-sync.js";
import { createModalShellController } from "./shell/modal-shell.js";
import { createSpaceSwitcherController } from "./shell/space-switcher.js";
import { createTopbarCreateController } from "./shell/topbar-create.js";
import { createShellNavigationController } from "./shell/navigation.js";
import { createProgramEntityController } from "./entities/programs.js";
import { createProjectEntityController } from "./entities/projects.js";
import { createTaskEntityController } from "./entities/tasks.js";
import { createSolutionEntityController } from "./entities/solutions.js";
import {
  filteredDeliverables as filteredMasterDeliverables,
  normalizeMasterFilters,
} from "./routes/master/filters.js";
import { renderMasterQuickstart as renderMasterQuickstartView } from "./routes/master/quickstart.js";
import {
  bindDeliverablesControls as bindMasterDeliverablesControls,
  bindDeliverablesTable as bindMasterDeliverablesTable,
} from "./routes/master/interactions.js";
import {
  clearTasksWorkbenchFilters as clearWorkbenchFilters,
  normalizeTasksWorkbenchUiState as normalizeWorkbenchUiState,
  tasksWorkbenchRows as buildTasksWorkbenchRows,
  tasksWorkbenchSummary as buildTasksWorkbenchSummary,
  updateTasksWorkbenchPresetButtons as updateWorkbenchPresetButtons,
  updateTasksWorkbenchSelectionCount as updateWorkbenchSelectionCount,
} from "./routes/tasks-workbench/filters.js";
import {
  applyTasksWorkbenchBulkAction as applyWorkbenchBulkAction,
  syncTasksWorkbenchBulkInputs as syncWorkbenchBulkInputs,
} from "./routes/tasks-workbench/bulk-actions.js";
import {
  fillTasksWorkbenchForm,
  scrollActiveTaskIntoView,
  syncTasksWorkbenchDrawer,
} from "./routes/tasks-workbench/drawer.js";
import {
  loadTasksWorkbenchSavedViews,
  updateTasksWorkbenchSavedViewsUI,
} from "./routes/tasks-workbench/saved-views.js";
import {
  bindTasksWorkbenchControls as bindWorkbenchControls,
  updateTasksWorkbenchSolutionOptions as updateWorkbenchSolutionOptions,
} from "./routes/tasks-workbench/interactions.js";
import { populateTasksWorkbenchOptions } from "./routes/tasks-workbench/options.js";
import { nextTaskNameSort, sortTasksByName, taskNameSortPresentation } from "./utils/task-sort.js";
import { createCalendarRouteController } from "./routes/calendar/interactions.js";
import { createGanttRouteController } from "./routes/gantt/interactions.js";
import { createKanbanRouteController } from "./routes/kanban/interactions.js";
import { createTeamCapacityRouteController } from "./routes/team-capacity/interactions.js";
import { createSpaceGovernanceController } from "./routes/spaces/interactions.js";
import { createSpaceGovernanceRenderer } from "./routes/spaces/render.js";
import { formatStatusLabel } from "./utils/display-tokens.js";
import { safeExternalUrl } from "./utils/external-url.js";

const HOURS_PER_FTE_MONTH = 160;
const HOURS_PER_FTE_CAPACITY = 40;

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

const els = queryShellElements();
const shellNavigationController = createShellNavigationController({ els });

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
  return safeExternalUrl(value);
}

function effectiveTaskRepoInfo(solutionId, overrideUrl) {
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
  if (!targetUrl) return escapeHtml(label === "Open Repo" ? "" : label);
  const classes = ["repo-external-link", className].filter(Boolean).join(" ");
  return `<a class="${classes}" href="${escapeAttr(targetUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function updateTaskRepoPreview(solutionId, overrideUrl) {
  if (!els.taskRepoPreview) return;
  const { url, source } = effectiveTaskRepoInfo(solutionId, overrideUrl);
  if (!url) {
    els.taskRepoPreview.textContent = "No solution repo set.";
    return;
  }
  const sourceLabel = source === "override" ? "Override repo" : "Inherited repo";
  els.taskRepoPreview.innerHTML = `${escapeHtml(sourceLabel)}: ${renderExternalRepoLink(url, { label: url, className: "repo-external-link-inline" })}`;
}

function numberOr(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
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
  apiTokensByUser: {},
  apiTokensLoadedByUser: {},
  issuedApiToken: null,
  agentChangeRequests: [],
  agentChangeRequestsLoaded: false,
  agentChangeRequestPendingCount: 0,
  agentChangeRequestFailedCount: 0,
  agentChangeRequestSelectedIds: new Set(),
  agentChangeRequestSelectedOperationIds: {},
  agentChangeRequestActiveId: "",
  agentChangeRequestModalId: "",
  requestableSpaces: [],
  requestableSpacesLoaded: false,
  spaceAccessRequests: [],
  spaceAccessRequestsLoaded: false,
  reviewableAccessRequests: [],
  reviewableAccessRequestsLoaded: false,
  lobbyPersonalSpaceCreating: false,
  accessRequestSubmittingSpaceId: "",
  lobbyRequestSearch: "",
  authMode: "login",
  phases: [],
  programs: [],
  projects: [],
  solutions: [],
  solutionPhases: {}, // solution_id -> phases
  solutionDocuments: {}, // solution_id -> document metadata
  tasks: [],
  teams: [],
  users: [],
  filters: {},
  masterCollapsed: new Set(),
  taskView: "table",
  taskSort: "default",
  tasksWorkbench: {
    preset: "all",
    sort: "default",
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
    activeTaskId: "",
    visibleIds: [],
    savedViews: [],
    selectedSavedViewId: "",
    activityRequestId: 0,
    drawerOpen: false,
    drawerReturnTaskId: "",
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
  ganttWindow: { from: "", to: "" },
  ganttCollapsed: new Set(),
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

const ACCESS_REFRESH_INTERVAL_MS = 4 * 60 * 1000;
const MASTER_VIEW_STATE_KEY_PREFIX = "sipm-master-filters-v1";
const WORKSPACE_VIEW_PREFS_KEY_PREFIX = "sipm-workspace-prefs-v1";
const CALENDAR_VIEW_STATE_KEY_PREFIX = "sipm-calendar-view-state-v1";
const GANTT_VIEW_STATE_KEY_PREFIX = "sipm-gantt-view-state-v1";
const KANBAN_VIEW_STATE_KEY_PREFIX = "sipm-kanban-view-state-v1";
const TEAM_CAPACITY_VIEW_STATE_KEY_PREFIX = "sipm-team-capacity-view-state-v1";
const SPACE_GOVERNANCE_VIEW_STATE_KEY_PREFIX = "sipm-space-governance-state-v1";
const SPACE_RECENTS_KEY_PREFIX = "sipm-space-recents-v1";
const TASKS_WORKBENCH_UI_STATE_KEY_PREFIX = "sipm-tasks-workbench-state-v1";
const TASKS_WORKBENCH_SAVED_VIEWS_KEY_PREFIX = "sipm-tasks-workbench-views";
const RECENT_SPACES_LIMIT = 5;
const csvUploadState = {
  kind: "",
  file: null,
};

let routerController = null;
let dataStoreController = null;
let sessionController = null;
let activitySessionController = null;
let liveSyncController = null;
let telemetryController = null;
const ignoreNextRefresh = {
  delete(entity) {
    return dataStoreController.clearIgnoredRefresh(entity);
  },
};
const programEntityController = createProgramEntityController({
  state,
  els,
  api,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  removeById,
  populateSelects,
  renderActiveView,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  timestampLabel,
  showConfirmModal,
  trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
});
const projectEntityController = createProjectEntityController({
  state,
  els,
  api,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  removeById,
  populateSelects,
  renderMasterTable,
  renderDashboard,
  renderKanban,
  renderCalendar,
  renderGantt,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  timestampLabel,
  showConfirmModal,
  trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
});
const solutionEntityController = createSolutionEntityController({
  state,
  els,
  api,
  hoursFromFteInput,
  fteFromHoursForInput,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  removeById,
  populateSelects,
  renderActiveView,
  renderMasterTable,
  renderDashboard,
  renderKanban,
  renderCalendar,
  renderGantt,
  renderSolutionPhases,
  renderSolutionTasks,
  renderSolutionDocuments,
  renderSolutionActivity,
  setTaskFormVisibility,
  setTaskActionButtonLabel,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  updateCurrentPhaseOptions,
  updateTaskRepoPreview,
  setSolutionTab,
  timestampLabel,
  showConfirmModal,
  trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
});
const taskEntityController = createTaskEntityController({
  state,
  els,
  api,
  findUserBySoeid,
  resolveAssigneeSelectValue,
  hoursFromFteInput,
  hoursFromNullableFteInput,
  fteFromHoursForInput,
  updateTaskRepoPreview,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  deleteTasksById,
  renderSolutionTasks,
  renderDashboard,
  renderGantt,
  timestampLabel,
  trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
});
const calendarRouteController = createCalendarRouteController({
  state,
  els,
  calendarViewStateKey: CALENDAR_VIEW_STATE_KEY_PREFIX,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  bindDebouncedInput,
  renderCalendar,
  openProjectForm,
  openSolutionModal,
  fillTaskForm,
  getRouteModule,
  ensureRouteModule,
  filteredSolutionsForCalendar,
  filteredTasksForCalendar,
  formatStatus,
});
const ganttRouteController = createGanttRouteController({
  state,
  els,
  ganttViewStateKey: GANTT_VIEW_STATE_KEY_PREFIX,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  renderGantt,
  openProgramForm,
  openProjectForm,
  openSolutionModal,
  fillTaskForm,
});
const kanbanRouteController = createKanbanRouteController({
  state,
  els,
  kanbanViewStateKey: KANBAN_VIEW_STATE_KEY_PREFIX,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  bindDebouncedInput,
  renderKanban,
  openProjectForm,
  openSolutionModal,
  hideClosedDeliverables,
  isClosedSolutionStatus,
});
const teamCapacityRouteController = createTeamCapacityRouteController({
  state,
  els,
  teamCapacityViewStateKey: TEAM_CAPACITY_VIEW_STATE_KEY_PREFIX,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  bindDebouncedInput,
  renderTeamCapacity,
  api,
  applyEntityData,
  handleAuthError,
  populateSelects,
  clearCapacityUserFormStatus,
  setCapacityUserFormStatus,
  userCapacityFteMonth,
  formatFte,
  numberOr,
  timestampLabel,
  showConfirmModal,
  onViewDataLoaded: ({ view, durationMs }) => telemetryController?.noteRouteDataLoaded?.(view, durationMs),
  trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
});
const spaceGovernanceController = createSpaceGovernanceController({
  state,
  els,
  api,
  normalize,
  normalizeGovernanceSection,
  userIsGlobalAdmin,
  activeSpaceId,
  canManageSpaceMembership,
  effectiveDirectorySpaces,
  spaceNameForId,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  setSpaceGovernanceNotice,
  renderGovernanceHub,
  renderSpaceDirectoryModal,
  isSpaceGovernanceView,
  refreshSpaceContext,
  refreshFromServer,
  switchActiveSpace,
  showConfirmModal,
  copyText,
  buildAppUrl,
  buildResetPageUrl,
  trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
});
const spaceGovernanceRenderer = createSpaceGovernanceRenderer({
  state,
  els,
  normalize,
  normalizeSpaceRole,
  activeSpaceId,
  userIsGlobalAdmin,
  currentSpaceRoleLabel,
  canManageSpaceMembership,
  esc,
  escapeAttr,
  formatDateTime,
  effectiveDirectorySpaces,
  governanceSections,
  resolveGovernanceSection,
  refreshGlobalAdmins: (...args) => refreshGlobalAdmins(...args),
  refreshAccessRequests: (...args) => refreshAccessRequests(...args),
  refreshApiTokens: (...args) => refreshApiTokens(...args),
  refreshSpaceMembers: (...args) => refreshSpaceMembers(...args),
  refreshAgentChangeRequests: (...args) => refreshAgentChangeRequests(...args),
  refreshRequestableSpaces: (...args) => refreshRequestableSpaces(...args),
  refreshReviewableAccessRequests: (...args) => refreshReviewableAccessRequests(...args),
  closeSpaceDirectoryModal,
  setSpaceGovernanceNotice,
  buildAppUrl,
});

const topbarCreateController = createTopbarCreateController({
  state,
  els,
  escapeHtml,
  openProgramForm,
  openProjectForm,
  openSolutionModal,
  showTaskForm,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
});
const {
  bindTaskCreatePicker,
  bindTopbarCreateMenu,
  closeTopbarCreateMenu,
  closeTaskCreatePicker,
} = topbarCreateController;
const modalShellController = createModalShellController({ els });
const spaceSwitcherController = createSpaceSwitcherController({
  state,
  els,
  normalize,
  normalizeSpaceRole,
  escapeAttr,
  esc,
  userIsGlobalAdmin,
  syncRoleAwareNavigation,
  onSwitchActiveSpace: async (targetSpaceId) => switchActiveSpace(targetSpaceId),
});

function getRouteModule(view) {
  return routerController.getRouteModule(view);
}

async function ensureRouteModule(view) {
  return routerController.ensureRouteModule(view);
}

function isAdminView(view) {
  return routerController.isAdminView(view);
}

function canAccessView(view) {
  return routerController.canAccessView(view);
}

function appRelativePath(pathname = window.location.pathname) {
  return routerController.appRelativePath(pathname);
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

function isSpaceGovernanceView(view) {
  return routerController.isSpaceGovernanceView(view);
}

function clearDataState() {
  return dataStoreController.clearDataState();
}

function markIgnoreRefresh(entity) {
  return dataStoreController.markIgnoreRefresh(entity);
}

function applyEntityData(entity, data) {
  return dataStoreController.applyEntityData(entity, data);
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

function usageAnalyticsEnabled() {
  return !!state.activeSpace?.usage_analytics_enabled;
}

function initShellControllers() {
  activitySessionController = createActivitySessionController({
    onWarning: showIdleModal,
    onWarningDismissed: hideIdleModal,
    onHeartbeat: (options) => sessionController.recordSessionActivity(options),
    onIdleLogout: () => sessionController.logoutForInactivity(),
    onRemoteLogout: () => sessionController.handleRemoteLogout(),
  });
  routerController = createRouterController({
    state,
    els,
    renderActiveView,
    userIsGlobalAdmin,
    isSpaceAdminRole,
    usageAnalyticsEnabled,
    loadData: (...args) => dataStoreController.loadData(...args),
    loadTeamCapacityData,
    onBeforeViewChange: ({ previousView, nextView, expectsData }) => {
      telemetryController?.syncRuntimeContext?.();
      telemetryController?.beginRouteTransition?.(nextView, previousView, { expectsData });
      telemetryController?.trackRouteView?.(nextView, previousView);
    },
    onAccessRedirect: ({ reason }) => {
      if (reason !== "lobby") return;
      setSpaceGovernanceNotice(
        "You do not have access to a working space yet. Create Personal or request access to a collaboration space.",
        "warn",
        8000,
      );
    },
    onModuleLoadFailure: ({ view }) => telemetryController?.trackModuleLoadFailure?.(view),
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
    onViewDataLoaded: ({ view, durationMs }) => telemetryController?.noteRouteDataLoaded?.(view, durationMs),
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
    viewFromLocationPath,
    setView,
    setAuthMode,
    setAuthed,
    setStatus,
    setAuthVisible,
    setResetVisible,
    showAuthError,
    showAuthNotice,
    showResetError,
    showResetSuccess,
    configureSessionPolicy: (policy) => activitySessionController.configure(policy),
    noteSessionActivity: () => activitySessionController.noteUserActivity(),
    broadcastSessionLogout: () => activitySessionController.broadcastLogout(),
    refreshSpaceContext,
    onApiFailure: (...args) => telemetryController?.trackApiFailure?.(...args),
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
    refreshAgentChangeRequests: (...args) => refreshAgentChangeRequests(...args),
    handleAuthError: (...args) => sessionController.handleAuthError(...args),
    handleSessionExpired: (...args) => handleSessionExpired(...args),
    renderTopbarStatus,
    setSpaceFeedback,
    spaceNameForId,
    clearDataState: (...args) => dataStoreController.clearDataState(...args),
  });
  telemetryController = createTelemetryController({
    state,
    apiBase: API_BASE,
    isEnabled: usageAnalyticsEnabled,
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
  return spaceSwitcherController.currentSpaceRoleLabel(ctx);
}

function clearSpaceFeedback() {
  return spaceSwitcherController.clearSpaceFeedback();
}

function setSpaceFeedback(message, tone = "info", autoClearMs = 0) {
  return spaceSwitcherController.setSpaceFeedback(message, tone, autoClearMs);
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
  const canUseWorkEditActions = !!state.authed && state.activeSpace?.space_kind !== "lobby";
  els.topbarCreateShell?.classList.toggle("hidden", !canUseWorkEditActions);
  if (!canUseWorkEditActions) {
    closeTopbarCreateMenu({ restoreFocus: false });
  }
  [
    els.deleteProjectBtn,
    els.deleteSolutionBtn,
    els.deleteTaskBtn,
  ].forEach((button) => {
    if (!button) return;
    button.classList.toggle("hidden", !canUseWorkEditActions);
    if (!canUseWorkEditActions) {
      button.disabled = true;
    }
  });
}

function syncRoleAwareNavigation() {
  const lobbyActive = state.authed && state.activeSpace?.space_kind === "lobby";
  els.navWorkSection?.classList.toggle("hidden", lobbyActive);
  els.navInsightSection?.classList.toggle("hidden", lobbyActive);
  Array.from(els.navButtons || [])
    .filter((btn) => btn.dataset.view === "team-capacity")
    .forEach((btn) => btn.classList.toggle("hidden", lobbyActive));
  const adminButtons = Array.from(els.navButtons || []).filter((btn) => isAdminView(btn.dataset.view));
  let hasAnyVisibleAdminButton = false;
  adminButtons.forEach((btn) => {
    const view = btn.dataset.view || "";
    const allowed = canAccessView(view) && (!lobbyActive || view === "spaces" || view === "access");
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
  return spaceSwitcherController.renderSpaceSwitcher();
}


function spaceNameForId(spaceId) {
  return spaceSwitcherController.spaceNameForId(spaceId);
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
    if (state.activeSpace?.space_kind !== "lobby") {
      clearSpaceGovernanceNotice();
    }
    state.spaceMembershipSpaceId = state.activeSpace?.space_id || state.spaceMembershipSpaceId;
    stopLiveSync({ phase: "reconnecting" });
    clearDataState();
    restoreGanttViewState();
    await reloadCurrentViewData({ force: true, preserveCapacitySelection: false });
    startLiveSync({ force: true });
    state.spaceSwitcherOpen = false;
    telemetryController?.syncRuntimeContext?.();
    telemetryController?.trackSpaceSwitch?.();
    setSpaceFeedback(`Now working in ${spaceNameForId(state.activeSpace?.space_id || target) || targetName || target}.`, "success", 4200);
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
    state.requestableSpaces = [];
    state.requestableSpacesLoaded = false;
    state.spaceAccessRequests = [];
    state.spaceAccessRequestsLoaded = false;
    state.reviewableAccessRequests = [];
    state.reviewableAccessRequestsLoaded = false;
    state.agentChangeRequestModalId = "";
    state.lobbyPersonalSpaceCreating = false;
    state.accessRequestSubmittingSpaceId = "";
    state.lobbyRequestSearch = "";
    state.tasksWorkbench.savedViews = [];
    state.tasksWorkbench.selectedSavedViewId = "";
    state.filters = {};
    state.masterCollapsed = new Set();
    state.ganttWindow = { from: "", to: "" };
    state.ganttCollapsed = new Set();
    closeSpaceCreateModal();
    closeSpaceMemberModal();
    closeSpaceDirectoryModal();
    renderSpaceSwitcher();
    updateTasksWorkbenchSavedViewsUI(createTasksWorkbenchContext());
    return;
  }
  const [spaces, activeSpace] = await Promise.all([
    api("/spaces", apiOptions),
    api("/auth/active-space", apiOptions),
  ]);
  state.spaces = Array.isArray(spaces) ? spaces : [];
  state.activeSpace = activeSpace || null;
  if ((state.activeSpace?.space_id || "") !== previousActiveSpaceId) {
    state.requestableSpacesLoaded = false;
    state.spaceAccessRequestsLoaded = false;
    state.reviewableAccessRequestsLoaded = false;
  }
  telemetryController?.syncRuntimeContext?.();
  if (state.activeSpace?.space_id && !state.spaces.some((s) => s.space_id === state.activeSpace.space_id)) {
    state.spaces.unshift({
      space_id: state.activeSpace.space_id,
      name: state.activeSpace.space_name || state.activeSpace.space_id,
      slug: "",
      is_active: true,
      space_kind: state.activeSpace.space_kind || "collaboration",
      owner_user_id: state.activeSpace.owner_user_id || null,
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
  restoreGanttViewState();
  restoreKanbanViewState();
  restoreTeamCapacityViewState();
  restoreSpaceGovernanceViewState();
  restoreTasksWorkbenchUiState();
  renderSpaceSwitcher();
  loadTasksWorkbenchSavedViews(createTasksWorkbenchContext());
  updateTasksWorkbenchSavedViewsUI(createTasksWorkbenchContext());
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
    activitySessionController.start(user.user_id);
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
    state.requestableSpaces = [];
    state.requestableSpacesLoaded = false;
    state.spaceAccessRequests = [];
    state.spaceAccessRequestsLoaded = false;
    state.reviewableAccessRequests = [];
    state.reviewableAccessRequestsLoaded = false;
    state.agentChangeRequestModalId = "";
    state.lobbyPersonalSpaceCreating = false;
    state.accessRequestSubmittingSpaceId = "";
    state.lobbyRequestSearch = "";
    state.tasksWorkbench.savedViews = [];
    state.tasksWorkbench.selectedSavedViewId = "";
    state.ganttWindow = { from: "", to: "" };
    state.masterCollapsed = new Set();
    state.ganttCollapsed = new Set();
    closeSpaceCreateModal();
    closeSpaceMemberModal();
    closeSpaceDirectoryModal();
    activitySessionController.stop();
    setLiveSyncPhase("idle", { clear: true });
  }
  setAuthVisible(!state.authed);
  if (!state.authed) {
    setStatus("Sign in required", "warn");
  }
  renderSpaceSwitcher();
  renderCompletedVisibilityToggle();
  updateTasksWorkbenchSavedViewsUI(createTasksWorkbenchContext());
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

function showIdleModal(remainingSeconds) {
  if (!els.idleModal) return;
  if (els.idleCountdown) {
    const seconds = Math.max(1, Number(remainingSeconds) || 60);
    els.idleCountdown.textContent = `${seconds} second${seconds === 1 ? "" : "s"}`;
  }
  els.idleModal.classList.remove("hidden");
}

function hideIdleModal() {
  if (!els.idleModal) return;
  els.idleModal.classList.add("hidden");
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

function isResetPath() {
  return sessionController.isResetPath();
}

function bindAuthUI() {
  return sessionController.bindAuthUI();
}

function stopLiveSync(options = {}) {
  return liveSyncController.stopLiveSync(options);
}

function startLiveSync(options = {}) {
  return liveSyncController.startLiveSync(options);
}

async function handleLiveSyncVisibilityChange() {
  return liveSyncController.handleLiveSyncVisibilityChange();
}

function initTasksWorkbench() {
  bindWorkbenchControls(createTasksWorkbenchContext());
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

function populateCapacityUserOptions() {
  if (!els.capacityUserOptions) return;
  const options = state.users
    .filter((u) => u.display_name || u.soeid)
    .map((u) => `<option value="${u.display_name || u.soeid}"></option>`)
    .join("");
  els.capacityUserOptions.innerHTML = options;
}

function renderActiveView() {
  const renderStartedAt = performance.now();
  const routeDispatch = {
    master: () => {
      renderMasterFilters();
      renderMasterTable();
    },
    "tasks-workbench": () => renderTasksWorkbench(),
    dashboard: () => renderDashboard(),
    "program-dashboard": () => renderProgramDashboard(),
    "pm-dashboard": () => renderPMDashboard(),
    kanban: () => renderKanban(),
    calendar: () => renderCalendar(),
    gantt: () => renderGantt(),
    "team-capacity": () => renderTeamCapacity(),
    spaces: () => renderSpaces(),
    access: () => renderAccess(),
    analytics: () => renderAnalytics(),
  };
  const renderRoute = routeDispatch[state.currentView] || routeDispatch.master;
  renderRoute();
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && els.solutionModal && !els.solutionModal.classList.contains("hidden")) {
    renderSolutionTasks(openSolutionId);
    renderSolutionActivity(openSolutionId);
    renderSolutionPhases(openSolutionId);
  }
  telemetryController?.noteViewRendered?.(state.currentView, performance.now() - renderStartedAt);
}

function restoreSelections(projectId, solutionId, taskId) {
  if (projectId) {
    const proj = state.projects.find((p) => p.project_id === projectId);
    if (proj) {
      openProjectForm(proj);
    }
  }

  if (solutionId) {
    const sol = state.solutions.find((s) => s.solution_id === solutionId);
    if (sol) {
      const activeTab = els.solutionModal?.querySelector(".modal-tabs .tab.active")?.dataset?.tab || "details";
      openSolutionModal(sol, activeTab);
    }
  }

  if (taskId) {
    const task = state.tasks.find((item) => item.task_id === taskId);
    if (task) {
      fillTaskForm(task);
    }
  }
}

function createMasterRouteContext(overrides = {}) {
  const base = createShellContext({
    state,
    els,
    api,
    upsertById,
    phaseDisplayName,
    solutionProgress,
    formatStatus,
    repoDisplayUrl,
    hideClosedDeliverables,
    isClosedProjectStatus,
    isClosedSolutionStatus,
    showCompletedOperationalWork,
    persistMasterViewState,
    persistWorkspaceViewPreferences,
    renderCompletedVisibilityToggle,
    renderMasterFilters,
    renderMasterTable,
    renderDashboard,
    renderKanban,
    renderCalendar,
    renderGantt,
    renderActiveView,
    openProgramForm,
    openProjectForm,
    openSolutionModal,
    showTaskForm,
    trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
  }, { view: "master" });
  return createShellContext(base, {
    filteredDeliverables: () => filteredMasterDeliverables(base),
    renderMasterQuickstart: (rowCount = 0) => renderMasterQuickstartView(base, rowCount),
    ...overrides,
  });
}

function createTasksWorkbenchContext(overrides = {}) {
  const base = createShellContext({
    state,
    els,
    api,
    upsertById,
    normalize,
    numberOr,
    ignoreNextRefresh,
    deriveTaskActionability,
    isCompletedTaskStatus,
    showCompletedOperationalWork,
    requestsClosedStatuses,
    persistTasksWorkbenchUiState,
    renderTasksWorkbench,
    clearTasksWorkbenchBulkFeedback,
    setTasksWorkbenchBulkFeedback,
    deleteTasksById,
    markIgnoreRefresh,
    renderSolutionTasks,
    renderDashboard,
    findUserBySoeid,
    escapeHtml,
    effectiveTaskRepoInfo,
    renderExternalRepoLink,
    openProjectForm,
    openSolutionModal,
    clearDeliverableFormNotice,
    setDeliverableFormNotice,
    timestampLabel,
    resolveAssigneeSelectValue,
    activeSpaceId,
    tasksWorkbenchSavedViewsKeyPrefix: TASKS_WORKBENCH_SAVED_VIEWS_KEY_PREFIX,
    showConfirmModal,
    bindDebouncedInput,
  }, { view: "tasks-workbench" });
  let ctx = null;
  ctx = createShellContext(base, {
    updateTasksWorkbenchPresetButtons: () => updateWorkbenchPresetButtons(ctx),
    updateTasksWorkbenchSelectionCount: () => updateWorkbenchSelectionCount(ctx),
    clearTasksWorkbenchFilters: () => clearWorkbenchFilters(ctx),
    syncTasksWorkbenchBulkInputs: () => syncWorkbenchBulkInputs(ctx),
    applyTasksWorkbenchBulkAction: () => applyWorkbenchBulkAction(ctx),
    normalizeTasksWorkbenchUiState: (options) => normalizeWorkbenchUiState(ctx, options),
    updateTasksWorkbenchSolutionOptions: (projectId) => updateWorkbenchSolutionOptions(ctx, projectId),
    ...overrides,
  });
  return ctx;
}

function renderMasterFilters() {
  const mod = getRouteModule("master");
  if (!mod || typeof mod.renderMasterFilters !== "function") {
    ensureRouteModule("master").then((loaded) => {
      if (loaded && state.currentView === "master") renderMasterFilters();
    });
    return;
  }
  mod.renderMasterFilters(createMasterRouteContext());
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

function isCompletedTaskStatus(statusValue) {
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

function deriveTaskActionability(task) {
  const hasServerFields =
    Object.prototype.hasOwnProperty.call(task || {}, "is_overdue") &&
    Object.prototype.hasOwnProperty.call(task || {}, "is_due_soon") &&
    Object.prototype.hasOwnProperty.call(task || {}, "is_stale") &&
    Object.prototype.hasOwnProperty.call(task || {}, "urgency_score");
  if (hasServerFields) {
    return {
      is_overdue: !!task.is_overdue,
      is_due_soon: !!task.is_due_soon,
      is_stale: !!task.is_stale,
      urgency_score: numberOr(task.urgency_score, 0),
    };
  }

  const done = isCompletedTaskStatus(task?.status);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dueDate = task?.due_date ? new Date(`${task.due_date}T00:00:00`) : null;
  const updated = task?.updated_at ? new Date(task.updated_at) : null;

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
    const priority = Math.max(1, Math.min(5, Number(task?.priority || 3)));
    const priorityScore = (6 - priority) * 15;
    const dueScore = dueSoonDays == null ? 0 : dueSoonDays < 0 ? 45 : Math.max(0, (15 - dueSoonDays) * 2);
    const blockedScore = task?.blocked ? 18 : 0;
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

function describeTasksForDelete(taskIds) {
  const uniqueIds = Array.from(new Set((taskIds || []).map((id) => String(id || "").trim()).filter(Boolean)));
  const names = uniqueIds.map((id) => {
    const row = state.tasks.find((item) => item.task_id === id);
    return row?.task_name || "";
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

async function deleteTasksById(taskIds, options = {}) {
  const details = describeTasksForDelete(taskIds);
  const { ids } = details;
  if (!ids.length) {
    return { cancelled: false, deletedIds: [], failed: [] };
  }

  const count = ids.length;
  const defaultTitle = count === 1 ? "Delete Task?" : "Delete Tasks?";
  const defaultConfirm = count === 1 ? "Delete Task" : `Delete ${count} Tasks`;
  const defaultMessage = count === 1
    ? `Delete ${details.previewText || "this task"}? This cannot be undone.`
    : `Delete ${count} tasks${details.previewText ? ` (${details.previewText})` : ""}? This cannot be undone.`;

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
      await api(`/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
      deletedIds.push(id);
    } catch (err) {
      failed.push({ id, error: err });
    }
  }

  deletedIds.forEach((id) => removeById(state.tasks, id, "task_id"));
  const wb = state.tasksWorkbench;
  deletedIds.forEach((id) => wb.selected.delete(id));
  if (deletedIds.includes(wb.activeTaskId)) {
    wb.activeTaskId = "";
  }

  return { cancelled: false, deletedIds, failed };
}

function clearTasksWorkbenchBulkFeedback() {
  clearDeliverableFormNotice(els.tasksWorkbenchBulkFeedback);
}

function setTasksWorkbenchBulkFeedback(message, tone = "info", autoClearMs = 0) {
  setDeliverableFormNotice(els.tasksWorkbenchBulkFeedback, message, tone, autoClearMs);
}

function renderTasksWorkbench() {
  const mod = getRouteModule("tasks-workbench");
  if (!mod || typeof mod.renderTasksWorkbench !== "function") {
    if (state.currentView === "tasks-workbench" && els.tasksWorkbenchTable) {
      els.tasksWorkbenchTable.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("tasks-workbench").then((loaded) => {
      if (loaded && state.currentView === "tasks-workbench") renderTasksWorkbench();
    });
    return;
  }

  const wb = state.tasksWorkbench;
  const workbenchCtx = createTasksWorkbenchContext();
  const { allRows, visibleRows } = buildTasksWorkbenchRows(workbenchCtx);
  const allIds = new Set((state.tasks || []).map((row) => row.task_id));
  Array.from(wb.selected).forEach((taskId) => {
    if (!allIds.has(taskId)) wb.selected.delete(taskId);
  });

  if (wb.activeTaskId) {
    const exists = visibleRows.find((row) => row.task_id === wb.activeTaskId);
    if (!exists) wb.activeTaskId = "";
  }
  if (wb.drawerOpen !== false && !wb.activeTaskId && visibleRows.length) {
    wb.activeTaskId = visibleRows[0].task_id;
  }
  persistTasksWorkbenchUiState();

  mod.renderTasksWorkbench({
    els,
    rows: visibleRows,
    activeTaskId: wb.activeTaskId,
    selectedIds: wb.selected,
    sort: wb.sort,
    formatStatus,
    summary: buildTasksWorkbenchSummary(workbenchCtx, allRows, visibleRows),
  });

  const active = wb.drawerOpen !== false && wb.activeTaskId
    ? (state.tasks || []).find((row) => row.task_id === wb.activeTaskId) || null
    : null;
  syncTasksWorkbenchDrawer(workbenchCtx);
  fillTasksWorkbenchForm(workbenchCtx, active);
  updateWorkbenchPresetButtons(workbenchCtx);
  updateWorkbenchSelectionCount(workbenchCtx);
  updateTasksWorkbenchSavedViewsUI(workbenchCtx);
  if (wb.suppressAutoScrollOnce) {
    wb.suppressAutoScrollOnce = false;
  } else {
    window.setTimeout(() => scrollActiveTaskIntoView(workbenchCtx), 0);
  }
}

function filteredSolutionsForKanban() {
  return kanbanRouteController.filteredSolutionsForKanban();
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

function filteredTasksForCalendar() {
  const { project, owner } = state.calendarFilters || {};
  const ownerNorm = (owner || "").toLowerCase();
  return (state.tasks || []).filter((sc) => {
    if (!showCompletedOperationalWork() && isCompletedTaskStatus(sc.status)) return false;
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

function updateCurrentPhaseOptions(solutionId, selectedPhaseId = null) {
  const sel = els.solutionForm?.querySelector('[name="current_phase"]');
  if (!sel) return;

  const selectedValue = selectedPhaseId ?? sel.value ?? "";
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
  if (selectedValue && phases.some((p) => p.phase_id === selectedValue)) {
    sel.value = selectedValue;
  }
}

function solutionProgress(solution) {
  if (!solution) return 0;
  if (solution.status === "complete") return 100;
  if (!state.phases.length || !solution.current_phase) return 0;
  const phases = [...state.phases].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
  const idx = phases.findIndex((p) => p.phase_id === solution.current_phase);
  if (idx === -1) return 0;
  return Math.round((idx / phases.length) * 100);
}

function formatStatus(status) {
  return formatStatusLabel(status, "—");
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

function phaseDisplayName(phaseId) {
  if (!phaseId) return "";
  const phase = state.phases.find((p) => p.phase_id === phaseId);
  const name = phase?.phase_name || phaseId;
  if (phaseId === "poc" || name.toLowerCase() === "poc") return "Proof of Concept";
  return name;
}

function renderMasterTable() {
  const mod = getRouteModule("master");
  if (!mod || typeof mod.renderMasterTable !== "function") {
    ensureRouteModule("master").then((loaded) => {
      if (loaded && state.currentView === "master") renderMasterTable();
    });
    return;
  }
  mod.renderMasterTable(createMasterRouteContext());
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

function clearCapacityUserFormStatus() {
  clearDeliverableFormNotice(els.capacityUserFormStatus);
}

function setCapacityUserFormStatus(message, tone = "info", autoClearMs = 0) {
  setDeliverableFormNotice(els.capacityUserFormStatus, message, tone, autoClearMs);
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

function renderProgramDashboard() {
  const mod = getRouteModule("program-dashboard");
  if (!mod || typeof mod.renderProgramDashboard !== "function") {
    if (state.currentView === "program-dashboard" && els.programDashboardRoot) {
      els.programDashboardRoot.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("program-dashboard").then((loaded) => {
      if (loaded && state.currentView === "program-dashboard") renderProgramDashboard();
    });
    return;
  }
  mod.renderProgramDashboard({
    state,
    els,
    apiBase: API_BASE,
    setStatus,
    formatStatus,
    phaseDisplayName,
    solutionProgress,
    showCompletedOperationalWork,
    openProgramDashboardProjectDrilldown,
    openProgramDashboardSolutionDrilldown,
    openProgramDashboardTaskDrilldown,
    trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
  });
}

function publicProgramDashboardSlug(pathname = window.location.pathname) {
  const raw = String(pathname || "/");
  const relative = APP_CONTEXT_PATH && raw.startsWith(APP_CONTEXT_PATH)
    ? raw.slice(APP_CONTEXT_PATH.length) || "/"
    : raw;
  const match = relative.match(/^\/public\/program-dashboard\/([^/?#]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function loadPublicProgramDashboard() {
  const slug = publicProgramDashboardSlug();
  if (!slug) return false;
  document.body.classList.add("public-program-dashboard-page");
  setAuthed(null);
  setAuthVisible(false);
  setResetVisible(false);
  if (els.appShell) els.appShell.classList.remove("hidden");
  document.getElementById("public-login-link")?.setAttribute("href", buildAppUrl("/"));
  els.views.forEach((viewEl) => viewEl.classList.toggle("active", viewEl.id === "view-program-dashboard"));
  state.currentView = "program-dashboard";
  state.activeSpace = {
    space_id: `public:${slug}`,
    space_name: slug,
    space_role: "public",
  };
  if (els.programDashboardRoot) {
    els.programDashboardRoot.innerHTML = "<p class='muted'>Loading dashboard...</p>";
  }
  try {
    const response = await fetch(`${API_BASE}/public/program-dashboard/${encodeURIComponent(slug)}`, {
      credentials: "omit",
      headers: { "Accept": "application/json" },
    });
    if (!response.ok) {
      throw new Error(response.status === 404 ? "Dashboard not found." : `Dashboard failed to load (${response.status}).`);
    }
    const payload = await response.json();
    state.activeSpace = {
      space_id: payload?.space?.space_id || `public:${slug}`,
      space_name: payload?.space?.space_name || payload?.space?.slug || slug,
      space_role: "public",
    };
    state.phases = Array.isArray(payload?.phases) ? payload.phases : [];
    state.programs = Array.isArray(payload?.programs) ? payload.programs : [];
    state.projects = Array.isArray(payload?.projects) ? payload.projects : [];
    state.solutions = Array.isArray(payload?.solutions) ? payload.solutions : [];
    const mod = await ensureRouteModule("program-dashboard");
    if (!mod || typeof mod.renderProgramDashboard !== "function") throw new Error("Dashboard module failed to load.");
    mod.renderProgramDashboard({
      state,
      els,
      apiBase: API_BASE,
      setStatus,
      formatStatus,
      phaseDisplayName,
      solutionProgress,
      showCompletedOperationalWork,
      readOnly: true,
      publicMode: true,
      publicSlug: slug,
    });
  } catch (err) {
    console.warn("Public program dashboard load failed", err);
    if (els.programDashboardRoot) {
      els.programDashboardRoot.innerHTML = `<p class='program-dashboard-empty muted'>${escapeHtml(err?.message || "Dashboard not found.")}</p>`;
    }
  }
  return true;
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

function openProgramDashboardProjectDrilldown(projectId) {
  openDashboardProjectDrilldown(projectId);
}

function openProgramDashboardSolutionDrilldown(solutionId) {
  openDashboardSolutionDrilldown(solutionId);
}

function openProgramDashboardTaskDrilldown(taskId) {
  const targetId = String(taskId || "").trim();
  if (!targetId) return;
  const task = state.tasks.find((row) => row.task_id === targetId);
  if (!task) return;
  const solution = state.solutions.find((row) => row.solution_id === task.solution_id);
  if (!solution) return;
  openSolutionModal(solution, "tasks");
  fillTaskForm(task);
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
    apiBase: API_BASE,
    setStatus,
    formatStatus,
    viewHref,
    openPMDashboardProjectDrilldown,
    openPMDashboardSolutionDrilldown,
    openPMDashboardTaskDrilldown,
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

function openPMDashboardSolutionDrilldown(solutionId) {
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

function openKanbanProjectDrilldown(projectId) {
  return kanbanRouteController.openKanbanProjectDrilldown(projectId);
}

function openKanbanSolutionDrilldown(solutionId) {
  return kanbanRouteController.openKanbanSolutionDrilldown(solutionId);
}

function openPMDashboardTaskDrilldown(taskId) {
  const targetId = String(taskId || "").trim();
  if (!targetId) return;
  const task = state.tasks.find((row) => row.task_id === targetId);
  if (!task) return;
  const solution = state.solutions.find((row) => row.solution_id === task.solution_id);
  if (!solution) return;
  openSolutionModal(solution, "tasks");
  fillTaskForm(task);
}

function closeConfirmModal(result = false) {
  return modalShellController.closeConfirmModal(result);
}

function showConfirmModal(options = {}) {
  return modalShellController.showConfirmModal(options);
}

function bindConfirmModal() {
  return modalShellController.bindConfirmModal();
}

function openProjectForm(project = null) {
  return projectEntityController.openProjectForm(project);
}

function openProgramForm(program = null) {
  return programEntityController.openProgramForm(program);
}

function bindProgramForm() {
  return programEntityController.bindProgramForm();
}

function closeProjectForm() {
  return projectEntityController.closeProjectForm();
}

function bindProjectForm() {
  return projectEntityController.bindProjectForm();
}

function bindSolutionForm() {
  return solutionEntityController.bindSolutionForm();
}

function setTaskActionButtonLabel(isEditing) {
  return taskEntityController.setTaskActionButtonLabel(isEditing);
}

function setTaskFormVisibility(show) {
  return taskEntityController.setTaskFormVisibility(show);
}

function hideTaskForm() {
  return taskEntityController.hideTaskForm();
}

function setTaskCreateAvailability(solutionId) {
  return solutionEntityController.setTaskCreateAvailability(solutionId);
}

function openSolutionModal(solution = null, tab = "details") {
  return solutionEntityController.openSolutionModal(solution, tab);
}

function closeSolutionModal() {
  return solutionEntityController.closeSolutionModal();
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
  if (tab === "tasks") {
    const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (solutionId) renderSolutionTasks(solutionId);
  }
  if (tab === "documents") {
    const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    renderSolutionDocuments(solutionId);
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
    if (btn.dataset.tab === "tasks" && els.taskForm && !els.taskForm.classList.contains("hidden")) {
      hideTaskForm();
    }
    setSolutionTab(btn.dataset.tab);
  });
  tabs._bound = true;
}

function showTaskForm(solution) {
  return taskEntityController.showTaskForm(solution);
}

function fillTaskForm(task) {
  return taskEntityController.fillTaskForm(task);
}

function renderSolutionTasks(solutionId) {
  if (!els.solutionTaskTable) return;
  if (!solutionId) {
    setTaskCreateAvailability("");
    els.solutionTaskTable.innerHTML = "<p class='muted'>Save the solution to add tasks.</p>";
    return;
  }
  setTaskCreateAvailability(solutionId);
  const allSubs = state.tasks.filter((s) => s.solution_id === solutionId);
  const hiddenClosedCount = !showCompletedOperationalWork()
    ? allSubs.filter((task) => isCompletedTaskStatus(task.status)).length
    : 0;
  const visibleSubs = showCompletedOperationalWork()
    ? allSubs
    : allSubs.filter((task) => !isCompletedTaskStatus(task.status));
  const subs = sortTasksByName(visibleSubs, state.taskSort);
  const hiddenNote = hiddenClosedCount
    ? `<p class="form-notice">Completed items are hidden here. Use Show Completed in the top bar to review ${hiddenClosedCount} closed task${hiddenClosedCount === 1 ? "" : "s"}.</p>`
    : "";
  if (state.taskView === "swimlane") {
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
                  `<div class="swimlane-card" data-id="${s.task_id}">
                    <div class="swimlane-title">${s.task_name}</div>
                    <div class="swimlane-meta">${s.assignee || "—"} • P${s.priority ?? "–"}</div>
                    <div class="swimlane-meta">Due ${s.due_date || "—"}</div>
                  </div>`
              )
              .join("")
          : "<p class='muted'>Empty</p>";
        return `<div class="swimlane-column"><h4>${formatStatus(status)}</h4>${cards}</div>`;
      })
      .join("");
    els.solutionTaskTable.innerHTML = `${hiddenNote}<div class="swimlane-board">${columns}</div>`;
  } else {
    const sortPresentation = taskNameSortPresentation(state.taskSort);
    const rows = subs
      .map(
        (s) =>
          `<tr data-id="${s.task_id}">
            <td><button class="icon-btn edit-task-btn" data-id="${s.task_id}" title="Edit">✎</button></td>
            <td>${s.task_name || "—"}</td>
            <td>${formatStatus(s.status)}</td>
            <td>${s.assignee || "—"}</td>
            <td>${s.priority ?? "—"}</td>
            <td>${s.due_date || ""}</td>
          </tr>`
      )
      .join("");
    els.solutionTaskTable.innerHTML = `
      ${hiddenNote}
      <table class="task-table">
        <thead>
          <tr>
            <th></th>
            <th aria-sort="${sortPresentation.ariaSort}">
              <button class="task-name-sort-button" type="button" data-task-name-sort aria-label="${sortPresentation.nextLabel}" title="${sortPresentation.nextLabel}">
                <span>Task</span>
                <span class="task-name-sort-indicator" aria-hidden="true">${sortPresentation.indicator}</span>
              </button>
            </th>
            <th>Status</th>
            <th>Assignee</th>
            <th>Priority</th>
            <th>Due</th>
          </tr>
        </thead>
        <tbody>${rows || `<tr><td colspan='6' class='muted'>${hiddenClosedCount ? "No open tasks in view." : "No tasks"}</td></tr>`}</tbody>
      </table>`;
  }
}

function formatFileSize(bytes) {
  const size = Number(bytes || 0);
  if (!Number.isFinite(size) || size <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function documentDownloadUrl(solutionId, documentId) {
  return buildApiUrl(
    `/solutions/${encodeURIComponent(solutionId)}/documents/${encodeURIComponent(documentId)}/download`
  );
}

async function loadSolutionDocuments(solutionId, { force = false } = {}) {
  if (!solutionId) return [];
  if (!force && state.solutionDocuments[solutionId]) return state.solutionDocuments[solutionId];
  state.solutionDocuments[solutionId] = await api(`/solutions/${encodeURIComponent(solutionId)}/documents`);
  return state.solutionDocuments[solutionId];
}

async function renderSolutionDocuments(solutionId, options = {}) {
  if (!els.solutionDocumentsList) return;
  const id = solutionId || els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (!id) {
    els.solutionDocumentsList.innerHTML = "<p class='muted'>Save the solution to upload documents.</p>";
    if (els.solutionDocumentUpload) els.solutionDocumentUpload.disabled = true;
    return;
  }
  if (els.solutionDocumentUpload) els.solutionDocumentUpload.disabled = false;
  if (!options.silent) {
    els.solutionDocumentsList.innerHTML = "<p class='muted'>Loading documents...</p>";
  }
  try {
    const documents = await loadSolutionDocuments(id, options);
    if (!documents.length) {
      els.solutionDocumentsList.innerHTML = "<p class='muted'>No documents uploaded.</p>";
      return;
    }
    const rows = documents
      .map((doc) => {
        const created = doc.created_at ? new Date(doc.created_at).toLocaleString() : "";
        const downloadUrl = documentDownloadUrl(id, doc.document_id);
        return `<div class="solution-document-row" data-document-id="${escapeAttr(doc.document_id)}">
          <div class="solution-document-main">
            <a href="${escapeAttr(downloadUrl)}" download="${escapeAttr(doc.filename || "document")}" class="solution-document-name">${esc(doc.filename || "document")}</a>
            <div class="solution-document-meta">${esc(formatFileSize(doc.size_bytes))}${created ? ` &middot; ${esc(created)}` : ""}</div>
          </div>
          <div class="solution-document-actions">
            <a href="${escapeAttr(downloadUrl)}" download="${escapeAttr(doc.filename || "document")}" class="secondary button-like">Download</a>
            <button type="button" class="secondary danger solution-document-delete" data-document-id="${escapeAttr(doc.document_id)}">Delete</button>
          </div>
        </div>`;
      })
      .join("");
    els.solutionDocumentsList.innerHTML = rows;
  } catch (err) {
    els.solutionDocumentsList.innerHTML = "<p class='muted'>Unable to load documents.</p>";
    setDeliverableFormNotice(els.solutionDocumentsStatus, `Unable to load documents: ${err.message}`, "error");
  }
}

function bindSolutionDocumentControls() {
  if (els.solutionDocumentUpload && !els.solutionDocumentUpload._bound) {
    els.solutionDocumentUpload.addEventListener("click", () => {
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      if (!solutionId) {
        setDeliverableFormNotice(els.solutionDocumentsStatus, "Save the solution to upload documents.", "error");
        return;
      }
      els.solutionDocumentFile?.click();
    });
    els.solutionDocumentUpload._bound = true;
  }
  if (els.solutionDocumentFile && !els.solutionDocumentFile._bound) {
    els.solutionDocumentFile.addEventListener("change", async () => {
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      const file = els.solutionDocumentFile?.files?.[0] || null;
      if (!solutionId || !file) return;
      const formData = new FormData();
      formData.append("file", file);
      try {
        setDeliverableFormNotice(els.solutionDocumentsStatus, "Uploading document...");
        await api(`/solutions/${encodeURIComponent(solutionId)}/documents`, {
          method: "POST",
          body: formData,
          timeoutMs: 60000,
        });
        await renderSolutionDocuments(solutionId, { force: true, silent: true });
        setDeliverableFormNotice(els.solutionDocumentsStatus, `Uploaded ${file.name}.`, "success", 3200);
      } catch (err) {
        setDeliverableFormNotice(els.solutionDocumentsStatus, `Upload failed: ${err.message}`, "error");
      } finally {
        els.solutionDocumentFile.value = "";
      }
    });
    els.solutionDocumentFile._bound = true;
  }
  if (els.solutionDocumentsList && !els.solutionDocumentsList._bound) {
    els.solutionDocumentsList.addEventListener("click", async (event) => {
      const btn = event.target.closest(".solution-document-delete");
      if (!btn) return;
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      const documentId = btn.getAttribute("data-document-id") || "";
      if (!solutionId || !documentId) return;
      const row = state.solutionDocuments[solutionId]?.find((item) => item.document_id === documentId);
      const confirmed = await showConfirmModal({
        title: "Delete Document?",
        message: `Delete document "${row?.filename || "document"}"? This cannot be undone.`,
        confirmLabel: "Delete Document",
      });
      if (!confirmed) return;
      try {
        setDeliverableFormNotice(els.solutionDocumentsStatus, "Deleting document...");
        await api(`/solutions/${encodeURIComponent(solutionId)}/documents/${encodeURIComponent(documentId)}`, {
          method: "DELETE",
        });
        await renderSolutionDocuments(solutionId, { force: true, silent: true });
        setDeliverableFormNotice(els.solutionDocumentsStatus, "Deleted document.", "success", 3200);
      } catch (err) {
        setDeliverableFormNotice(els.solutionDocumentsStatus, `Delete failed: ${err.message}`, "error");
      }
    });
    els.solutionDocumentsList._bound = true;
  }
}

function bindSolutionTaskControls() {
  if (els.taskViewToggle && !els.taskViewToggle._bound) {
    els.taskViewToggle.addEventListener("click", () => {
      state.taskView = state.taskView === "table" ? "swimlane" : "table";
      els.taskViewToggle.textContent = state.taskView === "table" ? "Swimlane View" : "Table View";
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      renderSolutionTasks(solutionId);
    });
    els.taskViewToggle._bound = true;
  }
  if (els.solutionTaskTable && !els.solutionTaskTable._bound) {
    els.solutionTaskTable.addEventListener("click", (e) => {
      const sortButton = e.target.closest("[data-task-name-sort]");
      if (sortButton) {
        state.taskSort = nextTaskNameSort(state.taskSort);
        const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        renderSolutionTasks(solutionId);
        return;
      }
      const btn = e.target.closest(".edit-task-btn");
      const card = e.target.closest(".swimlane-card");
      const id = btn?.getAttribute("data-id") || card?.getAttribute("data-id");
      if (!id) return;
      const task = state.tasks.find((item) => item.task_id === id);
      if (!task) return;
      fillTaskForm(task);
    });
    els.solutionTaskTable._bound = true;
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
    if (els.taskCreatePickerModal && !els.taskCreatePickerModal.classList.contains("hidden")) {
      closeTaskCreatePicker();
      return;
    }
    if (els.solutionModal && !els.solutionModal.classList.contains("hidden")) {
      if (els.taskForm && !els.taskForm.classList.contains("hidden")) {
        hideTaskForm();
        return;
      }
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
  } catch (_err) {
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
  const currentPhaseValue = els.solutionForm?.querySelector('[name="current_phase"]')?.value || "";
  updateCurrentPhaseOptions(solutionId, currentPhaseValue);

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

        updateCurrentPhaseOptions(solutionId, updatedSolution.current_phase || "");
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

function bindTaskForm() {
  return taskEntityController.bindTaskForm();
}

function programNameForProject(project) {
  return project?.program_name
    || state.programs.find((program) => program.program_id === project?.program_id)?.program_name
    || "";
}

function projectLabel(project) {
  const programName = programNameForProject(project);
  return programName ? `${programName} / ${project.project_name}` : project.project_name;
}

function populateSelects() {
  const programOpts = state.programs
    .map((program) => `<option value="${program.program_id}">${escapeHtml(program.program_name)}</option>`)
    .join("");
  const projectOpts = state.projects
    .map((p) => `<option value="${p.project_id}">${escapeHtml(projectLabel(p))}</option>`)
    .join("");
  const kanbanProjectFilterChanged = normalizeScopedProjectFilter(state.kanbanFilters);
  const kanbanOwnerFilterChanged = normalizeScopedOwnerFilter(state.kanbanFilters, { includeSolutions: true });
  const calendarProjectFilterChanged = normalizeScopedProjectFilter(state.calendarFilters);
  const calendarOwnerFilterChanged = normalizeScopedOwnerFilter(state.calendarFilters, {
    includeSolutions: true,
    includeTasks: true,
  });
  const projSelects = [
    els.solutionForm?.querySelector('[name="project_id"]'),
  ].filter(Boolean);
  const programSelects = [
    els.projectForm?.querySelector('[name="program_id"]'),
  ].filter(Boolean);
  programSelects.forEach((sel) => {
    if (sel.tagName === "SELECT") {
      const previous = sel.value;
      sel.innerHTML = `<option value="">Select</option>${programOpts}`;
      if (previous && state.programs.find((program) => program.program_id === previous)) {
        sel.value = previous;
      } else {
        sel.value = state.programs.find((program) => program.program_name === "Default Program")?.program_id
          || state.programs[0]?.program_id
          || "";
      }
    }
  });
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
  const teamOpts = state.teams.map((t) => `<option value="${t.team_id}">${t.name}</option>`).join("");
  const teamSelects = [els.teamMemberForm?.querySelector('[name="team_id"]')].filter(Boolean);
  teamSelects.forEach((sel) => (sel.innerHTML = `<option value="">Unassigned</option>${teamOpts}`));
  if (els.teamMemberForm && els.teamMemberForm.querySelector('[name="team_id"]') && state.teams.length && !els.teamMemberForm.querySelector('[name="team_id"]').value) {
    els.teamMemberForm.querySelector('[name="team_id"]').value = state.teams[0].team_id;
  }
  populateCapacityUserOptions();

  // Assignee dropdown for tasks from team members
  if (els.taskForm) {
    const assigneeSel = els.taskForm.querySelector('[name="assignee"]');
    const assigneeUserInput = els.taskForm.querySelector('[name="assignee_user_soeid"]');
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
  populateTasksWorkbenchOptions(createTasksWorkbenchContext(), { projectOptionsHtml: projectOpts });

  if (els.aiEntityType && els.aiEntityId) {
    const type = els.aiEntityType.value;
    let options = "";
    if (type === "project") {
      options =
        `<option value=\"\">New project</option>` +
        state.projects.map((p) => `<option value="${p.project_id}">${escapeHtml(projectLabel(p))}</option>`).join("");
    } else if (type === "solution") {
      options = state.solutions.map((s) => `<option value="${s.solution_id}">${s.solution_name}</option>`).join("");
    } else {
      options = state.tasks.map((sc) => `<option value="${sc.task_id}">${sc.task_name}</option>`).join("");
    }
    els.aiEntityId.innerHTML = options || `<option value=\"\">No items</option>`;
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
    openKanbanProjectDrilldown,
    openKanbanSolutionDrilldown,
  });
}

function normalizeScopedOwnerFilter(filterState, { includeSolutions = true, includeTasks = false } = {}) {
  if (!filterState || typeof filterState !== "object") return false;
  const currentOwner = String(filterState.owner || "").trim();
  if (!currentOwner) return false;
  const ownerToken = currentOwner.toLowerCase();
  const hasSolutionMatch = includeSolutions
    && (state.solutions || []).some((solution) => String(solution?.owner || "").toLowerCase().includes(ownerToken));
  const hasTaskMatch = includeTasks
    && (state.tasks || []).some((task) => {
      const assigneeName = String(task?.assignee || "").toLowerCase();
      const assigneeSoeid = String(task?.assignee_user_soeid || "").toLowerCase();
      return assigneeName.includes(ownerToken) || assigneeSoeid.includes(ownerToken);
    });
  if (hasSolutionMatch || hasTaskMatch) return false;
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
    filteredTasksForCalendar,
    formatStatus,
  });
}

function renderGantt() {
  const mod = getRouteModule("gantt");
  if (!mod || typeof mod.renderGantt !== "function") {
    if (state.currentView === "gantt" && els.ganttChart) {
      els.ganttChart.innerHTML = "<p class='muted'>Loading...</p>";
    }
    ensureRouteModule("gantt").then((loaded) => {
      if (loaded && state.currentView === "gantt") renderGantt();
    });
    return;
  }
  mod.renderGantt({
    state,
    els,
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
      setImportResult(resultEl, "Portal sign-in required", true);
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
    telemetryController?.trackWorkflow?.("csv", "export", "success", { kind, source: "csv_menu" });
    setImportResult(resultEl, `Downloaded ${filename}`);
  } catch (err) {
    telemetryController?.trackWorkflow?.("csv", "export", "failure", { kind, source: "csv_menu" });
    setImportResult(resultEl, `Download failed: ${err.message}`, true);
  }
}

function csvImportResultElement(kind) {
  if (kind === "projects") return els.projectsImportResult;
  if (kind === "solutions") return els.solutionsImportResult;
  if (kind === "tasks") return els.taskCsvImportResult;
  if (kind === "users") return els.rosterImportResult;
  return null;
}

function csvKindConfig(kind) {
  const configs = {
    projects: {
      label: "Projects",
      filename: "projects-template.csv",
      templateContent: [
        "program_id,program_name,project_name,status,description,success_criteria,sponsor,sponsor_user_soeid,strategic_objective,priority",
        ",Default Program,Example Project,not_started,Simple project description,Deliver one small milestone,Example Sponsor,,,3",
      ].join("\n"),
    },
    solutions: {
      label: "Solutions",
      filename: "solutions-template.csv",
      templateContent: [
        "project_name,solution_name,version,status,owner,assignee,priority,due_date,current_phase,github_repo_url",
        "Example Project,Example Solution,0.1.0,not_started,Example Owner,Example Owner,3,,,https://github.com/example-org/example-repo",
      ].join("\n"),
    },
    tasks: {
      label: "Tasks",
      filename: "tasks-template.csv",
      templateContent: [
        "project_name,solution_name,version,task_name,description,status,priority,due_date,assignee,assignee_user_soeid,github_repo_url,estimate_hours,blocked,blocker_note,acceptance_criteria,completed_at",
        "Example Project,Example Solution,0.1.0,Example Task,Describe the expected work,to_do,3,2026-07-31,Example Owner,,https://github.com/example-org/example-repo,8,false,Waiting on vendor,Acceptance criteria met,",
      ].join("\n"),
    },
  };
  return configs[kind] || configs.projects;
}

function csvTemplateConfig(kind) {
  const config = csvKindConfig(kind);
  return {
    filename: config.filename,
    content: config.templateContent,
  };
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
  const normalizedKind = ["projects", "solutions", "tasks"].includes(kind) ? kind : "projects";
  const config = csvKindConfig(normalizedKind);
  csvUploadState.kind = normalizedKind;
  csvUploadState.file = null;
  if (els.csvUploadTitle) {
    els.csvUploadTitle.textContent = `Upload ${config.label} CSV`;
  }
  if (els.csvUploadDescription) {
    els.csvUploadDescription.textContent = `Upload a ${config.label} CSV. Use the template if you need the expected columns.`;
  }
  if (els.csvDownloadTemplate) {
    els.csvDownloadTemplate.textContent = `Download ${config.label} Template`;
  }
  if (els.csvSubmitUpload) {
    els.csvSubmitUpload.textContent = `Upload ${config.label} CSV`;
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
  if (els.csvDownloadTemplate) els.csvDownloadTemplate.textContent = "Download Template";
  if (els.csvSubmitUpload) els.csvSubmitUpload.textContent = "Upload CSV";
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
      const msg = "Portal sign-in required";
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
    telemetryController?.trackWorkflow?.("csv", "import", errs.length ? "failure" : "success", {
      kind,
      result_kind: errs.length ? "partial" : "complete",
      source: "csv_menu",
    });
    return { ok: errs.length === 0, message: detail, partial: errs.length > 0 };
  } catch (err) {
    const msg = `Import failed: ${err.message}`;
    telemetryController?.trackWorkflow?.("csv", "import", "failure", { kind, source: "csv_menu" });
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
  if (els.tasksCsvDownload && !els.tasksCsvDownload._bound) {
    els.tasksCsvDownload.addEventListener("click", () => {
      closeCsvMenu();
      downloadCsv("tasks", "tasks.csv", els.taskCsvImportResult);
    });
    els.tasksCsvDownload._bound = true;
  }
  if (els.tasksCsvUpload && !els.tasksCsvUpload._bound) {
    els.tasksCsvUpload.addEventListener("click", () => {
      closeCsvMenu();
      openCsvUploadModal("tasks");
    });
    els.tasksCsvUpload._bound = true;
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
      const config = csvKindConfig(kind);
      downloadCsvTemplate(kind, csvImportResultElement(kind));
      setCsvUploadStatus(`${config.label} CSV template downloaded.`, "success");
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
  return spaceSwitcherController.bindSpaceSwitcher();
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
  calendarRouteController.bindCalendarRouteControls();
  ganttRouteController.bindGanttRouteControls();
  kanbanRouteController.bindKanbanRouteControls();
}

async function loadTeamCapacityData(options = {}) {
  return teamCapacityRouteController.loadTeamCapacityData(options);
}

function bindCapacityUsers() {
  return teamCapacityRouteController.bindTeamCapacityControls();
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

function normalizeMasterCollapsedKeys(value) {
  if (!Array.isArray(value)) return new Set();
  return new Set(
    value
      .map((key) => String(key || "").trim())
      .filter((key) => key.startsWith("program:") || key.startsWith("project:"))
  );
}

function persistMasterViewState() {
  writeStoredJson(
    activeSpaceScopedStorageKey(MASTER_VIEW_STATE_KEY_PREFIX),
    {
      filters: { ...(state.filters || {}) },
      collapsed: Array.from(state.masterCollapsed || []),
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

function persistTasksWorkbenchUiState() {
  const wb = state.tasksWorkbench || {};
  writeStoredJson(
    activeSpaceScopedStorageKey(TASKS_WORKBENCH_UI_STATE_KEY_PREFIX),
    {
      preset: wb.preset || "all",
      sort: wb.sort || "default",
      filters: { ...(wb.filters || {}) },
      drawerOpen: wb.drawerOpen !== false,
      activeTaskId: wb.activeTaskId || "",
      selectedSavedViewId: wb.selectedSavedViewId || "",
    }
  );
}

function restoreTasksWorkbenchUiState() {
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(TASKS_WORKBENCH_UI_STATE_KEY_PREFIX), {});
  const wb = state.tasksWorkbench;
  wb.preset = String(stored.preset || "all");
  wb.sort = String(stored.sort || "default");
  wb.filters = stored.filters && typeof stored.filters === "object" ? { ...stored.filters } : {};
  wb.activeTaskId = String(stored.activeTaskId || "");
  wb.drawerOpen = stored.drawerOpen === true && Boolean(wb.activeTaskId);
  wb.selectedSavedViewId = String(stored.selectedSavedViewId || "");
  normalizeWorkbenchUiState(createTasksWorkbenchContext());
  if (recovered || !Object.keys(stored || {}).length) persistTasksWorkbenchUiState();
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
  state.masterCollapsed = normalizeMasterCollapsedKeys(stored.collapsed);
  let changed = recovered;
  const normalized = normalizeMasterFilters(rawFilters);
  state.filters = normalized.filters;
  if (normalized.changed) changed = true;
  if (!Array.isArray(stored.collapsed)) changed = true;
  if (changed) persistMasterViewState();
}

function persistCalendarViewState() {
  return calendarRouteController.persistCalendarViewState();
}

function restoreCalendarViewState() {
  return calendarRouteController.restoreCalendarViewState();
}

function restoreGanttViewState() {
  return ganttRouteController.restoreGanttViewState();
}

function persistKanbanViewState() {
  return kanbanRouteController.persistKanbanViewState();
}

function restoreKanbanViewState() {
  return kanbanRouteController.restoreKanbanViewState();
}

function restoreTeamCapacityViewState() {
  return teamCapacityRouteController.restoreTeamCapacityViewState();
}

function persistSpaceGovernanceViewState() {
  if (!state.authed || !activeSpaceId() || state.activeSpace?.space_kind === "lobby") return;
  writeStoredJson(
    activeSpaceScopedStorageKey(SPACE_GOVERNANCE_VIEW_STATE_KEY_PREFIX),
    { section: normalizeGovernanceSection(state.spaceAdminSection) }
  );
}

function restoreSpaceGovernanceViewState() {
  if (!state.authed || !activeSpaceId()) return;
  const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(SPACE_GOVERNANCE_VIEW_STATE_KEY_PREFIX), {});
  const allowed = governanceSections().map((section) => section.id);
  const storedSection = normalizeGovernanceSection(stored.section);
  state.spaceAdminSection = allowed.includes(storedSection) ? storedSection : "current-space";
  if (recovered || !Object.keys(stored || {}).length || stored.section !== state.spaceAdminSection) {
    persistSpaceGovernanceViewState();
  }
}

function canManageSpaceMembership(spaceId) {
  if (!spaceId) return false;
  if (userIsGlobalAdmin()) return true;
  return isSpaceAdminRole(state.activeSpace?.space_role) && activeSpaceId() === spaceId;
}

function normalizeGovernanceSection(value) {
  const raw = normalize(value).replace(/[\s_]+/g, "-");
  return raw || "current-space";
}

function governanceSections() {
  const sections = [
    { id: "agent-approvals", label: `Agent Approvals${state.agentChangeRequestPendingCount ? ` (${state.agentChangeRequestPendingCount})` : ""}` },
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

function closeSpaceCreateModal() {
  return spaceGovernanceController.closeSpaceCreateModal();
}

function closeSpaceMemberModal() {
  return spaceGovernanceController.closeSpaceMemberModal();
}

function closeSpaceDirectoryModal() {
  return spaceGovernanceController.closeSpaceDirectoryModal();
}

function renderSpaceDirectoryModal() {
  return spaceGovernanceRenderer.renderSpaceDirectoryModal();
}

function renderGovernanceHub(preferredSection = "") {
  const result = spaceGovernanceRenderer.renderGovernanceHub(preferredSection);
  persistSpaceGovernanceViewState();
  return result;
}

async function refreshGlobalAdmins() {
  return spaceGovernanceController.refreshGlobalAdmins();
}

async function refreshAccessRequests(options = {}) {
  return spaceGovernanceController.refreshAccessRequests(options);
}

async function refreshApiTokens(userId, options = {}) {
  return spaceGovernanceController.refreshApiTokens(userId, options);
}

async function refreshSpaceMembers(spaceId, options = {}) {
  return spaceGovernanceController.refreshSpaceMembers(spaceId, options);
}

async function refreshAgentChangeRequests(options = {}) {
  return spaceGovernanceController.refreshAgentChangeRequests(options);
}

async function refreshRequestableSpaces(options = {}) {
  return spaceGovernanceController.refreshRequestableSpaces(options);
}

async function refreshReviewableAccessRequests(options = {}) {
  return spaceGovernanceController.refreshReviewableAccessRequests(options);
}

function bindSpaceAdminControls() {
  return spaceGovernanceController.bindSpaceAdminControls();
}

function renderTeamCapacity() {
  const renderStartedAt = performance.now();
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
    userCapacityFteMonth,
    formatFte,
    teamCapacityState: state.teamCapacity,
    selectedSoeid: state.capacitySelectedSoeid,
  });
  if (state.currentView === "team-capacity") {
    telemetryController?.noteViewRendered?.("team-capacity", performance.now() - renderStartedAt);
  }
}

function renderAnalytics() {
  const mod = getRouteModule("analytics");
  if (!mod || typeof mod.renderAnalytics !== "function") {
    ensureRouteModule("analytics").then((loaded) => {
      if (loaded && state.currentView === "analytics") renderAnalytics();
    });
    return;
  }
  mod.renderAnalytics(createShellContext({
    state,
    els,
    api,
    setStatus,
    usageAnalyticsEnabled,
    trackWorkflow: (...args) => telemetryController?.trackWorkflow?.(...args),
    noteRouteDataLoaded: (durationMs) => telemetryController?.noteRouteDataLoaded?.("analytics", durationMs),
    noteViewRendered: (renderMs) => telemetryController?.noteViewRendered?.("analytics", renderMs),
  }, { view: "analytics" }));
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

function init() {
  initTheme();
  if (publicProgramDashboardSlug()) {
    loadPublicProgramDashboard();
    return;
  }
  bindWorkspaceViewPreferences();
  shellNavigationController.bind();
  bindAuthUI();
  bindTopbarCreateMenu();
  bindTaskCreatePicker();
  bindCsvControls();
  bindSpaceSwitcher();
  bindNav();
  document.addEventListener("visibilitychange", handleLiveSyncVisibilityChange);
  bindConfirmModal();
  renderTopbarStatus();
  renderSpaceSwitcher();
  bindMasterDeliverablesControls(createMasterRouteContext());
  bindMasterDeliverablesTable(createMasterRouteContext());
  bindProgramForm();
  bindProjectForm();
  bindSolutionForm();
  bindTaskForm();
  bindSolutionTabs();
  bindSolutionDocumentControls();
  bindSolutionTaskControls();
  bindModalShortcuts();
  bindCalendarControls();
  bindCapacityUsers();
  bindSpaceAdminControls();
  initTasksWorkbench();
  const initialView = viewFromLocationPath();
  setView(initialView, { fromHistory: true });
  if (!isResetPath()) {
    syncPathForView(initialView, true);
  }
  bootstrapAuth();
}

init();
