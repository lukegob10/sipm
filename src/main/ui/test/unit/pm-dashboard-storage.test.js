import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ensureActiveSection,
  ensureCapacityMonth,
  persistActiveSection,
  persistCapacityMonth,
  readStoredActiveSection,
  readStoredCapacityMonth,
} from "../../js/routes/pm-dashboard/storage.js";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("PM dashboard preferences storage", () => {
  it("uses defaults and continues rendering when storage access throws", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("Storage blocked", "SecurityError");
    });
    expect(readStoredActiveSection()).toBe("actions");
    expect(readStoredCapacityMonth("space")).toBe("");
    expect(() => persistActiveSection("health")).not.toThrow();
    expect(() => persistCapacityMonth("space", "2026-10")).not.toThrow();
    const state = { activeSection: "", capacitySpaceId: "", capacityMonth: "" };
    expect(ensureActiveSection(state)).toBe("actions");
    expect(ensureCapacityMonth(state, "space")).toMatch(/^\d{4}-\d{2}$/);
  });

  it("persists and restores valid per-space month and active section", () => {
    persistActiveSection("health");
    persistCapacityMonth("space-a", "2026-10");
    persistCapacityMonth("space-b", "2027-02");
    expect(readStoredActiveSection()).toBe("health");
    expect(readStoredCapacityMonth("space-a")).toBe("2026-10");
    expect(readStoredCapacityMonth("space-b")).toBe("2027-02");
  });
});
