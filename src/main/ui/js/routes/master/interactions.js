import { normalizeMasterFilters } from "./filters.js";

function syncSelectAllCheckbox(ctx) {
  const { els } = ctx;
  const selectAll = document.getElementById("deliverables-select-all");
  if (!selectAll) return;
  const boxes = els.masterTable?.querySelectorAll("input.deliverable-select") || [];
  const total = boxes.length;
  if (!total) {
    selectAll.checked = false;
    selectAll.indeterminate = false;
    return;
  }
  const checkedCount = Array.from(boxes).filter((box) => box.checked).length;
  selectAll.checked = checkedCount === total;
  selectAll.indeterminate = checkedCount > 0 && checkedCount < total;
}

function setRagSelectVisualState(fieldEl, value) {
  if (!fieldEl || !fieldEl.classList?.contains("rag-select")) return;
  const normalized = String(value || "").toLowerCase();
  const rag = normalized === "red" || normalized === "amber" ? normalized : "green";
  fieldEl.dataset.ragState = rag;
  fieldEl.classList.remove("rag-red", "rag-amber", "rag-green");
  fieldEl.classList.add(`rag-${rag}`);
}

export function updatePresetButtons(ctx) {
  const { els, state } = ctx;
  const preset = state.deliverablesPreset || "";
  [els.presetMy, els.presetOverdue, els.presetBlocked].forEach((btn) => {
    if (!btn) return;
    const match = btn.id === `preset-${preset}`;
    btn.classList.toggle("active", match);
  });
}

export function clearDeliverablesFilters(ctx) {
  const {
    state,
    persistMasterViewState,
    renderMasterFilters,
    renderMasterTable,
    renderKanban,
    renderCalendar,
    renderGantt,
  } = ctx;

  state.filters = {};
  state.deliverablesPreset = "";
  state.deliverableSelection.clear();
  persistMasterViewState();
  updatePresetButtons(ctx);
  renderMasterFilters();
  renderMasterTable();
  renderKanban();
  renderCalendar();
  if (typeof renderGantt === "function") renderGantt();
}

export function setDeliverablesPreset(ctx, preset) {
  const { state, persistMasterViewState, renderMasterTable } = ctx;
  state.deliverablesPreset = preset || "";
  const normalized = normalizeMasterFilters(state.filters, state.deliverablesPreset);
  state.filters = normalized.filters;
  persistMasterViewState();
  updatePresetButtons(ctx);
  renderMasterTable();
}

export function updateBulkSelectionCount(ctx) {
  const { els, state } = ctx;
  if (!els.bulkSelectedCount) return;
  els.bulkSelectedCount.textContent = `${state.deliverableSelection.size} selected`;
  if (els.bulkApply) {
    els.bulkApply.disabled = !state.deliverableSelection.size || !els.bulkAction?.value;
  }
  syncSelectAllCheckbox(ctx);
}

function syncBulkInputs(ctx) {
  const { els, clearBulkFeedback } = ctx;
  clearBulkFeedback();
  const action = els.bulkAction?.value || "";
  if (els.bulkStatus) els.bulkStatus.classList.toggle("hidden", action !== "status");
  if (els.bulkOwner) els.bulkOwner.classList.toggle("hidden", action !== "owner");
  updateBulkSelectionCount(ctx);
}

async function applyBulkAction(ctx) {
  const {
    state,
    els,
    api,
    upsertById,
    renderMasterTable,
    renderDashboard,
    renderKanban,
    renderCalendar,
    renderGantt,
    setBulkFeedback,
  } = ctx;

  const action = els.bulkAction?.value || "";
  if (!action || !state.deliverableSelection.size) return;
  const status = els.bulkStatus?.value || "";
  const owner = String(els.bulkOwner?.value || "").trim();
  if (action === "status" && !status) {
    setBulkFeedback("Select a status first.", "error");
    return;
  }
  if (action === "owner" && !owner) {
    setBulkFeedback("Enter an owner name.", "error");
    return;
  }

  const updates = Array.from(state.deliverableSelection);
  try {
    setBulkFeedback("Updating deliverables…");
    for (const key of updates) {
      const [type, id] = key.split(":");
      if (action === "status") {
        if (type === "project") {
          const updated = await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
          upsertById(state.projects, updated, "project_id");
        } else if (type === "solution") {
          const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
          upsertById(state.solutions, updated, "solution_id");
        }
      } else if (action === "owner" && type === "solution") {
        const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify({ owner }) });
        upsertById(state.solutions, updated, "solution_id");
      }
    }
    state.deliverableSelection.clear();
    renderMasterTable();
    renderDashboard();
    renderKanban();
    renderCalendar();
    if (typeof renderGantt === "function") renderGantt();
    setBulkFeedback("Deliverables updated.", "success", 3200);
  } catch (err) {
    setBulkFeedback(`Bulk update failed: ${err.message}`, "error");
  }
}

