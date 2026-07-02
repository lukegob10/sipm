import {
  boardState,
  defaultDetailDraft,
  rerenderPlanning,
} from "./state.js";
import {
  formatFte,
  visibleBoardProjects,
  visibleBoardSolutions,
  visibleBoardTasks,
} from "./common.js";
import { persistViewState } from "./storage.js";

export function selectedWorkItem() {
  const type = String(boardState.selectedWorkItemType || (boardState.selectedTaskId ? "task" : "")).trim();
  const id = String(boardState.selectedWorkItemId || boardState.selectedTaskId || "").trim();
  if (!type || !id) return null;
  if (type === "project") return visibleBoardProjects().find((project) => project.id === id) || null;
  if (type === "solution") return visibleBoardSolutions().find((solution) => solution.id === id) || null;
  return visibleBoardTasks().find((task) => task.id === id) || null;
}

export function selectedTask() {
  return selectedWorkItem();
}

export function syncDetailDraft(workItem = selectedWorkItem()) {
  if (!workItem) {
    boardState.detailDraft = defaultDetailDraft();
    return;
  }
  const type = boardState.selectedWorkItemType || (boardState.selectedTaskId ? "task" : "");
  const id = workItem.id || "";
  boardState.detailDraft = {
    workItemType: type,
    workItemId: id,
    taskId: type === "task" ? id : "",
    title: workItem.title || "",
    fte: formatFte(workItem.remaining_fte_months ?? workItem.residual_fte_months ?? workItem.fte_months),
    assignmentTarget: boardState.detailDraft.workItemId === id ? (boardState.detailDraft.assignmentTarget || "") : "",
  };
}

export function restoreTaskFocusSoon(workItemId = boardState.focusReturnTaskId) {
  if (!workItemId) return;
  window.requestAnimationFrame(() => {
    const root = boardState.ctx?.els?.planningBoard;
    if (!root) return;
    const target = Array.from(root.querySelectorAll(".wab-work-chip,.wab-task-chip")).find(
      (node) => (
        node.getAttribute("data-work-item-id") === workItemId
        || node.getAttribute("data-task-id") === workItemId
      )
    );
    if (!target || typeof target.focus !== "function") return;
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  });
}

export function selectWorkItem(workItemType, workItemId, { focusReturnTaskId = workItemId } = {}) {
  const type = String(workItemType || "").trim();
  const id = String(workItemId || "").trim();
  boardState.selectedWorkItemType = type;
  boardState.selectedWorkItemId = id;
  boardState.selectedTaskId = type === "task" ? id : "";
  boardState.focusReturnTaskId = String(focusReturnTaskId || boardState.focusReturnTaskId || "");
  syncDetailDraft();
  persistViewState();
  rerenderPlanning();
}

export function selectTask(taskId, { focusReturnTaskId = taskId } = {}) {
  selectWorkItem("task", taskId, { focusReturnTaskId });
}

export function closeWorkItemDetail({ restoreFocus = true } = {}) {
  if (!boardState.selectedWorkItemId && !boardState.selectedTaskId) return;
  const focusTargetId = restoreFocus ? (boardState.focusReturnTaskId || boardState.selectedWorkItemId || boardState.selectedTaskId) : "";
  boardState.selectedWorkItemType = "";
  boardState.selectedWorkItemId = "";
  boardState.selectedTaskId = "";
  boardState.detailDraft = defaultDetailDraft();
  persistViewState();
  rerenderPlanning();
  if (focusTargetId) restoreTaskFocusSoon(focusTargetId);
}

export function closeTaskDetail(options = {}) {
  closeWorkItemDetail(options);
}
