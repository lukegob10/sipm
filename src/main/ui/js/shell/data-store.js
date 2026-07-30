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
  onViewDataLoaded = null,
  entitiesForView,
  isKnownEntity,
  dataEntities,
  viewPrefetchTarget,
}) {
  let refreshInFlight = false;
  const pendingRefreshEntities = new Set();
  const ignoreNextRefresh = new Set();
  let viewPrefetchTimer = null;
  let pendingLoadOptions = null;

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
    state.programs = [];
    state.projects = [];
    state.solutions = [];
    state.tasks = [];
    state.teams = [];
    state.users = [];
    state.ganttCollapsed = new Set();
    state.loadedEntities = new Set();
    if (state.myWork) {
      state.myWork.records = null;
      state.myWork.loading = false;
      state.myWork.error = "";
      state.myWork.selectedTaskId = "";
      state.myWork.search = "";
      state.myWork.repository = "";
      state.myWork.editingTaskId = "";
      state.myWork.draggingTaskId = "";
      state.myWork.savingPrivateTaskId = "";
      state.myWork.detailTab = "task";
      state.myWork.privateNotice = null;
      state.myWork.sharedActions = null;
    }
    if (state.repositoryInventory) {
      state.repositoryInventory.records = null;
      state.repositoryInventory.loading = false;
      state.repositoryInventory.error = "";
      state.repositoryInventory.search = "";
    }
    state.capacitySelectedSoeid = "";
    state.teamCapacity = createTeamCapacityState();
    if (state.tasksWorkbench) {
      state.tasksWorkbench.selected = new Set();
      state.tasksWorkbench.activeTaskId = "";
      state.tasksWorkbench.visibleIds = [];
      state.tasksWorkbench.activityRequestId = 0;
      state.tasksWorkbench.drawerOpen = false;
      state.tasksWorkbench.drawerReturnTaskId = "";
      state.tasksWorkbench.drawerReturnScrollY = null;
      state.tasksWorkbench.suppressAutoScrollOnce = false;
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
    if (entity === "programs") return api("/programs");
    if (entity === "projects") return api("/projects");
    if (entity === "solutions") return api("/solutions");
    if (entity === "tasks") return api("/tasks");
    if (entity === "teams") return api("/teams");
    if (entity === "users") return api("/users");
    throw new Error(`Unknown data entity: ${entity}`);
  }

  function applyEntityData(entity, data) {
    if (entity === "phases") {
      state.phases = Array.isArray(data) ? data : [];
    } else if (entity === "programs") {
      state.programs = Array.isArray(data) ? data : [];
    } else if (entity === "projects") {
      state.projects = Array.isArray(data) ? data : [];
    } else if (entity === "solutions") {
      state.solutions = Array.isArray(data) ? data : [];
    } else if (entity === "tasks") {
      state.tasks = Array.isArray(data) ? data : [];
    } else if (entity === "teams") {
      state.teams = Array.isArray(data) ? data : [];
    } else if (entity === "users") {
      state.users = Array.isArray(data) ? data : [];
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
      viewPrefetchTimer = null;
      if (!state.authed || state.loading || refreshInFlight) return;
      const entitiesToPrefetch = entitiesForView(targetView).filter((entity) => !state.loadedEntities.has(entity));
      if (!entitiesToPrefetch.length) return;
      try {
        const results = await Promise.allSettled(entitiesToPrefetch.map((entity) => fetchEntityData(entity)));
        let changed = false;
        results.forEach((result, idx) => {
          if (result.status !== "fulfilled") return;
          applyEntityData(entitiesToPrefetch[idx], result.value);
          changed = true;
        });
        if (changed) populateSelects();
      } catch (err) {
        console.warn("Prefetch skipped", err);
      }
    }, 450);
  }

  function syncUiAfterDataLoad({
    selectedProjectId = "",
    selectedSolutionId = "",
    selectedTaskId = "",
    prefetchView = "",
  } = {}) {
    let uiSyncError = null;

    try {
      populateSelects();
    } catch (err) {
      uiSyncError = err;
      console.error("Post-load select population failed", err);
    }

    try {
      restoreSelections(selectedProjectId, selectedSolutionId, selectedTaskId);
    } catch (err) {
      if (!uiSyncError) uiSyncError = err;
      console.error("Post-load selection restore failed", err);
    }

    try {
      renderActiveView();
    } catch (err) {
      if (!uiSyncError) uiSyncError = err;
      console.error("Post-load render failed", err);
    }

    if (prefetchView) {
      try {
        scheduleViewPrefetch(prefetchView);
      } catch (err) {
        if (!uiSyncError) uiSyncError = err;
        console.error("Post-load prefetch scheduling failed", err);
      }
    }

    return uiSyncError;
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
    const selectedTaskId = els.taskForm?.querySelector('[name="task_id"]')?.value || "";

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
        const entityKey = effectiveEntities[idx];
        applyEntityData(entityKey, result.value);
        if (entityKey === "tasks" && state.myWork) {
          state.myWork.records = null;
        }
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
      if (changed) {
        const uiSyncError = syncUiAfterDataLoad({
          selectedProjectId,
          selectedSolutionId,
          selectedTaskId,
        });
        if (uiSyncError) {
          setStatus(`Refresh partially applied: ${uiSyncError.message || "UI sync failed"}`, "warn");
        }
        return;
      }
      renderActiveView();
    } catch (err) {
      console.warn("Refresh failed", err);
      if (handleAuthError(err)) {
        setStatus("Portal sign-in required", "warn");
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

  function rememberPendingLoad(options = {}) {
    pendingLoadOptions = {
      ...options,
      force: !!options.force || !!pendingLoadOptions?.force,
    };
  }

  async function loadData(options = {}) {
    const loadStartedAt = Date.now();
    const force = !!options.force;
    const silent = !!options.silent;
    const routeReady = options.routeReady || Promise.resolve(null);
    const requestedEntities = Array.isArray(options.entities) ? options.entities.filter(isKnownEntity) : null;
    if (!state.authed) {
      setStatus("Portal sign-in required", "warn");
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
      await routeReady;
      renderActiveView();
      scheduleViewPrefetch(state.currentView);
      if (typeof onViewDataLoaded === "function") {
        onViewDataLoaded({ view: state.currentView, durationMs: 0, changed: false });
      }
      return;
    }
    const selectedProjectId = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
    const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    const selectedTaskId = els.taskForm?.querySelector('[name="task_id"]')?.value || "";
    if (state.loading) {
      state.pendingRefresh = true;
      rememberPendingLoad(options);
      return;
    }
    state.loading = true;
    try {
      if (!silent) setStatus("Loading...", "warn");
      if (!silent) {
        routeReady.then(() => {
          if (state.loading) renderActiveView();
        });
      }
      const results = await Promise.allSettled(entitiesToFetch.map((entity) => fetchEntityData(entity)));
      const errors = [];
      let changed = false;
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          applyEntityData(entitiesToFetch[idx], result.value);
          changed = true;
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
        if (!changed) {
          setStatus(`Load failed: ${labels}`, "danger");
          if (typeof onViewDataLoaded === "function") {
            onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: false });
          }
          return;
        }
        await routeReady;
        const uiSyncError = syncUiAfterDataLoad({
          selectedProjectId,
          selectedSolutionId,
          selectedTaskId,
          prefetchView: state.currentView,
        });
        const suffix = uiSyncError ? `; UI sync issue: ${uiSyncError.message || "render failed"}` : "";
        setStatus(`Partial load failed: ${labels}${suffix}`, "warn");
        if (typeof onViewDataLoaded === "function") {
          onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: true });
        }
        return;
      }

      await routeReady;
      const uiSyncError = syncUiAfterDataLoad({
        selectedProjectId,
        selectedSolutionId,
        selectedTaskId,
        prefetchView: state.currentView,
      });
      if (uiSyncError) {
        setStatus(`Loaded with UI sync issue: ${uiSyncError.message || "render failed"}`, "warn");
        if (typeof onViewDataLoaded === "function") {
          onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: true });
        }
        return;
      }
      if ((requestedEntities == null || requestedEntities.includes("programs") || requestedEntities.includes("projects") || requestedEntities.includes("solutions"))
        && !state.programs.length && !state.projects.length && !state.solutions.length) {
        setStatus("No data loaded", "warn");
      } else if (!silent) {
        setStatus("Online", "positive");
      }
      if (typeof onViewDataLoaded === "function") {
        onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: true });
      }
    } catch (err) {
      console.error("Load failed", err);
      if (!handleAuthError(err)) {
        setStatus(err.message || "Load failed", "danger");
      }
      if (typeof onViewDataLoaded === "function") {
        onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: false });
      }
    } finally {
      state.loading = false;
      if (state.pendingRefresh) {
        state.pendingRefresh = false;
        const queuedOptions = pendingLoadOptions || {};
        pendingLoadOptions = null;
        loadData(queuedOptions);
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
