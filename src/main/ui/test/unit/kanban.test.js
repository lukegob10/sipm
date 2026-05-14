import { describe, expect, it } from "vitest";

import { renderKanban } from "../../js/routes/kanban.js";

describe("kanban route", () => {
  it("escapes backend-provided card and lane text before rendering", () => {
    document.body.innerHTML = '<div id="view-kanban"><div id="kanban-board"></div></div>';

    const ctx = {
      state: {
        phases: [
          {
            phase_id: "phase-1",
            phase_group: '<img src=x onerror="alert(1)">',
            phase_name: "<b>Design</b>",
            sequence: 1,
          },
        ],
        projects: [
          {
            project_id: "project-1",
            project_name: "Project",
          },
        ],
      },
      els: {
        kanbanBoard: document.getElementById("kanban-board"),
      },
      filteredSolutionsForKanban: () => [
        {
          solution_id: "solution-1",
          solution_name: "<script>alert(1)</script>",
          project_id: "project-1",
          current_phase: "phase-1",
          version: "<em>v1</em>",
          owner: '<img src=x onerror="alert(2)">',
          assignee: "<svg onload=alert(3)>",
          priority: '<iframe src="bad"></iframe>',
          due_date: '<a href="javascript:alert(4)">today</a>',
          status: '<marquee>active</marquee>',
        },
      ],
      phaseDisplayName: (phaseId) =>
        ctx.state.phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
      formatStatus: (status) => status,
    };

    renderKanban(ctx);

    const board = ctx.els.kanbanBoard;
    expect(board.querySelector("script")).toBeNull();
    expect(board.querySelector("img")).toBeNull();
    expect(board.querySelector("svg")).toBeNull();
    expect(board.querySelector("iframe")).toBeNull();
    expect(board.innerHTML).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(board.innerHTML).toContain("&lt;img src=x onerror=");
    expect(board.innerHTML).toContain("&lt;b&gt;Design&lt;/b&gt;");
    expect(board.innerHTML).toContain("&lt;marquee&gt;active&lt;/marquee&gt;");
  });
});
