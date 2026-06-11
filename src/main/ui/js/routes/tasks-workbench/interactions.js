import { bindTasksWorkbenchSavedViewControls } from "./saved-views.js";
import {
  closeTasksWorkbenchDrawer,
  deleteActiveTasksWorkbenchItem,
  handleTasksWorkbenchContextClick,
  handleTasksWorkbenchShortcut,
  handleTasksWorkbenchTableClick,
  resetTasksWorkbenchEditor,
  saveTasksWorkbenchForm,
} from "./drawer.js";

export function updateTasksWorkbenchSolutionOptions(ctx, projectId) {
  const { state, els } = ctx;
  if (!els.tasksWorkbenchSolution) return;
  const prior = els.tasksWorkbenchSolution.value || "";
  const filteredSolutions = projectId
    ? state.solutions.filter((solution) => solution.project_id === projectId)
    : state.solutions;
  const opts = filteredSolutions
    .sort((a, b) => (a.solution_name || "").localeCompare(b.solution_name || ""))
    .map((solution) => `<option value="${solution.solution_id}">${solution.solution_name}</option>`)
    .join("");
  els.tasksWorkbenchSolution.innerHTML = `<option value="">All Solutions</option>${opts}`;
  if (prior && filteredSolutions.find((solution) => solution.solution_id === prior)) {
    els.tasksWorkbenchSolution.value = prior;
  }
}

