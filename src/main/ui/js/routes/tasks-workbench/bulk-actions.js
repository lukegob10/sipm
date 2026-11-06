import { beginTaskMutations } from "../../utils/form-state.js";
import { updateTasksWorkbenchSelectionCount } from "./filters.js";
import { captureEntityMutationContext, isEntityMutationContextCurrent } from "../../utils/form-state.js";
import { invalidateMyWorkRecords } from "../../utils/my-work-state.js";

export function syncTasksWorkbenchBulkInputs(ctx) {
  const { els, clearTasksWorkbenchBulkFeedback } = ctx;
  clearTasksWorkbenchBulkFeedback();
  if (!els.tasksWorkbenchBulkAction) return;
  const action = els.tasksWorkbenchBulkAction.value || "";
  if (els.tasksWorkbenchBulkStatus) {
    els.tasksWorkbenchBulkStatus.classList.toggle("hidden", action !== "status");
  }
  if (els.tasksWorkbenchBulkAssignee) {
    els.tasksWorkbenchBulkAssignee.classList.toggle("hidden", action !== "assignee");
  }
  if (els.tasksWorkbenchBulkShift) {
    els.tasksWorkbenchBulkShift.classList.toggle("hidden", action !== "shift_due");
  }
  updateTasksWorkbenchSelectionCount(ctx);
}

export async function applyTasksWorkbenchBulkAction(ctx) {
  const { state, els } = ctx;
  const wb = state.tasksWorkbench;
  const ids = Array.from(wb.selected);
  if (!ids.length && els.tasksWorkbenchBulkAction?.value === "delete" && wb.activeTaskId) ids.push(wb.activeTaskId);
  const release = beginTaskMutations(state, ids);
  if (!release) {
    ctx.setTasksWorkbenchBulkFeedback("A selected task is being updated. Wait for it to finish and try again.", "error");
    return;
  }
  try {
    await runTasksWorkbenchBulkAction(ctx, captureEntityMutationContext(state));
  } finally {
    release();
  }
}

async function runTasksWorkbenchBulkAction(ctx, requestContext) {
  const {
    state,
    els,
    api,
    upsertById,
    deleteTasksById,
    renderTasksWorkbench,
    renderSolutionTasks,
    renderDashboard,
    findUserBySoeid,
    setTasksWorkbenchBulkFeedback,
  } = ctx;

  const wb = state.tasksWorkbench;
  const selectedIds = Array.from(wb.selected);
  const action = els.tasksWorkbenchBulkAction?.value || "";
  if (!action) {
    setTasksWorkbenchBulkFeedback("Choose a bulk action.", "error");
    return;
  }
  const activeId = wb.activeTaskId || "";
  const allowActiveDelete = action === "delete" && !selectedIds.length && !!activeId;
  if (!selectedIds.length && !allowActiveDelete) {
    setTasksWorkbenchBulkFeedback("Select at least one task.", "error");
    return;
  }

  if (action === "delete") {
    const deleteTargets = selectedIds.length ? selectedIds : [activeId];
    setTasksWorkbenchBulkFeedback(
      deleteTargets.length === 1 ? "Deleting task…" : `Deleting ${deleteTargets.length} tasks…`
    );
    const result = await deleteTasksById(deleteTargets, {
      title: deleteTargets.length === 1 ? "Delete Task?" : "Delete Selected Tasks?",
      confirmLabel: deleteTargets.length === 1 ? "Delete Task" : `Delete ${deleteTargets.length} Tasks`,
    });
    if (result.cancelled || !isEntityMutationContextCurrent(state, requestContext)) return;
    renderTasksWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionTasks(openSolutionId);
    }
    renderDashboard();
    if (result.failed.length) {
      setTasksWorkbenchBulkFeedback(
        `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,
        "error"
      );
      return;
    }
    setTasksWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length} task${result.deletedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
    return;
  }

  const payload = { task_ids: selectedIds };
  if (action === "status") {
    payload.status = els.tasksWorkbenchBulkStatus?.value || "";
    if (!payload.status) {
      setTasksWorkbenchBulkFeedback("Select a status value.", "error");
      return;
    }
  } else if (action === "assignee") {
    const assigneeUserId = els.tasksWorkbenchBulkAssignee?.value || "";
    if (assigneeUserId) {
      const user = findUserBySoeid(assigneeUserId);
      payload.assignee_user_soeid = assigneeUserId;
      payload.assignee = user?.display_name || assigneeUserId;
    } else {
      payload.clear_assignee = true;
    }
  } else if (action === "shift_due") {
    const shift = Number(els.tasksWorkbenchBulkShift?.value || "");
    if (!Number.isSafeInteger(shift) || shift === 0) {
      setTasksWorkbenchBulkFeedback("Enter a due date shift in whole days (e.g. 3 or -2).", "error");
      return;
    }
    payload.due_date_shift_days = shift;
  } else {
    setTasksWorkbenchBulkFeedback("Unsupported bulk action.", "error");
    return;
  }

  let receivedResponse = false;
  try {
    const updated = await api("/tasks/actions/batch", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    receivedResponse = true;
    if (!isEntityMutationContextCurrent(state, requestContext)) return;
    const expectedIds = new Set(selectedIds);
    const returnedIds = new Set();
    const validResponse = Array.isArray(updated) && updated.length === expectedIds.size
      && updated.every((row) => {
        if (!row || typeof row !== "object" || typeof row.task_id !== "string"
            || !expectedIds.has(row.task_id) || returnedIds.has(row.task_id)
            || typeof row.task_name !== "string" || typeof row.status !== "string"
            || typeof row.project_id !== "string" || typeof row.solution_id !== "string"
            || !Number.isFinite(row.priority)) return false;
        returnedIds.add(row.task_id);
        return true;
      });
    if (!validResponse) {
      invalidateMyWorkRecords(state);
      setTasksWorkbenchBulkFeedback(
        "The server returned an incomplete response. The update may have succeeded; refresh before retrying.",
        "error"
      );
      return;
    }
    updated.forEach((row) => {
      upsertById(state.tasks, row, "task_id");
    });
    invalidateMyWorkRecords(state);
    renderTasksWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionTasks(openSolutionId);
    }
    setTasksWorkbenchBulkFeedback(
      `Updated ${selectedIds.length} task${selectedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
  } catch (err) {
    if (!isEntityMutationContextCurrent(state, requestContext)) return;
    const uncertain = receivedResponse || err?.code === "NETWORK_UNAVAILABLE"
      || err?.status === 0 || err?.status === 408 || err?.status >= 500;
    if (uncertain) {
      invalidateMyWorkRecords(state);
      setTasksWorkbenchBulkFeedback(
        "The update may have succeeded. Refresh before retrying.",
        "error"
      );
    } else {
      setTasksWorkbenchBulkFeedback(`Bulk update failed: ${err.message || err}`, "error");
    }
  }
}
