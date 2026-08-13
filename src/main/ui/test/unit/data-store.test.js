import { afterEach, describe, expect, it, vi } from "vitest";

import { createDataStoreController } from "../../js/shell/data-store.js";


function createError(message, status = 500) {
  const err = new Error(message);
  err.status = status;
  return err;
}

function createHarness(apiImpl, overrides = {}) {
  const state = {
    authed: true,
    activeSpace: { space_id: "space-a", space_name: "Space A" },
    currentView: "master",
    loading: false,
    pendingRefresh: false,
    loadedEntities: new Set(),
    phases: [],
    programs: [],
    projects: [],
    solutions: [],
    tasks: [],
    teams: [],
    users: [],
    capacitySelectedSoeid: "",
    teamCapacity: {},
    tasksWorkbench: null,
    ...(overrides.state || {}),
  };
  const setStatus = overrides.setStatus || vi.fn();
  const setAuthVisible = overrides.setAuthVisible || vi.fn();
  const renderActiveView = overrides.renderActiveView || vi.fn();
  const populateSelects = overrides.populateSelects || vi.fn();
  const restoreSelections = overrides.restoreSelections || vi.fn();
  const handleAuthError = overrides.handleAuthError || vi.fn(() => false);
  const onViewDataLoaded = overrides.onViewDataLoaded || vi.fn();
  const api = vi.fn(apiImpl);
  const controller = createDataStoreController({
    state,
    els: {
      projectForm: null,
      solutionForm: null,
      taskForm: null,
    },
    api,
    setStatus,
    setAuthVisible,
    renderActiveView,
    populateSelects,
    restoreSelections,
    handleAuthError,
    loadTeamCapacityData: vi.fn(),
    onViewDataLoaded,
    entitiesForView: overrides.entitiesForView || vi.fn(() => ["projects", "solutions"]),
    isKnownEntity: (entity) => ["phases", "projects", "solutions", "tasks", "teams", "users"].includes(entity),
    dataEntities: ["phases", "projects", "solutions", "tasks", "teams", "users"],
    viewPrefetchTarget: overrides.viewPrefetchTarget || {},
  });
  return {
    controller,
    state,
    api,
    setStatus,
    setAuthVisible,
    renderActiveView,
    populateSelects,
    restoreSelections,
    handleAuthError,
    onViewDataLoaded,
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}


describe("data store controller", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("renders partial data when a non-auth entity request fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { controller, state, setStatus, renderActiveView, populateSelects, restoreSelections } = createHarness((path) => {
      if (path === "/projects") {
        return Promise.resolve([{ project_id: "project-1", project_name: "Project 1" }]);
      }
      if (path === "/users") {
        return Promise.reject(createError("users unavailable"));
      }
      return Promise.resolve([]);
    });

    await controller.loadData({ entities: ["projects", "users"], silent: true });

    expect(state.projects).toEqual([{ project_id: "project-1", project_name: "Project 1" }]);
    expect(state.loadedEntities.has("projects")).toBe(true);
    expect(populateSelects).toHaveBeenCalledTimes(1);
    expect(restoreSelections).toHaveBeenCalledTimes(1);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalledWith("Partial load failed: users", "warn");
  });

  it("keeps total-load failures from pretending the view rendered", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { controller, state, setStatus, renderActiveView, populateSelects, restoreSelections } = createHarness((path) => {
      if (path === "/projects") return Promise.reject(createError("projects unavailable"));
      if (path === "/users") return Promise.reject(createError("users unavailable"));
      return Promise.resolve([]);
    });

    await controller.loadData({ entities: ["projects", "users"], silent: true });

    expect(state.projects).toEqual([]);
    expect(populateSelects).not.toHaveBeenCalled();
    expect(restoreSelections).not.toHaveBeenCalled();
    expect(renderActiveView).not.toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith("Load failed: projects, users", "danger");
  });

  it("still renders loaded data when post-load select sync throws", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const populateSelects = vi.fn(() => {
      throw new Error("select sync exploded");
    });
    const renderActiveView = vi.fn();

    const { controller, state, setStatus, restoreSelections } = createHarness(
      (path) => {
        if (path === "/projects") {
          return Promise.resolve([{ project_id: "project-1", project_name: "Project 1" }]);
        }
        if (path === "/solutions") {
          return Promise.resolve([{ solution_id: "solution-1", project_id: "project-1", solution_name: "Solution 1" }]);
        }
        return Promise.resolve([]);
      },
      { populateSelects, renderActiveView }
    );

    await controller.loadData({ entities: ["projects", "solutions"], silent: true });

    expect(state.projects).toHaveLength(1);
    expect(state.solutions).toHaveLength(1);
    expect(restoreSelections).toHaveBeenCalledTimes(1);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalledWith("Loaded with UI sync issue: select sync exploded", "warn");
  });

  it("awaits the actual queued load and its route readiness", async () => {
    const firstProjects = deferred();
    const secondTasks = deferred();
    const routeReady = deferred();
    const renderActiveView = vi.fn();
    const api = vi.fn((path) => {
      if (path === "/projects") return firstProjects.promise;
      if (path === "/tasks") return secondTasks.promise;
      return Promise.resolve([]);
    });
    const { controller, state } = createHarness(
      api,
      {
        renderActiveView,
        entitiesForView: vi.fn(() => ["tasks"]),
      }
    );

    const firstLoad = controller.loadData({ entities: ["projects"], silent: true });
    await Promise.resolve();
    state.currentView = "gantt";
    let queuedLoadSettled = false;
    const queuedLoad = controller.loadData({ entities: ["tasks"], routeReady: routeReady.promise, silent: true });
    void queuedLoad.then(() => {
      queuedLoadSettled = true;
    });

    expect(queuedLoadSettled).toBe(false);

    firstProjects.resolve([{ project_id: "project-1" }]);
    await firstLoad;
    await vi.waitFor(() => expect(api).toHaveBeenCalledWith(
      "/tasks",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
    expect(queuedLoadSettled).toBe(false);

    secondTasks.resolve([{ task_id: "task-1" }]);
    await vi.waitFor(() => expect(state.tasks).toEqual([{ task_id: "task-1" }]));
    expect(queuedLoadSettled).toBe(false);
    expect(renderActiveView).toHaveBeenCalledTimes(1);

    routeReady.resolve({});
    await queuedLoad;

    expect(queuedLoadSettled).toBe(true);
    expect(renderActiveView).toHaveBeenCalledTimes(2);
  });

  it("starts the replacement-space load immediately and discards stale results", async () => {
    const oldSpaceProjects = deferred();
    const newSpaceProjects = deferred();
    const requestSignals = [];
    let requestCount = 0;
    const harness = createHarness((_path, options = {}) => {
      requestSignals.push(options.signal);
      requestCount += 1;
      return requestCount === 1 ? oldSpaceProjects.promise : newSpaceProjects.promise;
    });
    const {
      controller,
      state,
      api,
      setStatus,
      renderActiveView,
      populateSelects,
      onViewDataLoaded,
    } = harness;

    const oldLoad = controller.loadData({ entities: ["projects"] });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));

    state.activeSpace = { space_id: "space-b", space_name: "Space B" };
    controller.clearDataState();
    const replacementLoad = controller.loadData({ entities: ["projects"] });
    await Promise.resolve();

    expect(api).toHaveBeenCalledTimes(2);
    expect(requestSignals[0]).toBeInstanceOf(AbortSignal);
    expect(requestSignals[0].aborted).toBe(true);
    expect(requestSignals[1].aborted).toBe(false);

    let replacementSettled = false;
    void replacementLoad.then(() => {
      replacementSettled = true;
    });
    expect(replacementSettled).toBe(false);

    newSpaceProjects.resolve([{ project_id: "project-b" }]);
    await replacementLoad;

    expect(replacementSettled).toBe(true);
    expect(state.projects).toEqual([{ project_id: "project-b" }]);
    const renderCountAfterReplacement = renderActiveView.mock.calls.length;
    const statusCountAfterReplacement = setStatus.mock.calls.length;

    oldSpaceProjects.resolve([{ project_id: "project-a" }]);
    await oldLoad;

    expect(state.projects).toEqual([{ project_id: "project-b" }]);
    expect(populateSelects).toHaveBeenCalledTimes(1);
    expect(renderActiveView).toHaveBeenCalledTimes(renderCountAfterReplacement);
    expect(onViewDataLoaded).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalledTimes(statusCountAfterReplacement);
    expect(setStatus.mock.calls.filter(([message]) => message === "Online")).toHaveLength(1);
  });

  it("invalidates My Work when authoritative task data refreshes", async () => {
    const { controller, state } = createHarness((path) => {
      if (path === "/tasks") return Promise.resolve([{ task_id: "task-1", status: "in_progress" }]);
      return Promise.resolve([]);
    });
    state.myWork = {
      records: [{ task: { task_id: "task-1", status: "to_do" } }],
      selectedTaskId: "task-1",
    };

    await controller.refreshFromServer("tasks");

    expect(state.tasks).toEqual([{ task_id: "task-1", status: "in_progress" }]);
    expect(state.myWork.records).toBeNull();
    expect(state.myWork.selectedTaskId).toBe("task-1");
  });

  it("coalesces refreshes within the current data context", async () => {
    const projectsRefresh = deferred();
    const tasksRefresh = deferred();
    const { controller, state, api } = createHarness((path) => {
      if (path === "/projects") return projectsRefresh.promise;
      if (path === "/tasks") return tasksRefresh.promise;
      return Promise.resolve([]);
    });

    const firstRefresh = controller.refreshFromServer("projects");
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    void controller.refreshFromServer("tasks");

    expect(api).toHaveBeenCalledTimes(1);

    projectsRefresh.resolve([{ project_id: "project-1" }]);
    await firstRefresh;
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(2));

    tasksRefresh.resolve([{ task_id: "task-1" }]);
    await vi.waitFor(() => expect(state.tasks).toEqual([{ task_id: "task-1" }]));

    expect(state.projects).toEqual([{ project_id: "project-1" }]);
    expect(state.tasks).toEqual([{ task_id: "task-1" }]);
  });

  it("does not let an old-space refresh overwrite the replacement space", async () => {
    const oldSpaceRefresh = deferred();
    const newSpaceRefresh = deferred();
    const requestSignals = [];
    const requestPaths = [];
    let requestCount = 0;
    const { controller, state, api, populateSelects, renderActiveView } = createHarness((path, options = {}) => {
      requestPaths.push(path);
      requestSignals.push(options.signal);
      requestCount += 1;
      return requestCount === 1 ? oldSpaceRefresh.promise : newSpaceRefresh.promise;
    });

    const oldRefresh = controller.refreshFromServer("projects");
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    void controller.refreshFromServer("tasks");
    expect(api).toHaveBeenCalledTimes(1);

    state.activeSpace = { space_id: "space-b", space_name: "Space B" };
    controller.clearDataState();
    const replacementRefresh = controller.refreshFromServer("projects");
    await Promise.resolve();

    expect(api).toHaveBeenCalledTimes(2);
    expect(requestSignals[0].aborted).toBe(true);

    newSpaceRefresh.resolve([{ project_id: "project-b" }]);
    await replacementRefresh;
    oldSpaceRefresh.resolve([{ project_id: "project-a" }]);
    await oldRefresh;

    expect(state.projects).toEqual([{ project_id: "project-b" }]);
    expect(requestPaths).toEqual(["/projects", "/projects"]);
    expect(populateSelects).toHaveBeenCalledTimes(1);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
  });

  it("clears private My Work interaction state with the session data", () => {
    const { controller, state } = createHarness(() => Promise.resolve([]));
    state.myWork = {
      records: [{ task: { task_id: "task-1" } }],
      loading: true,
      error: "failed",
      selectedTaskId: "task-1",
      search: "private text",
      repository: "repo",
      editingTaskId: "task-1",
      draggingTaskId: "task-1",
      savingPrivateTaskId: "task-1",
      sharedActions: { blockDraft: "private blocker draft" },
    };

    controller.clearDataState();

    expect(state.myWork).toMatchObject({
      records: null,
      loading: false,
      error: "",
      selectedTaskId: "",
      search: "",
      repository: "",
      editingTaskId: "",
      draggingTaskId: "",
      savingPrivateTaskId: "",
      sharedActions: null,
    });
  });

  it("rechecks loaded entities before running delayed prefetches", async () => {
    vi.useFakeTimers();
    const api = vi.fn((path) => {
      if (path === "/projects") return Promise.resolve([{ project_id: "project-1" }]);
      if (path === "/solutions") return Promise.resolve([{ solution_id: "solution-1" }]);
      return Promise.resolve([]);
    });
    const { controller, state, populateSelects } = createHarness(api, {
      entitiesForView: vi.fn((view) => (view === "next" ? ["projects", "solutions"] : ["projects"])),
      viewPrefetchTarget: { master: "next" },
    });
    state.loadedEntities.add("projects");

    controller.scheduleViewPrefetch("master");
    state.loadedEntities.add("solutions");
    await vi.runOnlyPendingTimersAsync();

    expect(api).not.toHaveBeenCalled();
    expect(populateSelects).not.toHaveBeenCalled();
  });

  it("cancels a scheduled prefetch when session data is cleared", async () => {
    vi.useFakeTimers();
    const { controller, api } = createHarness(() => Promise.resolve([{ project_id: "project-a" }]), {
      entitiesForView: vi.fn(() => ["projects"]),
      viewPrefetchTarget: { master: "next" },
    });

    controller.scheduleViewPrefetch("master");
    controller.clearDataState();
    await vi.runOnlyPendingTimersAsync();

    expect(api).not.toHaveBeenCalled();
  });

  it("discards an in-flight prefetch after the active space changes", async () => {
    vi.useFakeTimers();
    const oldSpacePrefetch = deferred();
    let requestSignal = null;
    const { controller, state, api, populateSelects } = createHarness((_path, options = {}) => {
      requestSignal = options.signal;
      return oldSpacePrefetch.promise;
    }, {
      entitiesForView: vi.fn(() => ["projects"]),
      viewPrefetchTarget: { master: "next" },
    });

    controller.scheduleViewPrefetch("master");
    await vi.advanceTimersByTimeAsync(450);
    expect(api).toHaveBeenCalledTimes(1);

    state.activeSpace = { space_id: "space-b", space_name: "Space B" };
    controller.clearDataState();
    expect(requestSignal.aborted).toBe(true);

    oldSpacePrefetch.resolve([{ project_id: "project-a" }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(state.projects).toEqual([]);
    expect(state.loadedEntities.has("projects")).toBe(false);
    expect(populateSelects).not.toHaveBeenCalled();
  });

  it("invalidates in-flight loads when logout clears local data", async () => {
    const oldSpaceProjects = deferred();
    let requestSignal = null;
    const {
      controller,
      state,
      api,
      setStatus,
      renderActiveView,
      populateSelects,
      onViewDataLoaded,
    } = createHarness((_path, options = {}) => {
      requestSignal = options.signal;
      return oldSpaceProjects.promise;
    });

    const oldLoad = controller.loadData({ entities: ["projects"], silent: true });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));

    state.teamCapacity.requestId = 7;
    state.authed = false;
    controller.clearDataState();
    expect(requestSignal.aborted).toBe(true);
    expect(state.teamCapacity.requestId).toBe(8);

    oldSpaceProjects.resolve([{ project_id: "project-a" }]);
    await oldLoad;

    expect(state.projects).toEqual([]);
    expect(state.loadedEntities.has("projects")).toBe(false);
    expect(populateSelects).not.toHaveBeenCalled();
    expect(renderActiveView).not.toHaveBeenCalled();
    expect(onViewDataLoaded).not.toHaveBeenCalled();
    expect(setStatus).not.toHaveBeenCalled();
  });
});
