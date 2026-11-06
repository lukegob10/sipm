import { describe, expect, it, vi } from "vitest";
import { createTaskEntityController } from "../../js/entities/tasks.js";

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function taskEditor() {
  const inputs = ["task_name", "description", "github_repo_url", "priority", "due_date", "assignee_user_soeid", "estimate_hours", "blocker_note", "acceptance_criteria", "capacity_hours"];
  document.body.innerHTML = `
    <form id="task-form" class="hidden">
      <input type="hidden" name="task_id"><input type="hidden" name="project_id"><input type="hidden" name="solution_id">
      ${inputs.map((name) => `<input name="${name}">`).join("")}
      <select name="status"><option value="to_do">To do</option></select>
      <select name="assignee"><option value="">Unassigned</option></select>
      <input type="checkbox" name="blocked">
    </form>
    <button id="task-delete" type="button">Delete</button><button id="task-submit" type="button">Save</button>
    <form id="solution-form"><input name="solution_id" value="solution-1"></form>
  `;
  const state = {
    authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" },
    solutions: [{ solution_id: "solution-1", project_id: "project-1" }], tasks: [],
  };
  const els = {
    taskForm: document.getElementById("task-form"), deleteTaskBtn: document.getElementById("task-delete"),
    taskSubmitBtn: document.getElementById("task-submit"), solutionForm: document.getElementById("solution-form"),
  };
  const deps = {
    state, els, api: vi.fn().mockResolvedValue({ task_id: "new-task", solution_id: "solution-1", project_id: "project-1", task_name: "New task", status: "to_do" }),
    findUserBySoeid: () => null, resolveAssigneeSelectValue: () => "",
    hoursFromFteInput: (value) => Number(value || 0), hoursFromNullableFteInput: (value) => value ? Number(value) : null,
    fteFromHoursForInput: (value) => String(value || 0), updateTaskRepoPreview: vi.fn(),
    clearDeliverableFormNotice: vi.fn(), setDeliverableFormNotice: vi.fn(), upsertById: vi.fn(),
    renderSolutionTasks: vi.fn(), renderDashboard: vi.fn(), renderGantt: vi.fn(), timestampLabel: () => "now",
    showConfirmModal: vi.fn().mockResolvedValueOnce(true).mockResolvedValue(false),
  };
  const deleted = { cancelled: false, deletedIds: ["task-1"], failed: [] };
  // The shared delete operation owns the destructive-action confirmation.
  deps.deleteTasksById = vi.fn(async () => await deps.showConfirmModal({ title: "Delete Task?" })
    ? deleted : { cancelled: true, deletedIds: [], failed: [] });
  const controller = createTaskEntityController(deps);
  controller.bindTaskForm();
  const original = { task_id: "task-1", project_id: "project-1", solution_id: "solution-1", task_name: "Original task", status: "to_do" };
  controller.fillTaskForm(original);
  const name = els.taskForm.querySelector('[name="task_name"]');
  name.value = "Unsaved edit";
  name.dispatchEvent(new Event("input", { bubbles: true }));
  return { controller, deps, name, original, deleted };
}

describe("task editor deletion lifecycle", () => {
  it("clears a confirmed deleted task without asking to discard it again", async () => {
    const { deps, name } = taskEditor();
    deps.els.deleteTaskBtn.click();
    await vi.waitFor(() => expect(deps.renderDashboard).toHaveBeenCalled());

    expect(deps.showConfirmModal).toHaveBeenCalledExactlyOnceWith({ title: "Delete Task?" });
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("");
    expect(name.value).toBe("");
    expect(deps.els.taskForm.hasAttribute("data-dirty")).toBe(false);
    expect(deps.els.deleteTaskBtn.disabled).toBe(true);
    expect(deps.els.taskSubmitBtn.textContent).toBe("Create Task");

    name.value = "New task";
    name.dispatchEvent(new Event("input", { bubbles: true }));
    deps.els.taskForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(deps.api).toHaveBeenCalledWith("/solutions/solution-1/tasks", expect.objectContaining({ method: "POST" }));
  });

  it("keeps the draft when deletion is cancelled", async () => {
    const { deps, name } = taskEditor();
    deps.showConfirmModal.mockReset().mockResolvedValue(false);
    deps.els.deleteTaskBtn.click();
    await vi.waitFor(() => expect(deps.showConfirmModal).toHaveBeenCalledTimes(1));
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("task-1");
    expect(name.value).toBe("Unsaved edit");
    expect(deps.els.taskForm.hasAttribute("data-dirty")).toBe(true);
    expect(deps.renderDashboard).not.toHaveBeenCalled();
  });

  it("keeps the draft when deletion fails", async () => {
    const { deps, name } = taskEditor();
    deps.deleteTasksById.mockResolvedValue({ cancelled: false, deletedIds: [], failed: [{ error: new Error("Unavailable") }] });
    deps.els.deleteTaskBtn.click();
    await vi.waitFor(() => expect(deps.setDeliverableFormNotice).toHaveBeenCalledWith(undefined, "Delete failed: Unavailable", "error"));
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("task-1");
    expect(name.value).toBe("Unsaved edit");
    expect(deps.els.taskForm.hasAttribute("data-dirty")).toBe(true);
  });

  it("preserves another task opened while deletion finishes", async () => {
    const { controller, deps, name, original, deleted } = taskEditor();
    const pending = deferred();
    deps.deleteTasksById.mockReturnValue(pending.promise);
    deps.els.deleteTaskBtn.click();
    controller.fillTaskForm({ ...original, task_id: "task-2", task_name: "Another task" });
    pending.resolve(deleted);
    await vi.waitFor(() => expect(deps.renderDashboard).toHaveBeenCalled());
    expect(deps.els.taskForm.querySelector('[name="task_id"]').value).toBe("task-2");
    expect(name.value).toBe("Another task");
    expect(deps.showConfirmModal).not.toHaveBeenCalled();
  });
});
