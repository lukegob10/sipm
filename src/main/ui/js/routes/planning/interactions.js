import {
  DRAG_KIND_PERSON,
  DRAG_KIND_TASK,
  UNASSIGNED_TEAM_ID,
  boardState,
} from "./state.js";
import { rerenderPlanning } from "./state.js";
import {
  assignSelectedTaskToTarget,
  createAssignment,
  loadBoard,
  moveAssignment,
  movePersonToTeam,
  onPlanningAction,
  unassignAllocation,
  unassignTask,
} from "./api.js";
import { persistViewState } from "./storage.js";
import { closeTaskDetail, selectTask } from "./selection.js";

function getDropzone(eventTarget) {
  if (!eventTarget?.closest) return null;
  const zone = eventTarget.closest("[data-dropzone]");
  if (!zone) return null;
  return {
    el: zone,
    type: zone.getAttribute("data-dropzone") || "",
    personId: zone.getAttribute("data-person-id") || "",
    teamId: zone.getAttribute("data-team-id") || "",
  };
}

function eventElement(target) {
  if (target instanceof Element) return target;
  if (target instanceof Node) return target.parentElement;
  return null;
}

function plainDragData(dataTransfer) {
  return String(dataTransfer?.getData("text/plain") || "").trim();
}

function activeDragItem() {
  return boardState.dragItem && typeof boardState.dragItem === "object" ? boardState.dragItem : null;
}

function dragKindFromDataTransfer(dataTransfer) {
  const dragItem = activeDragItem();
  if (dragItem?.kind === DRAG_KIND_PERSON || dragItem?.kind === DRAG_KIND_TASK) {
    return dragItem.kind;
  }
  const kind = String(dataTransfer?.getData("application/x-wab-kind") || "").trim();
  if (kind === DRAG_KIND_PERSON) return DRAG_KIND_PERSON;
  if (kind === DRAG_KIND_TASK) return DRAG_KIND_TASK;
  if (String(dataTransfer?.getData("application/x-wab-person-id") || "").trim()) return DRAG_KIND_PERSON;
  if (String(dataTransfer?.getData("application/x-wab-task-id") || "").trim()) return DRAG_KIND_TASK;
  const plain = plainDragData(dataTransfer);
  if (plain.startsWith("person:")) return DRAG_KIND_PERSON;
  if (plain.startsWith("task:")) return DRAG_KIND_TASK;
  if (plain) return DRAG_KIND_TASK;
  return DRAG_KIND_TASK;
}

function personIdFromDataTransfer(dataTransfer) {
  const dragItem = activeDragItem();
  if (dragItem?.kind === DRAG_KIND_PERSON && dragItem.personId) {
    return String(dragItem.personId);
  }
  const explicit = String(dataTransfer?.getData("application/x-wab-person-id") || "").trim();
  if (explicit) return explicit;
  const plain = plainDragData(dataTransfer);
  if (plain.startsWith("person:")) return plain.slice("person:".length).trim();
  return "";
}

function taskIdFromDataTransfer(dataTransfer) {
  const dragItem = activeDragItem();
  if (dragItem?.kind === DRAG_KIND_TASK && dragItem.taskId) {
    return String(dragItem.taskId);
  }
  const explicit = String(dataTransfer?.getData("application/x-wab-task-id") || "").trim();
  if (explicit) return explicit;
  const plain = plainDragData(dataTransfer);
  if (!plain) return "";
  if (plain.startsWith("task:")) return plain.slice("task:".length).trim();
  if (plain.startsWith("person:")) return "";
  return plain;
}

function allocationIdFromDataTransfer(dataTransfer) {
  const dragItem = activeDragItem();
  if (dragItem?.kind === DRAG_KIND_TASK && dragItem.allocationId) {
    return String(dragItem.allocationId);
  }
  return String(dataTransfer?.getData("application/x-wab-allocation-id") || "").trim();
}

function canDropOnZone(zone, dragKind) {
  if (!zone) return false;
  if (dragKind === DRAG_KIND_PERSON) {
    return zone.type === "team" || zone.type === "person" || zone.type === "unassigned";
  }
  if (zone.type === "backlog" || zone.type === "person") return true;
  if (zone.type === "team") return !!zone.teamId;
  return false;
}

