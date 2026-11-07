import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createSessionController } from "../../js/shell/session.js";


function jsonResponse(body, { status = 200, errorCode = "", binding = "" } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "ERROR",
    headers: {
      get: (name) => (String(name).toLowerCase() === "x-error-code" ? errorCode : String(name).toLowerCase() === "x-sipm-session" ? binding : ""),
    },
    text: async () => JSON.stringify(body),
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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
  const broadcastSessionLogout = vi.fn();
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
    broadcastSessionLogout,
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
    broadcastSessionLogout,
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

  it("binds authenticated requests and logout to the bootstrap session", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn(async (url, options) => {
      calls.push([url, options]);
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse({ user_id: "u1" }, { binding: "binding-a" });
      if (url.endsWith("/auth/logout")) return jsonResponse({});
      return jsonResponse([]);
    }));
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    expect(harness.controller.getSessionBinding()).toBe("binding-a");
    await harness.controller.api("/projects");
    expect(calls.at(-1)[1].headers["X-SIPM-Session"]).toBe("binding-a");
    await harness.controller.logoutForInactivity();
    expect(calls.at(-1)[0]).toBe("/api/auth/logout");
    expect(calls.at(-1)[1].headers["X-SIPM-Session"]).toBe("binding-a");
    expect(harness.controller.getSessionBinding()).toBe("");
  });

  it("clears only the local tab on a binding mismatch without refreshing", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse({ user_id: "u1" }, { binding: "binding-a" });
      return jsonResponse({ detail: "Session changed" }, { status: 409, errorCode: "SESSION_CONTEXT_CHANGED" });
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    await expect(harness.controller.api("/projects", { method: "POST" })).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(harness.setAuthed).toHaveBeenLastCalledWith(null);
    expect(harness.broadcastSessionLogout).not.toHaveBeenCalled();
    expect(harness.showAuthNotice).toHaveBeenCalledWith(expect.stringContaining("another tab"));
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/auth/refresh"))).toBe(false);
  });

  it("does not let a stale raw mismatch clear a new same-user session", async () => {
    let binding = "binding-a";
    vi.stubGlobal("fetch", vi.fn(async (url) => url.endsWith("/auth/bootstrap")
      ? jsonResponse({ user_id: "u1" }, { binding }) : jsonResponse({})));
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    await harness.controller.handleRemoteLogout();
    binding = "binding-b";
    await harness.controller.bootstrapAuth();
    const mismatch = jsonResponse({}, { status: 409, errorCode: "SESSION_CONTEXT_CHANGED" });
    expect(harness.controller.handleSessionBindingMismatch(mismatch, "binding-a")).toBe(true);
    expect(harness.controller.getSessionBinding()).toBe("binding-b");
    expect(harness.setAuthed).toHaveBeenLastCalledWith({ user_id: "u1" });
  });

  it("retains the binding through same-session token refresh", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse({ user_id: "u1" }, { binding: "binding-a" });
      if (url.endsWith("/auth/refresh")) return jsonResponse({ user_id: "u1" }, { binding: "binding-a" });
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    await harness.controller.refreshSessionTokens({ force: true, refreshContext: false });
    expect(fetchMock.mock.calls.find(([url]) => url.endsWith("/auth/refresh"))[1].headers["X-SIPM-Session"]).toBe("binding-a");
    expect(harness.controller.getSessionBinding()).toBe("binding-a");
    expect(harness.setAuthed).toHaveBeenLastCalledWith({ user_id: "u1" });
  });

  it.each(["login", "register"])("sets the binding from %s and sends it on subsequent requests", async (action) => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="u1"><input name="password" value="Password123">';
    const registerForm = document.createElement("form");
    registerForm.innerHTML = '<input name="soeid" value="u1"><input name="password" value="Password123"><input name="display_name" value="User">';
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith(`/auth/${action}`)) return jsonResponse({ user_id: "u1" }, { binding: "binding-new" });
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ els: { loginForm, registerForm }, applyAuthBootstrap: vi.fn(() => true) });
    harness.controller.bindAuthUI();
    (action === "login" ? loginForm : registerForm).dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(harness.controller.getSessionBinding()).toBe("binding-new"));
    await harness.controller.api("/projects");
    expect(fetchMock.mock.calls.at(-1)[1].headers["X-SIPM-Session"]).toBe("binding-new");
  });

  it("establishes binding during expired-access bootstrap refresh", async () => {
    let bootstrapCount = 0;
    const fetchMock = vi.fn(async (url, options) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) {
        bootstrapCount += 1;
        if (bootstrapCount === 1) return jsonResponse({}, { status: 401 });
        expect(options.headers["X-SIPM-Session"]).toBe("binding-restored");
        return jsonResponse({ user_id: "u1" }, { binding: "binding-restored" });
      }
      if (url.endsWith("/auth/refresh")) return jsonResponse({ user_id: "u1" }, { binding: "binding-restored" });
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    expect(harness.controller.getSessionBinding()).toBe("binding-restored");
    expect(harness.setAuthed).toHaveBeenLastCalledWith({ user_id: "u1" });
  });

  it("serializes a delayed refresh before a different tab starts login", async () => {
    let tail = Promise.resolve();
    const locks = { request: vi.fn((_name, _options, operation) => {
      const result = tail.then(operation);
      tail = result.catch(() => {});
      return result;
    }) };
    vi.stubGlobal("navigator", { locks });
    const refreshResponse = deferred();
    const order = [];
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/refresh")) {
        order.push("refresh-start");
        const result = await refreshResponse.promise;
        order.push("refresh-response");
        return result;
      }
      if (url.endsWith("/auth/login")) {
        order.push("login-start");
        return jsonResponse({ user_id: "u2" }, { binding: "binding-b" });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const oldTab = createHarness({ state: { authed: true, user: { user_id: "u1" }, activeSpace: { space_id: "s1" } } });
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="u2"><input name="password" value="Password123">';
    const newTab = createHarness({ els: { loginForm }, applyAuthBootstrap: vi.fn(() => true) });
    newTab.controller.bindAuthUI();
    const refresh = oldTab.controller.refreshSessionTokens({ force: true, refreshContext: false });
    await vi.waitFor(() => expect(order).toEqual(["refresh-start"]));
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(locks.request).toHaveBeenCalledTimes(2));
    expect(order).toEqual(["refresh-start"]);
    refreshResponse.resolve(jsonResponse({ user_id: "u1" }, { binding: "binding-a" }));
    await refresh;
    await vi.waitFor(() => expect(newTab.controller.getSessionBinding()).toBe("binding-b"));
    expect(order).toEqual(["refresh-start", "refresh-response", "login-start"]);
  });

  it("does not send a queued cookie-changing request after its session changes", async () => {
    const pendingLock = deferred();
    vi.stubGlobal("navigator", { locks: { request: vi.fn((_name, _options, operation) => pendingLock.promise.then(operation)) } });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness();
    const login = harness.controller.api("/auth/login", { method: "POST" });
    await harness.controller.handleRemoteLogout();
    pendingLock.resolve();
    await expect(login).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("checks the original binding when cookies change while waiting for the lock", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse({ user_id: "u1" }, { binding: "binding-a" });
      return jsonResponse({ detail: "Session changed" }, { status: 409, errorCode: "SESSION_CONTEXT_CHANGED" });
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ applyAuthBootstrap: vi.fn(() => true) });
    await harness.controller.bootstrapAuth();
    const pendingLock = deferred();
    vi.stubGlobal("navigator", { locks: { request: vi.fn((_name, _options, operation) => pendingLock.promise.then(operation)) } });
    const refresh = harness.controller.api("/auth/refresh", { method: "POST", skipAuthRefresh: true });
    pendingLock.resolve();
    await expect(refresh).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(fetchMock.mock.calls.at(-1)[1].headers["X-SIPM-Session"]).toBe("binding-a");
    expect(harness.setAuthed).toHaveBeenLastCalledWith(null);
    expect(harness.broadcastSessionLogout).not.toHaveBeenCalled();
  });

  it("times out while waiting for the auth cookie lock", async () => {
    vi.useFakeTimers();
    const request = vi.fn((_name, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true });
    }));
    vi.stubGlobal("navigator", { locks: { request } });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { controller } = createHarness();
    const result = controller.api("/auth/login", { method: "POST", timeoutMs: 50 });
    const rejected = expect(result).rejects.toMatchObject({ status: 408, code: "NETWORK_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(50);
    await rejected;
    expect(fetchMock).not.toHaveBeenCalled();
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

  it("does not retry an unauthorized request after logout during context refresh", async () => {
    const contextRefresh = deferred();
    let protectedReads = 0;
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/refresh")) return jsonResponse({ user_id: "user-1" });
      if (url.endsWith("/protected")) {
        protectedReads += 1;
        return protectedReads === 1
          ? jsonResponse({ detail: "Session expired" }, { status: 401 })
          : jsonResponse({ ok: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({
      state: { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } },
    });
    harness.refreshSpaceContext.mockReturnValue(contextRefresh.promise);

    const request = harness.controller.api("/protected");
    await vi.waitFor(() => expect(harness.refreshSpaceContext).toHaveBeenCalledTimes(1));
    await harness.controller.handleRemoteLogout();
    contextRefresh.resolve();

    await expect(request).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(protectedReads).toBe(1);
    expect(harness.setAuthed).toHaveBeenLastCalledWith(null);
  });

  it.each(["new user", "same user new session", "space", "space round trip"])("does not refresh or replay a delayed 401 after %s", async (change) => {
    const pending = deferred();
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const fetchMock = vi.fn(() => pending.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { controller } = createHarness({ state });
    const result = controller.api("/projects", { method: "POST", body: "{}" });
    if (change === "new user") state.user = { user_id: "user-2" };
    if (change === "same user new session") {
      controller.onAuthedChange(null);
      state.user = { user_id: "user-1" };
    }
    if (change === "space") state.activeSpace = { space_id: "space-2" };
    if (change === "space round trip") {
      controller.invalidatePendingRefreshContext();
      state.activeSpace = { space_id: "space-2" };
      controller.invalidatePendingRefreshContext();
      state.activeSpace = { space_id: "space-1" };
    }
    pending.resolve(jsonResponse({ detail: "expired" }, { status: 401 }));
    await expect(result).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("discards an old successful body after a space change", async () => {
    const body = deferred();
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, text: () => body.promise }));
    const { controller } = createHarness({ state });
    const result = controller.api("/projects");
    state.activeSpace = { space_id: "space-2" };
    body.resolve(JSON.stringify([{ project_name: "old" }]));
    await expect(result).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
  });

  it.each([
    ["ordinary first", "server"],
    ["request first", "server"],
    ["ordinary first", "network"],
    ["request first", "network"],
  ])("propagates transient shared refresh failures per caller: %s, %s", async (order, failure) => {
    const refresh = deferred();
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const fetchMock = vi.fn((url) => url.endsWith("/auth/refresh")
      ? refresh.promise
      : Promise.resolve(jsonResponse({ detail: "expired" }, { status: 401, errorCode: "TOKEN_EXPIRED" })));
    vi.stubGlobal("fetch", fetchMock);
    const { controller, stopLiveSync } = createHarness({ state });
    let ordinary;
    let request;
    if (order === "ordinary first") {
      ordinary = controller.refreshSessionTokens({ force: true, silentFailure: true });
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      request = controller.api("/projects");
    } else {
      request = controller.api("/projects");
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
      ordinary = controller.refreshSessionTokens({ force: true, silentFailure: true });
    }
    const requestResult = request.then((value) => ({ value }), (error) => ({ error }));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await Promise.resolve();
    await Promise.resolve();
    refresh.resolve(failure === "server"
      ? jsonResponse({ detail: "Service unavailable" }, { status: 503 })
      : Promise.reject(new TypeError("offline")));
    const [outcome, ordinaryResult] = await Promise.all([requestResult, ordinary]);

    expect(outcome.error).toMatchObject(failure === "server"
      ? { status: 503, message: "Service unavailable" }
      : { status: 0, code: "NETWORK_UNAVAILABLE" });
    expect(ordinaryResult).toBeNull();
    expect(state.authed).toBe(true);
    expect(controller.handleAuthError(outcome.error)).toBe(false);
    expect(stopLiveSync).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
  });

  it("preserves terminal sign-out when an API request joins a shared refresh", async () => {
    const refresh = deferred();
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const fetchMock = vi.fn((url) => url.endsWith("/auth/refresh")
      ? refresh.promise
      : Promise.resolve(jsonResponse({ detail: "expired" }, { status: 401, errorCode: "TOKEN_EXPIRED" })));
    vi.stubGlobal("fetch", fetchMock);
    const { controller, stopLiveSync } = createHarness({ state });
    const ordinary = controller.refreshSessionTokens({ force: true });
    const request = controller.api("/projects");
    const requestResult = request.then((value) => ({ value }), (error) => ({ error }));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await Promise.resolve();
    await Promise.resolve();
    refresh.resolve(jsonResponse({ detail: "revoked" }, { status: 401, errorCode: "TOKEN_REVOKED" }));
    const [outcome, ordinaryResult] = await Promise.all([requestResult, ordinary]);

    expect(outcome.error).toMatchObject({ status: 401, code: "TOKEN_EXPIRED" });
    expect(ordinaryResult).toBeNull();
    expect(state.authed).toBe(false);
    expect(stopLiveSync).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
  });

  it("clears only the local session when refresh returns a different authenticated user", async () => {
    const state = { authed: true, user: { user_id: "user-a" }, activeSpace: { space_id: "space-1" } };
    const fetchMock = vi.fn(async (url) => url.endsWith("/auth/refresh")
      ? jsonResponse({ user_id: "user-b" })
      : jsonResponse({ detail: "expired" }, { status: 401, errorCode: "TOKEN_EXPIRED" }));
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ state });
    await expect(harness.controller.api("/projects", { method: "POST" })).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(state.authed).toBe(false);
    expect(state.user).toBeNull();
    expect(harness.setAuthed).not.toHaveBeenCalledWith({ user_id: "user-b" });
    expect(harness.refreshSpaceContext).not.toHaveBeenCalled();
    expect(harness.setAuthVisible).toHaveBeenCalledWith(true);
    expect(harness.broadcastSessionLogout).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(["/api/projects", "/api/auth/refresh"]);
  });

  it("accepts the refreshed user during logged-out bootstrap", async () => {
    const state = { authed: false, user: null, activeSpace: { space_id: "space-1" } };
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ user_id: "user-b" })));
    const harness = createHarness({ state });
    await expect(harness.controller.refreshSessionTokens({ force: true, allowLoggedOut: true, refreshContext: false })).resolves.toMatchObject({ user_id: "user-b" });
    expect(state.user).toMatchObject({ user_id: "user-b" });
    expect(harness.broadcastSessionLogout).not.toHaveBeenCalled();
  });

  it("does not retry after caller cancellation during token refresh", async () => {
    const refresh = deferred();
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const fetchMock = vi.fn((url) => url.endsWith("/auth/refresh") ? refresh.promise : Promise.resolve(jsonResponse({ detail: "expired" }, { status: 401 })));
    vi.stubGlobal("fetch", fetchMock);
    const { controller } = createHarness({ state });
    const abort = new AbortController();
    const result = controller.api("/projects", { method: "POST", signal: abort.signal });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    abort.abort();
    refresh.resolve(jsonResponse({ user_id: "user-1" }));
    await expect(result).rejects.toMatchObject({ name: "AbortError" });
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/projects"))).toHaveLength(1);
  });

  it.each(["timeout", "cancel"])("settles a %s during shared refresh without disrupting another request", async (reason) => {
    vi.useFakeTimers();
    const refresh = deferred();
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const counts = new Map();
    const fetchMock = vi.fn((url) => {
      if (url.endsWith("/auth/refresh")) return refresh.promise;
      const count = (counts.get(url) || 0) + 1;
      counts.set(url, count);
      return Promise.resolve(count === 1 ? jsonResponse({ detail: "expired" }, { status: 401 }) : jsonResponse({ ok: true }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const { controller, onApiFailure } = createHarness({ state });
    const abort = new AbortController();
    let firstOutcome;
    const first = controller.api("/first", { timeoutMs: 50, signal: abort.signal })
      .then((value) => { firstOutcome = { value }; }, (error) => { firstOutcome = { error }; });
    const second = controller.api("/second", { timeoutMs: 500 });
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    if (reason === "cancel") abort.abort();
    await vi.advanceTimersByTimeAsync(reason === "timeout" ? 50 : 0);
    const settledWhileRefreshPending = firstOutcome;
    refresh.resolve(jsonResponse({ user_id: "user-1" }));
    await vi.advanceTimersByTimeAsync(0);
    await first;
    const secondResult = await second;

    expect(settledWhileRefreshPending?.error).toMatchObject(reason === "timeout"
      ? { status: 408, code: "NETWORK_UNAVAILABLE" }
      : { name: "AbortError" });
    expect(secondResult).toEqual({ ok: true });
    expect(counts.get("/api/first")).toBe(1);
    expect(counts.get("/api/second")).toBe(2);
    expect(onApiFailure).toHaveBeenCalledTimes(reason === "timeout" ? 1 : 0);
  });

  it("uses the original request deadline while replaying after token refresh", async () => {
    vi.useFakeTimers();
    const refresh = deferred();
    let projectCalls = 0;
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith("/auth/refresh")) return refresh.promise;
      projectCalls += 1;
      if (projectCalls === 1) return Promise.resolve(jsonResponse({ detail: "expired" }, { status: 401 }));
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { controller, onApiFailure } = createHarness({
      state: { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } },
    });
    let outcome;
    const request = controller.api("/projects", { timeoutMs: 50 })
      .then((value) => { outcome = { value }; }, (error) => { outcome = { error }; });
    await vi.advanceTimersByTimeAsync(40);
    refresh.resolve(jsonResponse({ user_id: "user-1" }));
    await vi.advanceTimersByTimeAsync(0);
    expect(projectCalls).toBe(2);
    await vi.advanceTimersByTimeAsync(10);
    const outcomeAtOriginalDeadline = outcome;
    // Allow an incorrectly restarted retry timer to settle before making assertions.
    await vi.advanceTimersByTimeAsync(50);
    await request;

    expect(outcomeAtOriginalDeadline?.error).toMatchObject({ status: 408, code: "NETWORK_UNAVAILABLE" });
    expect(onApiFailure).toHaveBeenCalledTimes(1);
  });

  it("retries a scoped write with its original space and caller headers after reconciliation", async () => {
    let projectWrites = 0;
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (url.endsWith("/auth/refresh")) return jsonResponse({ user_id: "user-1" });
      if (url.endsWith("/projects")) {
        projectWrites += 1;
        if (projectWrites === 1) return jsonResponse({ detail: "Expired" }, { status: 401 });
        return jsonResponse({
          ok: true,
          space_id: options.headers["X-Space-Id"],
          request_id: options.headers["X-Request-Id"],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const harness = createHarness({ state });
    harness.refreshSpaceContext.mockImplementation(async () => {
      state.activeSpace = { space_id: "space-1" };
    });

    const body = JSON.stringify({ project_id: "project-1" });
    const result = await harness.controller.api("/projects", {
      method: "POST",
      headers: { "X-Request-Id": "request-1" },
      body,
    });

    expect(result).toEqual({ ok: true, space_id: "space-1", request_id: "request-1" });
    const projectOptions = fetchMock.mock.calls
      .filter(([url]) => url.endsWith("/projects"))
      .map(([, options]) => options);
    expect(projectOptions).toHaveLength(2);
    projectOptions.forEach((options) => {
      expect(options.headers).toMatchObject({
        "X-Space-Id": "space-1",
        "X-Request-Id": "request-1",
        "Content-Type": "application/json",
      });
      expect(options.body).toBe(body);
    });
  });

  it("does not replay a write when token refresh changes the active space", async () => {
    let writes = 0;
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/refresh")) return jsonResponse({ user_id: "user-1" });
      writes += 1;
      return jsonResponse({ detail: "expired" }, { status: 401 });
    });
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ state });
    harness.refreshSpaceContext.mockImplementation(async () => { state.activeSpace = { space_id: "space-2" }; });
    await expect(harness.controller.api("/projects", { method: "POST", body: "{}" }))
      .rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(writes).toBe(1);
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

  it.each(["login", "register"])("prevents concurrent login and registration when %s starts first", async (first) => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="login"><input name="password" value="Password123"><button type="submit">Sign in</button>';
    const registerForm = document.createElement("form");
    registerForm.innerHTML = '<input name="display_name" value="New user"><input name="soeid" value="register"><input name="password" value="Password123"><button type="submit">Register</button>';
    const auth = deferred();
    const fetchMock = vi.fn(() => auth.promise);
    vi.stubGlobal("fetch", fetchMock);
    const harness = createHarness({ els: { loginForm, registerForm }, applyAuthBootstrap: vi.fn(() => true) });
    harness.controller.bindAuthUI();
    const firstForm = first === "login" ? loginForm : registerForm;
    const secondForm = first === "login" ? registerForm : loginForm;
    firstForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    secondForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(loginForm.querySelector("button").disabled).toBe(true);
    expect(registerForm.querySelector("button").disabled).toBe(true);
    auth.resolve(jsonResponse({ user_id: "user-1" }));
    await vi.waitFor(() => expect(harness.setAuthVisible).toHaveBeenCalledWith(false));
    expect(loginForm.querySelector("button").disabled).toBe(false);
    expect(registerForm.querySelector("button").disabled).toBe(false);
  });

  it.each(["success", "failure"])("ignores %s of auth setup after sign-out", async (completion) => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="user"><input name="password" value="Password123"><button type="submit">Sign in</button>';
    const setup = deferred();
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ user_id: "user-1" })));
    const harness = createHarness({ els: { loginForm } });
    harness.loadUserPreferences.mockReturnValue(setup.promise);
    harness.controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(harness.loadUserPreferences).toHaveBeenCalledTimes(1));
    const preferenceIsCurrent = harness.loadUserPreferences.mock.calls[0][0].isCurrent;
    const spaceIsCurrent = harness.refreshSpaceContext.mock.calls[0][0].isCurrent;
    expect(preferenceIsCurrent()).toBe(true);
    expect(spaceIsCurrent()).toBe(true);
    await harness.controller.handleRemoteLogout();
    expect(preferenceIsCurrent()).toBe(false);
    expect(spaceIsCurrent()).toBe(false);
    harness.setAuthVisible.mockClear();
    if (completion === "success") setup.resolve();
    else setup.resolve(Promise.reject(new Error("old setup failed")));
    await vi.waitFor(() => expect(loginForm.querySelector("button").disabled).toBe(false));
    expect(harness.startLiveSync).not.toHaveBeenCalled();
    expect(harness.setView).not.toHaveBeenCalled();
    expect(harness.setAuthVisible).not.toHaveBeenCalled();
    expect(harness.showAuthError).not.toHaveBeenCalledWith("old setup failed");
    expect(harness.setAuthed).toHaveBeenCalledTimes(2);
  });

  it("does not clear a replacement session when old authentication setup fails", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="user"><input name="password" value="Password123"><button type="submit">Sign in</button>';
    const setup = deferred();
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ user_id: "old-user" })));
    const harness = createHarness({ els: { loginForm } });
    harness.loadUserPreferences.mockReturnValue(setup.promise);
    harness.controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(harness.loadUserPreferences).toHaveBeenCalledTimes(1));
    await harness.controller.handleRemoteLogout();
    harness.setAuthed({ user_id: "replacement" });
    harness.setAuthed.mockClear();
    harness.setAuthVisible.mockClear();
    setup.resolve(Promise.reject(new Error("old setup failed")));
    await vi.waitFor(() => expect(loginForm.querySelector("button").disabled).toBe(false));
    expect(harness.setAuthed).not.toHaveBeenCalled();
    expect(harness.setAuthVisible).not.toHaveBeenCalled();
    expect(harness.startLiveSync).not.toHaveBeenCalled();
    expect(harness.showAuthError).not.toHaveBeenCalledWith("old setup failed");
  });

  it("discards a login response after a remote sign-out", async () => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="user"><input name="password" value="Password123"><button type="submit">Sign in</button>';
    const login = deferred();
    vi.stubGlobal("fetch", vi.fn(() => login.promise));
    const harness = createHarness({ els: { loginForm }, applyAuthBootstrap: vi.fn(() => true) });
    harness.controller.bindAuthUI();
    loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await harness.controller.handleRemoteLogout();
    harness.setAuthVisible.mockClear();
    login.resolve(jsonResponse({ user_id: "old-user" }));
    await vi.waitFor(() => expect(loginForm.querySelector("button").disabled).toBe(false));
    expect(harness.setAuthed).not.toHaveBeenCalledWith({ user_id: "old-user" });
    expect(harness.startLiveSync).not.toHaveBeenCalled();
    expect(harness.setAuthVisible).not.toHaveBeenCalled();
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

  it.each(["login", "bootstrap"])("subscribes during %s with catch-up following foreground completion", async (entry) => {
    const loginForm = document.createElement("form");
    loginForm.innerHTML = '<input name="soeid" value="user"><input name="password" value="Password123">';
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ user_id: "user" })));
    const harness = createHarness({ els: { loginForm }, applyAuthBootstrap: vi.fn(() => true) });
    const initialLoad = new Promise(() => {});
    harness.setView.mockReturnValue(initialLoad);
    if (entry === "login") {
      harness.controller.bindAuthUI();
      loginForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    } else {
      await harness.controller.bootstrapAuth();
    }
    await vi.waitFor(() => expect(harness.setAuthVisible).toHaveBeenCalledWith(false));
    expect(harness.startLiveSync).toHaveBeenCalledExactlyOnceWith({ catchUpAfter: initialLoad });
    expect(harness.setView.mock.invocationCallOrder[0]).toBeLessThan(harness.startLiveSync.mock.invocationCallOrder[0]);
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

  it("does not send a second unbound logout after the local session has cleared", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/session-policy")) return jsonResponse({});
      if (url.endsWith("/auth/bootstrap")) return jsonResponse({ user_id: "u1" }, { binding: "binding-a" });
      if (url.endsWith("/projects")) return jsonResponse({ detail: "Session changed" }, { status: 409, errorCode: "SESSION_CONTEXT_CHANGED" });
      if (url.endsWith("/auth/logout")) return jsonResponse({});
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const logoutButton = document.createElement("button");
    const harness = createHarness({ els: { logoutBtn: logoutButton }, applyAuthBootstrap: vi.fn(() => true) });
    harness.controller.bindAuthUI();
    await harness.controller.bootstrapAuth();
    await expect(harness.controller.api("/projects")).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    logoutButton.click();
    await harness.controller.logoutForInactivity();
    await Promise.resolve();
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/logout"))).toHaveLength(0);
    expect(harness.broadcastSessionLogout).not.toHaveBeenCalled();
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
