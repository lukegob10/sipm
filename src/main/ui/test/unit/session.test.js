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
    reloadCurrentViewData: vi.fn().mockResolvedValue(undefined),
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
  };
}


describe("session controller", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/project-manager/team-capacity");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("restores the requested route from the URL after bootstrap auth succeeds", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/session-policy")) {
        return jsonResponse({ idle_timeout_seconds: 1800, warning_seconds: 60, activity_heartbeat_seconds: 15 });
      }
      if (String(url).endsWith("/auth/me")) {
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
      if (String(url).endsWith("/auth/me")) {
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
      if (String(url).endsWith("/auth/me")) {
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
      if (String(url).endsWith("/auth/me")) {
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
      if (String(url).endsWith("/auth/me")) {
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
      if (String(url).endsWith("/auth/me")) {
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
    const refreshSpaceContext = vi.fn().mockResolvedValue(undefined);
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).endsWith("/auth/session-policy")) return jsonResponse({});
      if (String(url).endsWith("/auth/me")) {
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
      if (String(url).endsWith("/auth/me")) return jsonResponse({ user_id: "user-1" });
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
