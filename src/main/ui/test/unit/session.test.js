import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createSessionController } from "../../js/shell/session.js";


function jsonResponse(body, { status = 200, errorCode = "" } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "ERROR",
    headers: {
      get: (name) => (String(name).toLowerCase() === "x-error-code" ? errorCode : ""),
    },
    text: async () => JSON.stringify(body),
  };
}

function createHarness(overrides = {}) {
  const state = overrides.state || {
    authed: false,
    activeSpace: { space_id: "space-1" },
    user: null,
  };
  const els = overrides.els || {};
  const viewFromLocationPath = vi.fn(() => "team-capacity");
  const setView = vi.fn();
  const refreshSpaceContext = vi.fn().mockResolvedValue(undefined);
  const loadUserPreferences = vi.fn().mockResolvedValue(undefined);
  const applyAuthBootstrap = overrides.applyAuthBootstrap || vi.fn(() => false);
  const startLiveSync = vi.fn();
  const setAuthVisible = vi.fn();
  const stopLiveSync = vi.fn();
  const showAuthNotice = vi.fn();
  const showAuthError = vi.fn();
  const showResetError = vi.fn();
  const setStatus = vi.fn();
  const onApiFailure = overrides.onApiFailure || vi.fn();
  const setAuthed = vi.fn((user) => {
    state.user = user;
    state.authed = !!user;
  });
  const controller = createSessionController({
    state,
    els,
    apiBase: "/api",
    accessRefreshIntervalMs: 60_000,
    buildAppUrl: (path) => `/project-manager${path}`,
    isResetPathname: () => false,
    viewFromLocationPath,
    setView,
    setAuthMode: vi.fn(),
    setAuthed,
    setStatus,
    setAuthVisible,
    setResetVisible: vi.fn(),
    showAuthError,
    showAuthNotice,
    showResetError,
    showResetSuccess: vi.fn(),
    configureSessionPolicy: vi.fn(),
    noteSessionActivity: vi.fn(),
    broadcastSessionLogout: vi.fn(),
    refreshSpaceContext,
    loadUserPreferences,
    applyAuthBootstrap,
    resolvePostAuthView: overrides.resolvePostAuthView,
    preloadLoginRoute: overrides.preloadLoginRoute,
    reloadCurrentViewData: vi.fn().mockResolvedValue(undefined),
    onApiFailure,
    startLiveSync,
    stopLiveSync,
  });
  return {
    controller,
    viewFromLocationPath,
    setView,
    setAuthed,
    refreshSpaceContext,
    loadUserPreferences,
    applyAuthBootstrap,
    startLiveSync,
    stopLiveSync,
    setAuthVisible,
    showAuthNotice,
    showAuthError,
    showResetError,
    setStatus,
    onApiFailure,
  };
}


