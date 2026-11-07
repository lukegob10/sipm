import { localDateFromParts } from "../../utils/date-only.js";
import { captureEntityMutationContext, isEntityMutationContextCurrent } from "../../utils/form-state.js";

export function createCalendarRouteController({
  state,
  els,
  calendarViewStateKey,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  bindDebouncedInput,
  renderCalendar,
  openProjectForm,
  openSolutionModal,
  fillTaskForm,
  getRouteModule,
  ensureRouteModule,
  filteredSolutionsForCalendar,
  filteredTasksForCalendar,
  formatStatus,
}) {
  function formatMonthInputValue(date) {
    return `${String(date.getFullYear()).padStart(4, "0")}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  }

  function parseMonthInputValue(value) {
    const raw = String(value || "").trim();
    if (!/^\d{4}-\d{2}$/.test(raw)) return null;
    const [yearText, monthText] = raw.split("-");
    const year = Number(yearText);
    const monthIndex = Number(monthText) - 1;
    if (!Number.isFinite(year) || year < 1 || year > 9999 || !Number.isFinite(monthIndex) || monthIndex < 0 || monthIndex > 11) return null;
    return localDateFromParts(year, monthIndex, 1);
  }

  function persistCalendarViewState() {
    writeStoredJson(
      activeSpaceScopedStorageKey(calendarViewStateKey),
      {
        month: formatMonthInputValue(state.calendarMonth || new Date()),
        filters: {
          project: state.calendarFilters?.project || "",
          owner: state.calendarFilters?.owner || "",
        },
      }
    );
  }

  let ownerInputContext = null;

  function restoreCalendarViewState() {
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(calendarViewStateKey), {});
    const parsedMonth = parseMonthInputValue(stored.month || "");
    state.calendarMonth = parsedMonth || state.calendarMonth || new Date();
    if (els.calendarMonthInput) els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth);
    const pending = ownerInputContext;
    const retainPending = pending && state.authed === pending.authed
      && state.calendarFilters === pending.filters
      && isEntityMutationContextCurrent(state, pending.context);
    state.calendarFilters = {
      project: String(stored.filters?.project || ""),
      owner: retainPending ? pending.value : String(stored.filters?.owner || ""),
    };
    if (retainPending) pending.filters = state.calendarFilters;
    else ownerInputContext = null;
    if (recovered) persistCalendarViewState();
    if (recovered) return;
    if (recovered || !Object.keys(stored || {}).length || !parsedMonth) persistCalendarViewState();
  }

  function setCalendarMonth(date) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime()) || date.getFullYear() < 1 || date.getFullYear() > 9999) return;
    state.calendarMonth = localDateFromParts(date.getFullYear(), date.getMonth(), 1);
    if (els.calendarMonthInput) {
      els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth);
    }
    persistCalendarViewState();
    renderCalendar();
  }

  let modalOpenGeneration = 0;
  let modalReturnFocus = null;

  function closeCalendarModal({ restoreFocus = true } = {}) {
    const returnFocus = modalReturnFocus;
    modalReturnFocus = null;
    els.calendarModal?.classList.add("hidden");
    if (!restoreFocus || !returnFocus || !isEntityMutationContextCurrent(state, returnFocus.context)
        || state.currentView !== "calendar" || String(state.calendarMonth || "") !== returnFocus.month) return;
    const target = returnFocus.element?.isConnected ? returnFocus.element : (
      returnFocus.agenda
        ? els.calendarAgenda?.querySelector(`[data-calendar-agenda-day="${returnFocus.day}"]`)
        : els.calendarGrid?.querySelector(`.calendar-cell[data-day="${returnFocus.day}"] .calendar-open-day`)
    );
    target?.focus();
  }

  function openCalendarSolutionDrilldown(solutionId) {
    const targetId = String(solutionId || "").trim();
    if (!targetId) return;
    const solution = state.solutions.find((row) => row.solution_id === targetId);
    if (!solution) return;
    closeCalendarModal({ restoreFocus: false });
    openSolutionModal(solution, "details");
  }

  function openCalendarProjectDrilldown(projectId) {
    const targetId = String(projectId || "").trim();
    if (!targetId) return;
    const project = state.projects.find((row) => row.project_id === targetId);
    if (!project) return;
    closeCalendarModal({ restoreFocus: false });
    openProjectForm(project);
  }

  function openCalendarTaskDrilldown(taskId) {
    const targetId = String(taskId || "").trim();
    if (!targetId) return;
    const task = state.tasks.find((row) => row.task_id === targetId);
    if (!task) return;
    const solution = state.solutions.find((row) => row.solution_id === task.solution_id);
    if (!solution) return;
    closeCalendarModal({ restoreFocus: false });
    const context = captureEntityMutationContext(state);
    const opened = openSolutionModal(solution, "tasks");
    if (opened instanceof Promise) void opened.then((ok) => {
      if (!ok || !isEntityMutationContextCurrent(state, context)
          || els.solutionForm?.querySelector('[name="solution_id"]')?.value !== solution.solution_id) return;
      const latest = state.tasks.find((item) => item.task_id === task.task_id && item.solution_id === solution.solution_id);
      if (latest) fillTaskForm(latest);
    });
    else if (opened !== false) fillTaskForm(task);
  }

  function resetForContext() {
    modalOpenGeneration += 1;
    closeCalendarModal({ restoreFocus: false });
    els.calendarModalList?.replaceChildren();
    if (els.calendarModalTitle) els.calendarModalTitle.textContent = "";
  }

  function openCalendarModal(day, opener) {
    const generation = ++modalOpenGeneration;
    const context = captureEntityMutationContext(state);
    const month = String(state.calendarMonth || "");
    const open = (mod) => {
      if (!mod || typeof mod.openCalendarModal !== "function"
          || generation !== modalOpenGeneration
          || !isEntityMutationContextCurrent(state, context)
          || String(state.calendarMonth || "") !== month
          || (state.currentView && state.currentView !== "calendar")) return;
      mod.openCalendarModal(day, {
        state,
        els,
        filteredSolutionsForCalendar,
        filteredTasksForCalendar,
        formatStatus,
      });
      modalReturnFocus = { element: opener, context, month, day, agenda: !!opener?.matches("[data-calendar-agenda-day]") };
      els.calendarModalClose?.focus();
    };
    const mod = getRouteModule("calendar");
    if (!mod || typeof mod.openCalendarModal !== "function") {
      ensureRouteModule("calendar").then(open);
      return;
    }
    open(mod);
  }

  function bindCalendarRouteControls() {
    if (els.calendarMonthInput) {
      els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth || new Date());
      els.calendarMonthInput.addEventListener("change", () => {
        const date = parseMonthInputValue(els.calendarMonthInput.value);
        if (!date) {
          els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth || new Date());
          return;
        }
        setCalendarMonth(date);
      });
    }
    const shiftMonth = (delta) => {
      const base = state.calendarMonth || new Date();
      const next = localDateFromParts(base.getFullYear(), base.getMonth() + delta, 1);
      setCalendarMonth(next);
    };
    els.calendarPrev?.addEventListener("click", () => shiftMonth(-1));
    els.calendarNext?.addEventListener("click", () => shiftMonth(1));
    if (els.calendarGrid) {
      els.calendarGrid.addEventListener("click", (e) => {
        const previewActionEl = e.target.closest("[data-calendar-preview-action]");
        if (previewActionEl) {
          const action = previewActionEl.getAttribute("data-calendar-preview-action") || "";
          if (action === "open-solution") {
            openCalendarSolutionDrilldown(previewActionEl.getAttribute("data-solution-id"));
          }
          return;
        }
        const cell = e.target.closest(".calendar-cell[data-day]");
        if (!cell) return;
        const day = Number(cell.getAttribute("data-day"));
        if (Number.isFinite(day)) openCalendarModal(day, e.target.closest(".calendar-open-day") || cell.querySelector(".calendar-open-day"));
      });
    }
    els.calendarAgenda?.addEventListener("click", (event) => {
      const dayButton = event.target.closest("[data-calendar-agenda-day]");
      if (!dayButton) return;
      const day = Number(dayButton.getAttribute("data-calendar-agenda-day"));
      if (Number.isFinite(day)) openCalendarModal(day, dayButton);
    });
    els.calendarModalClose?.addEventListener("click", () => closeCalendarModal());
    els.calendarModal?.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || event.defaultPrevented || els.calendarModal.classList.contains("hidden")) return;
      event.preventDefault();
      closeCalendarModal();
    });
    els.calendarModalList?.addEventListener("click", (e) => {
      const actionEl = e.target.closest("[data-calendar-action]");
      if (!actionEl) return;
      const action = actionEl.getAttribute("data-calendar-action") || "";
      if (action === "open-project") {
        openCalendarProjectDrilldown(actionEl.getAttribute("data-project-id"));
        return;
      }
      if (action === "open-solution") {
        openCalendarSolutionDrilldown(actionEl.getAttribute("data-solution-id"));
        return;
      }
      if (action === "open-task") {
        openCalendarTaskDrilldown(actionEl.getAttribute("data-task-id"));
      }
    });
    els.calendarModal?.addEventListener("click", (e) => {
      if (e.target === els.calendarModal || e.target.classList.contains("modal-backdrop")) {
        closeCalendarModal();
      }
    });

    els.calendarFilterProject?.addEventListener("change", () => {
      state.calendarFilters.project = els.calendarFilterProject.value || "";
      persistCalendarViewState();
      renderCalendar();
    });
    bindDebouncedInput(els.calendarFilterOwner, (value) => {
      const captured = ownerInputContext;
      ownerInputContext = null;
      if (!captured || state.authed !== captured.authed || state.calendarFilters !== captured.filters
          || !isEntityMutationContextCurrent(state, captured.context)) return;
      state.calendarFilters.owner = value;
      persistCalendarViewState();
      renderCalendar();
    }, 180, (value) => {
      ownerInputContext = { context: captureEntityMutationContext(state), authed: state.authed, filters: state.calendarFilters, value };
    });
  }

  return {
    getPendingOwner: () => ownerInputContext && state.authed === ownerInputContext.authed
      && state.calendarFilters === ownerInputContext.filters
      && isEntityMutationContextCurrent(state, ownerInputContext.context) ? ownerInputContext.value : null,
    bindCalendarRouteControls,
    resetForContext,
    persistCalendarViewState,
    restoreCalendarViewState,
  };
}
