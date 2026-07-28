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
  api,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  setStatus,
  phaseDisplayName,
  trackWorkflow,
}) {
  const pendingSolutionMoves = new Set();

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

  function isKanbanSolutionMovePending(solutionId) {
    return pendingSolutionMoves.has(String(solutionId || "").trim());
  }

  async function moveKanbanSolutionToPhase(solutionId, phaseId) {
    const targetSolutionId = String(solutionId || "").trim();
    const targetPhaseId = String(phaseId || "").trim();
    const solution = state.solutions.find((row) => row.solution_id === targetSolutionId);
    const phase = state.phases.find((row) => row.phase_id === targetPhaseId);
    if (!solution || !phase || pendingSolutionMoves.has(targetSolutionId)) return false;

    const previousPhaseId = solution.current_phase || null;
    if (previousPhaseId === targetPhaseId) return false;

    const solutionLabel = String(solution.solution_name || "Untitled solution");
    const phaseLabel = phaseDisplayName(targetPhaseId) || phase.phase_name || targetPhaseId;
    pendingSolutionMoves.add(targetSolutionId);
    solution.current_phase = targetPhaseId;
    setStatus(`Moving ${solutionLabel} to ${phaseLabel}...`);
    renderKanban();

    try {
      markIgnoreRefresh("solutions");
      const updated = await api(`/solutions/${encodeURIComponent(targetSolutionId)}`, {
        method: "PATCH",
        body: JSON.stringify({ current_phase: targetPhaseId }),
      });
      upsertById(state.solutions, updated, "solution_id");
      setStatus(`${solutionLabel} moved to ${phaseLabel}.`, "success");
      trackWorkflow?.("solutions", "update", "success", {
        source: "kanban_drag",
        field: "current_phase",
        from_phase: previousPhaseId,
        to_phase: targetPhaseId,
      });
      return true;
    } catch (err) {
      ignoreNextRefresh?.delete?.("solutions");
      const current = state.solutions.find((row) => row.solution_id === targetSolutionId);
      if (current?.current_phase === targetPhaseId) current.current_phase = previousPhaseId;
      setStatus(`Could not move ${solutionLabel} to ${phaseLabel}: ${err.message || "Save failed"}`, "danger");
      trackWorkflow?.("solutions", "update", "failure", {
        source: "kanban_drag",
        field: "current_phase",
        from_phase: previousPhaseId,
        to_phase: targetPhaseId,
      });
      return false;
    } finally {
      pendingSolutionMoves.delete(targetSolutionId);
      renderKanban();
    }
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
    isKanbanSolutionMovePending,
    moveKanbanSolutionToPhase,
    openKanbanProjectDrilldown,
    openKanbanSolutionDrilldown,
    persistKanbanViewState,
    restoreKanbanViewState,
  };
}
