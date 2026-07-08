import { beforeEach, describe, expect, it } from "vitest";

import { buildBoardMarkup } from "../../js/routes/planning/render.js";
import { boardState } from "../../js/routes/planning/state.js";
import { resetBoardState } from "../../js/routes/planning/storage.js";

describe("planning board render", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetBoardState("space-1");
    boardState.ctx = { state: { workspacePrefs: { showCompleted: false } } };
    boardState.loaded = true;
    boardState.month = "2026-03";
  });

  it("renders project backlog cards, assigned residual projects, solution splits, and title drilldown controls", () => {
    boardState.data = {
      teams: [{ id: "team-1", name: "Delivery" }],
      people: [{ id: "person-1", name: "Taylor", team_id: "team-1", team_name: "Delivery", capacity_fte_months: 1 }],
      projects: [
        {
          id: "project-1",
          title: "Assigned Platform",
          status: "active",
          fte_months: 1,
          allocated_solution_fte_months: 0.25,
          residual_fte_months: 0.75,
          solution_count: 1,
        },
        {
          id: "project-2",
          title: "Backlog Analytics",
          status: "active",
          fte_months: 0.5,
          allocated_solution_fte_months: 0,
          residual_fte_months: 0.5,
          solution_count: 1,
        },
      ],
      solutions: [
        {
          id: "solution-1",
          project_id: "project-1",
          title: "Assigned Data Feed",
          version: "1.0.0",
          status: "active",
          fte_months: 0.25,
          allocated_fte_months: 0.25,
          remaining_fte_months: 0,
        },
        {
          id: "solution-2",
          project_id: "project-2",
          title: "Backlog Dashboard",
          version: "1.0.0",
          status: "active",
          fte_months: 0.5,
          allocated_fte_months: 0,
          remaining_fte_months: 0.5,
        },
      ],
      tasks: [],
      allocations: [
        {
          id: "alloc-project",
          work_item_type: "project",
          work_item_id: "project-1",
          assignee_type: "team",
          assignee_id: "team-1",
          assignee_name: "Delivery",
          month: "2026-03",
          fte_months_allocated: 0.75,
        },
        {
          id: "alloc-solution",
          work_item_type: "solution",
          work_item_id: "solution-1",
          assignee_type: "person",
          assignee_id: "person-1",
          assignee_name: "Taylor",
          month: "2026-03",
          fte_months_allocated: 0.25,
        },
      ],
    };
    boardState.selectedWorkItemType = "solution";
    boardState.selectedWorkItemId = "solution-1";
    boardState.detailDraft = {
      workItemType: "solution",
      workItemId: "solution-1",
      taskId: "",
      title: "Assigned Data Feed",
      fte: "0.25",
      assignmentTarget: "person:person-1",
    };

    const html = buildBoardMarkup();

    expect(html).toContain("Project Backlog");
    expect(html).toContain("Backlog Analytics");
    expect(html).toContain("Backlog Dashboard");
    expect(html).toContain("Assigned Platform");
    expect(html).toContain("Assigned Data Feed");
    expect(html).toContain("Residual 0.75");
    expect(html).toContain('data-wab-action="open-project" data-project-id="project-1"');
    expect(html).toContain('data-wab-action="open-solution" data-solution-id="solution-1"');
    expect(html.match(/data-work-item-id="solution-1"/g)).toHaveLength(1);
    expect(html).not.toContain("Solution Planning");
    expect(html).not.toContain('<option value="person:person-1" selected>');
    expect(html).not.toContain("Task Detail");
    expect(html).not.toContain("wab-modal-shell");
  });
});
