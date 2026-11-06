import { afterEach, describe, expect, it, vi } from "vitest";

import { createSessionController } from "../../js/shell/session.js";

function deferred() {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { promise, resolve };
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createHarness() {
  const state = {
    authed: true,
    user: { user_id: "user-1" },
    activeSpace: { space_id: "space-1" },
  };
  const setAuthed = vi.fn((user) => {
    state.user = user;
    state.authed = !!user;
  });
  const controller = createSessionController({
    state,
    els: {},
    apiBase: "/api",
    accessRefreshIntervalMs: 60_000,
    setAuthed,
    setStatus: vi.fn(),
    setAuthVisible: vi.fn(),
    showAuthNotice: vi.fn(),
    broadcastSessionLogout: vi.fn(),
    refreshSpaceContext: vi.fn().mockResolvedValue(undefined),
    stopLiveSync: vi.fn(),
  });
  return { state, controller, setAuthed };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("shell refresh lifetime", () => {
  it.each([
    ["another space", 200],
    ["another space", 401],
    ["a space round trip", 200],
    ["a space round trip", 401],
  ])("gives %s its own refresh while the old refresh returns %s", async (change, staleStatus) => {
    const { state, controller, setAuthed } = createHarness();
    const oldResponse = deferred();
    const newResponse = deferred();
    let refreshes = 0;
    let projectReads = 0;
    const fetchMock = vi.fn((url, options) => {
      if (url.endsWith("/auth/refresh")) {
        refreshes += 1;
        return refreshes === 1 ? oldResponse.promise : newResponse.promise;
      }
      projectReads += 1;
      return Promise.resolve(projectReads === 1
        ? jsonResponse({ detail: "Expired" }, 401)
        : jsonResponse({ space_id: options.headers["X-Space-Id"] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const oldRefresh = controller.refreshSessionTokens({ force: true, refreshContext: false });
    controller.invalidatePendingRefreshContext();
    state.activeSpace = { space_id: "space-2" };
    if (change === "a space round trip") {
      controller.invalidatePendingRefreshContext();
      state.activeSpace = { space_id: "space-1" };
    }
    const currentOutcome = controller.api("/projects").then(
      (value) => ({ value }),
      (error) => ({ error }),
    );

    try {
      await vi.waitFor(() => expect(refreshes).toBe(2));
      oldResponse.resolve(jsonResponse({ user_id: "user-1" }, staleStatus));
      await oldRefresh;

      // Finishing the old request must not clear the new context's shared work.
      const joinedRefresh = controller.refreshSessionTokens({ force: true, refreshContext: false });
      expect(refreshes).toBe(2);
      newResponse.resolve(jsonResponse({ user_id: "user-1" }));
      await joinedRefresh;

      await expect(currentOutcome).resolves.toEqual({ value: { space_id: state.activeSpace.space_id } });
      expect(projectReads).toBe(2);
      expect(setAuthed).not.toHaveBeenCalledWith(null);
      expect(state.authed).toBe(true);
    } finally {
      oldResponse.resolve(jsonResponse({ user_id: "user-1" }, staleStatus));
      newResponse.resolve(jsonResponse({ user_id: "user-1" }));
      await Promise.all([oldRefresh, currentOutcome]);
    }
  });
});
