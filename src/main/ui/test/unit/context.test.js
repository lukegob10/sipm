import { describe, expect, it, vi } from "vitest";

import { invalidateDataForSpaceContextChange } from "../../js/shell/context.js";


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
});
