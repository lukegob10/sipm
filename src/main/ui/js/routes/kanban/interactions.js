import { beginSolutionMutation, captureEntityMutationContext, isEntityMutationContextCurrent } from "../../utils/form-state.js";

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
  upsertById,
  setStatus,
  phaseDisplayName,
  trackWorkflow,
}) {
  const pendingSolutionMoves = new Map();

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
    const id = String(solutionId || "").trim();
    const request = pendingSolutionMoves.get(id);
    if (!request) return false;
    if (request.authed === state.authed && isEntityMutationContextCurrent(state, request.context)) return true;
    pendingSolutionMoves.delete(id);
    return false;
  }

  async function moveKanbanSolutionToPhase(solutionId, phaseId) {
    const targetSolutionId = String(solutionId || "").trim();
    const targetPhaseId = String(phaseId || "").trim();
    const solution = state.solutions.find((row) => row.solution_id === targetSolutionId);
    const phase = state.phases.find((row) => row.phase_id === targetPhaseId);
    if (!solution || !phase || isKanbanSolutionMovePending(targetSolutionId)) return false;

    const previousPhaseId = solution.current_phase || null;
    if (previousPhaseId === targetPhaseId) return false;
    const release = beginSolutionMutation(state, targetSolutionId);
    if (!release) {
      setStatus("This solution is being updated. Try again when it finishes.", "danger");
      return false;
    }

    const solutionLabel = String(solution.solution_name || "Untitled solution");
    const phaseLabel = phaseDisplayName(targetPhaseId) || phase.phase_name || targetPhaseId;
    const request = { context: captureEntityMutationContext(state), authed: state.authed };
    const isCurrent = () => pendingSolutionMoves.get(targetSolutionId) === request
      && state.authed === request.authed && isEntityMutationContextCurrent(state, request.context);
    pendingSolutionMoves.set(targetSolutionId, request);
    solution.current_phase = targetPhaseId;
    setStatus(`Moving ${solutionLabel} to ${phaseLabel}...`);
    renderKanban();

    try {
      const updated = await api(`/solutions/${encodeURIComponent(targetSolutionId)}`, {
        method: "PATCH",
        body: JSON.stringify({ current_phase: targetPhaseId }),
      });
      if (!isCurrent()) return false;
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
      if (!isCurrent()) return false;
      const current = state.solutions.find((row) => row.solution_id === targetSolutionId);
      if (current === solution && current.current_phase === targetPhaseId) current.current_phase = previousPhaseId;
      setStatus(`Could not move ${solutionLabel} to ${phaseLabel}: ${err.message || "Save failed"}`, "danger");
      trackWorkflow?.("solutions", "update", "failure", {
        source: "kanban_drag",
        field: "current_phase",
        from_phase: previousPhaseId,
        to_phase: targetPhaseId,
      });
      return false;
    } finally {
      release();
      const current = isCurrent();
      if (pendingSolutionMoves.get(targetSolutionId) === request) pendingSolutionMoves.delete(targetSolutionId);
      if (current) renderKanban();
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

  let ownerInputContext = null;

  function restoreKanbanViewState() {
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(kanbanViewStateKey), {});
    const pending = ownerInputContext;
    const retainPending = pending && state.authed === pending.authed
      && state.kanbanFilters === pending.filters
      && isEntityMutationContextCurrent(state, pending.context);
    state.kanbanFilters = {
      project: String(stored.filters?.project || ""),
      owner: retainPending ? pending.value : String(stored.filters?.owner || ""),
    };
    if (retainPending) pending.filters = state.kanbanFilters;
    else ownerInputContext = null;
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
      const captured = ownerInputContext;
      ownerInputContext = null;
      if (!captured || state.authed !== captured.authed || state.kanbanFilters !== captured.filters
          || !isEntityMutationContextCurrent(state, captured.context)) return;
      state.kanbanFilters.owner = value;
      persistKanbanViewState();
      renderKanban();
    }, 180, (value) => {
      ownerInputContext = { context: captureEntityMutationContext(state), authed: state.authed, filters: state.kanbanFilters, value };
    });
  }

  return {
    getPendingOwner: () => ownerInputContext && state.authed === ownerInputContext.authed
      && state.kanbanFilters === ownerInputContext.filters
      && isEntityMutationContextCurrent(state, ownerInputContext.context) ? ownerInputContext.value : null,
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
