export function createSessionController({
  state,
  els,
  apiBase,
  accessRefreshIntervalMs,
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
    setStatus("Session expired", "warn");
    showAuthNotice("Your session expired due to inactivity. Please sign in again.");
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
    return isResetPathname(window.location.pathname);
  }

  function bindAuthUI() {
    setAuthMode("login");
    els.authTabLogin?.addEventListener("click", () => setAuthMode("login"));
    els.authTabRegister?.addEventListener("click", () => setAuthMode("register"));
    els.resetLink?.addEventListener("click", () => {
      window.location.href = buildAppUrl("/reset-password");
    });

    els.loginForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAuthError("");
      const form = new FormData(els.loginForm);
      try {
        const user = await performLogin(form.get("soeid"), form.get("password"));
        setAuthed(user);
        await refreshSpaceContext();
        startLiveSync();
        restoreRouteFromLocationAfterAuth();
        setAuthVisible(false);
      } catch (err) {
        if (!handleAuthError(err)) showAuthError(err.message || "Login failed");
      }
    });

    els.registerForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAuthError("");
      const form = new FormData(els.registerForm);
      try {
        const user = await performRegister(form.get("display_name"), form.get("soeid"), form.get("password"));
        setAuthed(user);
        await refreshSpaceContext();
        startLiveSync();
        restoreRouteFromLocationAfterAuth();
        setAuthVisible(false);
      } catch (err) {
        if (!handleAuthError(err)) showAuthError(err.message || "Registration failed");
      }
    });

    els.resetForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showResetError("");
      showResetSuccess("");
      const form = new FormData(els.resetForm);
      try {
        await api("/auth/reset-password", {
          method: "POST",
          body: JSON.stringify({
            soeid: form.get("soeid"),
            temp_password: form.get("temp_password"),
            new_password: form.get("new_password"),
            confirm_password: form.get("confirm_password"),
          }),
        });
        showResetSuccess("Password reset complete. Redirecting to login...");
        setTimeout(() => {
          window.location.href = buildAppUrl("/");
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
        setAuthVisible(true);
      }
    });
  }

  async function bootstrapAuth() {
    if (isResetPath()) {
      showResetError("");
      showResetSuccess("");
      setResetVisible(true);
      setStatus("Password reset", "warn");
      return;
    }
    setStatus("Checking session...", "warn");
    const user = await fetchCurrentUser();
    if (user) {
      await refreshSpaceContext();
      startLiveSync();
      restoreRouteFromLocationAfterAuth();
      setAuthVisible(false);
    } else {
      setAuthVisible(true);
      setStatus("Sign in required", "warn");
    }
  }

  return {
    onAuthedChange,
    refreshSessionTokens,
    maybeRefreshSessionOnActivity,
    api,
    handleAuthError,
    handleSessionExpired,
    fetchCurrentUser,
    performLogin,
    performRegister,
    isResetPath,
    bindAuthUI,
    bootstrapAuth,
  };
}
