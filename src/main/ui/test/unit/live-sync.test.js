import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LIVE_SYNC_CLOSE_AUTH,
  LIVE_SYNC_CLOSE_BUSY,
  LIVE_SYNC_CLOSE_SPACE,
  createLiveSyncController,
} from "../../js/shell/live-sync.js";


class FakeWebSocket {
  static instances = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.CONNECTING;
    this.listeners = new Map();
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }

  send(payload) {
    this.sent.push(payload);
  }

  addEventListener(type, listener) {
    const existing = this.listeners.get(type) || [];
    existing.push(listener);
    this.listeners.set(type, existing);
  }

  close(code = 1000, reason = "") {
    this.readyState = FakeWebSocket.CLOSED;
    this.emit("close", { code, reason });
  }

  emit(type, payload = {}) {
    const listeners = this.listeners.get(type) || [];
    listeners.forEach((listener) => listener(payload));
  }
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}


describe("live sync controller", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeWebSocket);
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function createHarness() {
    const state = {
      authed: true,
      user: { user_id: "user-1" },
      activeSpace: { space_id: "space-1" },
      liveSync: {
        socketSpaceId: "",
        pausedForHidden: false,
        phase: "idle",
        statusText: "",
        statusTone: "",
      },
    };
    const refreshSessionTokens = vi.fn().mockResolvedValue({ user_id: "user-1" });
    const reloadCurrentViewData = vi.fn().mockResolvedValue(undefined);
    const refreshFromServer = vi.fn();
    const refreshAgentChangeRequests = vi.fn().mockResolvedValue([]);
    const refreshSpaceContext = vi.fn().mockResolvedValue(undefined);
    const handleAuthError = vi.fn(() => false);
    const handleSessionExpired = vi.fn();
    const clearDataState = vi.fn();
    const controller = createLiveSyncController({
      state,
      buildWsUrl: (path) => `ws://127.0.0.1:8000${path}`,
      isResetPath: () => false,
      refreshSessionTokens,
      refreshSpaceContext,
      reloadCurrentViewData,
      refreshFromServer,
      refreshAgentChangeRequests,
      handleAuthError,
      handleSessionExpired,
      renderTopbarStatus: vi.fn(),
      setSpaceFeedback: vi.fn(),
      spaceNameForId: (spaceId) => spaceId,
      clearDataState,
    });
    return {
      controller,
      state,
      refreshAgentChangeRequests,
      refreshFromServer,
      refreshSessionTokens,
      reloadCurrentViewData,
      refreshSpaceContext,
      handleAuthError,
      handleSessionExpired,
      clearDataState,
    };
  }

  it("retries websocket auth failures by refreshing the session", async () => {
    const { controller, refreshSessionTokens } = createHarness();

    controller.startLiveSync();
    const socket = FakeWebSocket.instances.at(-1);
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("close", { code: LIVE_SYNC_CLOSE_AUTH });
    await Promise.resolve();

    expect(refreshSessionTokens).toHaveBeenCalledWith({
      force: true,
      silentFailure: true,
      suppressLiveSyncRestart: true,
    });
  });

  it("schedules a reconnect for reconnectable close codes", () => {
    const { controller } = createHarness();

    controller.startLiveSync();
    const socket = FakeWebSocket.instances.at(-1);
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("close", { code: LIVE_SYNC_CLOSE_BUSY });

    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.runOnlyPendingTimers();
    expect(FakeWebSocket.instances.length).toBeGreaterThan(1);
  });

  it("bounds auth recovery when the server accepts then rejects each handshake", async () => {
    const { controller, refreshSessionTokens, handleSessionExpired } = createHarness();
    controller.startLiveSync();
    const first = FakeWebSocket.instances[0];
    first.readyState = FakeWebSocket.OPEN;
    first.emit("open");
    first.close(LIVE_SYNC_CLOSE_AUTH);
    await vi.advanceTimersByTimeAsync(0);

    const retry = FakeWebSocket.instances[1];
    retry.readyState = FakeWebSocket.OPEN;
    retry.emit("open");
    retry.close(LIVE_SYNC_CLOSE_AUTH);
    await vi.advanceTimersByTimeAsync(0);

    expect(refreshSessionTokens).toHaveBeenCalledOnce();
    expect(handleSessionExpired).toHaveBeenCalledOnce();
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("bounds space recovery when the server accepts then rejects each handshake", async () => {
    const { controller, state, refreshSpaceContext } = createHarness();
    controller.startLiveSync();
    const first = FakeWebSocket.instances[0];
    first.readyState = FakeWebSocket.OPEN;
    first.emit("open");
    first.close(LIVE_SYNC_CLOSE_SPACE);
    await vi.advanceTimersByTimeAsync(0);

    const retry = FakeWebSocket.instances[1];
    retry.readyState = FakeWebSocket.OPEN;
    retry.emit("open");
    retry.close(LIVE_SYNC_CLOSE_SPACE);
    await vi.advanceTimersByTimeAsync(0);

    expect(refreshSpaceContext).toHaveBeenCalledOnce();
    expect(state.liveSync.phase).toBe("attention");
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("increases backoff when an opened handshake is rejected as busy", () => {
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    const { controller } = createHarness();
    controller.startLiveSync();
    const first = FakeWebSocket.instances[0];
    first.readyState = FakeWebSocket.OPEN;
    first.emit("open");
    first.close(LIVE_SYNC_CLOSE_BUSY);
    vi.advanceTimersByTime(1000);

    const retry = FakeWebSocket.instances[1];
    retry.readyState = FakeWebSocket.OPEN;
    retry.emit("open");
    retry.close(LIVE_SYNC_CLOSE_BUSY);
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("allows fresh auth recovery after an established idle socket loses transport", async () => {
    const { controller, refreshSessionTokens, handleSessionExpired } = createHarness();
    controller.startLiveSync();
    FakeWebSocket.instances[0].close(LIVE_SYNC_CLOSE_AUTH);
    await vi.advanceTimersByTimeAsync(0);

    const recovered = FakeWebSocket.instances[1];
    recovered.readyState = FakeWebSocket.OPEN;
    recovered.emit("open");
    recovered.close(1006);
    vi.advanceTimersByTime(2000);
    FakeWebSocket.instances[2].close(LIVE_SYNC_CLOSE_AUTH);
    await vi.advanceTimersByTimeAsync(0);

    expect(refreshSessionTokens).toHaveBeenCalledTimes(2);
    expect(handleSessionExpired).not.toHaveBeenCalled();
  });

  it.each([null, { user_id: "user-1" }])("ignores obsolete auth recovery after a replacement connection (%j)", async (result) => {
    const { controller, refreshSessionTokens, handleSessionExpired } = createHarness();
    const recovery = deferred();
    refreshSessionTokens.mockReturnValueOnce(recovery.promise);
    controller.startLiveSync();
    FakeWebSocket.instances[0].close(LIVE_SYNC_CLOSE_AUTH);

    controller.stopLiveSync();
    controller.startLiveSync();
    const replacement = FakeWebSocket.instances[1];
    recovery.resolve(result);
    await vi.advanceTimersByTimeAsync(0);

    expect(handleSessionExpired).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(replacement.readyState).toBe(FakeWebSocket.CONNECTING);
  });

  it.each(["resolve", "reject"])("ignores obsolete space recovery after stopping (%s)", async (outcome) => {
    const { controller, refreshSpaceContext, reloadCurrentViewData, handleAuthError, clearDataState } = createHarness();
    const recovery = deferred();
    refreshSpaceContext.mockReturnValueOnce(recovery.promise);
    controller.startLiveSync();
    FakeWebSocket.instances[0].close(LIVE_SYNC_CLOSE_SPACE);

    controller.stopLiveSync();
    if (outcome === "resolve") recovery.resolve();
    else recovery.reject(new Error("Stale space request"));
    await vi.advanceTimersByTimeAsync(0);

    expect(handleAuthError).not.toHaveBeenCalled();
    expect(clearDataState).not.toHaveBeenCalled();
    expect(reloadCurrentViewData).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("does not restart a replacement socket after an obsolete space reload completes", async () => {
    const { controller, reloadCurrentViewData } = createHarness();
    const reload = deferred();
    reloadCurrentViewData.mockReturnValueOnce(reload.promise);
    controller.startLiveSync();
    FakeWebSocket.instances[0].close(LIVE_SYNC_CLOSE_SPACE);
    await vi.advanceTimersByTimeAsync(0);
    expect(reloadCurrentViewData).toHaveBeenCalledOnce();

    controller.startLiveSync({ force: true });
    reload.resolve();
    await vi.advanceTimersByTimeAsync(0);

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].readyState).toBe(FakeWebSocket.CONNECTING);
  });

  it("does not restart sync after stopping during a visibility refresh", async () => {
    const { controller, state, reloadCurrentViewData } = createHarness();
    const reload = deferred();
    reloadCurrentViewData.mockReturnValueOnce(reload.promise);
    state.liveSync.pausedForHidden = true;
    const visibilityRefresh = controller.handleLiveSyncVisibilityChange();

    controller.stopLiveSync();
    reload.resolve();
    await visibilityRefresh;

    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(state.liveSync.phase).toBe("idle");
  });

  it("refreshes agent approvals directly from websocket messages", async () => {
    const { controller, refreshAgentChangeRequests, refreshFromServer } = createHarness();

    controller.startLiveSync();
    const socket = FakeWebSocket.instances.at(-1);
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("message", {
      data: JSON.stringify({ type: "refresh", entity: "agent_change_requests" }),
    });

    await vi.waitFor(() => {
      expect(refreshAgentChangeRequests).toHaveBeenCalledWith({ force: true });
    });
    expect(refreshFromServer).not.toHaveBeenCalled();
  });

  it("keeps the connection active with application-level heartbeats", () => {
    const { controller } = createHarness();

    controller.startLiveSync();
    const socket = FakeWebSocket.instances.at(-1);
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("open");
    vi.advanceTimersByTime(60000);

    expect(socket.sent).toEqual([JSON.stringify({ type: "ping" })]);
  });

  it("performs a catch-up refresh whenever a socket opens", async () => {
    const { controller, refreshAgentChangeRequests, reloadCurrentViewData } = createHarness();

    controller.startLiveSync();
    const socket = FakeWebSocket.instances.at(-1);
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("open");

    await vi.waitFor(() => {
      expect(reloadCurrentViewData).toHaveBeenCalledWith({
        force: true,
        silent: true,
        preserveCapacitySelection: false,
      });
      expect(refreshAgentChangeRequests).toHaveBeenCalledWith({ force: true });
    });
  });

  it("subscribes immediately but lets the initial route finish before forced catch-up", async () => {
    const { controller, state, reloadCurrentViewData, refreshAgentChangeRequests } = createHarness();
    const initialLoad = deferred();

    controller.startLiveSync({ catchUpAfter: initialLoad.promise });
    expect(FakeWebSocket.instances).toHaveLength(1);
    const socket = FakeWebSocket.instances[0];
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("open");

    expect(state.liveSync.phase).toBe("live");
    expect(reloadCurrentViewData).not.toHaveBeenCalled();
    expect(refreshAgentChangeRequests).not.toHaveBeenCalled();

    initialLoad.resolve();
    await vi.waitFor(() => expect(reloadCurrentViewData).toHaveBeenCalledExactlyOnceWith({
      force: true, silent: true, preserveCapacitySelection: false,
    }));
    expect(refreshAgentChangeRequests).toHaveBeenCalledExactlyOnceWith({ force: true });
  });

  it.each(["before open", "after open"])("still catches up when the initial route rejects %s", async (timing) => {
    const { controller, reloadCurrentViewData, refreshAgentChangeRequests } = createHarness();
    const initialLoad = deferred();
    controller.startLiveSync({ catchUpAfter: initialLoad.promise });

    if (timing === "before open") {
      initialLoad.reject(new Error("Initial route failed"));
      await vi.advanceTimersByTimeAsync(0);
      expect(reloadCurrentViewData).not.toHaveBeenCalled();
    }
    const socket = FakeWebSocket.instances[0];
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("open");
    if (timing === "after open") {
      expect(reloadCurrentViewData).not.toHaveBeenCalled();
      initialLoad.reject(new Error("Initial route failed"));
    }

    await vi.waitFor(() => expect(reloadCurrentViewData).toHaveBeenCalledOnce());
    expect(refreshAgentChangeRequests).toHaveBeenCalledOnce();
  });

  it("processes refresh messages and heartbeats while initial catch-up is waiting", async () => {
    const { controller, reloadCurrentViewData, refreshFromServer, refreshAgentChangeRequests } = createHarness();
    const initialLoad = deferred();
    controller.startLiveSync({ catchUpAfter: initialLoad.promise });
    const socket = FakeWebSocket.instances[0];
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("open");

    socket.emit("message", { data: JSON.stringify({ type: "refresh", entity: "tasks" }) });
    socket.emit("message", { data: JSON.stringify({ type: "refresh", entity: "agent_change_requests" }) });
    vi.advanceTimersByTime(60000);

    expect(refreshFromServer).toHaveBeenCalledExactlyOnceWith("tasks");
    expect(refreshAgentChangeRequests).toHaveBeenCalledExactlyOnceWith({ force: true });
    expect(socket.sent).toEqual([JSON.stringify({ type: "ping" })]);
    expect(reloadCurrentViewData).not.toHaveBeenCalled();

    initialLoad.resolve();
    await vi.waitFor(() => expect(reloadCurrentViewData).toHaveBeenCalledOnce());
    expect(refreshAgentChangeRequests).toHaveBeenCalledTimes(2);
  });

  it("catches up a replacement socket immediately and discards the obsolete wait", async () => {
    const { controller, reloadCurrentViewData, refreshAgentChangeRequests } = createHarness();
    const initialLoad = deferred();
    controller.startLiveSync({ catchUpAfter: initialLoad.promise });
    const oldSocket = FakeWebSocket.instances[0];
    oldSocket.readyState = FakeWebSocket.OPEN;
    oldSocket.emit("open");

    controller.startLiveSync({ force: true });
    const replacement = FakeWebSocket.instances[1];
    replacement.readyState = FakeWebSocket.OPEN;
    replacement.emit("open");
    expect(reloadCurrentViewData).toHaveBeenCalledOnce();
    expect(refreshAgentChangeRequests).toHaveBeenCalledOnce();

    initialLoad.resolve();
    await vi.advanceTimersByTimeAsync(0);
    expect(reloadCurrentViewData).toHaveBeenCalledOnce();
    expect(refreshAgentChangeRequests).toHaveBeenCalledOnce();
  });

  it.each(["stop", "logout", "space", "user"])("discards delayed catch-up after %s", async (change) => {
    const { controller, state, reloadCurrentViewData, refreshAgentChangeRequests } = createHarness();
    const initialLoad = deferred();
    controller.startLiveSync({ catchUpAfter: initialLoad.promise });
    const socket = FakeWebSocket.instances[0];
    socket.readyState = FakeWebSocket.OPEN;
    socket.emit("open");

    if (change === "stop") controller.stopLiveSync();
    if (change === "logout") state.authed = false;
    if (change === "space") state.activeSpace = { space_id: "space-2" };
    if (change === "user") state.user = { user_id: "user-2" };
    initialLoad.resolve();
    await vi.advanceTimersByTimeAsync(0);

    expect(reloadCurrentViewData).not.toHaveBeenCalled();
    expect(refreshAgentChangeRequests).not.toHaveBeenCalled();
  });
});
