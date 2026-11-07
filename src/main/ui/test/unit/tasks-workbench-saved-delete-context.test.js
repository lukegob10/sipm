import { afterEach, describe, expect, it, vi } from "vitest";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";
import { bindTasksWorkbenchSavedViewControls } from "../../js/routes/tasks-workbench/saved-views.js";

afterEach(() => { document.body.innerHTML = ""; localStorage.clear(); });

function setup() {
  document.body.innerHTML = '<select id="select"></select><input id="name"><button id="delete"></button><p id="status"></p>';
  let finish;
  const confirmation = new Promise((resolve) => { finish = resolve; });
  const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" },
    tasksWorkbench: { selectedSavedViewId: "one", savedViews: [{ view_id: "one", name: "Private view", preset: "all", filters: {} }] } };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const persistTasksWorkbenchUiState = vi.fn();
  const ctx = { state, els: { tasksWorkbenchSavedSelect: document.getElementById("select"), tasksWorkbenchSavedName: document.getElementById("name"),
    tasksWorkbenchSavedDelete: document.getElementById("delete"), tasksWorkbenchSavedStatus: document.getElementById("status") },
    normalize: (v) => String(v || "").toLowerCase(), activeSpaceId: () => state.activeSpace.space_id,
    tasksWorkbenchSavedViewsKeyPrefix: "test", showConfirmModal: () => confirmation, persistTasksWorkbenchUiState,
    escapeHtml: (v) => String(v) };
  bindTasksWorkbenchSavedViewControls(ctx);
  return { state, lifetime, ctx, finish, persistTasksWorkbenchUiState };
}

describe("saved view delete context", () => {
  it.each(["session", "space", "selection", "edited"])("ignores confirmed deletion after %s changes", async (change) => {
    const h = setup();
    h.ctx.els.tasksWorkbenchSavedDelete.click();
    if (change === "session" || change === "space") h.lifetime[change] += 1;
    if (change === "selection") h.state.tasksWorkbench.selectedSavedViewId = "other";
    if (change === "edited") h.state.tasksWorkbench.savedViews[0].name = "Updated view";
    h.finish(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(h.state.tasksWorkbench.savedViews).toHaveLength(1);
    expect(h.state.tasksWorkbench.selectedSavedViewId).toBe(change === "selection" ? "other" : "one");
    expect(h.ctx.els.tasksWorkbenchSavedStatus.textContent).toBe("");
    expect(h.persistTasksWorkbenchUiState).not.toHaveBeenCalled();
  });

  it("deletes after a same-session refresh", async () => {
    const h = setup();
    h.ctx.els.tasksWorkbenchSavedDelete.click();
    h.state.user = { user_id: "user-1" };
    h.state.activeSpace = { space_id: "space-1" };
    h.finish(true);
    await vi.waitFor(() => expect(h.state.tasksWorkbench.savedViews).toHaveLength(0));
    expect(h.ctx.els.tasksWorkbenchSavedStatus.textContent).toContain('Deleted "Private view"');
  });
});
