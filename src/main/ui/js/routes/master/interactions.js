import { ragTone, statusTone } from "../../utils/display-tokens.js";
import { beginSolutionMutation, captureEntityMutationContext, isEntityMutationContextCurrent } from "../../utils/form-state.js";

const pendingSolutionUpdates = new WeakMap();
const solutionReadFields = [
  "solution_id", "project_id", "solution_name", "version", "github_repo_url", "status", "rag_status", "rag_reason", "priority",
  "due_date", "planned_start_date", "current_phase", "description", "success_criteria", "problem_statement", "escalation",
  "owner", "owner_user_soeid", "assignee", "assignee_user_soeid", "approver", "approver_user_soeid", "key_stakeholder",
  "blockers", "risks", "impact_confidence", "rag_confidence", "completed_at", "capacity_hours", "created_at", "updated_at",
];

function isCompleteSolution(value, id) {
  return !!value && typeof value === "object" && !Array.isArray(value) && value.solution_id === id
    && solutionReadFields.every((field) => Object.hasOwn(value, field))
    && ["project_id", "solution_name", "version", "status", "rag_status", "created_at", "updated_at"]
      .every((field) => typeof value[field] === "string" && value[field].length > 0)
    && typeof value.priority === "number" && Number.isFinite(value.priority);
}

function showMasterUpdateError(root, message) {
  if (!root) return;
  root.querySelector('[data-master-update-error]')?.remove();
  const notice = document.createElement("p");
  notice.dataset.masterUpdateError = "true";
  notice.setAttribute("role", "alert");
  notice.textContent = message;
  root.prepend(notice);
}

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

function firstElementWithAttribute(root, attr, value) {
  if (!root) return null;
  return Array.from(root.querySelectorAll(`[${attr}]`)).find((el) => el.getAttribute(attr) === value) || null;
}

function windowScrollPosition() {
  if (typeof window === "undefined") return { left: 0, top: 0 };
  return {
    left: Number(window.scrollX || window.pageXOffset || 0),
    top: Number(window.scrollY || window.pageYOffset || 0),
  };
}

function scrollWindowTo(left, top) {
  if (typeof window === "undefined" || typeof window.scrollTo !== "function") return;
  const targetLeft = Number(left || 0);
  const targetTop = Number(top || 0);
  const current = windowScrollPosition();
  if (current.left === targetLeft && current.top === targetTop) return;
  try {
    window.scrollTo(targetLeft, targetTop);
  } catch {
    // jsdom and older embedded browsers may not implement scrollTo.
  }
}

function captureMasterTableViewport(root, rowKey) {
  if (!root) return null;
  const windowScroll = windowScrollPosition();
  const row = firstElementWithAttribute(root, "data-master-row-key", rowKey);
  const rowTop = typeof row?.getBoundingClientRect === "function"
    ? row.getBoundingClientRect().top
    : null;
  return {
    rowKey,
    rowTop,
    scrollLeft: Number(root.scrollLeft || 0),
    scrollTop: Number(root.scrollTop || 0),
    windowLeft: windowScroll.left,
    windowTop: windowScroll.top,
  };
}

function restoreFocusWithoutScroll(target, root) {
  if (!target || typeof target.focus !== "function") return;
  const tableScrollTop = Number(root?.scrollTop || 0);
  const tableScrollLeft = Number(root?.scrollLeft || 0);
  const windowScroll = windowScrollPosition();
  try {
    target.focus({ preventScroll: true });
    return;
  } catch {
    target.focus();
  }
  if (root) {
    root.scrollTop = tableScrollTop;
    root.scrollLeft = tableScrollLeft;
  }
  scrollWindowTo(windowScroll.left, windowScroll.top);
}

