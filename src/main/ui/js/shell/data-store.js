export function createDataStoreController({
  state,
  els,
  api,
  setStatus,
  setAuthVisible,
  renderActiveView,
  populateSelects,
  restoreSelections,
  handleAuthError,
  loadTeamCapacityData,
  entitiesForView,
  isKnownEntity,
  dataEntities,
  viewPrefetchTarget,
}) {
  let refreshInFlight = false;
  const pendingRefreshEntities = new Set();
  const ignoreNextRefresh = new Set();
  let viewPrefetchTimer = null;

  function createTeamCapacityState() {
    return {
      loading: false,
      error: "",
      lastLoadedAt: "",
      lastLoadedSpaceId: "",
      lastLoadedSpaceName: "",
      requestId: 0,
    };
  }

  function clearDataState() {
    state.phases = [];
    state.projects = [];
    state.solutions = [];
    state.solutionPhases = {};
    state.subcomponents = [];
    state.teams = [];
    state.users = [];
    state.allocations = [];
    state.planningWindows = [];
    state.loadedEntities = new Set();
    state.capacitySelectedSoeid = "";
    state.teamCapacity = createTeamCapacityState();
    if (state.subcomponentsWorkbench) {
      state.subcomponentsWorkbench.selected = new Set();
      state.subcomponentsWorkbench.activeSubcomponentId = "";
      state.subcomponentsWorkbench.visibleIds = [];
      state.subcomponentsWorkbench.activityRequestId = 0;
      state.subcomponentsWorkbench.drawerOpen = false;
      state.subcomponentsWorkbench.drawerReturnSubcomponentId = "";
      state.subcomponentsWorkbench.drawerReturnScrollY = null;
      state.subcomponentsWorkbench.suppressAutoScrollOnce = false;
    }
  }

  function markIgnoreRefresh(entity) {
    if (entity) ignoreNextRefresh.add(entity);
  }

  function clearIgnoredRefresh(entity) {
    if (entity) ignoreNextRefresh.delete(entity);
  }

  async function fetchEntityData(entity) {
    if (entity === "phases") return api("/phases");
    if (entity === "projects") return api("/projects");
    if (entity === "solutions") return api("/solutions");
    if (entity === "subcomponents") return api("/subcomponents");
    if (entity === "teams") return api("/teams");
    if (entity === "users") return api("/users");
    if (entity === "allocations") return api("/resource-allocations");
    if (entity === "windows") return api("/planning/windows");
    throw new Error(`Unknown data entity: ${entity}`);
  }

  function applyEntityData(entity, data) {
    if (entity === "phases") {
      state.phases = Array.isArray(data) ? data : [];
      state.solutionPhases = {};
    } else if (entity === "projects") {
      state.projects = Array.isArray(data) ? data : [];
    } else if (entity === "solutions") {
      state.solutions = Array.isArray(data) ? data : [];
    } else if (entity === "subcomponents") {
      state.subcomponents = Array.isArray(data) ? data : [];
    } else if (entity === "teams") {
      state.teams = Array.isArray(data) ? data : [];
    } else if (entity === "users") {
      state.users = Array.isArray(data) ? data : [];
    } else if (entity === "allocations") {
      state.allocations = Array.isArray(data) ? data : [];
    } else if (entity === "windows") {
      state.planningWindows = Array.isArray(data) ? data : [];
    }
    state.loadedEntities.add(entity);
  }

  function scheduleViewPrefetch(view) {
    const targetView = viewPrefetchTarget[view] || viewPrefetchTarget.master;
    if (!targetView || !state.authed) return;
    const needed = entitiesForView(targetView).filter((entity) => !state.loadedEntities.has(entity));
    if (!needed.length) return;
    if (viewPrefetchTimer) window.clearTimeout(viewPrefetchTimer);
    viewPrefetchTimer = window.setTimeout(async () => {
      if (!state.authed || state.loading || refreshInFlight) return;
      try {
        const results = await Promise.allSettled(needed.map((entity) => fetchEntityData(entity)));
        let changed = false;
        results.forEach((result, idx) => {
          if (result.status !== "fulfilled") return;
          applyEntityData(needed[idx], result.value);
          changed = true;
        });
        if (changed) populateSelects();
      } catch (err) {
        console.warn("Prefetch skipped", err);
      }
    }, 450);
  }

  async function refreshFromServer(entity = "all") {
    const ent = (entity || "all").toString();
    if (!state.authed) return;

    if (ignoreNextRefresh.has(ent)) {
      ignoreNextRefresh.delete(ent);
      return;
    }

    if (state.loading || refreshInFlight) {
      pendingRefreshEntities.add(ent);
      return;
    }

    const selectedProjectId = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
    const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    const selectedSubcomponentId = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";

    refreshInFlight = true;
    try {
      const effectiveEntities = ent === "all" ? [...dataEntities] : (isKnownEntity(ent) ? [ent] : [...dataEntities]);
      const results = await Promise.allSettled(effectiveEntities.map((key) => fetchEntityData(key)));
      const errors = [];
      let changed = false;
      results.forEach((result, idx) => {
        if (result.status !== "fulfilled") {
          errors.push(result.reason);
          return;
        }
        applyEntityData(effectiveEntities[idx], result.value);
        changed = true;
      });
      if (errors.length) {
        const authError = errors.find((err) => err && err.status === 401);
        if (authError) {
          handleAuthError(authError);
          return;
        }
        console.warn("Refresh failed", errors);
      }
      if (changed) populateSelects();
      renderActiveView();
      restoreSelections(selectedProjectId, selectedSolutionId, selectedSubcomponentId);
    } catch (err) {
      console.warn("Refresh failed", err);
      if (handleAuthError(err)) {
        setStatus("Sign in required", "warn");
      }
    } finally {
      refreshInFlight = false;
      if (pendingRefreshEntities.size) {
        const pending = Array.from(pendingRefreshEntities);
        pendingRefreshEntities.clear();
        if (pending.includes("all") || pending.length > 1) {
          refreshFromServer("all");
        } else {
          refreshFromServer(pending[0]);
        }
      }
    }
  }

  async function loadData(options = {}) {
    const force = !!options.force;
    const silent = !!options.silent;
    const requestedEntities = Array.isArray(options.entities) ? options.entities.filter(isKnownEntity) : null;
    if (!state.authed) {
      setStatus("Sign in required", "warn");
      setAuthVisible(true);
      return;
    }
    const targetEntities = requestedEntities && requestedEntities.length
      ? [...new Set(requestedEntities)]
      : entitiesForView(state.currentView);
    const entitiesToFetch = force
      ? targetEntities
      : targetEntities.filter((entity) => !state.loadedEntities.has(entity));
    if (!entitiesToFetch.length) {
      renderActiveView();
      scheduleViewPrefetch(state.currentView);
      return;
    }
    const selectedProjectId = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
    const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    const selectedSubcomponentId = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";
    if (state.loading) {
      state.pendingRefresh = true;
      return;
    }
    state.loading = true;
    try {
      if (!silent) setStatus("Loading...", "warn");
      if (!silent) renderActiveView();
      const results = await Promise.allSettled(entitiesToFetch.map((entity) => fetchEntityData(entity)));
      const errors = [];
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          applyEntityData(entitiesToFetch[idx], result.value);
        } else {
          errors.push({ key: entitiesToFetch[idx], error: result.reason });
        }
      });

      if (errors.length) {
        const authError = errors.find((entry) => entry.error && entry.error.status === 401);
        if (authError) {
          handleAuthError(authError.error);
          return;
        }
        const labels = errors.map((entry) => entry.key).join(", ");
        console.error("Load failed", errors);
        setStatus(`Load failed: ${labels}`, "danger");
        return;
      }

      populateSelects();
      restoreSelections(selectedProjectId, selectedSolutionId, selectedSubcomponentId);
      renderActiveView();
      scheduleViewPrefetch(state.currentView);
      if ((requestedEntities == null || requestedEntities.includes("projects") || requestedEntities.includes("solutions"))
        && !state.projects.length && !state.solutions.length) {
        setStatus("No data loaded", "warn");
      } else if (!silent) {
        setStatus("Online", "positive");
      }
    } catch (err) {
      console.error("Load failed", err);
      if (!handleAuthError(err)) {
        setStatus(err.message || "Load failed", "danger");
      }
    } finally {
      state.loading = false;
      if (state.pendingRefresh) {
        state.pendingRefresh = false;
        loadData();
      }
      if (pendingRefreshEntities.size) {
        const pending = Array.from(pendingRefreshEntities);
        pendingRefreshEntities.clear();
        if (pending.includes("all") || pending.length > 1) {
          refreshFromServer("all");
        } else {
          refreshFromServer(pending[0]);
        }
      }
    }
  }

  async function reloadCurrentViewData(options = {}) {
    const force = !!options.force;
    const silent = !!options.silent;
    const preserveCapacitySelection = options.preserveCapacitySelection !== false;
    if (state.currentView === "team-capacity") {
      await loadTeamCapacityData({ force, preserveSelection: preserveCapacitySelection });
      return;
    }
    await loadData({ force, silent, entities: options.entities });
  }

  return {
    clearDataState,
    markIgnoreRefresh,
    clearIgnoredRefresh,
    fetchEntityData,
    applyEntityData,
    scheduleViewPrefetch,
    refreshFromServer,
    loadData,
    reloadCurrentViewData,
  };
}
