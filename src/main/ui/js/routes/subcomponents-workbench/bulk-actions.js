import { updateSubcomponentsWorkbenchSelectionCount } from "./filters.js";

export function syncSubcomponentsWorkbenchBulkInputs(ctx) {
  const { els, clearSubcomponentsWorkbenchBulkFeedback } = ctx;
  clearSubcomponentsWorkbenchBulkFeedback();
  if (!els.subcomponentsWorkbenchBulkAction) return;
  const action = els.subcomponentsWorkbenchBulkAction.value || "";
  if (els.subcomponentsWorkbenchBulkStatus) {
    els.subcomponentsWorkbenchBulkStatus.classList.toggle("hidden", action !== "status");
  }
  if (els.subcomponentsWorkbenchBulkAssignee) {
    els.subcomponentsWorkbenchBulkAssignee.classList.toggle("hidden", action !== "assignee");
  }
  if (els.subcomponentsWorkbenchBulkShift) {
    els.subcomponentsWorkbenchBulkShift.classList.toggle("hidden", action !== "shift_due");
  }
  updateSubcomponentsWorkbenchSelectionCount(ctx);
}

export async function applySubcomponentsWorkbenchBulkAction(ctx) {
  const {
    state,
    els,
    api,
    upsertById,
    deleteSubcomponentsById,
    ignoreNextRefresh,
    markIgnoreRefresh,
    renderSubcomponentsWorkbench,
    renderSolutionSubcomponents,
    renderDashboard,
    findUserBySoeid,
    setSubcomponentsWorkbenchBulkFeedback,
  } = ctx;

  const wb = state.subcomponentsWorkbench;
  const selectedIds = Array.from(wb.selected);
  const action = els.subcomponentsWorkbenchBulkAction?.value || "";
  if (!action) {
    setSubcomponentsWorkbenchBulkFeedback("Choose a bulk action.", "error");
    return;
  }
  const activeId = wb.activeSubcomponentId || "";
  const allowActiveDelete = action === "delete" && !selectedIds.length && !!activeId;
  if (!selectedIds.length && !allowActiveDelete) {
    setSubcomponentsWorkbenchBulkFeedback("Select at least one subcomponent.", "error");
    return;
  }

  if (action === "delete") {
    const deleteTargets = selectedIds.length ? selectedIds : [activeId];
    setSubcomponentsWorkbenchBulkFeedback(
      deleteTargets.length === 1 ? "Deleting subcomponent…" : `Deleting ${deleteTargets.length} subcomponents…`
    );
    markIgnoreRefresh("subcomponents");
    const result = await deleteSubcomponentsById(deleteTargets, {
      title: deleteTargets.length === 1 ? "Delete Subcomponent?" : "Delete Selected Subcomponents?",
      confirmLabel: deleteTargets.length === 1 ? "Delete Subcomponent" : `Delete ${deleteTargets.length} Subcomponents`,
    });
    if (result.cancelled) return;
    if (!result.deletedIds.length) {
      ignoreNextRefresh.delete("subcomponents");
    }
    renderSubcomponentsWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionSubcomponents(openSolutionId);
    }
    renderDashboard();
    if (result.failed.length) {
      setSubcomponentsWorkbenchBulkFeedback(
        `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,
        "error"
      );
      return;
    }
    setSubcomponentsWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length} subcomponent${result.deletedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
    return;
  }

  const payload = { subcomponent_ids: selectedIds };
  if (action === "status") {
    payload.status = els.subcomponentsWorkbenchBulkStatus?.value || "";
    if (!payload.status) {
      setSubcomponentsWorkbenchBulkFeedback("Select a status value.", "error");
      return;
    }
  } else if (action === "assignee") {
    const assigneeUserId = els.subcomponentsWorkbenchBulkAssignee?.value || "";
    if (assigneeUserId) {
      const user = findUserBySoeid(assigneeUserId);
      payload.assignee_user_soeid = assigneeUserId;
      payload.assignee = user?.display_name || assigneeUserId;
    } else {
      payload.clear_assignee = true;
    }
  } else if (action === "shift_due") {
    const shift = Number(els.subcomponentsWorkbenchBulkShift?.value || "");
    if (!Number.isFinite(shift) || Math.abs(shift) < 1) {
      setSubcomponentsWorkbenchBulkFeedback("Enter a due date shift in whole days (e.g. 3 or -2).", "error");
      return;
    }
    payload.due_date_shift_days = Math.trunc(shift);
  } else {
    setSubcomponentsWorkbenchBulkFeedback("Unsupported bulk action.", "error");
    return;
  }

  try {
    const updated = await api("/subcomponents/actions/batch", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    (Array.isArray(updated) ? updated : []).forEach((row) => {
      upsertById(state.subcomponents, row, "subcomponent_id");
    });
    renderSubcomponentsWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionSubcomponents(openSolutionId);
    }
    setSubcomponentsWorkbenchBulkFeedback(
      `Updated ${selectedIds.length} subcomponent${selectedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
  } catch (err) {
    setSubcomponentsWorkbenchBulkFeedback(`Bulk update failed: ${err.message || err}`, "error");
  }
}