describe("session controller", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/project-manager/team-capacity");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it.each([false, true])("restores consolidated context with developer mode %s without follow-up reads", async (developerMode) => {
    const payload = {
      user_id: "user-1",
      preferences: { developer_mode_enabled: developerMode, theme: "light" },
      spaces: [{ space_id: "space-1" }],
      active_space: { space_id: "space-1" },
    };
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse(payload);
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const applyAuthBootstrap = vi.fn(() => true);
    const harness = createHarness({
      applyAuthBootstrap,
      resolvePostAuthView: (view) => {
        expect(applyAuthBootstrap).toHaveBeenCalledWith(payload);
        return developerMode ? "my-work" : view;
      },
    });
    await harness.controller.bootstrapAuth();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(["/api/auth/session-policy", "/api/auth/bootstrap"]);
    expect(harness.setAuthed).toHaveBeenCalledWith({ user_id: "user-1" });
    expect(harness.loadUserPreferences).not.toHaveBeenCalled();
    expect(harness.refreshSpaceContext).not.toHaveBeenCalled();
    expect(harness.setView).toHaveBeenCalledWith(
      developerMode ? "my-work" : "team-capacity",
      developerMode ? { fromHistory: false, replacePath: true } : { fromHistory: true },
    );
  });

  it.each([200, 401, 503])("bounds bootstrap recovery when the retried response is %s", async (retryStatus) => {
    let reads = 0;
    const payload = { user_id: "user-1", preferences: {}, spaces: [], active_space: {} };
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/refresh")) return jsonResponse({ user_id: "user-1" });
      if (url.endsWith("/auth/bootstrap")) {
        const status = reads++ === 0 ? 401 : retryStatus;
        return status === 200 ? jsonResponse(payload) : jsonResponse({ detail: "Failed" }, { status });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/auth/session-policy", "/api/auth/bootstrap", "/api/auth/refresh", "/api/auth/bootstrap",
    ]);
    expect(harness.loadUserPreferences).not.toHaveBeenCalled();
    expect(harness.refreshSpaceContext).not.toHaveBeenCalled();
    expect(harness.applyAuthBootstrap).toHaveBeenCalledTimes(retryStatus === 200 ? 1 : 0);
    expect(harness.setAuthVisible).toHaveBeenLastCalledWith(retryStatus !== 200);
  });

  it("retains single-flight token refresh while restoring bootstrap context", async () => {
    let releaseRefresh;
    let reads = 0;
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) {
        return reads++ === 0 ? jsonResponse({}, { status: 401 }) : jsonResponse({ user_id: "user-1" });
      }
      if (url.endsWith("/auth/refresh")) {
        return new Promise((resolve) => { releaseRefresh = () => resolve(jsonResponse({ user_id: "user-1" })); });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    const opening = harness.controller.bootstrapAuth();
    await vi.waitFor(() => expect(releaseRefresh).toBeTypeOf("function"));
    const concurrent = harness.controller.refreshSessionTokens({ force: true, refreshContext: false });
    releaseRefresh();
    await Promise.all([opening, concurrent]);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(harness.applyAuthBootstrap).toHaveBeenCalledTimes(1);
  });

  it.each(["logout", "space", "refresh-logout"])("discards late bootstrap context after %s", async (change) => {
    const state = { authed: false, user: null, activeSpace: { space_id: "space-1" } };
    let releaseResponse;
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (change === "refresh-logout" && url.endsWith("/auth/bootstrap")) return jsonResponse({}, { status: 401 });
      return new Promise((resolve) => { releaseResponse = () => resolve(jsonResponse({ user_id: "old-user" })); });
    }));
    const harness = createHarness({ state, applyAuthBootstrap: vi.fn(() => true) });
    const opening = harness.controller.bootstrapAuth();
    await vi.waitFor(() => expect(releaseResponse).toBeTypeOf("function"));
    if (change === "space") state.activeSpace = { space_id: "space-2" };
    else await harness.controller.handleRemoteLogout();
    harness.setAuthVisible.mockClear();
    releaseResponse();
    await opening;
    expect(harness.setAuthed).not.toHaveBeenCalledWith({ user_id: "old-user" });
    expect(harness.applyAuthBootstrap).not.toHaveBeenCalled();
    expect(harness.startLiveSync).not.toHaveBeenCalled();
    expect(harness.setView).not.toHaveBeenCalled();
    expect(harness.setAuthVisible).not.toHaveBeenCalled();
  });

  it.each(["logout", "new login", "space"])("rejects a late ordinary refresh shared by bootstrap after %s", async (change) => {
    const state = { authed: true, user: { user_id: "old-user" }, activeSpace: { space_id: "space-1" } };
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="new-user"><input name="password" value="Password123">';
    let releaseRefresh;
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse({}, { status: 401 });
      if (url.endsWith("/auth/login")) return jsonResponse({ user_id: "new-user" });
      if (url.endsWith("/auth/refresh")) {
        return new Promise((resolve) => { releaseRefresh = () => resolve(jsonResponse({ user_id: "old-user" })); });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ state, els: { loginForm }, applyAuthBootstrap: vi.fn(() => true) });
    const ordinaryRefresh = harness.controller.refreshSessionTokens({ force: true, refreshContext: false });
    const opening = harness.controller.bootstrapAuth();
    await vi.waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/bootstrap"))).toHaveLength(1));
    if (change === "space") state.activeSpace = { space_id: "space-2" };
    else if (change === "logout") await harness.controller.handleRemoteLogout();
    else {
      harness.controller.bindAuthUI();
      loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await vi.waitFor(() => expect(state.user?.user_id).toBe("new-user"));
    }
    harness.applyAuthBootstrap.mockClear();
    harness.setView.mockClear();
    releaseRefresh();
    await Promise.all([ordinaryRefresh, opening]);
    expect(harness.setAuthed).not.toHaveBeenCalledWith({ user_id: "old-user" });
    expect(state.user?.user_id).toBe(change === "new login" ? "new-user" : change === "space" ? "old-user" : undefined);
    expect(harness.applyAuthBootstrap).not.toHaveBeenCalled();
    expect(harness.refreshSpaceContext).not.toHaveBeenCalled();
    expect(harness.setView).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
  });

  it("lets the newest bootstrap consume refresh shared with a superseded bootstrap", async () => {
    let releaseRefresh;
    let reads = 0;
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) {
        return reads++ < 2 ? jsonResponse({}, { status: 401 }) : jsonResponse({ user_id: "user-1" });
      }
      if (url.endsWith("/auth/refresh")) {
        return new Promise((resolve) => { releaseRefresh = () => resolve(jsonResponse({ user_id: "user-1" })); });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    const first = harness.controller.bootstrapAuth();
    await vi.waitFor(() => expect(releaseRefresh).toBeTypeOf("function"));
    const second = harness.controller.bootstrapAuth();
    await vi.waitFor(() => expect(reads).toBe(2));
    releaseRefresh();
    await Promise.all([first, second]);
    expect(reads).toBe(3);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(harness.setAuthed).not.toHaveBeenCalledWith(null);
    expect(harness.applyAuthBootstrap).toHaveBeenCalledTimes(1);
    expect(harness.setAuthVisible).toHaveBeenLastCalledWith(false);
  });

  it("does not let an obsolete refresh clear the replacement session's shared promise", async () => {
    const state = { authed: true, user: { user_id: "old-user" }, activeSpace: { space_id: "space-1" } };
    const releases = [];
    const fetchMock = vi.fn(() => new Promise((resolve) => {
      releases.push((user_id) => resolve(jsonResponse({ user_id })));
    }));
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ state });
    const options = { force: true, refreshContext: false };
    const oldRefresh = harness.controller.refreshSessionTokens(options);
    await harness.controller.handleRemoteLogout();
    state.user = { user_id: "new-user" };
    state.authed = true;
    const newRefresh = harness.controller.refreshSessionTokens(options);
    releases[0]("old-user");
    await oldRefresh;
    const joined = harness.controller.refreshSessionTokens(options);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    releases[1]("new-user");
    await Promise.all([newRefresh, joined]);
    expect(harness.setAuthed).not.toHaveBeenCalledWith({ user_id: "old-user" });
    expect(harness.setAuthed).toHaveBeenLastCalledWith({ user_id: "new-user" });
  });

  it("honors caller cancellation without reporting it as a network failure", async () => {
    let requestSignal = null;
    vi.stubGlobal("fetch", vi.fn((_url, options = {}) => {
      requestSignal = options.signal;
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () => {
          const error = new Error("cancelled");
          error.name = "AbortError";
          reject(error);
        }, { once: true });
      });
    }));
    const caller = new AbortController();
    const { controller, onApiFailure } = createHarness();

    const request = controller.api("/projects", { signal: caller.signal, timeoutMs: 10_000 });
    const rejection = expect(request).rejects.toMatchObject({ name: "AbortError", message: "cancelled" });
    await Promise.resolve();
    caller.abort();

    await rejection;
    expect(requestSignal).toBeInstanceOf(AbortSignal);
    expect(requestSignal).not.toBe(caller.signal);
    expect(requestSignal.aborted).toBe(true);
    expect(onApiFailure).not.toHaveBeenCalled();
  });

  it("keeps the request timeout when a caller cancellation signal is supplied", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn((_url, options = {}) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        const error = new Error("timed out");
        error.name = "AbortError";
        reject(error);
      }, { once: true });
    })));
    const caller = new AbortController();
    const { controller, onApiFailure } = createHarness();

    const request = controller.api("/projects", { signal: caller.signal, timeoutMs: 50 });
    const rejection = expect(request).rejects.toMatchObject({ status: 408, code: "NETWORK_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(50);

    await rejection;
    expect(caller.signal.aborted).toBe(false);
    expect(onApiFailure).toHaveBeenCalledWith({ path: "/projects", status: 408, kind: "timeout" });
  });

  it("restores the requested route from the URL after bootstrap auth succeeds", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) {
        return jsonResponse({ idle_timeout_seconds: 1800, warning_seconds: 60, activity_heartbeat_seconds: 15 });
      }
      if (String(url).endsWith("/auth/bootstrap")) {
        return jsonResponse({ user_id: "user-1", display_name: "User 1" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    const { controller, viewFromLocationPath, setView, refreshSpaceContext, startLiveSync, setAuthVisible } = createHarness();
    await controller.bootstrapAuth();

    expect(refreshSpaceContext).toHaveBeenCalledTimes(1);
    expect(startLiveSync).toHaveBeenCalledTimes(1);
    expect(viewFromLocationPath).toHaveBeenCalledWith("/project-manager/team-capacity");
    expect(setView).toHaveBeenCalledWith("team-capacity", { fromHistory: true });
    expect(setAuthVisible).not.toHaveBeenCalledWith(true);
    const lastAuthVisibleCall = setAuthVisible.mock.calls.at(-1);
    expect(lastAuthVisibleCall).toEqual([false]);
    expect(setView.mock.invocationCallOrder[0]).toBeLessThan(setAuthVisible.mock.invocationCallOrder.at(-1));
  });

  it("shows the local sign-in screen after the session check fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) {
        return jsonResponse({ idle_timeout_seconds: 1800, warning_seconds: 60, activity_heartbeat_seconds: 15 });
      }
      if (String(url).endsWith("/auth/bootstrap")) {
        return jsonResponse({ detail: "Not authenticated" }, { status: 401 });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return jsonResponse({ detail: "Not authenticated" }, { status: 401 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    const { controller, setView, refreshSpaceContext, startLiveSync, setAuthVisible } = createHarness();
    await controller.bootstrapAuth();

    expect(refreshSpaceContext).not.toHaveBeenCalled();
    expect(startLiveSync).not.toHaveBeenCalled();
    expect(setView).not.toHaveBeenCalled();
    expect(setAuthVisible).toHaveBeenCalledTimes(1);
    expect(setAuthVisible).toHaveBeenCalledWith(true);
  });

  it("handles terminal bootstrap auth failures without throwing", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) {
        return jsonResponse({ idle_timeout_seconds: 1800, warning_seconds: 60, activity_heartbeat_seconds: 15 });
      }
      if (String(url).endsWith("/auth/bootstrap")) {
        return jsonResponse({ detail: "Account locked" }, { status: 423, errorCode: "ACCOUNT_LOCKED" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    const { controller, showAuthNotice, setAuthVisible, stopLiveSync } = createHarness({
      state: { authed: true, activeSpace: { space_id: "space-1" }, user: { user_id: "user-1" } },
    });
    await controller.bootstrapAuth();

    expect(stopLiveSync).toHaveBeenCalledTimes(1);
    expect(showAuthNotice).toHaveBeenCalledWith("Account locked. Try again later or contact an administrator.");
    expect(setAuthVisible).toHaveBeenCalledWith(true);
  });

  it("keeps bootstrap network failures in a controlled sign-in state", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) {
        return jsonResponse({ idle_timeout_seconds: 1800, warning_seconds: 60, activity_heartbeat_seconds: 15 });
      }
      if (String(url).endsWith("/auth/bootstrap")) {
        throw new TypeError("Failed to fetch");
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    const { controller, showAuthNotice, setAuthVisible, setStatus, stopLiveSync } = createHarness({
      state: { authed: true, activeSpace: { space_id: "space-1" }, user: { user_id: "user-1" } },
    });
    await controller.bootstrapAuth();

    expect(stopLiveSync).toHaveBeenCalledTimes(1);
    expect(setAuthVisible).toHaveBeenCalledWith(true);
    expect(setStatus).toHaveBeenCalledWith("Connection issue", "warn");
    expect(showAuthNotice).toHaveBeenCalledWith(
      "Unable to reach the server. Check your connection and try again.",
    );
  });

  it("keeps bootstrap server failures on a visible sign-in surface", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) return jsonResponse({});
      if (String(url).endsWith("/auth/bootstrap")) {
        return jsonResponse({ detail: "Database unavailable" }, { status: 503 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    const { controller, showAuthNotice, setAuthVisible, setStatus } = createHarness();
    await expect(controller.bootstrapAuth()).resolves.toBeUndefined();

    expect(setAuthVisible).toHaveBeenCalledWith(true);
    expect(setStatus).toHaveBeenCalledWith("Unable to open session", "warn");
    expect(showAuthNotice).toHaveBeenCalledWith(
      "SIPM could not finish opening your session. Sign in again or retry in a moment.",
    );
  });

  it("does not let session policy loading block the sign-in screen", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).endsWith("/auth/session-policy")) return new Promise(() => {});
      if (String(url).endsWith("/auth/bootstrap")) {
        return Promise.resolve(jsonResponse({ detail: "Not authenticated" }, { status: 401 }));
      }
      if (String(url).endsWith("/auth/refresh")) {
        return Promise.resolve(jsonResponse({ detail: "Not authenticated" }, { status: 401 }));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    const { controller, setAuthVisible } = createHarness();
    await controller.bootstrapAuth();

    expect(setAuthVisible).toHaveBeenCalledWith(true);
  });

  it("bounds startup refresh and loads space context only once", async () => {
    let bootstrapReads = 0;
    const refreshSpaceContext = vi.fn().mockResolvedValue(undefined);
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/auth/session-policy")) return jsonResponse({});
      if (String(url).endsWith("/auth/bootstrap")) {
        if (bootstrapReads++ > 0) return jsonResponse({ user_id: "user-1" });
        return jsonResponse({ detail: "Expired" }, { status: 401, errorCode: "TOKEN_EXPIRED" });
      }
      if (String(url).endsWith("/auth/refresh")) {
        expect(options.signal).toBeInstanceOf(AbortSignal);
        return jsonResponse({ user_id: "user-1", display_name: "User 1" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const harness = createHarness();
    harness.refreshSpaceContext.mockImplementation(refreshSpaceContext);
    await harness.controller.bootstrapAuth();

    expect(harness.refreshSpaceContext).toHaveBeenCalledTimes(1);
    expect(harness.setAuthVisible).toHaveBeenLastCalledWith(false);
  });

  it("surfaces space-context bootstrap failures instead of leaving the shell hidden", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) return jsonResponse({});
      if (String(url).endsWith("/auth/bootstrap")) return jsonResponse({ user_id: "user-1" });
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const contextError = Object.assign(new Error("No active space"), {
      status: 403,
      code: "NO_ACTIVE_SPACE",
    });
    const { controller, refreshSpaceContext, setAuthVisible, showAuthNotice } = createHarness();
    refreshSpaceContext.mockRejectedValue(contextError);

    await controller.bootstrapAuth();

    expect(setAuthVisible).toHaveBeenCalledWith(true);
    expect(showAuthNotice).toHaveBeenCalledWith(
      "SIPM could not finish opening your session. Sign in again or retry in a moment.",
    );
  });

  it("clears local realtime session state when session expiry is handled", () => {
    const { controller, stopLiveSync, setAuthVisible } = createHarness();

    controller.handleAuthError({ status: 401 });

    expect(stopLiveSync).toHaveBeenCalledTimes(1);
    expect(setAuthVisible).toHaveBeenCalledWith(true);
  });

  it("does not treat bad login credentials as a terminal session failure", () => {
    const { controller, stopLiveSync, setAuthVisible } = createHarness();

    const handled = controller.handleAuthError({ status: 401, code: "LOGIN_FAILED", message: "Login failed" });

    expect(handled).toBe(false);
    expect(stopLiveSync).not.toHaveBeenCalled();
    expect(setAuthVisible).not.toHaveBeenCalled();
  });

  it("uses server auth error codes for user-facing terminal session messages", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/projects")) {
        return jsonResponse({ detail: "Token no longer valid" }, { status: 401, errorCode: "TOKEN_REVOKED" });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return jsonResponse({ detail: "Password reset required" }, { status: 403, errorCode: "PASSWORD_RESET_REQUIRED" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const { controller, stopLiveSync, setAuthVisible, showAuthNotice, setStatus } = createHarness({
      state: { authed: true, activeSpace: { space_id: "space-1" }, user: { user_id: "user-1" } },
    });

    await expect(controller.api("/projects")).rejects.toMatchObject({
      status: 401,
      code: "TOKEN_REVOKED",
    });

    expect(stopLiveSync).toHaveBeenCalledTimes(1);
    expect(setAuthVisible).not.toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith("Sign in required", "warn");
    expect(showAuthNotice).toHaveBeenCalledWith(
      "Password reset required. Use your temporary password to set a new one.",
    );
  });

  it("uses non-technical copy for expired sessions", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/projects")) {
        return jsonResponse({ detail: "Token expired" }, { status: 401, errorCode: "TOKEN_EXPIRED" });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return jsonResponse({ detail: "Token expired" }, { status: 401, errorCode: "TOKEN_EXPIRED" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const { controller, showAuthNotice } = createHarness({
      state: { authed: true, activeSpace: { space_id: "space-1" }, user: { user_id: "user-1" } },
    });

    await expect(controller.api("/projects")).rejects.toMatchObject({
      status: 401,
      code: "TOKEN_EXPIRED",
    });

    expect(showAuthNotice).toHaveBeenCalledWith("Your session expired. Sign in again to continue.");
  });

  it("warms the requested route during login without waiting for it or authenticating early", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="user"><input name="password" value="Password123"><button type="submit">Sign in</button>';
    let resolveLogin;
    const login = new Promise((resolve) => { resolveLogin = resolve; });
    const fetchMock = vi.fn(() => login);
    vi.stubGlobal("fetch", fetchMock);
    const preloadLoginRoute = vi.fn(() => new Promise(() => {}));
    const harness = createHarness({ els: { loginForm }, preloadLoginRoute, applyAuthBootstrap: vi.fn(() => true) });
    harness.controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(preloadLoginRoute).toHaveBeenCalledExactlyOnceWith("team-capacity"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.invocationCallOrder[0]).toBeLessThan(preloadLoginRoute.mock.invocationCallOrder[0]);
    expect(harness.setAuthed).not.toHaveBeenCalled();
    expect(harness.setView).not.toHaveBeenCalled();
    resolveLogin(jsonResponse({ user_id: "user" }));
    await vi.waitFor(() => expect(harness.setAuthVisible).toHaveBeenCalledWith(false));
    expect(harness.setView).toHaveBeenCalledExactlyOnceWith("team-capacity", { fromHistory: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each(["throw", "reject"])("keeps login successful when speculative route loading fails by %s", async (mode) => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="user"><input name="password" value="Password123">';
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ user_id: "user" })));
    const preloadLoginRoute = vi.fn(() => {
      if (mode === "throw") throw new Error("Module unavailable");
      return Promise.reject(new Error("Module unavailable"));
    });
    const harness = createHarness({ els: { loginForm }, preloadLoginRoute, applyAuthBootstrap: vi.fn(() => true) });
    harness.controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(harness.setAuthVisible).toHaveBeenCalledWith(false));
    expect(preloadLoginRoute).toHaveBeenCalledExactlyOnceWith("team-capacity");
    expect(harness.showAuthError).not.toHaveBeenCalledWith("Module unavailable");
  });

  it("prevents duplicate login submissions while a request is pending", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = `
      <input name="soeid" value="user1" />
      <input name="password" value="Password123" />
      <button type="submit">Log in</button>
    `;
    const submitButton = loginForm.querySelector("button");
    let resolveLogin;
    const fetchMock = vi.fn((url) => {
      if (String(url).endsWith("/auth/login")) {
        return new Promise((resolve) => {
          resolveLogin = () => resolve(jsonResponse({ user_id: "user-1", display_name: "User 1" }));
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const { controller } = createHarness({
      els: { loginForm },
    });

    controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(submitButton.disabled).toBe(true);
    expect(submitButton.getAttribute("aria-busy")).toBe("true");

    resolveLogin();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(submitButton.disabled).toBe(false);
    expect(submitButton.hasAttribute("aria-busy")).toBe(false);
  });

  it("uses the login bootstrap payload without redundant context requests", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = `
      <input name="soeid" value="user1" />
      <input name="password" value="Password123" />
      <button type="submit">Log in</button>
    `;
    const loginPayload = {
      user_id: "user-1",
      display_name: "User 1",
      preferences: { developer_mode_enabled: false, theme: "dark", has_saved_preferences: true },
      spaces: [{ space_id: "space-1", name: "Space 1" }],
      active_space: { space_id: "space-1", space_name: "Space 1" },
    };
    const fetchMock = vi.fn(async (url) => {
      if (String(url).endsWith("/auth/login")) return jsonResponse(loginPayload);
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const applyAuthBootstrap = vi.fn(() => true);
    const {
      controller,
      setAuthed,
      loadUserPreferences,
      refreshSpaceContext,
      startLiveSync,
      setAuthVisible,
    } = createHarness({ els: { loginForm }, applyAuthBootstrap });

    controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(setAuthVisible).toHaveBeenCalledWith(false));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(applyAuthBootstrap).toHaveBeenCalledWith(loginPayload);
    expect(setAuthed).toHaveBeenCalledWith({ user_id: "user-1", display_name: "User 1" });
    expect(loadUserPreferences).not.toHaveBeenCalled();
    expect(refreshSpaceContext).not.toHaveBeenCalled();
    expect(startLiveSync).toHaveBeenCalledTimes(1);
  });

  it("keeps login failures on the form error surface", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = `
      <input name="soeid" value="user1" />
      <input name="password" value="WrongPassword123" />
      <button type="submit">Log in</button>
    `;
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/login")) {
        return jsonResponse(
          { detail: "Login failed. Check your username or password." },
          { status: 401, errorCode: "LOGIN_FAILED" },
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const { controller, showAuthError, showAuthNotice, stopLiveSync } = createHarness({
      els: { loginForm },
    });

    controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(showAuthNotice).toHaveBeenCalledWith("");
    expect(showAuthError).toHaveBeenCalledWith(
      "The SOEID or password did not match. Try again, or use your temporary password if an admin reset your account.",
    );
    expect(stopLiveSync).not.toHaveBeenCalled();
  });

  it("shows a clear form error when login cannot reach the server", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = `
      <input name="soeid" value="user1" />
      <input name="password" value="Password123" />
      <button type="submit">Log in</button>
    `;
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/login")) throw new TypeError("Failed to fetch");
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const { controller, showAuthError, showAuthNotice, stopLiveSync } = createHarness({
      els: { loginForm },
    });

    controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(showAuthNotice).toHaveBeenCalledWith("");
    expect(showAuthError).toHaveBeenCalledWith("Unable to reach the server. Check your connection and try again.");
    expect(stopLiveSync).not.toHaveBeenCalled();
  });

  it("shows actionable reset errors without exposing auth internals", async () => {
    const resetForm = document.createElement("form");
    resetForm.innerHTML = `
      <input name="soeid" value="user1" />
      <input name="temp_password" value="WrongTemp123" />
      <input name="new_password" value="NewPassword123" />
      <input name="confirm_password" value="NewPassword123" />
      <button type="submit">Set new password</button>
    `;
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/reset-password")) {
        return jsonResponse(
          { detail: "Temporary password is invalid" },
          { status: 401, errorCode: "TEMP_PASSWORD_INVALID" },
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const { controller, showResetError } = createHarness({
      els: { resetForm },
    });

    controller.bindAuthUI();
    resetForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(showResetError).toHaveBeenCalledWith(
      "The SOEID or temporary password did not match. Check the reset details from your admin.",
    );
  });

  it("clears local realtime session state after explicit logout", async () => {
    const logoutButton = document.createElement("button");
    const { controller, stopLiveSync } = createHarness({
      state: { authed: true, activeSpace: { space_id: "space-1" }, user: { user_id: "user-1" } },
      els: { logoutBtn: logoutButton },
    });
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/logout")) return jsonResponse({}, { status: 204 });
      throw new Error(`Unexpected fetch: ${url}`);
    }));

    controller.bindAuthUI();
    logoutButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(stopLiveSync).toHaveBeenCalledTimes(1);
  });
});