export function bindTasksWorkbenchControls(ctx) {
  const {
    state,
    els,
    bindDebouncedInput,
    persistTasksWorkbenchUiState,
    renderTasksWorkbench,
    clearTasksWorkbenchFilters,
    syncTasksWorkbenchBulkInputs,
    applyTasksWorkbenchBulkAction,
    clearTasksWorkbenchBulkFeedback,
    updateTasksWorkbenchSelectionCount,
    findUserBySoeid,
  } = ctx;
  const wb = state.tasksWorkbench;

  const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");
  presetButtons.forEach((btn) => {
    if (btn._bound) return;
    btn.addEventListener("click", () => {
      wb.preset = btn.getAttribute("data-preset") || "all";
      wb.selected.clear();
      persistTasksWorkbenchUiState();
      renderTasksWorkbench();
    });
    btn._bound = true;
  });

  bindTasksWorkbenchSavedViewControls(ctx);

  bindDebouncedInput(els.tasksWorkbenchSearch, (value) => {
    wb.filters.search = value || "";
    persistTasksWorkbenchUiState();
    renderTasksWorkbench();
  });

  if (els.tasksWorkbenchProject && !els.tasksWorkbenchProject._bound) {
    els.tasksWorkbenchProject.addEventListener("change", () => {
      wb.filters.project_id = els.tasksWorkbenchProject.value || "";
      wb.filters.solution_id = "";
      updateTasksWorkbenchSolutionOptions(ctx, wb.filters.project_id);
      if (els.tasksWorkbenchSolution) {
        els.tasksWorkbenchSolution.value = "";
      }
      persistTasksWorkbenchUiState();
      renderTasksWorkbench();
    });
    els.tasksWorkbenchProject._bound = true;
  }

  if (els.tasksWorkbenchSolution && !els.tasksWorkbenchSolution._bound) {
    els.tasksWorkbenchSolution.addEventListener("change", () => {
      wb.filters.solution_id = els.tasksWorkbenchSolution.value || "";
      persistTasksWorkbenchUiState();
      renderTasksWorkbench();
    });
    els.tasksWorkbenchSolution._bound = true;
  }

  if (els.tasksWorkbenchAssignee && !els.tasksWorkbenchAssignee._bound) {
    els.tasksWorkbenchAssignee.addEventListener("change", () => {
      const value = els.tasksWorkbenchAssignee.value || "";
      wb.filters.assignee = value;
      const user = findUserBySoeid(value);
      wb.filters.assignee_name = user?.display_name || "";
      persistTasksWorkbenchUiState();
      renderTasksWorkbench();
    });
    els.tasksWorkbenchAssignee._bound = true;
  }

  if (els.tasksWorkbenchStatus && !els.tasksWorkbenchStatus._bound) {
    els.tasksWorkbenchStatus.addEventListener("change", () => {
      wb.filters.status = els.tasksWorkbenchStatus.value || "";
      persistTasksWorkbenchUiState();
      renderTasksWorkbench();
    });
    els.tasksWorkbenchStatus._bound = true;
  }

  if (els.tasksWorkbenchPriority && !els.tasksWorkbenchPriority._bound) {
    bindDebouncedInput(els.tasksWorkbenchPriority, (value) => {
      wb.filters.priority_max = value || "";
      persistTasksWorkbenchUiState();
      renderTasksWorkbench();
    });
    els.tasksWorkbenchPriority._bound = true;
  }

  if (els.tasksWorkbenchClearFilters && !els.tasksWorkbenchClearFilters._bound) {
    els.tasksWorkbenchClearFilters.addEventListener("click", () => clearTasksWorkbenchFilters());
    els.tasksWorkbenchClearFilters._bound = true;
  }

  if (els.tasksWorkbenchBulkAction && !els.tasksWorkbenchBulkAction._bound) {
    els.tasksWorkbenchBulkAction.addEventListener("change", () => syncTasksWorkbenchBulkInputs());
    els.tasksWorkbenchBulkAction._bound = true;
  }
  if (els.tasksWorkbenchBulkApply && !els.tasksWorkbenchBulkApply._bound) {
    els.tasksWorkbenchBulkApply.addEventListener("click", () => {
      void applyTasksWorkbenchBulkAction();
    });
    els.tasksWorkbenchBulkApply._bound = true;
  }
  syncTasksWorkbenchBulkInputs();

  if (els.tasksWorkbenchTable && !els.tasksWorkbenchTable._bound) {
    els.tasksWorkbenchTable.addEventListener("change", (event) => {
      const rowCheck = event.target.closest(".scwb-select-row");
      if (rowCheck) {
        const taskId = rowCheck.getAttribute("data-id") || "";
        if (!taskId) return;
        if (rowCheck.checked) wb.selected.add(taskId);
        else wb.selected.delete(taskId);
        clearTasksWorkbenchBulkFeedback();
        updateTasksWorkbenchSelectionCount();
        return;
      }
      if (event.target.id === "scwb-select-all") {
        const checked = !!event.target.checked;
        (wb.visibleIds || []).forEach((taskId) => {
          if (checked) wb.selected.add(taskId);
          else wb.selected.delete(taskId);
        });
        clearTasksWorkbenchBulkFeedback();
        persistTasksWorkbenchUiState();
        renderTasksWorkbench();
      }
    });
    els.tasksWorkbenchTable.addEventListener("click", (event) => handleTasksWorkbenchTableClick(ctx, event));
    els.tasksWorkbenchTable._bound = true;
  }

  if (els.tasksWorkbenchForm && !els.tasksWorkbenchForm._bound) {
    els.tasksWorkbenchForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveTasksWorkbenchForm(ctx);
    });
    els.tasksWorkbenchForm._bound = true;
  }

  if (els.tasksWorkbenchContext && !els.tasksWorkbenchContext._bound) {
    els.tasksWorkbenchContext.addEventListener("click", (event) => handleTasksWorkbenchContextClick(ctx, event));
    els.tasksWorkbenchContext._bound = true;
  }

  if (els.tasksWorkbenchDelete && !els.tasksWorkbenchDelete._bound) {
    els.tasksWorkbenchDelete.addEventListener("click", async () => {
      await deleteActiveTasksWorkbenchItem(ctx);
    });
    els.tasksWorkbenchDelete._bound = true;
  }

  if (els.tasksWorkbenchReset && !els.tasksWorkbenchReset._bound) {
    els.tasksWorkbenchReset.addEventListener("click", () => resetTasksWorkbenchEditor(ctx));
    els.tasksWorkbenchReset._bound = true;
  }

  if (els.tasksWorkbenchClose && !els.tasksWorkbenchClose._bound) {
    els.tasksWorkbenchClose.addEventListener("click", () => closeTasksWorkbenchDrawer(ctx));
    els.tasksWorkbenchClose._bound = true;
  }

  if (els.tasksWorkbenchDrawer && !els.tasksWorkbenchDrawer._bound) {
    els.tasksWorkbenchDrawer.addEventListener("click", (event) => {
      if (event.target === els.tasksWorkbenchDrawer || event.target?.classList?.contains("task-workbench-editor-backdrop")) {
        closeTasksWorkbenchDrawer(ctx);
      }
    });
    els.tasksWorkbenchDrawer._bound = true;
  }

  if (!document._scwbShortcutsBound) {
    document.addEventListener("keydown", async (event) => {
      await handleTasksWorkbenchShortcut(ctx, event);
    });
    document._scwbShortcutsBound = true;
  }
}
