import { describe, expect, it, vi } from "vitest";
import { createTaskEntityController } from "../../js/entities/tasks.js";

function setup(api, overrides = {}) {
  document.body.innerHTML = `<form id="task-form"><input name="task_id"><input name="project_id"><input name="solution_id"><input name="task_name"><textarea name="description"></textarea><input name="github_repo_url"><input name="priority"><input name="due_date"><select name="status"><option value="to_do">To do</option></select><select name="assignee"><option value="">Unassigned</option></select><input name="assignee_user_soeid"><input name="estimate_hours"><input type="checkbox" name="blocked"><textarea name="blocker_note"></textarea><textarea name="acceptance_criteria"></textarea><input name="capacity_hours"><button type="submit">Save</button></form><form id="solution-form"><input name="solution_id" value="s"></form>`;
  const form = document.getElementById("task-form");
  const state = { authed: true, user: { user_id: "u" }, activeSpace: { space_id: "space" }, tasks: [], solutions: [{ solution_id: "s", project_id: "p" }] };
  const els = { taskForm: form, solutionForm: document.getElementById("solution-form") };
  const controller = createTaskEntityController({ state, els, api, findUserBySoeid: () => null, resolveAssigneeSelectValue: () => "", hoursFromFteInput: () => 0, hoursFromNullableFteInput: () => null, fteFromHoursForInput: () => "0", updateTaskRepoPreview: vi.fn(), clearDeliverableFormNotice: vi.fn(), setDeliverableFormNotice: vi.fn(), upsertById: vi.fn(), renderSolutionTasks: vi.fn(), renderDashboard: vi.fn(), renderGantt: vi.fn(), timestampLabel: () => "now" });
  controller.bindTaskForm();
  controller.fillTaskForm({ task_id: "t", solution_id: "s", project_id: "p", task_name: "Task", status: "to_do", assignee: "Former User", assignee_user_soeid: "former", ...overrides });
  return form;
}

describe("task entity unavailable assignments", () => {
  it("preserves unresolved assignment on unrelated edits, and supports explicitly clearing it", async () => {
    const api = vi.fn().mockImplementation(() => Promise.resolve({ task_id: "t", solution_id: "s", project_id: "p", task_name: "Task", status: "to_do", assignee: "Former User", assignee_user_soeid: "former" }));
    const form = setup(api);
    const picker = form.querySelector('[name="assignee"]');
    expect(picker.selectedOptions[0].textContent).toBe("Former User (unavailable)");
    form.querySelector('[name="task_name"]').value = "Edited";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(JSON.parse(api.mock.calls[0][1].body)).not.toHaveProperty("assignee");
    expect(JSON.parse(api.mock.calls[0][1].body)).not.toHaveProperty("assignee_user_soeid");
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(form.querySelector('[name="task_name"]').value).toBe("Task"));
    picker.value = "";
    picker.dispatchEvent(new Event("change", { bubbles: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(JSON.parse(api.mock.calls[1][1].body)).toMatchObject({ assignee: "", assignee_user_soeid: null });
  });

  it("sends only changed fields and retains later edits for the next save", async () => {
    let resolveFirst;
    const first = new Promise((resolve) => { resolveFirst = resolve; });
    const saved = { task_id: "t", solution_id: "s", project_id: "p", task_name: "Changed", status: "in_progress", assignee: "Former User", assignee_user_soeid: "former" };
    const api = vi.fn().mockReturnValueOnce(first).mockResolvedValueOnce(saved);
    const form = setup(api);
    form.querySelector('[name="task_name"]').value = "Changed";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(JSON.parse(api.mock.calls[0][1].body)).toEqual({ task_name: "Changed" });
    form.querySelector('[name="description"]').value = "Newer draft";
    resolveFirst(saved);
    await vi.waitFor(() => expect(form.querySelector('[name="task_name"]').value).toBe("Changed"));
    await vi.waitFor(() => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      expect(api).toHaveBeenCalledTimes(2);
    });
    expect(JSON.parse(api.mock.calls[1][1].body)).toEqual({ description: "Newer draft" });
  });

  it("sends blocker fields together for an explicit unblock", () => {
    const api = vi.fn(() => new Promise(() => {}));
    const form = setup(api, { blocked: true, blocker_note: "Waiting" });
    form.querySelector('[name="blocked"]').checked = false;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(JSON.parse(api.mock.calls[0][1].body)).toEqual({ blocked: false, blocker_note: null });
  });
});
