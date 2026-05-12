import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createTelemetryController } from "../../js/shell/telemetry.js";


function buildHarness(overrides = {}) {
  const state = {
    currentView: "master",
    activeSpace: { space_id: "space-1", usage_analytics_enabled: true },
  };
  const fetchImpl = overrides.fetchImpl || vi.fn().mockResolvedValue({ ok: true });
  const sendBeacon = overrides.sendBeacon || vi.fn(() => true);
  const controller = createTelemetryController({
    state,
    apiBase: "/api",
    isEnabled: overrides.isEnabled || (() => true),
    fetchImpl,
    navigatorRef: { sendBeacon },
    documentRef: document,
    performanceRef: {
      getEntriesByType: vi.fn((type) => {
        if (type !== "navigation") return [];
        return [
          {
            type: "navigate",
            responseStart: 50,
            domInteractive: 120,
            domContentLoadedEventEnd: 180,
            loadEventEnd: 240,
          },
        ];
      }),
    },
  });
  return { controller, fetchImpl, sendBeacon };
}


describe("telemetry controller", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("emits route view and route transition telemetry", async () => {
    const { controller, fetchImpl } = buildHarness();

    controller.syncRuntimeContext();
    controller.beginRouteTransition("planning", "master", { expectsData: true });
    controller.trackRouteView("planning", "master");
    controller.noteViewRendered("planning", 18);
    controller.noteRouteDataLoaded("planning", 125);
    await controller.flush();

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(fetchImpl.mock.calls[0][1].body);
    expect(payload.events.some((event) => event.action_key === "route_view" && event.view_key === "planning")).toBe(true);
    expect(payload.events.some((event) => event.action_key === "route_transition_complete")).toBe(true);
    expect(payload.performance_samples.some((sample) => sample.sample_kind === "route_transition" && sample.view_key === "planning")).toBe(true);
  });

  it("uses sendBeacon when available and falls back to fetch when it returns false", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });
    const sendBeacon = vi.fn(() => false);
    const { controller } = buildHarness({ fetchImpl, sendBeacon });

    controller.syncRuntimeContext();
    controller.trackWorkflow("projects", "create", "success", { source: "unit" });
    await controller.flush({ useBeacon: true });

    expect(sendBeacon).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("retains queued telemetry when fetch ingest returns an HTTP failure", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({ ok: true });
    const { controller } = buildHarness({ fetchImpl });

    controller.trackWorkflow("projects", "create", "success", { source: "unit" });
    await expect(controller.flush()).resolves.toBe(false);
    await expect(controller.flush()).resolves.toBe(true);

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const retryPayload = JSON.parse(fetchImpl.mock.calls[1][1].body);
    expect(retryPayload.events).toHaveLength(1);
    expect(retryPayload.events[0].action_key).toBe("create");
  });

  it("records timeout and server-side API failures only", async () => {
    const { controller, fetchImpl } = buildHarness();

    controller.trackApiFailure({ path: "/projects", status: 408, kind: "timeout" });
    controller.trackApiFailure({ path: "/projects/123", status: 500, kind: "server_error" });
    controller.trackApiFailure({ path: "/projects/123", status: 404, kind: "client_error" });
    await controller.flush();

    const payload = JSON.parse(fetchImpl.mock.calls[0][1].body);
    const failures = payload.events.filter((event) => event.action_key === "api_failure");
    expect(failures).toHaveLength(2);
    expect(failures.every((event) => event.status_code === 408 || event.status_code === 500)).toBe(true);
  });
});
