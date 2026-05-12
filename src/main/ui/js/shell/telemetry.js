const DEFAULT_SESSION_STORAGE_KEY = "sipm-usage-analytics-session-id";
const DEFAULT_FLUSH_INTERVAL_MS = 10_000;

function createFallbackSessionId() {
  return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function getTabSessionId(storageKey = DEFAULT_SESSION_STORAGE_KEY) {
  try {
    const existing = window.sessionStorage.getItem(storageKey);
    if (existing) return existing;
    const created = (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
      ? crypto.randomUUID()
      : createFallbackSessionId();
    window.sessionStorage.setItem(storageKey, created);
    return created;
  } catch {
    return createFallbackSessionId();
  }
}

function toIsoTimestamp(value = Date.now()) {
  try {
    return new Date(value).toISOString();
  } catch {
    return new Date().toISOString();
  }
}

function finiteNumberOrNull(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function safeDurationMs(value) {
  const numeric = finiteNumberOrNull(value);
  if (numeric == null) return null;
  return Math.max(0, Math.round(numeric));
}

function currentViewFromPath() {
  try {
    const relative = String(window.location.pathname || "/")
      .replace(/\/+$/, "")
      .split("/")
      .filter(Boolean)
      .pop();
    return relative || "master";
  } catch {
    return "master";
  }
}

function normalizePathGroup(path) {
  const raw = String(path || "").trim();
  if (!raw) return "unknown";
  const trimmed = raw.replace(/\?.*$/, "").replace(/^https?:\/\/[^/]+/i, "");
  const segments = trimmed.split("/").filter(Boolean);
  if (!segments.length) return "/";
  if (segments.length === 1) return `/${segments[0]}`;
  return `/${segments.slice(0, 2).join("/")}${segments.length > 2 ? "/*" : ""}`;
}

function shouldDropFailedBatch(status) {
  const numericStatus = Number(status);
  if (!Number.isFinite(numericStatus)) return false;
  if (numericStatus === 401 || numericStatus === 403 || numericStatus === 408 || numericStatus === 429) return false;
  return numericStatus >= 400 && numericStatus < 500;
}

export function createTelemetryController({
  state,
  apiBase,
  isEnabled = () => false,
  flushIntervalMs = DEFAULT_FLUSH_INTERVAL_MS,
  fetchImpl = (...args) => fetch(...args),
  navigatorRef = typeof navigator === "undefined" ? null : navigator,
  documentRef = typeof document === "undefined" ? null : document,
  performanceRef = typeof performance === "undefined" ? null : performance,
  now = () => Date.now(),
}) {
  const sessionId = getTabSessionId();
  const queue = {
    events: [],
    performanceSamples: [],
  };
  const navigationMetrics = {
    firstPaintMs: null,
    firstContentfulPaintMs: null,
    largestContentfulPaintMs: null,
    clsScore: null,
    longTaskCount: 0,
    longTaskTotalMs: 0,
  };
  let bootTracked = false;
  let navigationSampleQueued = false;
  let performanceObserversStarted = false;
  let flushTimerId = null;
  let pendingTransition = null;
  let lifecycleFlushesBound = false;

  function enabled() {
    try {
      return !!isEnabled();
    } catch {
      return false;
    }
  }

  function currentView() {
    return String(state?.currentView || currentViewFromPath() || "master");
  }

  function enqueueEvent(payload) {
    if (!enabled()) return;
    queue.events.push({
      occurred_at: payload.occurred_at || toIsoTimestamp(now()),
      session_id: sessionId,
      view_key: payload.view_key || currentView(),
      category: payload.category,
      feature_key: payload.feature_key,
      action_key: payload.action_key,
      outcome: payload.outcome || "success",
      duration_ms: safeDurationMs(payload.duration_ms),
      status_code: payload.status_code ?? null,
      details: payload.details || {},
    });
  }

  function enqueuePerformanceSample(payload) {
    if (!enabled()) return;
    queue.performanceSamples.push({
      occurred_at: payload.occurred_at || toIsoTimestamp(now()),
      session_id: sessionId,
      view_key: payload.view_key || currentView(),
      sample_kind: payload.sample_kind,
      navigation_type: payload.navigation_type || null,
      data_load_ms: safeDurationMs(payload.data_load_ms),
      render_ms: safeDurationMs(payload.render_ms),
      ttfb_ms: safeDurationMs(payload.ttfb_ms),
      dom_interactive_ms: safeDurationMs(payload.dom_interactive_ms),
      dom_content_loaded_ms: safeDurationMs(payload.dom_content_loaded_ms),
      load_event_ms: safeDurationMs(payload.load_event_ms),
      first_paint_ms: safeDurationMs(payload.first_paint_ms),
      first_contentful_paint_ms: safeDurationMs(payload.first_contentful_paint_ms),
      largest_contentful_paint_ms: safeDurationMs(payload.largest_contentful_paint_ms),
      cls_score: payload.cls_score == null ? null : Number(payload.cls_score),
      long_task_count: payload.long_task_count == null ? null : Math.max(0, Math.round(Number(payload.long_task_count))),
      long_task_total_ms: safeDurationMs(payload.long_task_total_ms),
    });
  }

  async function flush(options = {}) {
    if (!enabled()) return false;
    if (!queue.events.length && !queue.performanceSamples.length) return false;

    const payload = {
      events: queue.events.slice(),
      performance_samples: queue.performanceSamples.slice(),
    };
    const body = JSON.stringify(payload);
    const headers = { "Content-Type": "application/json" };
    if (state?.activeSpace?.space_id) {
      headers["X-Space-Id"] = state.activeSpace.space_id;
    }

    try {
      if (options.useBeacon && navigatorRef && typeof navigatorRef.sendBeacon === "function") {
        const blob = new Blob([body], { type: "application/json" });
        const sent = navigatorRef.sendBeacon(`${apiBase}/analytics/ingest`, blob);
        if (sent) {
          queue.events.splice(0, payload.events.length);
          queue.performanceSamples.splice(0, payload.performance_samples.length);
          return true;
        }
      }
      const response = await fetchImpl(`${apiBase}/analytics/ingest`, {
        method: "POST",
        credentials: "include",
        keepalive: !!options.useBeacon,
        headers,
        body,
      });
      if (!response?.ok) {
        if (shouldDropFailedBatch(response?.status)) {
          queue.events.splice(0, payload.events.length);
          queue.performanceSamples.splice(0, payload.performance_samples.length);
        }
        return false;
      }
      queue.events.splice(0, payload.events.length);
      queue.performanceSamples.splice(0, payload.performance_samples.length);
      return true;
    } catch {
      return false;
    }
  }

  function ensureFlushTimer() {
    if (flushTimerId || !enabled()) return;
    flushTimerId = window.setInterval(() => {
      void flush();
    }, Math.max(1000, Number(flushIntervalMs) || DEFAULT_FLUSH_INTERVAL_MS));
  }

  function collectNavigationTimingMetrics() {
    const entry = performanceRef?.getEntriesByType?.("navigation")?.[0];
    if (!entry) return;
    navigationMetrics.navigationType = entry.type || "navigate";
    navigationMetrics.ttfbMs = safeDurationMs(entry.responseStart);
    navigationMetrics.domInteractiveMs = safeDurationMs(entry.domInteractive);
    navigationMetrics.domContentLoadedMs = safeDurationMs(entry.domContentLoadedEventEnd);
    navigationMetrics.loadEventMs = safeDurationMs(entry.loadEventEnd);
  }

  function maybeQueueNavigationSample() {
    if (navigationSampleQueued || !enabled()) return;
    collectNavigationTimingMetrics();
    enqueuePerformanceSample({
      view_key: currentView(),
      sample_kind: "navigation",
      navigation_type: navigationMetrics.navigationType || "navigate",
      ttfb_ms: navigationMetrics.ttfbMs,
      dom_interactive_ms: navigationMetrics.domInteractiveMs,
      dom_content_loaded_ms: navigationMetrics.domContentLoadedMs,
      load_event_ms: navigationMetrics.loadEventMs,
      first_paint_ms: navigationMetrics.firstPaintMs,
      first_contentful_paint_ms: navigationMetrics.firstContentfulPaintMs,
      largest_contentful_paint_ms: navigationMetrics.largestContentfulPaintMs,
      cls_score: navigationMetrics.clsScore,
      long_task_count: navigationMetrics.longTaskCount,
      long_task_total_ms: navigationMetrics.longTaskTotalMs,
    });
    navigationSampleQueued = true;
  }

  function maybeCompletePendingTransition() {
    if (!pendingTransition) return;
    if (pendingTransition.dataLoadMs == null || pendingTransition.renderMs == null) return;
    const totalDuration = pendingTransition.dataLoadMs + pendingTransition.renderMs;
    enqueueEvent({
      view_key: pendingTransition.viewKey,
      category: "navigation",
      feature_key: "navigation",
      action_key: "route_transition_complete",
      outcome: "success",
      duration_ms: totalDuration,
      details: {
        previous_view: pendingTransition.previousView || undefined,
      },
    });
    enqueuePerformanceSample({
      view_key: pendingTransition.viewKey,
      sample_kind: "route_transition",
      data_load_ms: pendingTransition.dataLoadMs,
      render_ms: pendingTransition.renderMs,
    });
    pendingTransition = null;
  }

  function startPerformanceObservers() {
    if (performanceObserversStarted || typeof PerformanceObserver !== "function") return;
    performanceObserversStarted = true;
    try {
      const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (entry.entryType === "paint") {
            if (entry.name === "first-paint") {
              navigationMetrics.firstPaintMs = safeDurationMs(entry.startTime);
            }
            if (entry.name === "first-contentful-paint") {
              navigationMetrics.firstContentfulPaintMs = safeDurationMs(entry.startTime);
            }
          }
          if (entry.entryType === "largest-contentful-paint") {
            navigationMetrics.largestContentfulPaintMs = safeDurationMs(entry.startTime);
          }
          if (entry.entryType === "layout-shift" && !entry.hadRecentInput) {
            const nextScore = Number(navigationMetrics.clsScore || 0) + Number(entry.value || 0);
            navigationMetrics.clsScore = Math.round(nextScore * 10_000) / 10_000;
          }
          if (entry.entryType === "longtask") {
            navigationMetrics.longTaskCount += 1;
            navigationMetrics.longTaskTotalMs += safeDurationMs(entry.duration) || 0;
          }
        });
      });
      observer.observe({
        entryTypes: ["paint", "largest-contentful-paint", "layout-shift", "longtask"],
        buffered: true,
      });
    } catch {
      // Best-effort only.
    }
  }

  function bindLifecycleFlushes() {
    if (lifecycleFlushesBound || !documentRef) return;
    lifecycleFlushesBound = true;
    window.addEventListener("pagehide", () => {
      void flush({ useBeacon: true });
    });
    documentRef.addEventListener("visibilitychange", () => {
      if (documentRef.visibilityState === "hidden") {
        void flush({ useBeacon: true });
      }
    });
  }

  function syncRuntimeContext() {
    startPerformanceObservers();
    bindLifecycleFlushes();
    if (!enabled()) return;
    ensureFlushTimer();
    if (!bootTracked) {
      enqueueEvent({
        category: "lifecycle",
        feature_key: "app",
        action_key: "app_boot",
        outcome: "success",
      });
      bootTracked = true;
    }
    maybeQueueNavigationSample();
  }

  function beginRouteTransition(viewKey, previousView = "", options = {}) {
    if (!enabled()) return;
    pendingTransition = {
      viewKey: String(viewKey || currentView() || "master"),
      previousView: String(previousView || ""),
      dataLoadMs: options.expectsData ? null : 0,
      renderMs: null,
    };
  }

  function trackRouteView(viewKey, previousView = "") {
    enqueueEvent({
      view_key: viewKey,
      category: "navigation",
      feature_key: "navigation",
      action_key: "route_view",
      outcome: "success",
      details: {
        previous_view: previousView || undefined,
      },
    });
  }

  function noteRouteDataLoaded(viewKey, durationMs = 0) {
    if (!pendingTransition || pendingTransition.viewKey !== String(viewKey || currentView())) return;
    pendingTransition.dataLoadMs = safeDurationMs(durationMs) || 0;
    maybeCompletePendingTransition();
  }

  function noteViewRendered(viewKey, renderMs = 0) {
    if (!pendingTransition || pendingTransition.viewKey !== String(viewKey || currentView())) return;
    pendingTransition.renderMs = safeDurationMs(renderMs) || 0;
    maybeCompletePendingTransition();
  }

  function trackSpaceSwitch() {
    enqueueEvent({
      category: "navigation",
      feature_key: "navigation",
      action_key: "space_switch",
      outcome: "success",
      details: {
        source: "space_switcher",
      },
    });
  }

  function trackModuleLoadFailure(viewKey) {
    enqueueEvent({
      view_key: viewKey,
      category: "operations",
      feature_key: "app",
      action_key: "module_load_failure",
      outcome: "failure",
      details: {
        error_kind: "lazy_route",
        target_view: viewKey,
      },
    });
  }

  function trackApiFailure({ path = "", status = null, kind = "", viewKey = "" } = {}) {
    const numericStatus = Number(status);
    const timeout = String(kind || "").toLowerCase() === "timeout" || numericStatus === 408;
    const serverError = Number.isFinite(numericStatus) && numericStatus >= 500;
    if (!timeout && !serverError) return;
    if (String(path || "").includes("/analytics/ingest")) return;
    enqueueEvent({
      view_key: viewKey || currentView(),
      category: "operations",
      feature_key: "app",
      action_key: "api_failure",
      outcome: timeout ? "timeout" : "server_error",
      status_code: timeout ? 408 : numericStatus,
      details: {
        error_kind: timeout ? "timeout" : "server_error",
        path_group: normalizePathGroup(path),
        status_family: Number.isFinite(numericStatus) ? `${Math.floor(numericStatus / 100)}xx` : undefined,
      },
    });
  }

  function trackWorkflow(featureKey, actionKey, outcome = "success", details = {}, extras = {}) {
    enqueueEvent({
      view_key: extras.viewKey || currentView(),
      category: "workflow",
      feature_key: featureKey,
      action_key: actionKey,
      outcome,
      duration_ms: extras.durationMs,
      status_code: extras.statusCode,
      details,
    });
  }

  return {
    syncRuntimeContext,
    beginRouteTransition,
    trackRouteView,
    noteRouteDataLoaded,
    noteViewRendered,
    trackSpaceSwitch,
    trackModuleLoadFailure,
    trackApiFailure,
    trackWorkflow,
    flush,
  };
}
