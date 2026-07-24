import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createActivitySessionController } from "../../js/shell/activity-session.js";


function createHarness(overrides = {}) {
  const onWarning = vi.fn();
  const onWarningDismissed = vi.fn();
  const onHeartbeat = vi.fn().mockResolvedValue({});
  const onIdleLogout = vi.fn();
  const onRemoteLogout = vi.fn();
  const controller = createActivitySessionController({
    onWarning,
    onWarningDismissed,
    onHeartbeat,
    onIdleLogout,
    onRemoteLogout,
    ...overrides,
  });
  controller.configure({
    idle_timeout_seconds: 1800,
    warning_seconds: 60,
    activity_heartbeat_seconds: 15,
  });
  return { controller, onWarning, onWarningDismissed, onHeartbeat, onIdleLogout, onRemoteLogout };
}


describe("activity session controller", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-15T00:00:00Z"));
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it("warns at 29 minutes and logs out at 30 minutes", async () => {
    const { controller, onWarning, onIdleLogout } = createHarness();
    controller.start("user-1");

    await vi.advanceTimersByTimeAsync(29 * 60 * 1000);
    expect(onWarning).toHaveBeenLastCalledWith(60);

    await vi.advanceTimersByTimeAsync(60 * 1000);
    expect(onIdleLogout).toHaveBeenCalledTimes(1);
  });

  it("restarts the full deadline and dismisses the warning on genuine activity", async () => {
    const { controller, onWarning, onWarningDismissed, onIdleLogout } = createHarness();
    controller.start("user-1");
    await vi.advanceTimersByTimeAsync(29 * 60 * 1000);
    expect(onWarning).toHaveBeenCalled();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    expect(onWarningDismissed).toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(29 * 60 * 1000);
    expect(onIdleLogout).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(60 * 1000);
    expect(onIdleLogout).toHaveBeenCalledTimes(1);
  });

  it("records activity before the action handler can start an authenticated request", async () => {
    const { controller, onHeartbeat } = createHarness();
    const action = vi.fn();
    const button = document.createElement("button");
    button.addEventListener("click", action);
    document.body.append(button);
    controller.start("user-1");
    await vi.advanceTimersByTimeAsync(15 * 1000);

    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    expect(onHeartbeat).toHaveBeenCalledTimes(1);
    expect(action).toHaveBeenCalledTimes(1);
    expect(onHeartbeat.mock.invocationCallOrder[0]).toBeLessThan(action.mock.invocationCallOrder[0]);
    button.remove();
  });

  it("throttles leading heartbeats and sends a trailing heartbeat", async () => {
    const { controller, onHeartbeat } = createHarness();
    controller.start("user-1");

    await vi.advanceTimersByTimeAsync(15 * 1000);
    controller.noteUserActivity();
    expect(onHeartbeat).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(500);
    controller.noteUserActivity();
    expect(onHeartbeat).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(onHeartbeat).toHaveBeenCalledTimes(2);
  });

  it("accepts activity and logout messages from another tab without sending a heartbeat", () => {
    const { controller, onHeartbeat, onRemoteLogout } = createHarness();
    controller.start("user-1");
    const remoteActivityAt = Date.now() + 5000;

    window.dispatchEvent(new StorageEvent("storage", {
      key: "sipm-auth-activity-v1",
      newValue: JSON.stringify({ version: 1, user_id: "user-1", at: remoteActivityAt }),
    }));
    expect(onHeartbeat).not.toHaveBeenCalled();

    window.dispatchEvent(new StorageEvent("storage", {
      key: "sipm-auth-logout-v1",
      newValue: JSON.stringify({ version: 1, user_id: "user-1", at: remoteActivityAt + 1 }),
    }));
    expect(onRemoteLogout).toHaveBeenCalledTimes(1);
  });

  it("evaluates elapsed wall time when a hidden tab becomes visible", () => {
    let currentTime = Date.now();
    const { controller, onIdleLogout } = createHarness({ now: () => currentTime });
    controller.start("user-1");
    currentTime += 30 * 60 * 1000;

    controller.evaluate();
    expect(onIdleLogout).toHaveBeenCalledTimes(1);
  });
});
