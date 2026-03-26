import {
  boardState,
  defaultDetailDraft,
  rerenderPlanning,
} from "./state.js";
import { formatFte, visibleBoardTasks } from "./common.js";
import { persistViewState } from "./storage.js";

export function selectedTask() {
  return visibleBoardTasks().find((task) => task.id === boardState.selectedTaskId) || null;
}

export function syncDetailDraft(task = selectedTask()) {
  if (!task) {
    boardState.detailDraft = defaultDetailDraft();
    return;
  }
  boardState.detailDraft = {
    taskId: task.id,
    title: task.title || "",
    fte: formatFte(task.fte_months),
    assignmentTarget: boardState.detailDraft.taskId === task.id ? (boardState.detailDraft.assignmentTarget || "") : "",
  };
}

export function restoreTaskFocusSoon(taskId = boardState.focusReturnTaskId) {
  if (!taskId) return;
  window.requestAnimationFrame(() => {
    const root = boardState.ctx?.els?.planningBoard;
    if (!root) return;
    const target = Array.from(root.querySelectorAll(".wab-task-chip")).find(
      (node) => node.getAttribute("data-task-id") === taskId
    );
    if (!target || typeof target.focus !== "function") return;
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  });
}

export function selectTask(taskId, { focusReturnTaskId = taskId } = {}) {
  boardState.selectedTaskId = String(taskId || "");
  boardState.focusReturnTaskId = String(focusReturnTaskId || boardState.focusReturnTaskId || "");
  syncDetailDraft();
  persistViewState();
  rerenderPlanning();
}

export function closeTaskDetail({ restoreFocus = true } = {}) {
  if (!boardState.selectedTaskId) return;
  const focusTargetId = restoreFocus ? (boardState.focusReturnTaskId || boardState.selectedTaskId) : "";
  boardState.selectedTaskId = "";
  boardState.detailDraft = defaultDetailDraft();
  persistViewState();
  rerenderPlanning();
  if (focusTargetId) restoreTaskFocusSoon(focusTargetId);
}
