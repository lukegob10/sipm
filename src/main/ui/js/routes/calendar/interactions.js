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
  fillSubcomponentForm,
  getRouteModule,
  ensureRouteModule,
  filteredSolutionsForCalendar,
  filteredSubcomponentsForCalendar,
  formatStatus,
}) {
  function formatMonthInputValue(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  }

  function parseMonthInputValue(value) {
    const raw = String(value || "").trim();
    if (!/^\d{4}-\d{2}$/.test(raw)) return null;
    const [yearText, monthText] = raw.split("-");
    const year = Number(yearText);
    const monthIndex = Number(monthText) - 1;
    if (!Number.isFinite(year) || !Number.isFinite(monthIndex) || monthIndex < 0 || monthIndex > 11) return null;
    return new Date(year, monthIndex, 1);
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

  function restoreCalendarViewState() {
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(calendarViewStateKey), {});
    const parsedMonth = parseMonthInputValue(stored.month || "");
    state.calendarMonth = parsedMonth || state.calendarMonth || new Date();
    state.calendarFilters = {
      project: String(stored.filters?.project || ""),
      owner: String(stored.filters?.owner || ""),
    };
    if (recovered) persistCalendarViewState();
    if (recovered) return;
    if (recovered || !Object.keys(stored || {}).length || !parsedMonth) persistCalendarViewState();
  }

  function setCalendarMonth(date) {
    if (!date || Number.isNaN(date)) return;
    state.calendarMonth = new Date(date.getFullYear(), date.getMonth(), 1);
    if (els.calendarMonthInput) {
      els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth);
    }
    persistCalendarViewState();
    renderCalendar();
  }

  function closeCalendarModal() {
    els.calendarModal?.classList.add("hidden");
  }

  function openCalendarSolutionDrilldown(solutionId) {
    const targetId = String(solutionId || "").trim();
    if (!targetId) return;
    const solution = state.solutions.find((row) => row.solution_id === targetId);
    if (!solution) return;
    closeCalendarModal();
    openSolutionModal(solution, "details");
  }

  function openCalendarProjectDrilldown(projectId) {
    const targetId = String(projectId || "").trim();
    if (!targetId) return;
    const project = state.projects.find((row) => row.project_id === targetId);
    if (!project) return;
    closeCalendarModal();
    openProjectForm(project);
  }

  function openCalendarSubcomponentDrilldown(subcomponentId) {
    const targetId = String(subcomponentId || "").trim();
    if (!targetId) return;
    const subcomponent = state.subcomponents.find((row) => row.subcomponent_id === targetId);
    if (!subcomponent) return;
    const solution = state.solutions.find((row) => row.solution_id === subcomponent.solution_id);
    if (!solution) return;
    closeCalendarModal();
    openSolutionModal(solution, "subcomponents");
    fillSubcomponentForm(subcomponent);
  }

  function openCalendarModal(day) {
    const mod = getRouteModule("calendar");
    if (!mod || typeof mod.openCalendarModal !== "function") {
      ensureRouteModule("calendar").then((loaded) => {
        if (loaded && typeof loaded.openCalendarModal === "function") {
          openCalendarModal(day);
        }
      });
      return;
    }
    mod.openCalendarModal(day, {
      state,
      els,
      filteredSolutionsForCalendar,
      filteredSubcomponentsForCalendar,
      formatStatus,
    });
  }

  function bindCalendarRouteControls() {
    if (els.calendarMonthInput) {
      els.calendarMonthInput.value = formatMonthInputValue(state.calendarMonth || new Date());
      els.calendarMonthInput.addEventListener("change", () => {
        const val = els.calendarMonthInput.value;
        if (!val) return;
        const [year, month] = val.split("-").map(Number);
        setCalendarMonth(new Date(year, (month || 1) - 1, 1));
      });
    }
    const shiftMonth = (delta) => {
      const base = state.calendarMonth || new Date();
      const next = new Date(base.getFullYear(), base.getMonth() + delta, 1);
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
        if (Number.isFinite(day)) openCalendarModal(day);
      });
    }
    els.calendarModalClose?.addEventListener("click", closeCalendarModal);
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
      if (action === "open-subcomponent") {
        openCalendarSubcomponentDrilldown(actionEl.getAttribute("data-subcomponent-id"));
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
      state.calendarFilters.owner = value;
      persistCalendarViewState();
      renderCalendar();
    });
  }

  return {
    bindCalendarRouteControls,
    persistCalendarViewState,
    restoreCalendarViewState,
  };
}
