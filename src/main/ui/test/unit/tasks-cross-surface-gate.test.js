import { expect, it, vi } from "vitest";
import { saveTasksWorkbenchForm } from "../../js/routes/tasks-workbench/drawer.js";
import { bindSharedActions } from "../../js/routes/my-work/shared-actions.js";

function deferred() {
  let resolve;
  const promise = new Promise((res) => { resolve = res; });
  return { promise, resolve };
}
function setup() {
  document.body.innerHTML = '<form id="editor"><input name="task_id" value="a"><input name="task_name" value="Title"></form><div id="root"><button data-my-work-action="complete">Complete</button></div>';
  const pending = deferred();
  const state = { user: { user_id: "u" }, activeSpace: { space_id: "s" }, tasks: [], tasksWorkbench: { activeTaskId: "a" }, myWork: { selectedTaskId: "a" } };
  const ctx = { state, els: { tasksWorkbenchForm: document.querySelector("#editor"), myWorkRoot: document.querySelector("#root") }, api: vi.fn().mockReturnValue(pending.promise), findUserBySoeid: () => null, setDeliverableFormNotice: vi.fn(), upsertById: vi.fn(), persistTasksWorkbenchUiState: vi.fn(), renderTasksWorkbench: vi.fn(), renderSolutionTasks: vi.fn(), timestampLabel: () => "now" };
  bindSharedActions(ctx, { record: { task: { task_id: "a" } }, refresh: vi.fn() });
  return { ctx, pending };
}
it("blocks My Work action while the same task is saving in Workbench", async () => {
  const { ctx, pending } = setup();
  const saving = saveTasksWorkbenchForm(ctx);
  document.querySelector('[data-my-work-action="complete"]').click();
  expect(ctx.api).toHaveBeenCalledTimes(1);
  expect(ctx.state.myWork.sharedActions.notice.message).toMatch(/already being updated/);
  pending.resolve({ task_id: "a" });
  await saving;
});
it("blocks Workbench save while My Work updates the same task", async () => {
  const { ctx, pending } = setup();
  document.querySelector('[data-my-work-action="complete"]').click();
  await saveTasksWorkbenchForm(ctx);
  expect(ctx.api).toHaveBeenCalledTimes(1);
  expect(ctx.setDeliverableFormNotice).toHaveBeenCalledWith(undefined, expect.stringMatching(/being updated/), "error");
  pending.resolve({ task_id: "a" });
  await vi.waitFor(() => expect(ctx.state.myWork.sharedActions.pendingTaskId).toBe(""));
});
