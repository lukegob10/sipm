import { describe, expect, it, vi } from "vitest";

import {
  invalidateDataForSpaceContextChange,
  refreshSpaceContextData,
} from "../../js/shell/context.js";


function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}


describe("space context data invalidation", () => {
  it("invalidates cached data when context falls back to another active space", () => {
    const clearDataState = vi.fn();

    const invalidated = invalidateDataForSpaceContextChange({
      previousSpaceId: "space-a",
      nextSpaceId: "space-b",
      clearDataState,
    });

    expect(invalidated).toBe(true);
    expect(clearDataState).toHaveBeenCalledTimes(1);
  });

  it("preserves initial, unchanged, and caller-owned invalidation paths", () => {
    const clearDataState = vi.fn();

    expect(invalidateDataForSpaceContextChange({
      previousSpaceId: "",
      nextSpaceId: "space-b",
      clearDataState,
    })).toBe(false);
    expect(invalidateDataForSpaceContextChange({
      previousSpaceId: "space-a",
      nextSpaceId: "space-a",
      clearDataState,
    })).toBe(false);
    expect(invalidateDataForSpaceContextChange({
      previousSpaceId: "space-a",
      nextSpaceId: "space-b",
      clearDataState,
      suppress: true,
    })).toBe(false);

    expect(clearDataState).not.toHaveBeenCalled();
  });

  it("clears space A and awaits the replacement load when a context refresh selects space B", async () => {
    const replacementLoad = deferred();
    const clearDataState = vi.fn();
    const reloadCurrentViewData = vi.fn(() => replacementLoad.promise);
    const renderActiveView = vi.fn();
    let currentSpaceId = "space-a";
    const spaces = [{ space_id: "space-b" }];
    const activeSpace = { space_id: "space-b" };
    const applySpaceContext = vi.fn((_nextSpaces, nextActiveSpace, options) => {
      const invalidated = invalidateDataForSpaceContextChange({
        previousSpaceId: currentSpaceId,
        nextSpaceId: nextActiveSpace?.space_id,
        clearDataState,
        suppress: options.suppressDataInvalidation,
      });
      currentSpaceId = nextActiveSpace?.space_id || "";
      return invalidated;
    });
    let refreshSettled = false;

    const refreshPromise = refreshSpaceContextData({
      loadSpaces: vi.fn().mockResolvedValue(spaces),
      loadActiveSpace: vi.fn().mockResolvedValue(activeSpace),
      applySpaceContext,
      reloadCurrentViewData,
      renderActiveView,
      options: {},
    }).then(() => {
      refreshSettled = true;
    });

    await vi.waitFor(() => expect(reloadCurrentViewData).toHaveBeenCalledTimes(1));
    expect(applySpaceContext).toHaveBeenCalledWith(spaces, activeSpace, {});
    expect(clearDataState).toHaveBeenCalledTimes(1);
    expect(reloadCurrentViewData).toHaveBeenCalledWith({
      force: true,
      preserveCapacitySelection: false,
    });
    expect(renderActiveView).not.toHaveBeenCalled();
    expect(refreshSettled).toBe(false);

    replacementLoad.resolve();
    await refreshPromise;

    expect(refreshSettled).toBe(true);
  });

  it("renders cleared data without loading when a context refresh has no next space", async () => {
    const clearDataState = vi.fn();
    const reloadCurrentViewData = vi.fn();
    const renderActiveView = vi.fn();

    const invalidated = await refreshSpaceContextData({
      loadSpaces: vi.fn().mockResolvedValue([]),
      loadActiveSpace: vi.fn().mockResolvedValue(null),
      applySpaceContext: (_spaces, activeSpace) => invalidateDataForSpaceContextChange({
        previousSpaceId: "space-a",
        nextSpaceId: activeSpace?.space_id,
        clearDataState,
      }),
      reloadCurrentViewData,
      renderActiveView,
      options: {},
    });

    expect(invalidated).toBe(true);
    expect(clearDataState).toHaveBeenCalledTimes(1);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
    expect(reloadCurrentViewData).not.toHaveBeenCalled();
  });

  it("does not render or reload when applying refreshed context keeps data valid", async () => {
    const reloadCurrentViewData = vi.fn();
    const renderActiveView = vi.fn();

    const invalidated = await refreshSpaceContextData({
      loadSpaces: vi.fn().mockResolvedValue([{ space_id: "space-a" }]),
      loadActiveSpace: vi.fn().mockResolvedValue({ space_id: "space-a" }),
      applySpaceContext: vi.fn(() => false),
      reloadCurrentViewData,
      renderActiveView,
      options: {},
    });

    expect(invalidated).toBe(false);
    expect(renderActiveView).not.toHaveBeenCalled();
    expect(reloadCurrentViewData).not.toHaveBeenCalled();
  });

  it("discards a superseded context response before applying or rendering it", async () => {
    const response = deferred();
    let isCurrent = true;
    const applySpaceContext = vi.fn(() => true);
    const reloadCurrentViewData = vi.fn();
    const renderActiveView = vi.fn();
    const refresh = refreshSpaceContextData({
      loadSpaces: vi.fn().mockResolvedValue([{ space_id: "old-space" }]),
      loadActiveSpace: () => response.promise,
      applySpaceContext,
      reloadCurrentViewData,
      renderActiveView,
      isCurrent: () => isCurrent,
    });

    isCurrent = false;
    response.resolve({ space_id: "old-space" });
    await expect(refresh).resolves.toBe(false);
    expect(applySpaceContext).not.toHaveBeenCalled();
    expect(reloadCurrentViewData).not.toHaveBeenCalled();
    expect(renderActiveView).not.toHaveBeenCalled();
  });

  it("ignores obsolete request failures while preserving failures from the current context", async () => {
    const response = deferred();
    let isCurrent = true;
    const refresh = refreshSpaceContextData({
      loadSpaces: () => response.promise,
      loadActiveSpace: vi.fn().mockResolvedValue({ space_id: "old-space" }),
      applySpaceContext: vi.fn(),
      isCurrent: () => isCurrent,
    });
    isCurrent = false;
    response.reject(new Error("Old request failed"));
    await expect(refresh).resolves.toBe(false);

    await expect(refreshSpaceContextData({
      loadSpaces: vi.fn().mockRejectedValue(new Error("Current request failed")),
      loadActiveSpace: vi.fn().mockResolvedValue(null),
      isCurrent: () => true,
    })).rejects.toThrow("Current request failed");
  });
});
