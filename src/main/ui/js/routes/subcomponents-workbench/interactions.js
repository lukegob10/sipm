import { bindSubcomponentsWorkbenchSavedViewControls } from "./saved-views.js";
import {
  closeSubcomponentsWorkbenchDrawer,
  deleteActiveSubcomponentsWorkbenchItem,
  handleSubcomponentsWorkbenchContextClick,
  handleSubcomponentsWorkbenchShortcut,
  handleSubcomponentsWorkbenchTableClick,
  resetSubcomponentsWorkbenchEditor,
  saveSubcomponentsWorkbenchForm,
} from "./drawer.js";

export function updateSubcomponentsWorkbenchSolutionOptions(ctx, projectId) {
  const { state, els } = ctx;
  if (!els.subcomponentsWorkbenchSolution) return;
  const prior = els.subcomponentsWorkbenchSolution.value || "";
  const filteredSolutions = projectId
    ? state.solutions.filter((solution) => solution.project_id === projectId)
    : state.solutions;
  const opts = filteredSolutions
    .sort((a, b) => (a.solution_name || "").localeCompare(b.solution_name || ""))
    .map((solution) => `<option value="${solution.solution_id}">${solution.solution_name}</option>`)
    .join("");
  els.subcomponentsWorkbenchSolution.innerHTML = `<option value="">All Solutions</option>${opts}`;
  if (prior && filteredSolutions.find((solution) => solution.solution_id === prior)) {
    els.subcomponentsWorkbenchSolution.value = prior;
  }
}