async function updateDeliverableField(ctx, type, id, field, value) {
  const {
    state,
    api,
    upsertById,
    clearBulkFeedback,
    setBulkFeedback,
    renderMasterTable,
    renderDashboard,
    renderKanban,
    renderCalendar,
    renderGantt,
  } = ctx;

  clearBulkFeedback();
  setBulkFeedback("Saving deliverable change…");
  try {
    if (type === "project") {
      const payload = { [field]: field === "priority" ? Number(value) : value };
      const updated = await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      upsertById(state.projects, updated, "project_id");
    } else {
      const payload = { [field]: field === "priority" ? Number(value) : value };
      if (field === "rag_status") {
        payload.rag_reason = "";
      }
      const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      upsertById(state.solutions, updated, "solution_id");
    }
    renderMasterTable();
    renderDashboard();
    renderKanban();
    renderCalendar();
    if (typeof renderGantt === "function") renderGantt();
    setBulkFeedback("Deliverable updated.", "success", 2200);
  } catch (err) {
    setBulkFeedback(`Update failed: ${err.message}`, "error");
  }
}

export function bindDeliverablesTable(ctx) {
  const {
    state,
    els,
    deliverableKey,
    clearBulkFeedback,
    openProjectForm,
    openSolutionModal,
    showTaskForm,
  } = ctx;

  if (!els.masterTable || els.masterTable._bound) return;
  els.masterTable.addEventListener("change", (event) => {
    const select = event.target.closest(".deliverable-select");
    if (select) {
      const type = select.getAttribute("data-type");
      const id = select.getAttribute("data-id");
      const key = deliverableKey(type, id);
      if (select.checked) state.deliverableSelection.add(key);
      else state.deliverableSelection.delete(key);
      clearBulkFeedback();
      updateBulkSelectionCount(ctx);
      return;
    }
    const fieldEl = event.target.closest("[data-field]");
    if (fieldEl) {
      const type = fieldEl.getAttribute("data-type");
      const id = fieldEl.getAttribute("data-id");
      const field = fieldEl.getAttribute("data-field");
      const value = fieldEl.value;
      if (field === "rag_status") setRagSelectVisualState(fieldEl, value);
      void updateDeliverableField(ctx, type, id, field, value);
    }
  });
  els.masterTable.addEventListener("click", (event) => {
    const actionBtn = event.target.closest("[data-action]");
    if (!actionBtn) return;
    const action = actionBtn.getAttribute("data-action");
    const type = actionBtn.getAttribute("data-type");
    const id = actionBtn.getAttribute("data-id");
    if (action === "edit") {
      if (type === "project") {
        const project = state.projects.find((row) => row.project_id === id);
        openProjectForm(project);
      } else if (type === "solution") {
        const solution = state.solutions.find((row) => row.solution_id === id);
        openSolutionModal(solution, "details");
      }
    }
    if (action === "add-task" && type === "solution") {
      const solution = state.solutions.find((row) => row.solution_id === id);
      openSolutionModal(solution, "tasks");
      showTaskForm(solution);
    }
  });
  els.masterTable._bound = true;
}

export function bindDeliverablesControls(ctx) {
  const {
    els,
    clearBulkFeedback,
    persistWorkspaceViewPreferences,
    renderCompletedVisibilityToggle,
    renderActiveView,
    openProjectForm,
    openSolutionModal,
  } = ctx;

  const sentinel = els.bulkApply || els.bulkAction || els.presetClear || els.masterQuickstart;
  if (sentinel?._deliverablesControlsBound) {
    syncBulkInputs(ctx);
    updatePresetButtons(ctx);
    return;
  }

  els.presetMy?.addEventListener("click", () => setDeliverablesPreset(ctx, "my"));
  els.presetOverdue?.addEventListener("click", () => setDeliverablesPreset(ctx, "overdue"));
  els.presetBlocked?.addEventListener("click", () => setDeliverablesPreset(ctx, "blocked"));
  els.presetClear?.addEventListener("click", () => clearDeliverablesFilters(ctx));
  els.bulkAction?.addEventListener("change", () => syncBulkInputs(ctx));
  els.bulkApply?.addEventListener("click", () => {
    void applyBulkAction(ctx);
  });
  els.bulkStatus?.addEventListener("change", clearBulkFeedback);
  els.bulkOwner?.addEventListener("input", clearBulkFeedback);
  if (els.masterQuickstart && !els.masterQuickstart._bound) {
    els.masterQuickstart.addEventListener("click", (event) => {
      const btn = event.target.closest("button[data-quick-action]");
      if (!btn) return;
      const action = String(btn.getAttribute("data-quick-action") || "").trim();
      if (action === "create-project") {
        openProjectForm(null);
      } else if (action === "create-solution") {
        openSolutionModal(null, "details");
      } else if (action === "clear-filters") {
        clearDeliverablesFilters(ctx);
      } else if (action === "show-completed") {
        ctx.state.workspacePrefs.showCompleted = true;
        persistWorkspaceViewPreferences();
        renderCompletedVisibilityToggle();
        renderActiveView();
      }
    });
    els.masterQuickstart._bound = true;
  }

  if (sentinel) sentinel._deliverablesControlsBound = true;
  syncBulkInputs(ctx);
  updatePresetButtons(ctx);
}
