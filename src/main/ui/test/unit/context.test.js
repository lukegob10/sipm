import { describe, expect, it, vi } from "vitest";

import {
  invalidateDataForSpaceContextChange,
  refreshSpaceContextData,
} from "../../js/shell/context.js";


function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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
});
