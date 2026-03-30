import { loadBoard } from "./planning/api.js";
import { bindPlanningBoardEvents } from "./planning/interactions.js";
import { renderPlanningView } from "./planning/render.js";
import { syncDetailDraft, selectedTask } from "./planning/selection.js";
import { boardState, setPlanningRerender } from "./planning/state.js";
import { resetBoardState } from "./planning/storage.js";

setPlanningRerender(() => {
  if (boardState.ctx) renderPlanning(boardState.ctx);
});

export function renderPlanning(ctx) {
  const renderStartedAt = performance.now();
  boardState.ctx = ctx;
  const root = ctx.els?.planningBoard;
  if (!root) return;

  const nextSpaceId = ctx.state?.activeSpace?.space_id || "";
  if (nextSpaceId !== boardState.spaceId) {
    resetBoardState(nextSpaceId);
  }

  bindPlanningBoardEvents();

  if (!boardState.loaded && !boardState.loading) {
    void loadBoard(ctx, { allocationsOnly: false });
  }

  const activeTask = selectedTask();
  if (activeTask && boardState.detailDraft.taskId !== activeTask.id) {
    syncDetailDraft(activeTask);
  }

  renderPlanningView(root);
  if (typeof ctx?.noteViewRendered === "function") {
    ctx.noteViewRendered(performance.now() - renderStartedAt);
  }
}

export function render(ctx) {
  renderPlanning(ctx);
}
