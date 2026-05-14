import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createSessionController } from "../../js/shell/session.js";


function jsonResponse(body, { status = 200 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "ERROR",
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
  const startLiveSync = vi.fn();
  const setAuthVisible = vi.fn();
  const stopLiveSync = vi.fn();
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
    setAuthed: vi.fn((user) => {
      state.user = user;
      state.authed = !!user;
    }),
    setStatus: vi.fn(),
    setAuthVisible,
    setResetVisible: vi.fn(),
    showAuthError: vi.fn(),
    showAuthNotice: vi.fn(),
    showResetError: vi.fn(),
    showResetSuccess: vi.fn(),
    resetIdleTimer: vi.fn(),
    hideIdleModal: vi.fn(),
    refreshSpaceContext,
    reloadCurrentViewData: vi.fn().mockResolvedValue(undefined),
    startLiveSync,
    stopLiveSync,
  });
  return { controller, viewFromLocationPath, setView, refreshSpaceContext, startLiveSync, stopLiveSync, setAuthVisible };
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

  it("clears local realtime session state when session expiry is handled", () => {
    const { controller, stopLiveSync, setAuthVisible } = createHarness();

    controller.handleAuthError({ status: 401 });

    expect(stopLiveSync).toHaveBeenCalledTimes(1);
    expect(setAuthVisible).toHaveBeenCalledWith(true);
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
