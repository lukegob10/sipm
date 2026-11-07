import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { Linter } from "eslint";
import { expect, it, vi } from "vitest";

const source = readFileSync(resolve("src/main/ui/js/app.js"), "utf8");
let helper;
const diagnostics = new Linter().verify(source, [{
  languageOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: { extract: { rules: { actionability: { create: () => ({
    FunctionDeclaration(node) {
      if (node.id.name === "deriveTaskActionability") helper = source.slice(...node.range);
    },
  }) } } } },
  rules: { "extract/actionability": "error" },
}]);
if (diagnostics.length || !helper) throw new Error("Could not load the task actionability helper");

it("treats priority zero as the highest urgency in fallback calculations", () => {
  const actionability = runInNewContext(`${helper}\nderiveTaskActionability;`, {
    isCompletedTaskStatus: () => false,
    numberOr: (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback,
  });
  expect(actionability({ priority: 0 }).urgency_score).toBe(75);
  expect(actionability({ priority: 3 }).urgency_score).toBe(45);
});

it("matches the server urgency score for work due in fourteen days", () => {
  vi.useFakeTimers();
  try {
    vi.setSystemTime(new Date(2026, 9, 1, 12));
    const actionability = runInNewContext(`${helper}\nderiveTaskActionability;`, {
      Date,
      isCompletedTaskStatus: () => false,
      numberOr: (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback,
    });
    expect(actionability({ priority: 3, due_date: "2026-10-15" }).urgency_score).toBe(53);
  } finally {
    vi.useRealTimers();
  }
});


it("counts calendar days across daylight saving and stale timestamps", () => {
  const previousTimezone = process.env.TZ;
  process.env.TZ = "America/New_York";
  vi.useFakeTimers();
  try {
    vi.setSystemTime(new Date(2026, 9, 31, 12));
    const actionability = runInNewContext(`${helper}\nderiveTaskActionability;`, {
      Date,
      isCompletedTaskStatus: () => false,
      numberOr: (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback,
    });
    expect(actionability({ priority: 3, due_date: "2026-11-02" }).urgency_score).toBe(71);
    expect(actionability({ priority: 3, updated_at: "2026-10-23T10:00:00" }).is_stale).toBe(true);
  } finally {
    vi.useRealTimers();
    if (previousTimezone === undefined) delete process.env.TZ;
    else process.env.TZ = previousTimezone;
  }
});