export function bindSubcomponentsWorkbenchControls(ctx) {
  const {
    state,
    els,
    bindDebouncedInput,
    persistSubcomponentsWorkbenchUiState,
    renderSubcomponentsWorkbench,
    clearSubcomponentsWorkbenchFilters,
    syncSubcomponentsWorkbenchBulkInputs,
    applySubcomponentsWorkbenchBulkAction,
    clearSubcomponentsWorkbenchBulkFeedback,
    updateSubcomponentsWorkbenchSelectionCount,
    findUserBySoeid,
  } = ctx;
  const wb = state.subcomponentsWorkbench;

  const presetButtons = document.querySelectorAll(".scwb-preset[data-preset]");
  presetButtons.forEach((btn) => {
    if (btn._bound) return;
    btn.addEventListener("click", () => {
      wb.preset = btn.getAttribute("data-preset") || "all";
      wb.selected.clear();
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    btn._bound = true;
  });

  bindSubcomponentsWorkbenchSavedViewControls(ctx);

  bindDebouncedInput(els.subcomponentsWorkbenchSearch, (value) => {
    wb.filters.search = value || "";
    persistSubcomponentsWorkbenchUiState();
    renderSubcomponentsWorkbench();
  });

  if (els.subcomponentsWorkbenchProject && !els.subcomponentsWorkbenchProject._bound) {
    els.subcomponentsWorkbenchProject.addEventListener("change", () => {
      wb.filters.project_id = els.subcomponentsWorkbenchProject.value || "";
      wb.filters.solution_id = "";
      updateSubcomponentsWorkbenchSolutionOptions(ctx, wb.filters.project_id);
      if (els.subcomponentsWorkbenchSolution) {
        els.subcomponentsWorkbenchSolution.value = "";
      }
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchProject._bound = true;
  }

  if (els.subcomponentsWorkbenchSolution && !els.subcomponentsWorkbenchSolution._bound) {
    els.subcomponentsWorkbenchSolution.addEventListener("change", () => {
      wb.filters.solution_id = els.subcomponentsWorkbenchSolution.value || "";
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchSolution._bound = true;
  }

  if (els.subcomponentsWorkbenchAssignee && !els.subcomponentsWorkbenchAssignee._bound) {
    els.subcomponentsWorkbenchAssignee.addEventListener("change", () => {
      const value = els.subcomponentsWorkbenchAssignee.value || "";
      wb.filters.assignee = value;
      const user = findUserBySoeid(value);
      wb.filters.assignee_name = user?.display_name || "";
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchAssignee._bound = true;
  }

  if (els.subcomponentsWorkbenchStatus && !els.subcomponentsWorkbenchStatus._bound) {
    els.subcomponentsWorkbenchStatus.addEventListener("change", () => {
      wb.filters.status = els.subcomponentsWorkbenchStatus.value || "";
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchStatus._bound = true;
  }

  if (els.subcomponentsWorkbenchPriority && !els.subcomponentsWorkbenchPriority._bound) {
    bindDebouncedInput(els.subcomponentsWorkbenchPriority, (value) => {
      wb.filters.priority_max = value || "";
      persistSubcomponentsWorkbenchUiState();
      renderSubcomponentsWorkbench();
    });
    els.subcomponentsWorkbenchPriority._bound = true;
  }

  if (els.subcomponentsWorkbenchClearFilters && !els.subcomponentsWorkbenchClearFilters._bound) {
    els.subcomponentsWorkbenchClearFilters.addEventListener("click", () => clearSubcomponentsWorkbenchFilters());
    els.subcomponentsWorkbenchClearFilters._bound = true;
  }

  if (els.subcomponentsWorkbenchBulkAction && !els.subcomponentsWorkbenchBulkAction._bound) {
    els.subcomponentsWorkbenchBulkAction.addEventListener("change", () => syncSubcomponentsWorkbenchBulkInputs());
    els.subcomponentsWorkbenchBulkAction._bound = true;
  }
  if (els.subcomponentsWorkbenchBulkApply && !els.subcomponentsWorkbenchBulkApply._bound) {
    els.subcomponentsWorkbenchBulkApply.addEventListener("click", () => {
      void applySubcomponentsWorkbenchBulkAction();
    });
    els.subcomponentsWorkbenchBulkApply._bound = true;
  }
  syncSubcomponentsWorkbenchBulkInputs();

  if (els.subcomponentsWorkbenchTable && !els.subcomponentsWorkbenchTable._bound) {
    els.subcomponentsWorkbenchTable.addEventListener("change", (event) => {
      const rowCheck = event.target.closest(".scwb-select-row");
      if (rowCheck) {
        const subId = rowCheck.getAttribute("data-id") || "";
        if (!subId) return;
        if (rowCheck.checked) wb.selected.add(subId);
        else wb.selected.delete(subId);
        clearSubcomponentsWorkbenchBulkFeedback();
        updateSubcomponentsWorkbenchSelectionCount();
        return;
      }
      if (event.target.id === "scwb-select-all") {
        const checked = !!event.target.checked;
        (wb.visibleIds || []).forEach((subId) => {
          if (checked) wb.selected.add(subId);
          else wb.selected.delete(subId);
        });
        clearSubcomponentsWorkbenchBulkFeedback();
        persistSubcomponentsWorkbenchUiState();
        renderSubcomponentsWorkbench();
      }
    });
    els.subcomponentsWorkbenchTable.addEventListener("click", (event) => handleSubcomponentsWorkbenchTableClick(ctx, event));
    els.subcomponentsWorkbenchTable._bound = true;
  }

  if (els.subcomponentsWorkbenchForm && !els.subcomponentsWorkbenchForm._bound) {
    els.subcomponentsWorkbenchForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveSubcomponentsWorkbenchForm(ctx);
    });
    els.subcomponentsWorkbenchForm._bound = true;
  }

  if (els.subcomponentsWorkbenchContext && !els.subcomponentsWorkbenchContext._bound) {
    els.subcomponentsWorkbenchContext.addEventListener("click", (event) => handleSubcomponentsWorkbenchContextClick(ctx, event));
    els.subcomponentsWorkbenchContext._bound = true;
  }

  if (els.subcomponentsWorkbenchDelete && !els.subcomponentsWorkbenchDelete._bound) {
    els.subcomponentsWorkbenchDelete.addEventListener("click", async () => {
      await deleteActiveSubcomponentsWorkbenchItem(ctx);
    });
    els.subcomponentsWorkbenchDelete._bound = true;
  }

  if (els.subcomponentsWorkbenchReset && !els.subcomponentsWorkbenchReset._bound) {
    els.subcomponentsWorkbenchReset.addEventListener("click", () => resetSubcomponentsWorkbenchEditor(ctx));
    els.subcomponentsWorkbenchReset._bound = true;
  }

  if (els.subcomponentsWorkbenchClose && !els.subcomponentsWorkbenchClose._bound) {
    els.subcomponentsWorkbenchClose.addEventListener("click", () => closeSubcomponentsWorkbenchDrawer(ctx));
    els.subcomponentsWorkbenchClose._bound = true;
  }

  if (!document._scwbShortcutsBound) {
    document.addEventListener("keydown", async (event) => {
      await handleSubcomponentsWorkbenchShortcut(ctx, event);
    });
    document._scwbShortcutsBound = true;
  }
}
