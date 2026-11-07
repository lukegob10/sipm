import { expect, it } from "vitest";
import { formatDateTime } from "../../js/shell/paths.js";

it("formats naive UTC and explicit offsets as the same instant", () => {
  const utc = formatDateTime("2026-01-01T12:00:00Z");
  expect(formatDateTime("2026-01-01T12:00:00")).toBe(utc);
  expect(formatDateTime("2026-01-01T07:00:00-05:00")).toBe(utc);
});
it("preserves invalid timestamp fallback and blank values", () => {
  expect(formatDateTime("invalid")).toBe("invalid");
  expect(formatDateTime("")).toBe("");
});
