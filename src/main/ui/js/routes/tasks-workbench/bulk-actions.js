import { updateTasksWorkbenchSelectionCount } from "./filters.js";

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
  const {
    state,
    els,
    api,
    upsertById,
    deleteTasksById,
    ignoreNextRefresh,
    markIgnoreRefresh,
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
    markIgnoreRefresh("tasks");
    const result = await deleteTasksById(deleteTargets, {
      title: deleteTargets.length === 1 ? "Delete Task?" : "Delete Selected Tasks?",
      confirmLabel: deleteTargets.length === 1 ? "Delete Task" : `Delete ${deleteTargets.length} Tasks`,
    });
    if (result.cancelled) return;
    if (!result.deletedIds.length) {
      ignoreNextRefresh.delete("tasks");
    }
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
    if (!Number.isFinite(shift) || Math.abs(shift) < 1) {
      setTasksWorkbenchBulkFeedback("Enter a due date shift in whole days (e.g. 3 or -2).", "error");
      return;
    }
    payload.due_date_shift_days = Math.trunc(shift);
  } else {
    setTasksWorkbenchBulkFeedback("Unsupported bulk action.", "error");
    return;
  }

  try {
    const updated = await api("/tasks/actions/batch", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    (Array.isArray(updated) ? updated : []).forEach((row) => {
      upsertById(state.tasks, row, "task_id");
    });
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
    setTasksWorkbenchBulkFeedback(`Bulk update failed: ${err.message || err}`, "error");
  }
}
