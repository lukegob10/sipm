import { describe, expect, it } from "vitest";

import { buildGanttRows, dateRangesOverlap, resolveGanttTimelineScale } from "../../js/routes/gantt.js";


describe("gantt route helpers", () => {
  it("detects overlapping date ranges", () => {
    expect(dateRangesOverlap(10, 15, 12, 20)).toBe(true);
    expect(dateRangesOverlap(10, 15, 15, 20)).toBe(true);
    expect(dateRangesOverlap(10, 15, 16, 20)).toBe(false);
  });

  it("fits ranges up to one year before enabling long-range scroll", () => {
    const halfYear = resolveGanttTimelineScale({ totalDays: 181 }, 1200, 540);
    expect(halfYear.fitToArea).toBe(true);
    expect(halfYear.trackWidth).toBe(658);
    expect(halfYear.dayWidth).toBeCloseTo(658 / 181);

    const longRange = resolveGanttTimelineScale({ totalDays: 400 }, 1200, 540);
    expect(longRange.fitToArea).toBe(false);
    expect(longRange.trackWidth).toBe(1400);
    expect(longRange.dayWidth).toBeCloseTo(3.5);
  });

  it("builds project, solution, and subcomponent rows for overlapping work", () => {
    const { rows } = buildGanttRows({
      ganttWindow: { from: "2026-04-03", to: "2026-04-06" },
      projects: [
        {
          project_id: "p1",
          project_name: "Portfolio Project",
          sponsor: "Sponsor",
          status: "active",
          priority: 2,
        },
      ],
      solutions: [
        {
          solution_id: "s1",
          project_id: "p1",
          solution_name: "Platform Solution",
          owner: "Owner",
          assignee: "Engineer",
          status: "active",
          priority: 1,
          planned_start_date: "2026-04-01",
          due_date: "2026-04-10",
        },
        {
          solution_id: "s2",
          project_id: "p1",
          solution_name: "Later Solution",
          owner: "Owner",
          status: "active",
          priority: 3,
          planned_start_date: "2026-07-01",
          due_date: "2026-07-10",
        },
      ],
      subcomponents: [
        {
          subcomponent_id: "sc1",
          project_id: "p1",
          solution_id: "s1",
          subcomponent_name: "Launch Task",
          assignee: "Assignee",
          status: "to_do",
          priority: 4,
          due_date: "2026-04-05",
        },
      ],
      collapsedKeys: new Set(),
    });

    expect(rows.map((row) => row.type)).toEqual(["project", "solution", "subcomponent"]);
    expect(rows[0]).toMatchObject({
      type: "project",
      id: "p1",
      assignee: "Sponsor",
      priority: 2,
      childCount: 1,
      range: { startIso: "2026-04-01", endIso: "2026-04-10" },
    });
    expect(rows[1]).toMatchObject({
      type: "solution",
      id: "s1",
      assignee: "Engineer",
      priority: 1,
    });
    expect(rows[2]).toMatchObject({
      type: "subcomponent",
      id: "sc1",
      assignee: "Assignee",
      priority: 4,
      milestone: true,
      range: { startIso: "2026-04-05", endIso: "2026-04-05" },
    });
  });

  it("collapses child rows under owning entities", () => {
    const { rows } = buildGanttRows({
      ganttWindow: { from: "2026-04-01", to: "2026-04-30" },
      projects: [{ project_id: "p1", project_name: "Project" }],
      solutions: [
        {
          solution_id: "s1",
          project_id: "p1",
          solution_name: "Solution",
          due_date: "2026-04-10",
        },
      ],
      subcomponents: [
        {
          subcomponent_id: "sc1",
          project_id: "p1",
          solution_id: "s1",
          subcomponent_name: "Task",
          due_date: "2026-04-12",
        },
      ],
      collapsedKeys: new Set(["solution:s1"]),
    });

    expect(rows.map((row) => row.key)).toEqual(["project:p1", "solution:s1"]);
    expect(rows[1].collapsed).toBe(true);
  });
});
