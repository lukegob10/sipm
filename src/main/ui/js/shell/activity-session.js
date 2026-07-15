const ACTIVITY_STORAGE_KEY = "sipm-auth-activity-v1";
const LOGOUT_STORAGE_KEY = "sipm-auth-logout-v1";
const TRAILING_HEARTBEAT_MS = 1000;

const DEFAULT_POLICY = Object.freeze({
  idle_timeout_seconds: 30 * 60,
  warning_seconds: 60,
  activity_heartbeat_seconds: 15,
});

export function createActivitySessionController({
  windowRef = window,
  documentRef = document,
  storage = window.localStorage,
  now = () => Date.now(),
  onWarning,
  onWarningDismissed,
  onHeartbeat,
  onIdleLogout,
  onRemoteLogout,
}) {
  let policy = { ...DEFAULT_POLICY };
  let active = false;
  let userId = "";
  let lastActivityAt = 0;
  let lastHeartbeatAt = 0;
  let lastBroadcastAt = 0;
  let deadlineTimer = null;
  let trailingHeartbeatTimer = null;
  let logoutStarted = false;
  let listenersBound = false;

  const activityEvents = ["mousemove", "keydown", "click", "scroll", "touchstart"];

  function clearTimer(timer) {
    if (timer !== null) windowRef.clearTimeout(timer);
  }

  function writeStorage(key, at) {
    try {
      storage?.setItem(key, JSON.stringify({ version: 1, user_id: userId, at }));
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
    }
  }

  function hideWarning() {
    onWarningDismissed?.();
  }

  function scheduleEvaluation(delayMs) {
    clearTimer(deadlineTimer);
    deadlineTimer = windowRef.setTimeout(evaluate, Math.max(0, delayMs));
  }

  function evaluate() {
    deadlineTimer = null;
    if (!active || logoutStarted) return;
    const elapsedMs = Math.max(0, now() - lastActivityAt);
    const timeoutMs = policy.idle_timeout_seconds * 1000;
    const warningMs = policy.warning_seconds * 1000;
    const remainingMs = timeoutMs - elapsedMs;
    if (remainingMs <= 0) {
      logoutStarted = true;
      active = false;
      hideWarning();
      void onIdleLogout?.();
      return;
    }
    if (remainingMs <= warningMs) {
      onWarning?.(Math.max(1, Math.ceil(remainingMs / 1000)));
      scheduleEvaluation(Math.min(1000, remainingMs));
      return;
    }
    hideWarning();
    scheduleEvaluation(remainingMs - warningMs);
  }

  async function sendHeartbeat(options = {}) {
    if (!active || logoutStarted) return;
    lastHeartbeatAt = now();
    try {
      await onHeartbeat?.({ keepalive: !!options.keepalive });
    } catch {
      // A transient heartbeat failure must not manufacture user inactivity.
      // Terminal authentication failures are handled by the session controller.
    }
  }

  function scheduleTrailingHeartbeat() {
    clearTimer(trailingHeartbeatTimer);
    trailingHeartbeatTimer = windowRef.setTimeout(() => {
      trailingHeartbeatTimer = null;
      if (lastHeartbeatAt < lastActivityAt) void sendHeartbeat();
    }, TRAILING_HEARTBEAT_MS);
  }

  function applyActivity(at, { broadcast = false, heartbeat = false } = {}) {
    if (!active || logoutStarted || !Number.isFinite(at) || at <= 0) return;
    lastActivityAt = Math.max(lastActivityAt, at);
    hideWarning();
    evaluate();
    if (broadcast && lastActivityAt - lastBroadcastAt >= 1000) {
      lastBroadcastAt = lastActivityAt;
      writeStorage(ACTIVITY_STORAGE_KEY, lastActivityAt);
    }
    if (!heartbeat) return;
    const heartbeatIntervalMs = policy.activity_heartbeat_seconds * 1000;
    if (lastActivityAt - lastHeartbeatAt >= heartbeatIntervalMs) {
      void sendHeartbeat();
    }
    scheduleTrailingHeartbeat();
  }

  function noteUserActivity() {
    applyActivity(now(), { broadcast: true, heartbeat: true });
  }

  function handleStorage(event) {
    if (!active || !event?.newValue) return;
    if (event.key !== ACTIVITY_STORAGE_KEY && event.key !== LOGOUT_STORAGE_KEY) return;
    let message;
    try {
      message = JSON.parse(event.newValue);
    } catch {
      return;
    }
    if (message?.version !== 1 || message.user_id !== userId) return;
    if (event.key === LOGOUT_STORAGE_KEY) {
      active = false;
      logoutStarted = true;
      stopTimers();
      hideWarning();
      onRemoteLogout?.();
      return;
    }
    applyActivity(Number(message.at), { broadcast: false, heartbeat: false });
  }

  function handleVisibilityChange() {
    if (!documentRef.hidden) evaluate();
  }

  function handlePageHide() {
    if (active && trailingHeartbeatTimer !== null && lastHeartbeatAt < lastActivityAt) {
      clearTimer(trailingHeartbeatTimer);
      trailingHeartbeatTimer = null;
      void sendHeartbeat({ keepalive: true });
    }
  }

  function bindListeners() {
    if (listenersBound) return;
    activityEvents.forEach((eventName) => windowRef.addEventListener(eventName, noteUserActivity, { passive: true }));
    windowRef.addEventListener("storage", handleStorage);
    windowRef.addEventListener("pagehide", handlePageHide);
    documentRef.addEventListener("visibilitychange", handleVisibilityChange);
    listenersBound = true;
  }

  function unbindListeners() {
    if (!listenersBound) return;
    activityEvents.forEach((eventName) => windowRef.removeEventListener(eventName, noteUserActivity));
    windowRef.removeEventListener("storage", handleStorage);
    windowRef.removeEventListener("pagehide", handlePageHide);
    documentRef.removeEventListener("visibilitychange", handleVisibilityChange);
    listenersBound = false;
  }

  function stopTimers() {
    clearTimer(deadlineTimer);
    clearTimer(trailingHeartbeatTimer);
    deadlineTimer = null;
    trailingHeartbeatTimer = null;
  }

  function configure(nextPolicy = {}) {
    const normalized = {
      idle_timeout_seconds: Number(nextPolicy.idle_timeout_seconds),
      warning_seconds: Number(nextPolicy.warning_seconds),
      activity_heartbeat_seconds: Number(nextPolicy.activity_heartbeat_seconds),
    };
    if (
      normalized.idle_timeout_seconds > 0
      && normalized.warning_seconds > 0
      && normalized.warning_seconds < normalized.idle_timeout_seconds
      && normalized.activity_heartbeat_seconds > 0
    ) {
      policy = normalized;
      if (active) evaluate();
    }
  }

  function start(nextUserId) {
    const normalizedUserId = String(nextUserId || "").trim();
    if (!normalizedUserId) return;
    if (active && userId === normalizedUserId) return;
    stopTimers();
    userId = normalizedUserId;
    active = true;
    logoutStarted = false;
    lastActivityAt = now();
    lastHeartbeatAt = lastActivityAt;
    lastBroadcastAt = lastActivityAt;
    bindListeners();
    writeStorage(ACTIVITY_STORAGE_KEY, lastActivityAt);
    evaluate();
  }

  function stop() {
    active = false;
    logoutStarted = false;
    stopTimers();
    unbindListeners();
    hideWarning();
    userId = "";
  }

  function broadcastLogout() {
    if (userId) writeStorage(LOGOUT_STORAGE_KEY, now());
  }

  return {
    configure,
    start,
    stop,
    noteUserActivity,
    broadcastLogout,
    evaluate,
  };
}
