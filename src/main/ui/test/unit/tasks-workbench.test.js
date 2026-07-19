import { describe, expect, it } from "vitest";

import { renderTasksWorkbench } from "../../js/routes/tasks-workbench.js";

describe("tasks workbench route", () => {
  it("renders task identity and project/solution context in separate columns", () => {
    document.body.innerHTML = '<div id="tasks-workbench-table"></div>';
    const table = document.getElementById("tasks-workbench-table");

    renderTasksWorkbench({
      els: { tasksWorkbenchTable: table },
      rows: [{
        task_id: "task-1",
        task_name: "Prepare release notes",
        project_id: "project-1",
        project_name: "Platform Renewal",
        solution_id: "solution-1",
        solution_name: "Case Management",
        status: "active",
        assignee: "Engineer One",
        due_date: "2026-07-31",
        priority: 2,
        urgency_score: 42,
      }],
      activeTaskId: "",
      selectedIds: new Set(),
      sort: "default",
      formatStatus: (status) => status,
      summary: { total: 1, visible: 1 },
    });

    const headers = [...table.querySelectorAll("thead th")]
      .map((cell) => cell.querySelector("button span")?.textContent.trim() || cell.textContent.trim());
    expect(headers).toEqual(["", "Task", "Project / Solution", "Status", "Assignee", "Due", "Priority", "Urgency"]);

    const cells = table.querySelectorAll("tbody td");
    expect(cells).toHaveLength(8);
    expect(cells[1].textContent.trim()).toBe("Prepare release notes");
    expect(cells[1].querySelector(".task-workbench-context")).toBeNull();
    expect(cells[2].textContent).toContain("Platform Renewal");
    expect(cells[2].textContent).toContain("Case Management");
    expect(cells[2].querySelectorAll(".task-workbench-context-link")).toHaveLength(2);
  });
});
