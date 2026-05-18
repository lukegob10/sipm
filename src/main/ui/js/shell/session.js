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
  const pendingAuthActions = new Set();

  function authErrorMessage(err, fallback = "Session expired. Please sign in again.") {
    if (!err) return fallback;
    if (err.code === "TOKEN_EXPIRED" || err.code === "AUTH_REQUIRED") {
      return "Your session expired. Sign in again to continue.";
    }
    if (err.code === "PASSWORD_RESET_REQUIRED") {
      return "Password reset required. Use your temporary password to set a new one.";
    }
    if (err.code === "ACCOUNT_LOCKED" || err.status === 423) {
      return "Account locked. Try again later or contact an administrator.";
    }
    if (err.code === "TOKEN_REVOKED") {
      return "Your session was reset after an account change. Please sign in again.";
    }
    return err.message || fallback;
  }

  function loginErrorMessage(err) {
    if (!err) return "Sign-in failed. Try again.";
    if (err.code === "LOGIN_FAILED" || err.code === "USER_INACTIVE") {
      return "The SOEID or password did not match. Try again, or use your temporary password if an admin reset your account.";
    }
    if (isNetworkOrTimeoutFailure(err)) {
      return err.message || "Unable to reach the server. Check your connection and try again.";
    }
    return err.message || "Sign-in failed. Try again.";
  }

  function resetPasswordErrorMessage(err) {
    if (!err) return "Password reset failed. Try again.";
    if (err.code === "TEMP_PASSWORD_INVALID") {
      return "The SOEID or temporary password did not match. Check the reset details from your admin.";
    }
    if (err.code === "TEMP_PASSWORD_EXPIRED") {
      return "The temporary password has expired. Ask an admin to issue a new one.";
    }
    if (err.code === "RESET_PASSWORD_MISMATCH") {
      return "The new passwords do not match.";
    }
    if (err.code === "RESET_PASSWORD_INPUT_INVALID") {
      return "Enter your SOEID and temporary password to continue.";
    }
    if (err.status === 422) {
      return "Use a new password with at least 8 characters.";
    }
    if (isNetworkOrTimeoutFailure(err)) {
      return err.message || "Unable to reach the server. Check your connection and try again.";
    }
    return err.message || "Password reset failed. Try again.";
  }

  function isTerminalAuthFailure(err) {
    if (!err) return false;
    if (err.status === 423 || err.code === "ACCOUNT_LOCKED") return true;
    if (err.code === "PASSWORD_RESET_REQUIRED") return true;
    const terminalCodes = new Set([
      "AUTH_REQUIRED",
      "TOKEN_EXPIRED",
      "TOKEN_INVALID",
      "TOKEN_TYPE_INVALID",
      "TOKEN_SUBJECT_INVALID",
      "TOKEN_REVOKED",
      "USER_INACTIVE_OR_MISSING",
    ]);
    if (err.code) return terminalCodes.has(err.code);
    return err.status === 401;
  }

  function errorFromResponse(res, data, path) {
    const detail = data && data.detail !== undefined ? data.detail : data;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : res.statusText;
    const err = new Error(message || res.statusText);
    err.status = res.status;
    err.path = path;
    err.code = res.headers?.get?.("X-Error-Code") || "";
    return err;
  }

  function networkError(path, err) {
    const message = err?.name === "AbortError"
      ? `Request timed out: ${path}`
      : "Unable to reach the server. Check your connection and try again.";
    const normalized = new Error(message);
    normalized.status = err?.name === "AbortError" ? 408 : 0;
    normalized.path = path;
    normalized.code = "NETWORK_UNAVAILABLE";
    normalized.cause = err;
    return normalized;
  }

  function isNetworkOrTimeoutFailure(err) {
    return err?.code === "NETWORK_UNAVAILABLE" || err?.status === 0 || err?.status === 408;
  }

  async function withPendingAuthAction(key, form, action) {
    if (pendingAuthActions.has(key)) return null;
    pendingAuthActions.add(key);
    const buttons = Array.from(form?.querySelectorAll?.('button[type="submit"]') || []);
    buttons.forEach((button) => {
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
    });
    try {
      return await action();
    } finally {
      pendingAuthActions.delete(key);
      buttons.forEach((button) => {
        button.disabled = false;
        button.removeAttribute("aria-busy");
      });
    }
  }

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

        if (!res.ok) throw errorFromResponse(res, data, "/auth/refresh");

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
        if (!silentFailure && isTerminalAuthFailure(err)) {
          handleSessionExpired({ message: authErrorMessage(err) });
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
        cache: "no-store",
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
        const err = errorFromResponse(res, data, path);
        throw err;
      }
      return data;
    } catch (err) {
      if (err && (err.name === "AbortError" || err.name === "TypeError")) {
        const timeoutErr = networkError(path, err);
        if (typeof onApiFailure === "function") {
          onApiFailure({
            path,
            status: timeoutErr.status,
            kind: timeoutErr.status === 408 ? "timeout" : "network_error",
          });
        }
        throw timeoutErr;
      }
      throw err;
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }
  }

  function handleSessionExpired(options = {}) {
    clearLocalSession();
    setStatus(options.statusText || "Sign in required", "warn");
    showAuthNotice(options.message || "Your session expired due to inactivity. Please sign in again.");
  }

  function clearLocalSession() {
    stopLiveSync();
    sessionRefreshPromise = null;
    lastSessionRefreshAt = 0;
    setAuthed(null);
  }

  function handleAuthError(err) {
    if (isTerminalAuthFailure(err)) {
      handleSessionExpired({ message: authErrorMessage(err) });
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
      if (isTerminalAuthFailure(err)) {
        handleSessionExpired({ message: authErrorMessage(err) });
        return null;
      }
      throw err;
    }
  }

  async function performLogin(soeid, password) {
    return api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ soeid, password }),
    });
  }

  async function performRegister(display_name, soeid, password) {
    return api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ display_name, soeid, password }),
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
      showAuthNotice("");
      const form = new FormData(els.loginForm);
      await withPendingAuthAction("login", els.loginForm, async () => {
        const user = await performLogin(form.get("soeid"), form.get("password"));
        setAuthed(user);
        await refreshSpaceContext();
        startLiveSync();
        restoreRouteFromLocationAfterAuth();
        setAuthVisible(false);
      }).catch((err) => {
        if (!handleAuthError(err)) showAuthError(loginErrorMessage(err));
      });
    });

    els.registerForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAuthError("");
      showAuthNotice("");
      const form = new FormData(els.registerForm);
      await withPendingAuthAction("register", els.registerForm, async () => {
        const user = await performRegister(form.get("display_name"), form.get("soeid"), form.get("password"));
        setAuthed(user);
        await refreshSpaceContext();
        startLiveSync();
        restoreRouteFromLocationAfterAuth();
        setAuthVisible(false);
      }).catch((err) => {
        if (!handleAuthError(err)) showAuthError(err.message || "Registration failed");
      });
    });

    els.resetForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showResetError("");
      showResetSuccess("");
      const form = new FormData(els.resetForm);
      await withPendingAuthAction("reset-password", els.resetForm, async () => {
        await api("/auth/reset-password", {
          method: "POST",
          body: JSON.stringify({
            soeid: form.get("soeid"),
            temp_password: form.get("temp_password"),
            new_password: form.get("new_password"),
            confirm_password: form.get("confirm_password"),
          }),
        });
        showResetSuccess("Password reset complete. Redirecting to sign in...");
        setTimeout(() => {
          window.location.href = buildAppUrl("/");
        }, 1200);
      }).catch((err) => {
        showResetError(resetPasswordErrorMessage(err));
      });
    });

    els.logoutBtn?.addEventListener("click", async () => {
      try {
        await api("/auth/logout", { method: "POST" });
      } catch (err) {
        console.warn("Logout error", err);
      } finally {
        clearLocalSession();
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
        clearLocalSession();
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
    let user = null;
    try {
      user = await fetchCurrentUser();
    } catch (err) {
      if (!isNetworkOrTimeoutFailure(err)) throw err;
      clearLocalSession();
      setAuthVisible(true);
      setStatus("Connection issue", "warn");
      showAuthNotice(err.message || "Unable to reach the server. Check your connection and try again.");
      return;
    }
    if (user) {
      await refreshSpaceContext();
      startLiveSync();
      restoreRouteFromLocationAfterAuth();
      setAuthVisible(false);
      return;
    }
    setAuthVisible(true);
    setStatus("Sign in required", "warn");
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
