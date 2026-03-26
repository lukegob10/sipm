import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LIVE_SYNC_CLOSE_AUTH,
  LIVE_SYNC_CLOSE_BUSY,
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
    FakeWebSocket.instances.push(this);
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
    const controller = createLiveSyncController({
      state,
      buildWsUrl: (path) => `ws://127.0.0.1:8000${path}`,
      isResetPath: () => false,
      refreshSessionTokens,
      refreshSpaceContext: vi.fn().mockResolvedValue(undefined),
      reloadCurrentViewData,
      refreshFromServer: vi.fn(),
      handleAuthError: vi.fn(() => false),
      handleSessionExpired: vi.fn(),
      renderTopbarStatus: vi.fn(),
      setSpaceFeedback: vi.fn(),
      spaceNameForId: (spaceId) => spaceId,
      clearDataState: vi.fn(),
    });
    return { controller, refreshSessionTokens };
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
});
