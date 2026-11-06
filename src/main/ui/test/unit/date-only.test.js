import { describe, expect, test } from "vitest";

import {
  dayNumberToIso,
  daysBetweenDateOnly,
  localDateFromParts,
  parseDateOnly,
  startOfDateOnlyDay,
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

  test.each(["0001-01-01", "0004-02-29", "0099-12-31", "0100-03-01", "9999-12-31"])(
    "round-trips supported date %s", (iso) => {
      const parsed = parseDateOnly(iso);
      expect(parsed).not.toBeNull();
      expect(dayNumberToIso(parsed.dayNumber)).toBe(iso);
    },
  );

  test("rejects year zero and invalid Gregorian leap days", () => {
    expect(parseDateOnly("0000-01-01")).toBeNull();
    expect(parseDateOnly("0001-02-29")).toBeNull();
    expect(parseDateOnly("0100-02-29")).toBeNull();
    expect(parseDateOnly("0004-02-29")).not.toBeNull();
    expect(parseDateOnly("2000-02-29")).not.toBeNull();
  });

  test("constructs local dates with early years and normalizes date-only days", () => {
    const local = localDateFromParts(1, 0, 2);
    expect(local.getFullYear()).toBe(1);
    expect(local.getMonth()).toBe(0);
    expect(local.getDate()).toBe(2);
    expect(startOfDateOnlyDay(local).toISOString()).toBe("0001-01-02T00:00:00.000Z");
    expect(localDateFromParts(99, 12, 1).getFullYear()).toBe(100);
    expect(localDateFromParts(100, -1, 1).getFullYear()).toBe(99);
  });

  test("does not format a day outside the supported date range", () => {
    const first = parseDateOnly("0001-01-01").dayNumber;
    const last = parseDateOnly("9999-12-31").dayNumber;
    expect(dayNumberToIso(first - 1)).toBe("");
    expect(dayNumberToIso(last + 1)).toBe("");
  });

  test("accepts valid ISO timestamps by their date prefix and rejects malformed suffixes", () => {
    for (const value of ["2026-04-01T23:59:59", "2026-04-01T23:59:59.123456Z", "2026-04-01T23:59:59-05:00"]) {
      expect(parseDateOnly(value)?.iso).toBe("2026-04-01");
    }
    for (const value of ["2026-04-01garbage", "2026-04-01T99:99:99Z", "2026-04-01T12:00:00-99:99", "2026-04-01T12:00:00Zjunk"]) {
      expect(parseDateOnly(value)).toBeNull();
    }
  });

  test("rejects invalid dates and computes day ranges", () => {
    expect(parseDateOnly("2026-02-30")).toBeNull();
    const start = parseDateOnly("2026-04-01").date;
    const end = parseDateOnly("2026-04-10").date;
    expect(daysBetweenDateOnly(start, end)).toBe(9);
  });
});
