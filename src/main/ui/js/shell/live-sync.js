export const LIVE_SYNC_CLOSE_AUTH = 4401;
export const LIVE_SYNC_CLOSE_SPACE = 4403;
export const LIVE_SYNC_CLOSE_LIMIT = 4408;
export const LIVE_SYNC_CLOSE_BUSY = 1013;


export function createLiveSyncController({
  state,
  buildWsUrl,
  isResetPath,
  refreshSessionTokens,
  refreshSpaceContext,
  reloadCurrentViewData,
  refreshFromServer,
  refreshAgentChangeRequests = null,
  handleAuthError,
  handleSessionExpired,
  renderTopbarStatus,
  setSpaceFeedback,
  spaceNameForId,
  clearDataState,
}) {
  const LIVE_SYNC_RETRY_DELAYS_MS = [1000, 2000, 4000, 8000, 15000];
  const LIVE_SYNC_HEARTBEAT_MS = 60000;
  let liveSyncSocket = null;
  let liveSyncRetryTimer = null;
  let liveSyncHeartbeatTimer = null;
  let liveSyncRecoveryPromise = null;
  let liveSyncReconnectAttempt = 0;
  let liveSyncAuthRecoveryUsed = false;
  let liveSyncSpaceRecoveryUsed = false;

  function setLiveSyncPhase(phase, options = {}) {
    state.liveSync.phase = phase;
    if (options.clear) {
      state.liveSync.statusText = "";
      state.liveSync.statusTone = "";
      renderTopbarStatus();
      return;
    }
    const defaultByPhase = {
      live: { text: "Sync live", tone: "positive" },
      reconnecting: { text: "Reconnecting…", tone: "warn" },
      paused: { text: "Sync paused", tone: "muted" },
      attention: { text: "Space attention", tone: "warn" },
    };
    const fallback = defaultByPhase[phase] || { text: "", tone: "" };
    state.liveSync.statusText = options.text !== undefined ? options.text : fallback.text;
    state.liveSync.statusTone = options.tone !== undefined ? options.tone : fallback.tone;
    renderTopbarStatus();
  }

  function clearLiveSyncRetry() {
    if (liveSyncRetryTimer) {
      clearTimeout(liveSyncRetryTimer);
      liveSyncRetryTimer = null;
    }
  }

  function clearLiveSyncHeartbeat() {
    if (liveSyncHeartbeatTimer) {
      window.clearInterval(liveSyncHeartbeatTimer);
      liveSyncHeartbeatTimer = null;
    }
  }

  function startLiveSyncHeartbeat(socket) {
    clearLiveSyncHeartbeat();
    liveSyncHeartbeatTimer = window.setInterval(() => {
      if (socket !== liveSyncSocket || socket.readyState !== WebSocket.OPEN) return;
      try {
        socket.send(JSON.stringify({ type: "ping" }));
      } catch (err) {
        console.warn("Live sync heartbeat failed", err);
      }
    }, LIVE_SYNC_HEARTBEAT_MS);
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
    clearLiveSyncHeartbeat();
    if (!socket) return;
    try {
      if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
        socket.close(closeCode, reason);
      }
    } catch (err) {
      console.warn("Live sync close failed", err);
    }
  }

  async function catchUpLiveSync() {
    const requests = [
      reloadCurrentViewData({ force: true, silent: true, preserveCapacitySelection: false }),
    ];
    if (typeof refreshAgentChangeRequests === "function") {
      requests.push(refreshAgentChangeRequests({ force: true }));
    }
    const results = await Promise.allSettled(requests);
    results.forEach((result) => {
      if (result.status === "rejected") {
        console.warn("Live sync catch-up refresh failed", result.reason);
      }
    });
  }

  function stopLiveSync(options = {}) {
    clearLiveSyncRetry();
    liveSyncRecoveryPromise = null;
    if (!options.preserveRecovery) resetLiveSyncRecoveryFlags();
    closeLiveSyncSocket(options.closeCode || 1000, options.reason || "");
    state.liveSync.pausedForHidden = !!options.pausedForHidden;
    if (options.clearStatus) {
      setLiveSyncPhase("idle", { clear: true });
      return;
    }
    if (options.phase) {
      setLiveSyncPhase(options.phase, { text: options.text, tone: options.tone });
    } else {
      setLiveSyncPhase("idle", { clear: true });
    }
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
          suppressDataInvalidation: true,
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
    const force = !!options.force;
    const preserveRecovery = !!options.preserveRecovery;
    if (!state.authed || isResetPath()) {
      stopLiveSync({ clearStatus: true });
      return;
    }
    if (document.hidden) {
      stopLiveSync({ phase: "paused", pausedForHidden: true, preserveRecovery });
      return;
    }
    if (!state.activeSpace?.space_id) {
      stopLiveSync({ phase: "paused", text: "Sync paused", tone: "muted", preserveRecovery });
      return;
    }
    clearLiveSyncRetry();
    const currentSpaceId = state.activeSpace.space_id;
    const isOpenForCurrentSpace = !!liveSyncSocket
      && state.liveSync.socketSpaceId === currentSpaceId
      && (liveSyncSocket.readyState === WebSocket.CONNECTING || liveSyncSocket.readyState === WebSocket.OPEN);
    if (!force && isOpenForCurrentSpace) return;
    if (!preserveRecovery) resetLiveSyncRecoveryFlags();
    closeLiveSyncSocket(1000, "restart");
    state.liveSync.pausedForHidden = false;
    setLiveSyncPhase("reconnecting");
    const socket = new WebSocket(liveUrl());
    liveSyncSocket = socket;
    state.liveSync.socketSpaceId = currentSpaceId;

    socket.addEventListener("open", () => {
      if (socket !== liveSyncSocket) return;
      resetLiveSyncRecoveryFlags();
      startLiveSyncHeartbeat(socket);
      setLiveSyncPhase("live");
      void catchUpLiveSync();
    });

    socket.addEventListener("message", (event) => {
      if (socket !== liveSyncSocket) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "refresh") {
          const entity = msg.entity || "all";
          if (entity === "agent_change_requests" && typeof refreshAgentChangeRequests === "function") {
            refreshAgentChangeRequests({ force: true }).catch((err) => {
              console.warn("Agent approvals live refresh failed", err);
            });
            return;
          }
          refreshFromServer(entity);
        }
      } catch (err) {
        console.warn("Live message parse failed", err);
      }
    });

    socket.addEventListener("error", () => {
      if (socket !== liveSyncSocket) return;
      setLiveSyncPhase("reconnecting");
    });

    socket.addEventListener("close", (event) => {
      if (socket !== liveSyncSocket) return;
      clearLiveSyncHeartbeat();
      liveSyncSocket = null;
      state.liveSync.socketSpaceId = "";
      void handleLiveSyncClose(event);
    });
  }

  async function handleLiveSyncVisibilityChange() {
    if (document.hidden) {
      if (state.authed) stopLiveSync({ phase: "paused", pausedForHidden: true, preserveRecovery: true });
      return;
    }
    if (!state.authed || !state.liveSync.pausedForHidden) return;
    state.liveSync.pausedForHidden = false;
    try {
      await reloadCurrentViewData({ force: true, silent: true, preserveCapacitySelection: false });
    } catch (err) {
      console.warn("Live sync visibility refresh failed", err);
      if (handleAuthError(err)) return;
    }
    startLiveSync({ force: true, preserveRecovery: true });
  }

  return {
    setLiveSyncPhase,
    stopLiveSync,
    startLiveSync,
    handleLiveSyncVisibilityChange,
  };
}
