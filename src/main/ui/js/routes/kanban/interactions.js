export function createKanbanRouteController({
  state,
  els,
  kanbanViewStateKey,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  bindDebouncedInput,
  renderKanban,
  openProjectForm,
  openSolutionModal,
  hideClosedDeliverables,
  isClosedSolutionStatus,
}) {
  function filteredSolutionsForKanban() {
    const { project, owner } = state.kanbanFilters || {};
    const ownerNorm = (owner || "").toLowerCase();
    return (state.solutions || []).filter((solution) => {
      if (hideClosedDeliverables() && isClosedSolutionStatus(solution.status)) return false;
      if (project && solution.project_id !== project) return false;
      if (ownerNorm && !(solution.owner || "").toLowerCase().includes(ownerNorm)) return false;
      return true;
    });
  }

  function openKanbanProjectDrilldown(projectId) {
    const targetId = String(projectId || "").trim();
    if (!targetId) return;
    const project = state.projects.find((row) => row.project_id === targetId);
    if (!project) return;
    openProjectForm(project);
  }

  function openKanbanSolutionDrilldown(solutionId) {
    const targetId = String(solutionId || "").trim();
    if (!targetId) return;
    const solution = state.solutions.find((row) => row.solution_id === targetId);
    if (!solution) return;
    openSolutionModal(solution, "details");
  }

  function persistKanbanViewState() {
    writeStoredJson(
      activeSpaceScopedStorageKey(kanbanViewStateKey),
      {
        filters: {
          project: state.kanbanFilters?.project || "",
          owner: state.kanbanFilters?.owner || "",
        },
      }
    );
  }

  function restoreKanbanViewState() {
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(kanbanViewStateKey), {});
    state.kanbanFilters = {
      project: String(stored.filters?.project || ""),
      owner: String(stored.filters?.owner || ""),
    };
    if (recovered) persistKanbanViewState();
    if (recovered) return;
    if (recovered || !Object.keys(stored || {}).length) persistKanbanViewState();
  }

  function bindKanbanRouteControls() {
    els.kanbanFilterProject?.addEventListener("change", () => {
      state.kanbanFilters.project = els.kanbanFilterProject.value || "";
      persistKanbanViewState();
      renderKanban();
    });
    bindDebouncedInput(els.kanbanFilterOwner, (value) => {
      state.kanbanFilters.owner = value;
      persistKanbanViewState();
      renderKanban();
    });
  }

  return {
    bindKanbanRouteControls,
    filteredSolutionsForKanban,
    openKanbanProjectDrilldown,
    openKanbanSolutionDrilldown,
    persistKanbanViewState,
    restoreKanbanViewState,
  };
}