function restoreMasterTableViewport(root, snapshot) {
  if (!root || !snapshot) return;
  root.scrollTop = snapshot.scrollTop;
  root.scrollLeft = snapshot.scrollLeft;
  scrollWindowTo(snapshot.windowLeft, snapshot.windowTop);

  const row = firstElementWithAttribute(root, "data-master-row-key", snapshot.rowKey);
  if (row && Number.isFinite(snapshot.rowTop) && typeof row.getBoundingClientRect === "function") {
    const nextTop = row.getBoundingClientRect().top;
    if (Number.isFinite(nextTop)) {
      const delta = nextTop - snapshot.rowTop;
      if (Math.abs(delta) > 0.5) {
        if (root.scrollHeight > root.clientHeight + 1) {
          root.scrollTop += delta;
        } else {
          scrollWindowTo(snapshot.windowLeft, snapshot.windowTop + delta);
        }
      }
    }
  }

  root.scrollLeft = snapshot.scrollLeft;
  const replacementToggle = firstElementWithAttribute(root, "data-master-collapse-key", snapshot.rowKey);
  restoreFocusWithoutScroll(replacementToggle, root);
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
  const context = captureEntityMutationContext(state);
  const authed = state.authed;
  const current = () => state.authed === authed && isEntityMutationContextCurrent(state, context);
  const pending = pendingSolutionUpdates.get(state) || new Map();
  const previous = pending.get(id);
  if (previous && current() && isEntityMutationContextCurrent(state, previous.context) && previous.authed === state.authed) {
    renderMasterTable();
    showMasterUpdateError(ctx.els.masterTable, "This solution is being updated. Try again when it finishes.");
    return;
  }
  const release = beginSolutionMutation(state, id);
  if (!release) {
    renderMasterTable();
    showMasterUpdateError(ctx.els.masterTable, "This solution is being updated. Try again when it finishes.");
    return;
  }
  const request = { context, authed };
  pending.set(id, request);
  pendingSolutionUpdates.set(state, pending);
  ctx.els.masterTable?.querySelector('[data-master-update-error]')?.remove();
  const fields = Array.from(ctx.els.masterTable?.querySelectorAll('[data-type="solution"][data-field]') || [])
    .filter((element) => element.getAttribute("data-id") === id);
  fields.forEach((element) => { element.disabled = true; });
  try {
    const payload = { [field]: field === "priority" ? Number(value) : value };
    if (field === "rag_status") {
      payload.rag_reason = "";
    }
    const updated = await api(`/solutions/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) });
    if (!current()) return;
    if (!isCompleteSolution(updated, id)) throw new Error("The update returned an invalid solution.");
    upsertById(state.solutions, updated, "solution_id");
    renderMasterTable();
    renderDashboard();
    renderKanban();
    renderCalendar();
    if (typeof renderGantt === "function") renderGantt();
  } catch (err) {
    if (!current()) return;
    const status = Number(err?.status);
    const ambiguous = !Number.isFinite(status) || status === 0 || status === 408 || status >= 500;
    if (ambiguous) {
      try {
        const latest = await api(`/solutions/${encodeURIComponent(id)}`);
        if (!current()) return;
        if (!isCompleteSolution(latest, id)) throw new Error("Incomplete solution response");
        upsertById(state.solutions, latest, "solution_id");
        renderMasterTable();
        renderDashboard();
        renderKanban();
        renderCalendar();
        if (typeof renderGantt === "function") renderGantt();
        showMasterUpdateError(ctx.els.masterTable, "Update result is uncertain. The latest available solution has been loaded; refresh before retrying.");
        return;
      } catch (_refreshErr) {
        if (!current()) return;
        renderMasterTable();
        showMasterUpdateError(ctx.els.masterTable, `Could not confirm whether the update saved (${err?.message || "connection error"}). Refresh before retrying.`);
        return;
      }
    }
    renderMasterTable();
    showMasterUpdateError(ctx.els.masterTable, `Update failed: ${err?.message || "Please try again."}`);
  } finally {
    release();
    if (pending.get(id) === request) pending.delete(id);
    if (current()) fields.forEach((element) => { element.disabled = false; });
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
      event.preventDefault();
      const key = String(actionBtn.getAttribute("data-master-collapse-key") || "").trim();
      if (!key) return;
      const viewportSnapshot = captureMasterTableViewport(els.masterTable, key);
      if (!(state.masterCollapsed instanceof Set)) state.masterCollapsed = new Set();
      if (state.masterCollapsed.has(key)) state.masterCollapsed.delete(key);
      else state.masterCollapsed.add(key);
      if (typeof persistMasterViewState === "function") persistMasterViewState();
      if (typeof renderMasterTable === "function") renderMasterTable();
      restoreMasterTableViewport(els.masterTable, viewportSnapshot);
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
      const context = captureEntityMutationContext(state);
      const opened = openSolutionModal(solution, "tasks");
      if (opened instanceof Promise) void opened.then((ok) => {
        if (!ok || !isEntityMutationContextCurrent(state, context)
            || els.solutionForm?.querySelector('[name="solution_id"]')?.value !== solution.solution_id) return;
        const latest = state.solutions.find((row) => row.solution_id === solution.solution_id);
        if (latest) showTaskForm(latest);
      });
      else if (opened !== false) showTaskForm(solution);
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
