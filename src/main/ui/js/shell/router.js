import { APP_CONTEXT_PATH, buildAppUrl } from "./paths.js";
import {
  VIEW_DATA_REQUIREMENTS,
  VIEW_PREFETCH_TARGET,
  normalizeRouteView,
  routeDefinition,
} from "./route-registry.js";


export function createRouterController({
  state,
  els,
  renderActiveView,
  userIsGlobalAdmin,
  isSpaceAdminRole,
  usageAnalyticsEnabled = () => false,
  loadData,
  loadTeamCapacityData,
  onBeforeViewChange = null,
  onAccessRedirect = null,
  onModuleLoadFailure = null,
  routeModuleLoaders = null,
}) {
  const DATA_ENTITIES = ["phases", "programs", "projects", "solutions", "tasks", "teams", "users"];
  const ADMIN_VIEWS = new Set(["spaces", "access"]);
  const GLOBAL_ADMIN_VIEWS = new Set(["analytics"]);
  const PROGRAM_DASHBOARD_ROUTE_VERSION = "program-dashboard-escalation-grid-v1";
  const ROUTE_MODULE_LOADERS = routeModuleLoaders || {
    master: () => import("../routes/master.js"),
    gantt: () => import("../routes/gantt.js"),
    "tasks-workbench": () => import("../routes/tasks-workbench.js"),
    dashboard: () => import("../routes/dashboard.js"),
    "program-dashboard": () => import(`../routes/program-dashboard.js?v=${PROGRAM_DASHBOARD_ROUTE_VERSION}`),
    "pm-dashboard": () => import("../routes/pm-dashboard.js"),
    kanban: () => import("../routes/kanban.js"),
    calendar: () => import("../routes/calendar.js"),
    "team-capacity": () => import("../routes/team-capacity.js"),
    spaces: () => import("../routes/spaces.js"),
    access: () => import("../routes/access.js"),
    analytics: () => import("../routes/analytics.js"),
  };
  const routeModuleCache = {};
  const routeModuleInFlight = {};
  let suppressRouteChange = false;

  function normalizeView(view) {
    return normalizeRouteView(view);
  }

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
        if (typeof onModuleLoadFailure === "function") {
          onModuleLoadFailure({ view: key, error: err });
        }
        return null;
      })
      .finally(() => {
        delete routeModuleInFlight[key];
      });
    return routeModuleInFlight[key];
  }

  function isAdminView(view) {
    const normalized = normalizeView(view);
    return ADMIN_VIEWS.has(normalized) || GLOBAL_ADMIN_VIEWS.has(normalized);
  }

  function userCanAccessAdminViews() {
    if (!state.authed) return false;
    if (userIsGlobalAdmin()) return true;
    return isSpaceAdminRole(state.activeSpace?.space_role);
  }

  function isLobbyActive() {
    return state.authed && state.activeSpace?.space_kind === "lobby";
  }

  function canAccessView(view) {
    const normalized = normalizeView(view);
    if (isLobbyActive() && !["spaces", "access"].includes(normalized)) {
      return false;
    }
    if (normalized === "analytics") {
      return state.authed && userIsGlobalAdmin() && usageAnalyticsEnabled();
    }
    if (normalized === "access") return userCanAccessAdminViews();
    if (normalized === "spaces") return state.authed;
    if (isAdminView(normalized)) return false;
    return true;
  }

  function resolveAccessibleView(view) {
    const normalized = normalizeView(view);
    if (!canAccessView(normalized)) return isLobbyActive() ? "spaces" : "master";
    return normalized;
  }

  function appRelativePath(pathname = window.location.pathname) {
    const raw = String(pathname || "/").trim() || "/";
    if (APP_CONTEXT_PATH && raw.startsWith(APP_CONTEXT_PATH)) {
      const trimmed = raw.slice(APP_CONTEXT_PATH.length) || "/";
      return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
    }
    return raw.startsWith("/") ? raw : `/${raw}`;
  }

  function routePathForView(view) {
    const normalized = normalizeView(view);
    return normalized === "master" ? "/" : `/${normalized}`;
  }

  function viewHref(view) {
    return buildAppUrl(routePathForView(view));
  }

  function isResetPathname(pathname = window.location.pathname) {
    const current = appRelativePath(pathname).replace(/\/+$/, "");
    return current === "/reset-password";
  }

  function viewFromLocationPath(pathname = window.location.pathname) {
    const relative = appRelativePath(pathname).replace(/\/+$/, "");
    if (relative === "/" || relative === "") return "master";
    const firstSegment = relative.replace(/^\/+/, "").split("/")[0].trim().toLowerCase();
    return normalizeView(firstSegment);
  }

  function syncPathForView(view, replace = false) {
    const target = viewHref(view);
    const currentUrl = new URL(window.location.href);
    const targetUrl = new URL(target, window.location.origin);
    if (currentUrl.pathname === targetUrl.pathname) return;
    suppressRouteChange = true;
    if (replace) {
      window.history.replaceState(null, "", targetUrl.pathname);
    } else {
      window.history.pushState(null, "", targetUrl.pathname);
    }
    window.setTimeout(() => {
      suppressRouteChange = false;
    }, 0);
  }

  function isRouteChangeSuppressed() {
    return suppressRouteChange;
  }

  function viewDomIdForRoute(view) {
    return routeDefinition(view).domView;
  }

  function navViewForRoute(view) {
    return routeDefinition(view).navView;
  }

  function isSpaceGovernanceView(view) {
    const normalized = normalizeView(view);
    return normalized === "spaces" || normalized === "access";
  }

  function entitiesForView(view) {
    if (isLobbyActive() && normalizeView(view) === "spaces" && !userIsGlobalAdmin()) return [];
    return VIEW_DATA_REQUIREMENTS[normalizeView(view)] || VIEW_DATA_REQUIREMENTS.master;
  }

  function isKnownEntity(entity) {
    return DATA_ENTITIES.includes(entity);
  }

  function viewHasLazyModule(view) {
    return !!ROUTE_MODULE_LOADERS[normalizeView(view)];
  }

  function setView(view, options = {}) {
    const previousView = state.currentView;
    const requestedView = normalizeView(view);
    const nextView = resolveAccessibleView(requestedView);
    const fromHistory = !!options.fromHistory;
    const replacePath = !!options.replacePath;
    const redirected = requestedView !== nextView;
    const nextDomView = viewDomIdForRoute(nextView);
    const nextNavView = navViewForRoute(nextView);
    if (redirected && isLobbyActive() && typeof onAccessRedirect === "function") {
      onAccessRedirect({
        requestedView,
        nextView,
        reason: "lobby",
      });
    }
    if (typeof onBeforeViewChange === "function") {
      onBeforeViewChange({
        previousView,
        nextView,
        redirected,
        expectsData: !!state.authed && (
          nextView === "team-capacity"
          || nextView === "analytics"
          || entitiesForView(nextView).length > 0
        ),
      });
    }
    state.currentView = nextView;
    if (nextView === "tasks-workbench" && previousView !== nextView && state.tasksWorkbench) {
      state.tasksWorkbench.drawerOpen = false;
      state.tasksWorkbench.drawerReturnTaskId = "";
      state.tasksWorkbench.drawerReturnScrollY = null;
      state.tasksWorkbench.suppressAutoScrollOnce = false;
    }
    els.views.forEach((viewEl) => {
      const isActive = viewEl.id === `view-${nextDomView}`;
      viewEl.classList.toggle("active", isActive);
      viewEl.setAttribute("aria-hidden", isActive ? "false" : "true");
    });
    els.navButtons.forEach((button) => {
      const isActive = button.dataset.view === nextNavView;
      button.classList.toggle("active", isActive);
      if (isActive) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    const definition = routeDefinition(nextView);
    if (els.currentRouteLabel) els.currentRouteLabel.textContent = definition.title;
    document.title = `${definition.title} · SIPM`;
    if (!fromHistory || redirected) {
      syncPathForView(nextView, redirected ? true : replacePath);
    }
    const routeModuleReady = viewHasLazyModule(nextView)
      ? ensureRouteModule(nextView)
      : Promise.resolve(null);
    if (state.authed) {
      if (nextView === "team-capacity") {
        routeModuleReady.then(() => {
          if (state.currentView !== nextView) return null;
          return loadTeamCapacityData({ force: true });
        }).catch((err) => {
          console.warn("Team capacity load failed", err);
        });
      } else {
        loadData({ entities: entitiesForView(nextView), routeReady: routeModuleReady }).catch((err) => {
          console.warn("View load failed", err);
        });
      }
      return;
    }
    routeModuleReady.finally(() => {
      if (state.currentView === nextView) renderActiveView();
    });
  }

  return {
    DATA_ENTITIES,
    VIEW_PREFETCH_TARGET,
    normalizeView,
    getRouteModule,
    ensureRouteModule,
    isAdminView,
    userCanAccessAdminViews,
    canAccessView,
    resolveAccessibleView,
    appRelativePath,
    routePathForView,
    viewHref,
    isResetPathname,
    viewFromLocationPath,
    syncPathForView,
    isRouteChangeSuppressed,
    viewDomIdForRoute,
    navViewForRoute,
    isSpaceGovernanceView,
    entitiesForView,
    isKnownEntity,
    setView,
  };
}
