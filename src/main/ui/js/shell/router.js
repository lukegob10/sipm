import { APP_ASSET_VERSION, APP_CONTEXT_PATH, buildAppUrl } from "./paths.js";


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
  onModuleLoadFailure = null,
}) {
  const DATA_ENTITIES = ["phases", "projects", "solutions", "subcomponents", "teams", "users", "allocations", "windows"];
  const KNOWN_VIEWS = [
    "master",
    "gantt",
    "subcomponents-workbench",
    "dashboard",
    "pm-dashboard",
    "kanban",
    "calendar",
    "planning",
    "team-capacity",
    "spaces",
    "access",
    "analytics",
  ];
  const ADMIN_VIEWS = new Set(["spaces", "access"]);
  const GLOBAL_ADMIN_VIEWS = new Set(["analytics"]);
  const VIEW_DATA_REQUIREMENTS = {
    master: ["phases", "projects", "solutions"],
    gantt: ["projects", "solutions", "subcomponents"],
    "subcomponents-workbench": ["projects", "solutions", "subcomponents", "users"],
    dashboard: ["projects", "solutions", "users"],
    "pm-dashboard": ["projects", "solutions", "subcomponents", "users", "allocations", "windows"],
    kanban: ["phases", "projects", "solutions"],
    calendar: ["projects", "solutions"],
    planning: ["projects", "solutions", "subcomponents", "teams", "users", "allocations", "windows"],
    "team-capacity": ["users", "allocations"],
    spaces: ["users"],
    access: ["users"],
    analytics: [],
  };
  const VIEW_PREFETCH_TARGET = {
    master: "dashboard",
    gantt: "subcomponents-workbench",
    "subcomponents-workbench": "planning",
    dashboard: "pm-dashboard",
    "pm-dashboard": "kanban",
    kanban: "planning",
    calendar: "planning",
    planning: "team-capacity",
    "team-capacity": "spaces",
    spaces: "access",
    access: "analytics",
    analytics: "planning",
  };
  const ROUTE_MODULE_LOADERS = {
    master: () => import(`../routes/master.js?v=${APP_ASSET_VERSION}`),
    gantt: () => import(`../routes/gantt.js?v=${APP_ASSET_VERSION}`),
    "subcomponents-workbench": () => import(`../routes/subcomponents-workbench.js?v=${APP_ASSET_VERSION}`),
    dashboard: () => import(`../routes/dashboard.js?v=${APP_ASSET_VERSION}`),
    "pm-dashboard": () => import(`../routes/pm-dashboard.js?v=${APP_ASSET_VERSION}`),
    kanban: () => import(`../routes/kanban.js?v=${APP_ASSET_VERSION}`),
    calendar: () => import(`../routes/calendar.js?v=${APP_ASSET_VERSION}`),
    planning: () => import(`../routes/planning.js?v=${APP_ASSET_VERSION}`),
    "team-capacity": () => import(`../routes/team-capacity.js?v=${APP_ASSET_VERSION}`),
    spaces: () => import(`../routes/spaces.js?v=${APP_ASSET_VERSION}`),
    access: () => import(`../routes/access.js?v=${APP_ASSET_VERSION}`),
    analytics: () => import(`../routes/analytics.js?v=${APP_ASSET_VERSION}`),
  };
  const routeModuleCache = {};
  const routeModuleInFlight = {};
  let suppressRouteChange = false;

  function normalizeView(view) {
    const candidate = (view || "").toString().trim().toLowerCase();
    if (candidate === "settings") return "team-capacity";
    return KNOWN_VIEWS.includes(candidate) ? candidate : "master";
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

  function canAccessView(view) {
    const normalized = normalizeView(view);
    if (normalized === "analytics") {
      return state.authed && userIsGlobalAdmin() && usageAnalyticsEnabled();
    }
    if (normalized === "access") return userCanAccessAdminViews();
    if (normalized === "spaces") return userCanAccessAdminViews();
    if (isAdminView(normalized)) return false;
    return true;
  }

  function resolveAccessibleView(view) {
    const normalized = normalizeView(view);
    if (!canAccessView(normalized)) return "master";
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
    const normalized = normalizeView(view);
    return normalized === "access" ? "spaces" : normalized;
  }

  function navViewForRoute(view) {
    const normalized = normalizeView(view);
    return normalized === "access" ? "spaces" : normalized;
  }

  function isSpaceGovernanceView(view) {
    const normalized = normalizeView(view);
    return normalized === "spaces" || normalized === "access";
  }

  function entitiesForView(view) {
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
    if (nextView === "subcomponents-workbench" && previousView !== nextView && state.subcomponentsWorkbench) {
      state.subcomponentsWorkbench.drawerOpen = false;
      state.subcomponentsWorkbench.drawerReturnSubcomponentId = "";
      state.subcomponentsWorkbench.drawerReturnScrollY = null;
      state.subcomponentsWorkbench.suppressAutoScrollOnce = false;
    }
    els.views.forEach((viewEl) => viewEl.classList.toggle("active", viewEl.id === `view-${nextDomView}`));
    els.navButtons.forEach((button) => button.classList.toggle("active", button.dataset.view === nextNavView));
    if (!fromHistory || redirected) {
      syncPathForView(nextView, redirected ? true : replacePath);
    }
    if (viewHasLazyModule(nextView)) {
      ensureRouteModule(nextView).then((loaded) => {
        if (state.currentView !== nextView) return;
        if (loaded) renderActiveView();
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
