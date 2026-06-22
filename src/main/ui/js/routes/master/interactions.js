import { ragTone, statusTone } from "../../utils/display-tokens.js";

function setRagSelectVisualState(fieldEl, value) {
  if (!fieldEl || !fieldEl.classList?.contains("rag-select")) return;
  const normalized = String(value || "").toLowerCase();
  const rag = normalized === "red" || normalized === "amber" ? normalized : "green";
  fieldEl.dataset.ragState = rag;
  fieldEl.classList.remove("rag-red", "rag-amber", "rag-green", "positive", "warn", "danger", "muted");
  fieldEl.classList.add(`rag-${rag}`, ragTone(rag));
}

function setStatusSelectVisualState(fieldEl, value) {
  if (!fieldEl || !fieldEl.classList?.contains("status-select")) return;
  const status = String(value || "").toLowerCase();
  fieldEl.dataset.statusState = status;
  fieldEl.classList.remove("positive", "warn", "danger", "muted");
  fieldEl.classList.add(statusTone(status));
}

async function updateDeliverableField(ctx, type, id, field, value) {
  const {
    state,
    api,
    upsertById,
    renderMasterTable,
    renderDashboard,
    renderKanban,
    renderCalendar,
    renderGantt,
  } = ctx;

  if (type !== "solution") return;
  try {
    const payload = { [field]: field === "priority" ? Number(value) : value };
    if (field === "rag_status") {
      payload.rag_reason = "";
    }
    const updated = await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    upsertById(state.solutions, updated, "solution_id");
    renderMasterTable();
    renderDashboard();
    renderKanban();
    renderCalendar();
    if (typeof renderGantt === "function") renderGantt();
  } catch (err) {
    console.error("Deliverable update failed", err);
  }
}

export function bindDeliverablesTable(ctx) {
  const {
    state,
    els,
    persistMasterViewState,
    renderMasterTable,
    openProgramForm,
    openProjectForm,
    openSolutionModal,
    showTaskForm,
  } = ctx;

  if (!els.masterTable || els.masterTable._bound) return;
  els.masterTable.addEventListener("change", (event) => {
    const fieldEl = event.target.closest("[data-field]");
    if (!fieldEl) return;
    const type = fieldEl.getAttribute("data-type");
    const id = fieldEl.getAttribute("data-id");
    const field = fieldEl.getAttribute("data-field");
    const value = fieldEl.value;
    if (field === "rag_status") setRagSelectVisualState(fieldEl, value);
    if (field === "status") setStatusSelectVisualState(fieldEl, value);
    void updateDeliverableField(ctx, type, id, field, value);
  });
  els.masterTable.addEventListener("click", (event) => {
    const actionBtn = event.target.closest("[data-action]");
    if (!actionBtn) return;
    const action = actionBtn.getAttribute("data-action");
    const type = actionBtn.getAttribute("data-type");
    const id = actionBtn.getAttribute("data-id");
    if (action === "toggle-master-collapse") {
      const key = String(actionBtn.getAttribute("data-master-collapse-key") || "").trim();
      if (!key) return;
      if (!(state.masterCollapsed instanceof Set)) state.masterCollapsed = new Set();
      if (state.masterCollapsed.has(key)) state.masterCollapsed.delete(key);
      else state.masterCollapsed.add(key);
      if (typeof persistMasterViewState === "function") persistMasterViewState();
      if (typeof renderMasterTable === "function") renderMasterTable();
      return;
    }
    if (action === "edit") {
      if (type === "program") {
        const program = state.programs.find((row) => row.program_id === id);
        openProgramForm(program);
      } else if (type === "project") {
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
    persistWorkspaceViewPreferences,
    renderCompletedVisibilityToggle,
    renderActiveView,
    openProjectForm,
    openSolutionModal,
  } = ctx;

  const sentinel = els.masterQuickstart || els.masterFilters;
  if (sentinel?._deliverablesControlsBound) return;

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
        ctx.state.filters = { query: "" };
        ctx.persistMasterViewState?.();
        ctx.renderMasterFilters?.();
        ctx.renderMasterTable?.();
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
}