function clearDropTargets() {
  const root = boardState.ctx?.els?.planningBoard;
  if (!root) return;
  root.querySelectorAll(".is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
}

export function bindPlanningBoardEvents() {
  const root = boardState.ctx?.els?.planningBoard;
  if (!root || boardState.bound) return;
  boardState.bound = true;

  root.addEventListener("click", async (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-wab-action]");
    if (actionEl) {
      event.preventDefault();
      const action = actionEl.getAttribute("data-wab-action") || "";
      await onPlanningAction(action, actionEl);
      return;
    }
    const chip = event.target.closest(".wab-task-chip");
    if (chip) {
      selectTask(chip.getAttribute("data-task-id") || "", {
        focusReturnTaskId: chip.getAttribute("data-task-id") || "",
      });
    }
  });

  root.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "wab-search") {
      boardState.search = target.value || "";
      persistViewState();
      rerenderPlanning();
      return;
    }
    if (target.id === "wab-person-search") {
      boardState.personSearch = target.value || "";
      persistViewState();
      rerenderPlanning();
      return;
    }
    if (target.id === "wab-new-team-name") {
      boardState.drafts.teamName = target.value || "";
      return;
    }
    if (target.id === "wab-new-person-name") {
      boardState.drafts.personName = target.value || "";
      return;
    }
    if (target.id === "wab-new-person-capacity") {
      boardState.drafts.personCapacity = target.value || "1.00";
      return;
    }
    if (target.id === "wab-new-task-title") {
      boardState.drafts.taskTitle = target.value || "";
      return;
    }
    if (target.id === "wab-new-task-fte") {
      boardState.drafts.taskFte = target.value || "0.25";
      return;
    }
    if (target.id === "wab-detail-title") {
      boardState.detailDraft.title = target.value || "";
      return;
    }
    if (target.id === "wab-detail-fte") {
      boardState.detailDraft.fte = target.value || "0.25";
      return;
    }
  });

  root.addEventListener("change", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "wab-month") {
      const value = String(target.value || "").trim();
      if (!/^\d{4}-\d{2}$/.test(value)) return;
      boardState.month = value;
      persistViewState();
      await loadBoard(boardState.ctx, { allocationsOnly: true });
      return;
    }
    if (target.id === "wab-team-filter") {
      boardState.teamFilter = target.value || "all";
      persistViewState();
      rerenderPlanning();
      return;
    }
    if (target.id === "wab-effort-filter") {
      boardState.effortFilter = target.value || "all";
      persistViewState();
      rerenderPlanning();
      return;
    }
    if (target.id === "wab-new-person-team") {
      boardState.drafts.personTeamId = target.value || "";
      return;
    }
    if (target.id === "wab-detail-assignee-target") {
      boardState.detailDraft.assignmentTarget = target.value || "";
    }
  });

  root.addEventListener("keydown", async (event) => {
    if (!(event.target instanceof Element)) return;
    const key = event.key || "";
    if (key === "Escape" && boardState.selectedTaskId) {
      event.preventDefault();
      closeTaskDetail({ restoreFocus: true });
      return;
    }
    if (key === "Escape" && boardState.topPanel) {
      event.preventDefault();
      boardState.topPanel = "";
      rerenderPlanning();
      return;
    }
    const chip = event.target.closest(".wab-task-chip");
    if (chip && (key === "Enter" || key === " ")) {
      event.preventDefault();
      selectTask(chip.getAttribute("data-task-id") || "", {
        focusReturnTaskId: chip.getAttribute("data-task-id") || "",
      });
      return;
    }
    const assignTarget = event.target.closest("[data-assign-target]");
    if (assignTarget && (key === "Enter" || key === " ")) {
      event.preventDefault();
      await assignSelectedTaskToTarget(assignTarget.getAttribute("data-assign-target") || "");
    }
  });

  root.addEventListener("dragstart", (event) => {
    const target = eventElement(event.target);
    if (!target) return;
    const chip = target.closest(".wab-task-chip");
    if (chip && event.dataTransfer) {
      const taskId = chip.getAttribute("data-task-id") || "";
      const allocationId = chip.getAttribute("data-allocation-id") || "";
      event.dataTransfer.setData("application/x-wab-kind", DRAG_KIND_TASK);
      event.dataTransfer.setData("text/plain", `task:${taskId}`);
      event.dataTransfer.setData("application/x-wab-task-id", taskId);
      event.dataTransfer.setData("application/x-wab-allocation-id", allocationId);
      event.dataTransfer.setData("application/x-wab-assigned", chip.getAttribute("data-assigned") || "0");
      event.dataTransfer.effectAllowed = "move";
      boardState.dragItem = {
        kind: DRAG_KIND_TASK,
        taskId,
        allocationId,
      };
      return;
    }
    const personCard = target.closest(".wab-person-card[data-person-id], .wab-unassigned-person-card[data-person-id]");
    if (personCard && event.dataTransfer) {
      const personId = personCard.getAttribute("data-person-id") || "";
      if (!personId) return;
      event.dataTransfer.setData("application/x-wab-kind", DRAG_KIND_PERSON);
      event.dataTransfer.setData("application/x-wab-person-id", personId);
      event.dataTransfer.setData("text/plain", `person:${personId}`);
      event.dataTransfer.effectAllowed = "move";
      boardState.dragItem = {
        kind: DRAG_KIND_PERSON,
        personId,
      };
    }
  });

  root.addEventListener("dragenter", (event) => {
    const target = eventElement(event.target);
    if (!target) return;
    const zone = getDropzone(target);
    if (!zone) return;
    const dragKind = dragKindFromDataTransfer(event.dataTransfer);
    if (!canDropOnZone(zone, dragKind)) return;
    event.preventDefault();
    clearDropTargets();
    zone.el.classList.add("is-drop-target");
  });

  root.addEventListener("dragover", (event) => {
    const target = eventElement(event.target);
    if (!target) return;
    const zone = getDropzone(target);
    if (!zone) return;
    const dragKind = dragKindFromDataTransfer(event.dataTransfer);
    if (!canDropOnZone(zone, dragKind)) return;
    event.preventDefault();
    clearDropTargets();
    zone.el.classList.add("is-drop-target");
  });

  root.addEventListener("dragleave", (event) => {
    const target = eventElement(event.target);
    if (!target) return;
    const zone = getDropzone(target);
    if (!zone) return;
    const nextTarget = eventElement(event.relatedTarget);
    if (nextTarget && zone.el.contains(nextTarget)) return;
    zone.el.classList.remove("is-drop-target");
  });

  root.addEventListener("drop", async (event) => {
    const target = eventElement(event.target);
    if (!target) return;
    const zone = getDropzone(target);
    if (!zone) return;
    const dragKind = dragKindFromDataTransfer(event.dataTransfer);
    if (!canDropOnZone(zone, dragKind)) return;
    event.preventDefault();
    clearDropTargets();
    try {
      if (dragKind === DRAG_KIND_PERSON) {
        const personId = personIdFromDataTransfer(event.dataTransfer);
        if (!personId) return;
        if (zone.type === "unassigned") {
          await movePersonToTeam(personId, UNASSIGNED_TEAM_ID, { pushUndo: true });
          return;
        }
        if (zone.type === "person") {
          const targetTeamId = zone.el.getAttribute("data-person-team-id") || UNASSIGNED_TEAM_ID;
          await movePersonToTeam(personId, targetTeamId, { pushUndo: true });
          return;
        }
        if (zone.type !== "team") return;
        await movePersonToTeam(personId, zone.teamId, { pushUndo: true });
        return;
      }
      const taskId = taskIdFromDataTransfer(event.dataTransfer);
      if (!taskId) return;
      if (zone.type === "backlog") {
        const allocationId = allocationIdFromDataTransfer(event.dataTransfer);
        if (allocationId) {
          await unassignAllocation(allocationId, { pushUndo: true, noticeMessage: "Assignee removed from task" });
        } else {
          await unassignTask(taskId, { pushUndo: true });
        }
        return;
      }
      if (zone.type === "person" && zone.personId) {
        const allocationId = allocationIdFromDataTransfer(event.dataTransfer);
        if (allocationId) {
          await moveAssignment(allocationId, "person", zone.personId, { pushUndo: true });
        } else {
          await createAssignment(taskId, "person", zone.personId, { pushUndo: true });
        }
        return;
      }
      if (zone.type === "team" && zone.teamId) {
        if (zone.teamId === UNASSIGNED_TEAM_ID) {
          const allocationId = allocationIdFromDataTransfer(event.dataTransfer);
          if (allocationId) {
            await unassignAllocation(allocationId, { pushUndo: true, noticeMessage: "Assignee removed from task" });
          } else {
            await unassignTask(taskId, { pushUndo: true });
          }
          return;
        }
        const allocationId = allocationIdFromDataTransfer(event.dataTransfer);
        if (allocationId) {
          await moveAssignment(allocationId, "team", zone.teamId, { pushUndo: true });
        } else {
          await createAssignment(taskId, "team", zone.teamId, { pushUndo: true });
        }
      }
    } catch (err) {
      boardState.notice = { message: err?.message || "Drop failed", tone: "error" };
      rerenderPlanning();
    } finally {
      boardState.dragItem = null;
    }
  });

  root.addEventListener("dragend", () => {
    boardState.dragItem = null;
    clearDropTargets();
  });
}
