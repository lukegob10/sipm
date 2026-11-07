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
  configureSessionPolicy,
  noteSessionActivity,
  broadcastSessionLogout,
  refreshSpaceContext,
  loadUserPreferences = async () => null,
  applyAuthBootstrap = () => false,
  resolvePostAuthView = (view) => view,
  preloadLoginRoute = () => null,
  onApiFailure = null,
  startLiveSync,
  stopLiveSync,
}) {
  let sessionRefreshPromise = null;
  let isPendingRefreshCurrent = () => false;
  let lastSessionRefreshAt = 0;
  let authBootstrapGeneration = 0;
  let sessionGeneration = 0;
  let sessionContextRefreshGeneration = 0;
  let terminalRefreshCounter = 0;
  let sessionBinding = "";
  const authResponseBindings = new WeakMap();
  const pendingAuthActions = new Set();

  function currentUserId() {
    return String(state.user?.user_id || state.user?.soeid || state.user?.email || "");
  }

  function getSessionBinding() {
    return sessionBinding;
  }

  function handleSessionBindingChanged(expectedBinding) {
    if (!expectedBinding || !state.authed || sessionBinding !== expectedBinding) return false;
    clearLocalSession();
    setAuthVisible(true);
    setStatus("Sign in required", "warn");
    showAuthNotice("Your session changed in another tab. Sign in again to continue.");
    return true;
  }

  function handleSessionBindingMismatch(response, expectedBinding) {
    if (response?.status !== 409 || response.headers?.get?.("X-Error-Code") !== "SESSION_CONTEXT_CHANGED") return false;
    handleSessionBindingChanged(expectedBinding);
    return true;
  }

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
    if (err.code === "SESSION_IDLE_EXPIRED") {
      return "You were signed out after 30 minutes of inactivity.";
    }
    if (err.code === "SESSION_REQUIRED" || err.code === "SESSION_REVOKED") {
      return "Your session is no longer active. Sign in again to continue.";
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
      "SESSION_REQUIRED",
      "SESSION_REVOKED",
      "SESSION_IDLE_EXPIRED",
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
    const forms = Array.isArray(form) ? form : [form];
    const buttons = forms.flatMap((item) => Array.from(item?.querySelectorAll?.('button[type="submit"]') || []));
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
    const resolvedView = resolvePostAuthView(nextView, window.location.pathname);
    const preferenceRedirect = resolvedView !== nextView;
    if (preferenceRedirect) {
      return setView(resolvedView, { fromHistory: false, replacePath: true });
    }
    return setView(nextView, { fromHistory: true });
  }

  function onAuthedChange(user) {
    lastSessionRefreshAt = user ? Date.now() : 0;
    if (!user) {
      sessionGeneration += 1;
      sessionRefreshPromise = null;
    }
  }

  function invalidatePendingRefreshContext() {
    sessionContextRefreshGeneration += 1;
  }

  async function refreshSessionTokens(options = {}) {
    const force = !!options.force;
    const allowLoggedOut = !!options.allowLoggedOut;
    const silentFailure = !!options.silentFailure;
    const suppressLiveSyncRestart = !!options.suppressLiveSyncRestart;
    const refreshContext = options.refreshContext !== false;
    const throwOnFailure = !!options.throwOnFailure;
    const waitForRefresh = (promise) => promise.catch((err) => {
      if (throwOnFailure) throw err;
      return null;
    });

    if (!force && !state.authed && !allowLoggedOut) return null;
    if (!force && Date.now() - lastSessionRefreshAt < accessRefreshIntervalMs) {
      return state.user || {};
    }
    if (sessionRefreshPromise && isPendingRefreshCurrent()) {
      return waitForRefresh(sessionRefreshPromise);
    }

    const generation = sessionGeneration;
    const contextGeneration = sessionContextRefreshGeneration;
    const spaceId = state.activeSpace?.space_id;
    const userId = currentUserId();
    const isCurrent = () => generation === sessionGeneration
      && contextGeneration === sessionContextRefreshGeneration
      && spaceId === state.activeSpace?.space_id && userId === currentUserId();
    const headers = {};
    if (state.activeSpace?.space_id) {
      headers["X-Space-Id"] = state.activeSpace.space_id;
    }

    const refreshPromise = (async () => {
      try {
        const data = await api("/auth/refresh", {
          method: "POST",
          headers,
          skipAuthRefresh: true,
        });

        if (!isCurrent()) return null;
        const refreshedBinding = data && typeof data === "object" ? authResponseBindings.get(data) : "";
        if (state.authed && sessionBinding && refreshedBinding && refreshedBinding !== sessionBinding) {
          clearLocalSession();
          setAuthVisible(true);
          setStatus("Sign in required", "warn");
          showAuthNotice("Your session changed in another tab. Sign in again to continue.");
          return null;
        }
        if (refreshedBinding) sessionBinding = refreshedBinding;
        let refreshedUserId = userId;
        if (data && typeof data === "object") {
          refreshedUserId = String(data.user_id || data.soeid || data.email || userId);
          if (state.authed && userId && refreshedUserId !== userId) {
            // Cookies may have changed in another tab. Clear this tab without
            // broadcasting a logout or revoking the replacement session.
            clearLocalSession();
            setAuthVisible(true);
            setStatus("Sign in required", "warn");
            showAuthNotice("Your session changed in another tab. Sign in again to continue.");
            return null;
          }
          setAuthed(data);
        }
        lastSessionRefreshAt = Date.now();

        if (refreshContext) {
          try {
            await refreshSpaceContext({
              apiOptions: { skipAuthRefresh: true },
              suppressLiveSyncRestart,
              isCurrent: () => contextGeneration === sessionContextRefreshGeneration
                && generation === sessionGeneration
                && state.authed
                && refreshedUserId === currentUserId(),
            });
          } catch (err) {
            if (generation === sessionGeneration && refreshedUserId === currentUserId()) {
              console.warn("Space context refresh after token refresh failed", err);
            }
          }
        }

        // Space reconciliation may select an authoritative server fallback, so only
        // auth lifetime and user identity decide whether the refreshed token is usable.
        if (
          generation !== sessionGeneration
          || !state.authed
          || refreshedUserId !== currentUserId()
        ) return null;
        return data || {};
      } catch (err) {
        if (!isCurrent()) return null;
        if (!silentFailure && isTerminalAuthFailure(err)) {
          terminalRefreshCounter += 1;
          handleSessionExpired({ message: authErrorMessage(err) });
        } else if (!silentFailure) {
          console.warn("Session refresh failed", err);
        }
        if (!isTerminalAuthFailure(err)) throw err;
        return null;
      } finally {
        if (sessionRefreshPromise === refreshPromise) sessionRefreshPromise = null;
      }
    })();

    sessionRefreshPromise = refreshPromise;
    isPendingRefreshCurrent = isCurrent;
    return waitForRefresh(refreshPromise);
  }

  function maybeRefreshSessionOnActivity() {
    if (!state.authed) return;
    if (sessionRefreshPromise) return;
    if (Date.now() - lastSessionRefreshAt < accessRefreshIntervalMs) return;
    refreshSessionTokens({ force: false }).catch(() => {});
  }

  const authCookiePaths = new Set([
    "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout",
    "/auth/reset-password", "/auth/bootstrap", "/auth/active-space",
  ]);

  async function withAuthCookieLock(path, signal, operation) {
    const locks = globalThis.navigator?.locks;
    if (!authCookiePaths.has(path) || typeof locks?.request !== "function") return operation();
    const options = signal ? { mode: "exclusive", signal } : { mode: "exclusive" };
    return locks.request("sipm-auth-cookies-v1", options, operation);
  }

  async function api(path, options = {}) {
    const {
      timeoutMs: timeoutOption,
      skipAuthRefresh = false,
      _retriedAfterRefresh = false,
      ...requestOptions
    } = options;
    const requestContext = {
      authenticated: !!state.authed,
      generation: sessionGeneration,
      spaceGeneration: sessionContextRefreshGeneration,
      userId: currentUserId(),
      spaceId: String(state.activeSpace?.space_id || ""),
    };
    const isRequestContextCurrent = () => !requestContext.authenticated || (
      state.authed && sessionGeneration === requestContext.generation
      && sessionContextRefreshGeneration === requestContext.spaceGeneration
      && currentUserId() === requestContext.userId
      && String(state.activeSpace?.space_id || "") === requestContext.spaceId
    );
    const contextChangedError = () => Object.assign(new Error("Request context changed."), { code: "REQUEST_CONTEXT_CHANGED" });
    const headers = { ...(requestOptions.headers || {}) };
    if (requestContext.authenticated && sessionBinding && !headers["X-SIPM-Session"]) {
      headers["X-SIPM-Session"] = sessionBinding;
    }
    const requestBinding = headers["X-SIPM-Session"] || "";
    if (state.authed && state.activeSpace?.space_id && !headers["X-Space-Id"]) {
      headers["X-Space-Id"] = state.activeSpace.space_id;
    }
    const isFormData = requestOptions.body instanceof FormData;
    if (!isFormData && requestOptions.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const timeoutMs = Number.isFinite(timeoutOption) ? timeoutOption : 15000;
    const callerSignal = requestOptions.signal;
    let terminalRefreshFailure = false;
    let controller = null;
    let timeoutId = null;
    let callerAbortListener = null;
    let timedOut = false;
    if (callerSignal || timeoutMs > 0) {
      controller = new AbortController();
      if (callerSignal) {
        callerAbortListener = () => controller.abort(callerSignal.reason);
        if (callerSignal.aborted) {
          callerAbortListener();
        } else {
          callerSignal.addEventListener("abort", callerAbortListener, { once: true });
        }
      }
      if (timeoutMs > 0) {
        timeoutId = setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeoutMs);
      }
    }
    try {
      let retriedAfterRefresh = _retriedAfterRefresh;
      while (true) {
        const { res, text } = await withAuthCookieLock(path, controller?.signal, async () => {
          if (sessionGeneration !== requestContext.generation || !isRequestContextCurrent()) throw contextChangedError();
          if (controller?.signal.aborted) throw new DOMException("Request cancelled.", "AbortError");
          const response = await fetch(`${apiBase}${path}`, {
            credentials: "include",
            ...requestOptions,
            headers,
            signal: controller?.signal,
          });
          return { res: response, text: await response.text() };
        });
        if (!isRequestContextCurrent()) throw contextChangedError();
        let data = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch {
          data = text || null;
        }
        if (!res.ok) {
          if (handleSessionBindingMismatch(res, requestBinding)) throw errorFromResponse(res, data, path);
          if (res.status >= 500 && typeof onApiFailure === "function") {
            onApiFailure({ path, status: res.status, kind: "server_error" });
          }
          if (res.status === 401 && requestContext.authenticated && !retriedAfterRefresh && !skipAuthRefresh) {
            const terminalCounter = terminalRefreshCounter;
            const refreshPromise = refreshSessionTokens({ force: true, throwOnFailure: true });
            const signal = controller?.signal;
            let abortListener;
            let refreshed;
            try {
              refreshed = signal ? await Promise.race([
                refreshPromise,
                new Promise((_, reject) => {
                  abortListener = () => reject(new DOMException("Request cancelled.", "AbortError"));
                  if (signal.aborted) abortListener();
                  else signal.addEventListener("abort", abortListener, { once: true });
                }),
              ]) : await refreshPromise;
            } finally {
              if (abortListener) signal.removeEventListener("abort", abortListener);
            }
            if (!isRequestContextCurrent()) {
              if (!refreshed && !state.authed && !state.user && terminalRefreshCounter !== terminalCounter) {
                terminalRefreshFailure = true;
                throw errorFromResponse(res, data, path);
              }
              throw contextChangedError();
            }
            if (signal?.aborted) throw new DOMException("Request cancelled.", "AbortError");
            if (refreshed) {
              retriedAfterRefresh = true;
              continue;
            }
          }
          throw errorFromResponse(res, data, path);
        }
        if (data && typeof data === "object" && ["/auth/login", "/auth/register", "/auth/bootstrap", "/auth/refresh"].includes(path)) {
          const binding = res.headers?.get?.("X-SIPM-Session");
          if (binding) authResponseBindings.set(data, binding);
        }
        return data;
      }
    } catch (err) {
      if (!isRequestContextCurrent() && !terminalRefreshFailure) throw contextChangedError();
      if (err?.name === "AbortError" && callerSignal?.aborted && !timedOut) throw err;
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
      if (callerSignal && callerAbortListener) {
        callerSignal.removeEventListener("abort", callerAbortListener);
      }
    }
  }

  function handleSessionExpired(options = {}) {
    broadcastSessionLogout?.();
    clearLocalSession();
    setStatus(options.statusText || "Sign in required", "warn");
    showAuthNotice(options.message || "Your session expired due to inactivity. Please sign in again.");
  }

  function clearLocalSession() {
    sessionGeneration += 1;
    authBootstrapGeneration += 1;
    sessionBinding = "";
    stopLiveSync();
    sessionRefreshPromise = null;
    lastSessionRefreshAt = 0;
    setAuthed(null);
  }

  async function recordSessionActivity(options = {}) {
    try {
      return await api("/auth/activity", {
        method: "POST",
        keepalive: !!options.keepalive,
      });
    } catch (err) {
      if (isTerminalAuthFailure(err)) handleSessionExpired({ message: authErrorMessage(err) });
      throw err;
    }
  }

  async function logoutLocally({ idle = false, remote = false } = {}) {
    if (!remote && !state.authed) return;
    if (!remote) broadcastSessionLogout?.();
    const binding = sessionBinding;
    clearLocalSession();
    setAuthVisible(true);
    setStatus("Sign in required", "warn");
    if (idle) {
      showAuthNotice("You were signed out after 30 minutes of inactivity.");
    } else if (remote) {
      showAuthNotice("You were signed out in another tab.");
    }
    if (remote) return;
    try {
      await api("/auth/logout", {
        method: "POST", skipAuthRefresh: true, headers: binding ? { "X-SIPM-Session": binding } : {},
      });
    } catch (err) {
      console.warn("Logout error", err);
    }
  }

  function handleAuthError(err) {
    if (isTerminalAuthFailure(err)) {
      handleSessionExpired({ message: authErrorMessage(err) });
      setAuthVisible(true);
      return true;
    }
    return false;
  }

  async function fetchCurrentUser({ includeContext = false, retried = false, isCurrent = () => true } = {}) {
    try {
      const me = await api(includeContext ? "/auth/bootstrap" : "/auth/me", { skipAuthRefresh: true });
      if (!isCurrent()) return null;
      if (me && typeof me === "object") sessionBinding = authResponseBindings.get(me) || sessionBinding;
      setAuthed(userFromAuthResponse(me));
      return me;
    } catch (err) {
      if (!isCurrent()) return null;
      if (err.status === 401 && !retried) {
        const refreshed = await refreshSessionTokens({
          force: true,
          allowLoggedOut: true,
          silentFailure: true,
          refreshContext: false,
          throwOnFailure: true,
        });
        if (!isCurrent()) return null;
        if (refreshed) {
          return includeContext ? fetchCurrentUser({ includeContext: true, retried: true, isCurrent }) : state.user;
        }
        setAuthed(null);
        return null;
      }
      if (isTerminalAuthFailure(err)) {
        handleSessionExpired({ message: authErrorMessage(err) });
        if (includeContext) setAuthVisible(true);
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

  function userFromAuthResponse(payload) {
    if (!payload || typeof payload !== "object") return payload;
    const user = { ...payload };
    delete user.preferences;
    delete user.spaces;
    delete user.active_space;
    return user;
  }

  async function finishAuthentication(payload) {
    sessionGeneration += 1;
    authBootstrapGeneration += 1;
    sessionBinding = authResponseBindings.get(payload) || "";
    setAuthed(userFromAuthResponse(payload));
    const generation = sessionGeneration;
    const userId = currentUserId();
    const isCurrent = () => generation === sessionGeneration && state.authed && userId === currentUserId();
    try {
      if (!applyAuthBootstrap(payload)) {
        await Promise.all([loadUserPreferences({ isCurrent }), refreshSpaceContext({ isCurrent })]);
      }
      if (!isCurrent()) return;
      const initialLoad = restoreRouteFromLocationAfterAuth();
      startLiveSync({ catchUpAfter: initialLoad });
      setAuthVisible(false);
    } catch (err) {
      if (!isCurrent()) return;
      clearLocalSession();
      setAuthVisible(true);
      throw err;
    }
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
    els.resetBackLink?.addEventListener("click", (event) => {
      event.preventDefault();
      window.location.href = buildAppUrl("/");
    });

    els.loginForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAuthError("");
      showAuthNotice("");
      const form = new FormData(els.loginForm);
      await withPendingAuthAction("authenticate", [els.loginForm, els.registerForm], async () => {
        const generation = sessionGeneration;
        const login = performLogin(form.get("soeid"), form.get("password"));
        // Warm code while credentials are checked; authenticated routing remains authoritative.
        void Promise.resolve()
          .then(() => preloadLoginRoute(viewFromLocationPath(window.location.pathname)))
          .catch(() => {});
        let result;
        try {
          result = await login;
        } catch (err) {
          if (generation !== sessionGeneration) return;
          throw err;
        }
        if (generation !== sessionGeneration) return;
        await finishAuthentication(result);
      }).catch((err) => {
        if (!handleAuthError(err)) showAuthError(loginErrorMessage(err));
      });
    });

    els.registerForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      showAuthError("");
      showAuthNotice("");
      const form = new FormData(els.registerForm);
      await withPendingAuthAction("authenticate", [els.loginForm, els.registerForm], async () => {
        const generation = sessionGeneration;
        let result;
        try {
          result = await performRegister(form.get("display_name"), form.get("soeid"), form.get("password"));
        } catch (err) {
          if (generation !== sessionGeneration) return;
          throw err;
        }
        if (generation !== sessionGeneration) return;
        await finishAuthentication(result);
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

    els.logoutBtn?.addEventListener("click", () => logoutLocally());

    els.idleStay?.addEventListener("click", () => noteSessionActivity?.());

    els.idleLogout?.addEventListener("click", () => logoutLocally());
  }

  async function bootstrapAuth() {
    if (isResetPath()) {
      showResetError("");
      showResetSuccess("");
      setResetVisible(true);
      setStatus("Password reset", "warn");
      return;
    }
    const generation = ++authBootstrapGeneration;
    const spaceId = state.activeSpace?.space_id;
    const isCurrent = () => generation === authBootstrapGeneration && spaceId === state.activeSpace?.space_id;
    setStatus("Checking session...", "warn");
    void api("/auth/session-policy", { skipAuthRefresh: true })
      .then((policy) => configureSessionPolicy?.(policy))
      .catch((err) => {
        if (!isNetworkOrTimeoutFailure(err)) console.warn("Session policy load failed", err);
      });
    try {
      const user = await fetchCurrentUser({ includeContext: true, isCurrent });
      if (!isCurrent()) return;
      if (user) {
        if (!applyAuthBootstrap(user)) {
          await Promise.all([loadUserPreferences(), refreshSpaceContext()]);
        }
        if (generation !== authBootstrapGeneration) return;
        const initialLoad = restoreRouteFromLocationAfterAuth();
        startLiveSync({ catchUpAfter: initialLoad });
        setAuthVisible(false);
        return;
      }
      setAuthVisible(true);
      setStatus("Sign in required", "warn");
    } catch (err) {
      if (generation !== authBootstrapGeneration) return;
      clearLocalSession();
      setAuthVisible(true);
      if (isNetworkOrTimeoutFailure(err)) {
        setStatus("Connection issue", "warn");
        showAuthNotice(err.message || "Unable to reach the server. Check your connection and try again.");
      } else {
        console.warn("Session bootstrap failed", err);
        setStatus("Unable to open session", "warn");
        showAuthNotice("SIPM could not finish opening your session. Sign in again or retry in a moment.");
      }
    }
  }

  return {
    getSessionGeneration: () => sessionGeneration,
    getSessionBinding,
    handleSessionBindingChanged,
    handleSessionBindingMismatch,
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
    recordSessionActivity,
    invalidatePendingRefreshContext,
    logoutForInactivity: () => logoutLocally({ idle: true }),
    handleRemoteLogout: () => logoutLocally({ remote: true }),
  };
}
