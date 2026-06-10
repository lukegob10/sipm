function parseDateInputValue(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const [yearText, monthText, dayText] = raw.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return date;
}

function formatDateInputValue(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function defaultGanttWindow() {
  const now = new Date();
  const from = new Date(now.getFullYear(), now.getMonth(), 1);
  const to = new Date(now.getFullYear(), now.getMonth() + 3, 0);
  return {
    from: formatDateInputValue(from),
    to: formatDateInputValue(to),
  };
}

function normalizeWindow(windowState) {
  const fallback = defaultGanttWindow();
  const from = String(windowState?.from || fallback.from);
  const to = String(windowState?.to || fallback.to);
  const fromDate = parseDateInputValue(from);
  const toDate = parseDateInputValue(to);
  if (!fromDate || !toDate || fromDate.getTime() > toDate.getTime()) {
    return fallback;
  }
  return { from, to };
}

function normalizeCollapsedKeys(value) {
  if (!Array.isArray(value)) return new Set();
  return new Set(
    value
      .map((key) => String(key || "").trim())
      .filter((key) => key.startsWith("project:") || key.startsWith("solution:"))
  );
}

export function createGanttRouteController({
  state,
  els,
  ganttViewStateKey,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  renderGantt,
  openProjectForm,
  openSolutionModal,
  fillTaskForm,
}) {
  function persistGanttViewState() {
    writeStoredJson(
      activeSpaceScopedStorageKey(ganttViewStateKey),
      {
        window: {
          from: state.ganttWindow?.from || "",
          to: state.ganttWindow?.to || "",
        },
        collapsed: Array.from(state.ganttCollapsed || []),
      }
    );
  }

  function restoreGanttViewState() {
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(ganttViewStateKey), {});
    const storedWindow = stored.window || {};
    state.ganttWindow = normalizeWindow(storedWindow);
    state.ganttCollapsed = normalizeCollapsedKeys(stored.collapsed);
    if (els.ganttFrom) els.ganttFrom.value = state.ganttWindow.from;
    if (els.ganttTo) els.ganttTo.value = state.ganttWindow.to;
    if (
      recovered
      || !Object.keys(stored || {}).length
      || storedWindow.from !== state.ganttWindow.from
      || storedWindow.to !== state.ganttWindow.to
      || !Array.isArray(stored.collapsed)
    ) {
      persistGanttViewState();
    }
  }

  function syncWindowFromInputs() {
    state.ganttWindow = {
      from: els.ganttFrom?.value || "",
      to: els.ganttTo?.value || "",
    };
    persistGanttViewState();
    renderGantt();
  }

  function collapseAllGanttRows() {
    state.ganttCollapsed = new Set();
    (state.projects || []).forEach((project) => {
      if (project?.project_id) state.ganttCollapsed.add(`project:${project.project_id}`);
    });
    (state.solutions || []).forEach((solution) => {
      if (solution?.solution_id) state.ganttCollapsed.add(`solution:${solution.solution_id}`);
    });
    persistGanttViewState();
    renderGantt();
  }

  function expandAllGanttRows() {
    state.ganttCollapsed = new Set();
    persistGanttViewState();
    renderGantt();
  }

  function toggleCollapsedRow(key) {
    const target = String(key || "").trim();
    if (!target) return;
    if (!(state.ganttCollapsed instanceof Set)) state.ganttCollapsed = new Set();
    if (state.ganttCollapsed.has(target)) {
      state.ganttCollapsed.delete(target);
    } else {
      state.ganttCollapsed.add(target);
    }
    persistGanttViewState();
    renderGantt();
  }

  function openGanttProjectDrilldown(projectId) {
    const targetId = String(projectId || "").trim();
    if (!targetId) return;
    const project = (state.projects || []).find((row) => row.project_id === targetId);
    if (!project) return;
    openProjectForm(project);
  }

  function openGanttSolutionDrilldown(solutionId) {
    const targetId = String(solutionId || "").trim();
    if (!targetId) return;
    const solution = (state.solutions || []).find((row) => row.solution_id === targetId);
    if (!solution) return;
    openSolutionModal(solution, "details");
  }

  function openGanttTaskDrilldown(taskId) {
    const targetId = String(taskId || "").trim();
    if (!targetId) return;
    const task = (state.tasks || []).find((row) => row.task_id === targetId);
    if (!task) return;
    const solution = (state.solutions || []).find((row) => row.solution_id === task.solution_id);
    if (!solution) return;
    openSolutionModal(solution, "tasks");
    fillTaskForm(task);
  }

  function openGanttItem(type, id) {
    if (type === "project") {
      openGanttProjectDrilldown(id);
      return;
    }
    if (type === "solution") {
      openGanttSolutionDrilldown(id);
      return;
    }
    if (type === "task") {
      openGanttTaskDrilldown(id);
    }
  }

  function bindGanttRouteControls() {
    if (els.ganttFrom && !els.ganttFrom._bound) {
      els.ganttFrom.addEventListener("change", syncWindowFromInputs);
      els.ganttFrom._bound = true;
    }
    if (els.ganttTo && !els.ganttTo._bound) {
      els.ganttTo.addEventListener("change", syncWindowFromInputs);
      els.ganttTo._bound = true;
    }
    if (els.ganttExpandAll && !els.ganttExpandAll._bound) {
      els.ganttExpandAll.addEventListener("click", expandAllGanttRows);
      els.ganttExpandAll._bound = true;
    }
    if (els.ganttCollapseAll && !els.ganttCollapseAll._bound) {
      els.ganttCollapseAll.addEventListener("click", collapseAllGanttRows);
      els.ganttCollapseAll._bound = true;
    }
    if (els.ganttChart && !els.ganttChart._bound) {
      els.ganttChart.addEventListener("click", (event) => {
        const actionEl = event.target.closest("[data-gantt-action]");
        if (!actionEl) return;
        const action = actionEl.getAttribute("data-gantt-action") || "";
        if (action === "toggle-collapse") {
          toggleCollapsedRow(actionEl.getAttribute("data-gantt-key"));
          return;
        }
        if (action === "open-item") {
          openGanttItem(actionEl.getAttribute("data-gantt-type"), actionEl.getAttribute("data-gantt-id"));
        }
      });
      els.ganttChart._bound = true;
    }
    if (els.ganttChart && !els.ganttChart._resizeBound && typeof window !== "undefined") {
      let resizeFrame = 0;
      window.addEventListener("resize", () => {
        if (state.currentView !== "gantt") return;
        if (resizeFrame && typeof cancelAnimationFrame === "function") cancelAnimationFrame(resizeFrame);
        if (typeof requestAnimationFrame === "function") {
          resizeFrame = requestAnimationFrame(() => {
            resizeFrame = 0;
            renderGantt();
          });
          return;
        }
        renderGantt();
      });
      els.ganttChart._resizeBound = true;
    }
  }

  return {
    bindGanttRouteControls,
    persistGanttViewState,
    restoreGanttViewState,
    openGanttProjectDrilldown,
    openGanttSolutionDrilldown,
    openGanttTaskDrilldown,
  };
}
