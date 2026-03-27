function hasActiveDeliverableFilters(state) {
  const filterValues = Object.values(state.filters || {});
  const hasFieldFilters = filterValues.some((value) => {
    if (value == null) return false;
    if (typeof value === "number") return !Number.isNaN(value);
    return String(value).trim() !== "";
  });
  return hasFieldFilters || Boolean(state.deliverablesPreset);
}

export function renderMasterQuickstart(ctx, rowCount = 0) {
  const { els, state, showCompletedOperationalWork, isClosedProjectStatus, isClosedSolutionStatus } = ctx;
  if (!els.masterQuickstart) return;

  const hasRows = Number(rowCount) > 0;
  const hasDeliverableData = (state.projects?.length || 0) > 0 || (state.solutions?.length || 0) > 0;
  const hasFilters = hasActiveDeliverableFilters(state);
  const hiddenClosedDeliverables = !showCompletedOperationalWork()
    ? (state.projects || []).filter((project) => isClosedProjectStatus(project.status)).length
      + (state.solutions || []).filter((solution) => isClosedSolutionStatus(solution.status)).length
    : 0;

  if (hasRows) {
    els.masterQuickstart.classList.add("hidden");
    els.masterQuickstart.innerHTML = "";
    return;
  }

  if (!hasDeliverableData) {
    els.masterQuickstart.classList.remove("hidden");
    els.masterQuickstart.innerHTML = `
      <div class="quickstart-head">
        <h3>Quick Start</h3>
        <p class="muted">No deliverables in this space yet. Start with one project, then add solutions.</p>
      </div>
      <div class="quickstart-actions">
        <button type="button" class="primary" data-quick-action="create-project">Create first project</button>
        <button type="button" class="secondary" data-quick-action="create-solution">Create first solution</button>
      </div>
      <ol class="quickstart-steps">
        <li>Create a project with sponsor and objective.</li>
        <li>Add 1-3 solutions, then assign owners and due dates.</li>
        <li>Use Planning to allocate work and Dashboard to track progress.</li>
      </ol>
    `;
    return;
  }

  if (hasFilters) {
    els.masterQuickstart.classList.remove("hidden");
    els.masterQuickstart.innerHTML = `
      <div class="quickstart-head">
        <h3>No Matches</h3>
        <p class="muted">Current filters returned zero deliverables in this space.</p>
      </div>
      <div class="quickstart-actions">
        <button type="button" class="secondary" data-quick-action="clear-filters">Clear filters</button>
      </div>
    `;
    return;
  }

  if (hiddenClosedDeliverables > 0) {
    els.masterQuickstart.classList.remove("hidden");
    els.masterQuickstart.innerHTML = `
      <div class="quickstart-head">
        <h3>Completed Work Hidden</h3>
        <p class="muted">${hiddenClosedDeliverables} completed or abandoned deliverable${hiddenClosedDeliverables === 1 ? "" : "s"} are hidden from the workspace.</p>
      </div>
      <div class="quickstart-actions">
        <button type="button" class="secondary" data-quick-action="show-completed">Show completed work</button>
      </div>
    `;
    return;
  }

  els.masterQuickstart.classList.remove("hidden");
  els.masterQuickstart.innerHTML = `
    <div class="quickstart-head">
      <h3>No Deliverables Yet</h3>
      <p class="muted">This space is ready, but no projects or solutions have been added.</p>
    </div>
    <div class="quickstart-actions">
      <button type="button" class="primary" data-quick-action="create-project">Create project</button>
      <button type="button" class="secondary" data-quick-action="create-solution">Create solution</button>
    </div>
  `;
}
