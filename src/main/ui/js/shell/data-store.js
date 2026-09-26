import { createFormDraftGuard } from "../utils/form-draft.js";

export function bindTaskRefreshDraft(form) {
  const draft = createFormDraftGuard({ form });
  draft.bind();
  // Entity fills and successful saves reset first, then populate synchronously.
  // Capture after both native reset and the entity's field assignments finish.
  form?.addEventListener("reset", () => queueMicrotask(() => draft.capture()));
  return draft;
}

export function restoreEditorSelections({
  state,
  els,
  openProjectForm,
  openSolutionModal,
  fillTaskForm,
}, projectId, solutionId, taskId) {
  const taskOpen = !!els.taskForm && !els.taskForm.classList.contains("hidden")
    && !els.solutionModal?.classList.contains("hidden");
  const taskDirty = taskOpen && els.taskForm.hasAttribute("data-dirty");
  if (projectId && !els.projectForm?.hasAttribute("data-dirty") && !els.projectModal?.classList.contains("hidden")) {
    const project = state.projects.find((row) => row.project_id === projectId);
    if (project) openProjectForm(project);
  }
  // Reopening the parent resets its fields and closes the nested task editor.
  if (solutionId && !els.solutionForm?.hasAttribute("data-dirty") && !taskDirty
      && !els.solutionModal?.classList.contains("hidden")) {
    const solution = state.solutions.find((row) => row.solution_id === solutionId);
    if (solution) {
      const activeTab = els.solutionModal?.querySelector(".modal-tabs .tab.active")?.dataset?.tab || "details";
      openSolutionModal(solution, activeTab);
    }
  }
  if (taskId && taskOpen && !taskDirty) {
    const task = state.tasks.find((row) => row.task_id === taskId);
    if (task) fillTaskForm(task);
  }
}

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
  let dataGeneration = 0;
  const activeRequestControllers = new Set();
  const entityReads = new Map();
  const entityVersions = new Map();
  const activePrefetchReads = new Set();
  let loadOperation = null;
  let refreshOperation = null;
  const pendingRefreshEntities = new Set();
  const ignoreNextRefresh = new Set();
  let viewPrefetchTimer = null;
  let prefetchGeneration = 0;
  let selectsNeedSync = false;

  function createTeamCapacityState(requestId = 0) {
    return {
      loading: false,
      error: "",
      lastLoadedAt: "",
      lastLoadedSpaceId: "",
      lastLoadedSpaceName: "",
      requestId,
    };
  }

  function currentSpaceId() {
    return String(state.activeSpace?.space_id || "");
  }

  function captureDataContext() {
    return {
      generation: dataGeneration,
      spaceId: currentSpaceId(),
      userId: String(state.user?.soeid || state.user?.email || ""),
    };
  }

  function isDataContextCurrent(context) {
    return context.generation === dataGeneration && context.spaceId === currentSpaceId()
      && context.userId === String(state.user?.soeid || state.user?.email || "");
  }

  function hasPendingForegroundLoad() {
    return loadOperation && isDataContextCurrent(loadOperation.context) && loadOperation.view === state.currentView;
  }

  function createRequestController(context) {
    if (!isDataContextCurrent(context) || typeof AbortController !== "function") return null;
    const controller = new AbortController();
    activeRequestControllers.add(controller);
    return controller;
  }

  function releaseRequestController(controller) {
    if (controller) activeRequestControllers.delete(controller);
  }

  function cancelViewPrefetch() {
    prefetchGeneration += 1;
    if (!viewPrefetchTimer) return;
    window.clearTimeout(viewPrefetchTimer);
    viewPrefetchTimer = null;
  }

  function invalidateDataContext() {
    dataGeneration += 1;
    cancelViewPrefetch();
    activeRequestControllers.forEach((controller) => controller.abort());
    activeRequestControllers.clear();
    entityReads.clear();
    entityVersions.clear();
    activePrefetchReads.clear();
    selectsNeedSync = false;
    loadOperation = null;
    refreshOperation = null;
    pendingRefreshEntities.clear();
    ignoreNextRefresh.clear();
    state.loading = false;
    state.pendingRefresh = false;
  }

  function clearDataState() {
    invalidateDataContext();
    const nextTeamCapacityRequestId = (Number(state.teamCapacity?.requestId) || 0) + 1;
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
    state.teamCapacity = createTeamCapacityState(nextTeamCapacityRequestId);
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

  async function fetchEntityData(entity, options = {}) {
    if (entity === "phases") return api("/phases", options);
    if (entity === "programs") return api("/programs", options);
    if (entity === "projects") return api("/projects", options);
    if (entity === "solutions") return api("/solutions", options);
    if (entity === "tasks") return api("/tasks", options);
    if (entity === "teams") return api("/teams", options);
    if (entity === "users") return api("/users", options);
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
    selectsNeedSync = true;
  }

  function syncSelects() {
    populateSelects();
    selectsNeedSync = false;
  }

  function invalidateEntity(entity) {
    entityVersions.set(entity, (entityVersions.get(entity) || 0) + 1);
    state.loadedEntities.delete(entity);
    // A read started before this invalidation cannot satisfy any consumer's freshness requirement.
    entityReads.get(entity)?.controller?.abort();
    entityReads.delete(entity);
  }

  async function readEntity(entity, context, canContinue = () => true) {
    while (isDataContextCurrent(context)) {
      const version = entityVersions.get(entity) || 0;
      if (state.loadedEntities.has(entity)) return { status: "fulfilled", version };
      if (!canContinue()) break;
      let read = entityReads.get(entity);
      // These collection endpoints have no query parameters. Sharing is limited to the
      // same identity, space, generation, entity endpoint, and invalidation version.
      if (!read || !isDataContextCurrent(read.context) || read.version !== version) {
        read = { context, version, controller: createRequestController(context) };
        const request = read;
        request.promise = (async () => {
          try {
            const data = await fetchEntityData(entity, request.controller ? { signal: request.controller.signal } : {});
            if (isDataContextCurrent(context) && version === (entityVersions.get(entity) || 0)) {
              applyEntityData(entity, data);
            }
          } finally {
            releaseRequestController(request.controller);
            if (entityReads.get(entity) === request) entityReads.delete(entity);
          }
        })();
        entityReads.set(entity, request);
      }
      try {
        await read.promise;
      } catch (err) {
        if (!isDataContextCurrent(context)) break;
        if (version === (entityVersions.get(entity) || 0)) return { status: "rejected", reason: err, version };
      }
      // A force/reload or live invalidation during this read requires the newer read.
      // Existing callers keep awaiting it instead of accepting the obsolete response.
    }
    return { status: "cancelled" };
  }

  async function readEntities(entities, context, routeReady = Promise.resolve()) {
    const results = await Promise.all(entities.map((entity) => readEntity(entity, context)));
    await routeReady;
    // Recheck even cached dependencies: one collection may have been invalidated
    // while another collection or the route module was still pending.
    while (isDataContextCurrent(context)) {
      const invalidated = entities.filter((entity, idx) => results[idx].version !== (entityVersions.get(entity) || 0));
      if (!invalidated.length) break;
      const retried = await Promise.all(invalidated.map((entity) => readEntity(entity, context)));
      invalidated.forEach((entity, idx) => {
        results[entities.indexOf(entity)] = retried[idx];
      });
    }
    return results;
  }

  function scheduleViewPrefetch(view) {
    cancelViewPrefetch();
    const context = captureDataContext();
    const generation = prefetchGeneration;
    const sourceView = state.currentView;
    const targetView = viewPrefetchTarget[view] || viewPrefetchTarget.master;
    if (!targetView || !state.authed) return;
    const needed = entitiesForView(targetView).filter((entity) => !state.loadedEntities.has(entity));
    if (!needed.length) return;
    viewPrefetchTimer = window.setTimeout(async () => {
      viewPrefetchTimer = null;
      const canPrefetch = () => isDataContextCurrent(context) && state.authed
        && generation === prefetchGeneration && state.currentView === sourceView
        && !state.loading && !hasPendingForegroundLoad() && !refreshOperation
        && document.visibilityState !== "hidden" && !navigator.connection?.saveData
        && !["slow-2g", "2g"].includes(navigator.connection?.effectiveType);
      if (!canPrefetch()) return;
      const entitiesToPrefetch = entitiesForView(targetView).filter((entity) => !state.loadedEntities.has(entity));
      if (!entitiesToPrefetch.length) return;
      let changed = false;
      const prefetchNext = async () => {
        while (entitiesToPrefetch.length && canPrefetch() && activePrefetchReads.size < 2) {
          const entity = entitiesToPrefetch.shift();
          const pending = readEntity(entity, context, canPrefetch);
          activePrefetchReads.add(pending);
          const result = await pending;
          activePrefetchReads.delete(pending);
          changed = result.status === "fulfilled" || changed;
        }
      };
      try {
        // At most two speculative reads; navigation can share them and starts its own
        // dependencies immediately without waiting for the rest of this queue.
        await Promise.all([prefetchNext(), prefetchNext()]);
        if (!isDataContextCurrent(context)) return;
        if (changed && !state.loading && !hasPendingForegroundLoad()) syncSelects();
      } catch (err) {
        if (isDataContextCurrent(context)) console.warn("Prefetch skipped", err);
      }
    }, 450);
  }

  function syncUiAfterDataLoad({
    prefetchView = "",
  } = {}) {
    const selectedProjectId = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
    const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    const selectedTaskId = els.taskForm?.querySelector('[name="task_id"]')?.value || "";
    let uiSyncError = null;

    try {
      syncSelects();
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

    const entities = isKnownEntity(ent) ? [ent] : dataEntities;
    entities.forEach((key) => {
      invalidateEntity(key);
      pendingRefreshEntities.add(key);
    });
    return flushPendingRefreshes();
  }

  async function runRefresh(effectiveEntities) {
    const context = captureDataContext();
    const operation = { context };
    refreshOperation = operation;
    try {
      const results = await readEntities(effectiveEntities, context);
      if (!isDataContextCurrent(context) || refreshOperation !== operation) return;
      const errors = [];
      let changed = false;
      results.forEach((result, idx) => {
        if (result.status !== "fulfilled") {
          errors.push(result.reason);
          return;
        }
        const entityKey = effectiveEntities[idx];
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
      // The foreground load owns rendering while its route module/data are pending.
      if (state.loading || hasPendingForegroundLoad()) return;
      if (changed) {
        const uiSyncError = syncUiAfterDataLoad();
        if (uiSyncError) {
          setStatus(`Refresh partially applied: ${uiSyncError.message || "UI sync failed"}`, "warn");
        }
        return;
      }
      renderActiveView();
    } catch (err) {
      if (!isDataContextCurrent(context) || refreshOperation !== operation) return;
      console.warn("Refresh failed", err);
      if (handleAuthError(err)) {
        setStatus("Portal sign-in required", "warn");
      }
    } finally {
      if (refreshOperation !== operation) return;
      refreshOperation = null;
      if (!isDataContextCurrent(context)) return;
      void flushPendingRefreshes();
    }
  }

  function flushPendingRefreshes() {
    if (!state.authed || state.loading || hasPendingForegroundLoad() || refreshOperation || !pendingRefreshEntities.size) return;
    const pending = Array.from(pendingRefreshEntities);
    pendingRefreshEntities.clear();
    return runRefresh(pending);
  }

  async function loadData(options = {}) {
    const loadStartedAt = Date.now();
    const force = !!options.force;
    const silent = !!options.silent;
    const routeReady = options.routeReady || Promise.resolve(null);
    const requestedEntities = Array.isArray(options.entities) ? options.entities.filter(isKnownEntity) : null;
    const context = captureDataContext();
    const view = state.currentView;
    cancelViewPrefetch();
    if (!state.authed) {
      setStatus("Portal sign-in required", "warn");
      setAuthVisible(true);
      return;
    }
    const targetEntities = requestedEntities && requestedEntities.length
      ? [...new Set(requestedEntities)]
      : entitiesForView(view);
    if (force) targetEntities.forEach(invalidateEntity);
    const entitiesToFetch = targetEntities.filter((entity) => !state.loadedEntities.has(entity));
    const versions = targetEntities.map((entity) => entityVersions.get(entity) || 0);
    const operation = {
      context,
      view,
      pendingStatus: (!silent && entitiesToFetch.length > 0)
        || (loadOperation?.pendingStatus && isDataContextCurrent(loadOperation.context)),
    };
    const isActiveLoad = () => isDataContextCurrent(context) && loadOperation === operation
      && state.currentView === view;
    const setLoadedStatus = () => {
      if ((requestedEntities == null || requestedEntities.includes("programs") || requestedEntities.includes("projects") || requestedEntities.includes("solutions"))
        && !state.programs.length && !state.projects.length && !state.solutions.length) {
        setStatus("No data loaded", "warn");
      } else if (!silent || operation.pendingStatus) {
        setStatus("Online", "positive");
      }
    };
    loadOperation = operation;
    state.loading = entitiesToFetch.length > 0;
    try {
      if (!silent && state.loading) setStatus("Loading...", "warn");
      void routeReady.then(
        () => {
          if (!silent && isActiveLoad() && state.loading) renderActiveView();
        },
        () => {},
      );
      const entityResults = await readEntities(targetEntities, context, routeReady);
      if (!isDataContextCurrent(context)) return;
      targetEntities.forEach((entity, idx) => {
        if (versions[idx] !== entityResults[idx].version && !entitiesToFetch.includes(entity)) entitiesToFetch.push(entity);
      });
      const results = entitiesToFetch.map((entity) => entityResults[targetEntities.indexOf(entity)]);
      const authError = results.find((result) => result.reason?.status === 401);
      if (authError) {
        handleAuthError(authError.reason);
        return;
      }
      if (!isActiveLoad()) return;
      if (!entitiesToFetch.length) {
        // Another route can have supplied these collections before its remaining
        // reads finish. Its eventual completion will not synchronize the current UI.
        if (selectsNeedSync) syncSelects();
        renderActiveView();
        scheduleViewPrefetch(view);
        if (operation.pendingStatus) setLoadedStatus();
        if (typeof onViewDataLoaded === "function") {
          onViewDataLoaded({ view, durationMs: 0, changed: false });
        }
        return;
      }
      const errors = [];
      let changed = false;
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          changed = true;
        } else {
          errors.push({ key: entitiesToFetch[idx], error: result.reason });
        }
      });

      if (errors.length) {
        const labels = errors.map((entry) => entry.key).join(", ");
        console.error("Load failed", errors);
        if (!changed) {
          setStatus(`Load failed: ${labels}`, "danger");
          if (typeof onViewDataLoaded === "function") {
            onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: false });
          }
          return;
        }
        const uiSyncError = syncUiAfterDataLoad({
          prefetchView: state.currentView,
        });
        const suffix = uiSyncError ? `; UI sync issue: ${uiSyncError.message || "render failed"}` : "";
        setStatus(`Partial load failed: ${labels}${suffix}`, "warn");
        if (typeof onViewDataLoaded === "function") {
          onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: true });
        }
        return;
      }

      const uiSyncError = syncUiAfterDataLoad({
        prefetchView: state.currentView,
      });
      if (uiSyncError) {
        setStatus(`Loaded with UI sync issue: ${uiSyncError.message || "render failed"}`, "warn");
        if (typeof onViewDataLoaded === "function") {
          onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: true });
        }
        return;
      }
      setLoadedStatus();
      if (typeof onViewDataLoaded === "function") {
        onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: true });
      }
    } catch (err) {
      if (!isActiveLoad()) return;
      console.error("Load failed", err);
      if (!handleAuthError(err)) {
        setStatus(err.message || "Load failed", "danger");
      }
      if (typeof onViewDataLoaded === "function") {
        onViewDataLoaded({ view: state.currentView, durationMs: Date.now() - loadStartedAt, changed: false });
      }
    } finally {
      if (loadOperation !== operation) return;
      loadOperation = null;
      state.loading = false;
      if (!isDataContextCurrent(context)) return;
      void flushPendingRefreshes();
    }
  }

  async function reloadCurrentViewData(options = {}) {
    const force = !!options.force;
    const silent = !!options.silent;
    const preserveCapacitySelection = options.preserveCapacitySelection !== false;
    if (state.currentView === "team-capacity") {
      const context = captureDataContext();
      const controller = createRequestController(context);
      try {
        return await loadTeamCapacityData({
          force,
          preserveSelection: preserveCapacitySelection,
          signal: controller?.signal,
        });
      } finally {
        releaseRequestController(controller);
      }
    }
    return loadData({ force, silent, entities: options.entities });
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
