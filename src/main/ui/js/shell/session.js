const PORTAL_ACCESS_NOTICE = "Access SIPM through the company portal to start a session.";
const PORTAL_SESSION_EXPIRED_NOTICE = "Your SIPM session expired. Refresh this page from the company portal to continue.";

export function createSessionController({
  state,
  els,
  apiBase,
  accessRefreshIntervalMs,
  isResetPathname,
  viewFromLocationPath,
  setView,
  setAuthed,
  setStatus,
  setAuthVisible,
  showAuthNotice,
  resetIdleTimer,
  hideIdleModal,
  refreshSpaceContext,
  onApiFailure = null,
  startLiveSync,
  stopLiveSync,
}) {
  let sessionRefreshPromise = null;
  let lastSessionRefreshAt = 0;

  function restoreRouteFromLocationAfterAuth() {
    const nextView = viewFromLocationPath(window.location.pathname);
    setView(nextView, { fromHistory: true });
  }

  function onAuthedChange(user) {
    lastSessionRefreshAt = user ? Date.now() : 0;
    if (!user) {
      sessionRefreshPromise = null;
    }
  }

  async function refreshSessionTokens(options = {}) {
    const force = !!options.force;
    const allowLoggedOut = !!options.allowLoggedOut;
    const silentFailure = !!options.silentFailure;
    const suppressLiveSyncRestart = !!options.suppressLiveSyncRestart;

    if (!force && !state.authed && !allowLoggedOut) return null;
    if (!force && Date.now() - lastSessionRefreshAt < accessRefreshIntervalMs) {
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
        const res = await fetch(`${apiBase}/auth/refresh`, {
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
          await refreshSpaceContext({
            apiOptions: { skipAuthRefresh: true },
            suppressLiveSyncRestart,
          });
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
    if (Date.now() - lastSessionRefreshAt < accessRefreshIntervalMs) return;
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
      const res = await fetch(`${apiBase}${path}`, {
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
        if (res.status >= 500 && typeof onApiFailure === "function") {
          onApiFailure({ path, status: res.status, kind: "server_error" });
        }
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
        if (typeof onApiFailure === "function") {
          onApiFailure({ path, status: 408, kind: "timeout" });
        }
        throw timeoutErr;
      }
      throw err;
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }
  }

  function handleSessionExpired() {
    stopLiveSync();
    sessionRefreshPromise = null;
    lastSessionRefreshAt = 0;
    setAuthed(null);
    setStatus("Portal session required", "warn");
    showAuthNotice(PORTAL_SESSION_EXPIRED_NOTICE);
  }

  function handleAuthError(err) {
    if (err && err.status === 401) {
      handleSessionExpired();
      setAuthVisible(true);
      return true;
    }
    return false;
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
        if (refreshed) return state.user;
        setAuthed(null);
        return null;
      }
      throw err;
    }
  }

  function isResetPath() {
    return isResetPathname(window.location.pathname);
  }

  function bindAuthUI() {
    els.logoutBtn?.addEventListener("click", async () => {
      try {
        await api("/auth/logout", { method: "POST" });
      } catch (err) {
        console.warn("Logout error", err);
      } finally {
        setAuthed(null);
        showAuthNotice(PORTAL_ACCESS_NOTICE);
        setAuthVisible(true);
      }
    });

    els.idleStay?.addEventListener("click", async () => {
      try {
        const user = await refreshSessionTokens({ force: true });
        if (!user) throw new Error("Session refresh failed");
        startLiveSync({ force: true });
        resetIdleTimer();
        hideIdleModal();
      } catch {
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
        showAuthNotice(PORTAL_ACCESS_NOTICE);
        setAuthVisible(true);
      }
    });
  }

  async function bootstrapAuth() {
    showAuthNotice(PORTAL_ACCESS_NOTICE);
    setStatus("Checking portal session...", "warn");
    const user = await fetchCurrentUser();
    if (user) {
      await refreshSpaceContext();
      startLiveSync();
      restoreRouteFromLocationAfterAuth();
      setAuthVisible(false);
      return;
    }
    setAuthVisible(true);
    setStatus("Portal sign-in required", "warn");
    showAuthNotice(PORTAL_ACCESS_NOTICE);
  }

  return {
    onAuthedChange,
    refreshSessionTokens,
    maybeRefreshSessionOnActivity,
    api,
    handleAuthError,
    handleSessionExpired,
    fetchCurrentUser,
    isResetPath,
    bindAuthUI,
    bootstrapAuth,
  };
}
