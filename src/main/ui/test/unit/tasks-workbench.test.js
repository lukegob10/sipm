import { describe, expect, it, vi } from "vitest";

import { renderTasksWorkbench } from "../../js/routes/tasks-workbench.js";
import { saveTasksWorkbenchForm } from "../../js/routes/tasks-workbench/drawer.js";
import { populateTasksWorkbenchOptions } from "../../js/routes/tasks-workbench/options.js";

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

  it("saves a manually entered assignee SOEID for My Work assignment", async () => {
    document.body.innerHTML = `
      <form id="tasks-workbench-form">
        <input name="task_id" value="task-1" />
        <input name="task_name" value="Prepare release notes" />
        <textarea name="description"></textarea>
        <textarea name="acceptance_criteria"></textarea>
        <select name="status"><option value="to_do" selected>To do</option></select>
        <input name="priority" value="2" />
        <input name="due_date" value="" />
        <select name="assignee"><option value="">Unassigned</option></select>
        <input name="assignee_user_soeid" value=" tu12345 " />
        <input type="checkbox" name="blocked" />
        <textarea name="blocker_note"></textarea>
      </form>
      <p id="tasks-workbench-form-status"></p>
    `;
    const api = vi.fn().mockResolvedValue({
      task_id: "task-1",
      assignee: "Test User",
      assignee_user_soeid: "tu12345",
    });
    const ctx = {
      state: { tasks: [], tasksWorkbench: {} },
      els: {
        tasksWorkbenchForm: document.getElementById("tasks-workbench-form"),
        tasksWorkbenchFormStatus: document.getElementById("tasks-workbench-form-status"),
      },
      api,
      upsertById: vi.fn(),
      findUserBySoeid: (soeid) => soeid === "tu12345"
        ? { soeid: "tu12345", display_name: "Test User" }
        : null,
      renderTasksWorkbench: vi.fn(),
      renderSolutionTasks: vi.fn(),
      setDeliverableFormNotice: vi.fn(),
      timestampLabel: () => "now",
      persistTasksWorkbenchUiState: vi.fn(),
    };

    await saveTasksWorkbenchForm(ctx);

    expect(api).toHaveBeenCalledWith("/tasks/task-1", expect.objectContaining({ method: "PATCH" }));
    const payload = JSON.parse(api.mock.calls[0][1].body);
    expect(payload.assignee).toBe("Test User");
    expect(payload.assignee_user_soeid).toBe("tu12345");
  });

  it("keeps the assignee picker and editable SOEID synchronized", () => {
    document.body.innerHTML = `
      <form id="tasks-workbench-form">
        <select name="assignee"></select>
        <input name="assignee_user_soeid" />
      </form>
    `;
    const form = document.getElementById("tasks-workbench-form");
    const select = form.querySelector('[name="assignee"]');
    const soeidInput = form.querySelector('[name="assignee_user_soeid"]');
    populateTasksWorkbenchOptions({
      state: {
        users: [{ soeid: "tu12345", display_name: "Test User" }],
      },
      els: { tasksWorkbenchForm: form },
      normalizeTasksWorkbenchUiState: vi.fn(),
    });

    select.value = "tu12345";
    select.dispatchEvent(new Event("change"));
    expect(soeidInput.value).toBe("tu12345");

    soeidInput.value = "TU12345";
    soeidInput.dispatchEvent(new Event("input"));
    expect(select.value).toBe("tu12345");

    soeidInput.value = "external-user";
    soeidInput.dispatchEvent(new Event("input"));
    expect(select.value).toBe("");
  });
});
