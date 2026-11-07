import { expect, it } from "vitest";
import { renderSolutionActivityItems } from "../../js/entities/solution-rendering.js";
import { renderTasksWorkbenchActivity } from "../../js/routes/tasks-workbench/drawer.js";

it("renders naive UTC, Z, and equivalent offset timestamps as the same local time", () => {
  const render = (created_at) => renderSolutionActivityItems([{ action: "update", created_at }]);
  expect(render("2026-01-01T12:00:00")).toBe(render("2026-01-01T12:00:00Z"));
  expect(render("2026-01-01T07:00:00-05:00")).toBe(render("2026-01-01T12:00:00Z"));
});

it("renders workbench activity using UTC for naive timestamps and hides invalid times", async () => {
  const activity = document.createElement("div");
  const ctx = { state: { tasksWorkbench: {} }, els: { tasksWorkbenchActivity: activity }, escapeHtml: String,
    api: async () => ["2026-01-01T12:00:00", "2026-01-01T12:00:00Z", "2026-01-01T07:00:00-05:00", "bad"].map((created_at) => ({ action: "update", created_at })) };
  await renderTasksWorkbenchActivity(ctx, "one");
  const times = [...activity.querySelectorAll(".activity-meta")].map((el) => el.textContent);
  expect(times[0]).toBe(times[1]);
  expect(times[2]).toBe(times[1]);
  expect(times[3]).not.toContain("Invalid Date");
});
it("hides invalid solution activity times", () => {
  expect(renderSolutionActivityItems([{ action: "update", created_at: "bad" }])).not.toContain("Invalid Date");
});
