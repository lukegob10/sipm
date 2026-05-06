import { describe, expect, test } from "vitest";

import {
  dayNumberToIso,
  daysBetweenDateOnly,
  parseDateOnly,
} from "../../js/utils/date-only.js";

describe("date-only utilities", () => {
  test("parseDateOnly is timezone stable for YYYY-MM-DD values", () => {
    const parsed = parseDateOnly("2026-04-01");

    expect(parsed).toMatchObject({
      year: 2026,
      month: 4,
      monthIndex: 3,
      day: 1,
      iso: "2026-04-01",
    });
    expect(dayNumberToIso(parsed.dayNumber)).toBe("2026-04-01");
  });

  test("rejects invalid dates and computes day ranges", () => {
    expect(parseDateOnly("2026-02-30")).toBeNull();
    const start = parseDateOnly("2026-04-01").date;
    const end = parseDateOnly("2026-04-10").date;
    expect(daysBetweenDateOnly(start, end)).toBe(9);
  });
});
