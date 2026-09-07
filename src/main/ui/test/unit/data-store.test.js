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
      ...overrides.els,
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
    isKnownEntity: (entity) => ["phases", "programs", "projects", "solutions", "tasks", "teams", "users"].includes(entity),
    dataEntities: ["phases", "programs", "projects", "solutions", "tasks", "teams", "users"],
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

  it("starts A, B, and C immediately and makes C ready before unrelated reads finish", async () => {
    const projects = deferred();
    const solutions = deferred();
    const tasks = deferred();
    const { controller, state, api, renderActiveView, onViewDataLoaded } = createHarness((path) => (
      ({ "/projects": projects, "/solutions": solutions, "/tasks": tasks })[path].promise
    ));
    const a = controller.loadData({ entities: ["projects"], silent: true });
    state.currentView = "b";
    const b = controller.loadData({ entities: ["solutions"], silent: true });
    state.currentView = "c";
    const c = controller.loadData({ entities: ["tasks"], silent: true });

    expect(api.mock.calls.map(([path]) => path)).toEqual(["/projects", "/solutions", "/tasks"]);
    tasks.resolve([{ task_id: "c" }]);
    await c;
    expect(state.loading).toBe(false);
    expect(state.tasks).toEqual([{ task_id: "c" }]);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
    expect(onViewDataLoaded).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ view: "c" }));

    projects.resolve([{ project_id: "a" }]);
    solutions.resolve([{ solution_id: "b" }]);
    await Promise.all([a, b]);
    expect(state.projects).toEqual([{ project_id: "a" }]);
    expect(state.solutions).toEqual([{ solution_id: "b" }]);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
    expect(onViewDataLoaded).toHaveBeenCalledTimes(1);
  });

  it("shares A on A to B to A and ignores B's late failure and readiness callback", async () => {
    const projects = deferred();
    const tasks = deferred();
    const oldRoute = deferred();
    const { controller, state, api, renderActiveView, onViewDataLoaded, setStatus } = createHarness((path) => (
      path === "/projects" ? projects.promise : tasks.promise
    ));
    const a = controller.loadData({ entities: ["projects"], silent: true });
    state.currentView = "b";
    const b = controller.loadData({ entities: ["tasks"], routeReady: oldRoute.promise, silent: true });
    state.currentView = "master";
    const latestA = controller.loadData({ entities: ["projects"], silent: true });
    expect(api).toHaveBeenCalledTimes(2);
    projects.resolve([{ project_id: "a" }]);
    await Promise.all([a, latestA]);
    tasks.reject(createError("old route failed"));
    oldRoute.resolve({});
    await b;
    expect(renderActiveView).toHaveBeenCalledTimes(1);
    expect(onViewDataLoaded).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ view: "master" }));
    expect(setStatus).not.toHaveBeenCalled();
    expect(state.loading).toBe(false);
  });

  it("does not share old-generation or old-user reads even when the space identifier matches", async () => {
    const old = deferred();
    const fresh = deferred();
    const { controller, state, api, onViewDataLoaded } = createHarness(() => (
      api.mock.calls.length === 1 ? old.promise : fresh.promise
    ), { state: { user: { soeid: "first-user" } } });
    const first = controller.loadData({ entities: ["projects"], silent: true });
    controller.clearDataState();
    state.user = { soeid: "second-user" };
    const second = controller.loadData({ entities: ["projects"], silent: true });
    fresh.resolve([{ project_id: "new-user" }]);
    await second;
    old.reject(createError("old-user authentication failure", 401));
    await first;
    expect(api).toHaveBeenCalledTimes(2);
    expect(state.projects).toEqual([{ project_id: "new-user" }]);
    expect(onViewDataLoaded).toHaveBeenCalledTimes(1);
  });

  it("handles a terminal auth failure from a superseded route in the same session", async () => {
    const old = deferred();
    const { controller, state, handleAuthError } = createHarness((path) => (
      path === "/projects" ? old.promise : Promise.resolve([])
    ));
    const first = controller.loadData({ entities: ["projects"], silent: true });
    state.currentView = "next";
    await controller.loadData({ entities: ["tasks"], silent: true });
    const error = createError("session expired", 401);
    old.reject(error);
    await first;
    expect(handleAuthError).toHaveBeenCalledExactlyOnceWith(error);
  });

  it("shares an in-flight prefetch with foreground navigation", async () => {
    vi.useFakeTimers();
    const projects = deferred();
    const { controller, api, state, onViewDataLoaded } = createHarness(() => projects.promise, {
      entitiesForView: () => ["projects"],
      viewPrefetchTarget: { master: "next" },
    });
    controller.scheduleViewPrefetch("master");
    await vi.advanceTimersByTimeAsync(450);
    state.currentView = "next";
    const load = controller.loadData({ silent: true });
    expect(api).toHaveBeenCalledTimes(1);

    projects.resolve([{ project_id: "shared" }]);
    await load;
    expect(state.projects).toEqual([{ project_id: "shared" }]);
    expect(onViewDataLoaded).toHaveBeenCalledTimes(1);
  });

  it("refreshes the exact queued entity union instead of all seven collections", async () => {
    const first = deferred();
    let calls = 0;
    const { controller, api } = createHarness(() => (++calls === 1 ? first.promise : Promise.resolve([])));
    const refresh = controller.refreshFromServer("phases");
    await controller.refreshFromServer("projects");
    await controller.refreshFromServer("tasks");
    await controller.refreshFromServer("tasks");
    first.resolve([]);
    await refresh;
    await vi.waitFor(() => expect(api.mock.calls.map(([path]) => path)).toEqual([
      "/phases", "/projects", "/tasks",
    ]));
  });

  it("shares a pending refresh with the latest foreground load", async () => {
    const projects = deferred();
    const { controller, state, api } = createHarness(() => projects.promise);
    const refresh = controller.refreshFromServer("projects");
    const load = controller.loadData({ entities: ["projects"], silent: true });
    expect(api).toHaveBeenCalledTimes(1);
    projects.resolve([{ project_id: "fresh" }]);
    await Promise.all([refresh, load]);
    expect(state.projects).toEqual([{ project_id: "fresh" }]);
  });

  it("starts force reloads immediately and never applies the superseded response", async () => {
    const old = deferred();
    const fresh = deferred();
    const { controller, state, api, onViewDataLoaded } = createHarness(
      () => (api.mock.calls.length === 1 ? old.promise : fresh.promise),
      { entitiesForView: () => ["projects"] },
    );
    const first = controller.loadData({ silent: true });
    const forced = controller.reloadCurrentViewData({ force: true, silent: true });
    const latest = controller.loadData({ silent: true });
    expect(api).toHaveBeenCalledTimes(2);
    expect(api.mock.calls[0][1].signal.aborted).toBe(true);
    let forceSettled = false;
    void forced.then(() => { forceSettled = true; });

    old.resolve([{ project_id: "obsolete" }]);
    await vi.waitFor(() => expect(api.mock.calls[0][1].signal.aborted).toBe(true));
    expect(state.loadedEntities.has("projects")).toBe(false);
    expect(forceSettled).toBe(false);

    fresh.resolve([{ project_id: "fresh" }]);
    await Promise.all([first, forced, latest]);
    expect(forceSettled).toBe(true);
    expect(state.projects).toEqual([{ project_id: "fresh" }]);
    expect(api).toHaveBeenCalledTimes(2);
    expect(onViewDataLoaded).toHaveBeenCalledTimes(1);
  });

  it("keeps separate force calls fresh when a newer reload finishes first", async () => {
    const reads = [deferred(), deferred()];
    const { controller, api, state } = createHarness(() => reads[api.mock.calls.length - 1].promise);
    const first = controller.loadData({ force: true, entities: ["tasks"], silent: true });
    const second = controller.loadData({ force: true, entities: ["tasks"], silent: true });
    reads[1].resolve([{ task_id: "new" }]);
    await second;
    reads[0].resolve([{ task_id: "old" }]);
    await first;
    expect(state.tasks).toEqual([{ task_id: "new" }]);
    expect(api).toHaveBeenCalledTimes(2);
    expect(state.loading).toBe(false);
  });

  it("invalidates queued refreshes immediately and shares their replacement with navigation", async () => {
    const old = deferred();
    const fresh = deferred();
    const { controller, api, state } = createHarness(() => (api.mock.calls.length === 1 ? old.promise : fresh.promise));
    const first = controller.loadData({ entities: ["tasks"], silent: true });
    await controller.refreshFromServer("tasks");
    expect(state.loadedEntities.has("tasks")).toBe(false);
    expect(api.mock.calls[0][1].signal.aborted).toBe(true);
    const next = controller.loadData({ entities: ["tasks"], silent: true });
    fresh.resolve([{ task_id: "fresh" }]);
    await next;
    old.resolve([{ task_id: "old" }]);
    await first;
    expect(state.tasks).toEqual([{ task_id: "fresh" }]);
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("reloads a cached dependency invalidated while another dependency is pending", async () => {
    const tasks = deferred();
    const projects = deferred();
    const { controller, state, api, renderActiveView } = createHarness((path) => (
      path === "/tasks" ? tasks.promise : projects.promise
    ));
    state.loadedEntities.add("projects");
    state.projects = [{ project_id: "old" }];
    const load = controller.loadData({ entities: ["projects", "tasks"], silent: true });
    await controller.refreshFromServer("projects");
    expect(state.loadedEntities.has("projects")).toBe(false);
    tasks.resolve([{ task_id: "task" }]);
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    expect(renderActiveView).not.toHaveBeenCalled();
    projects.resolve([{ project_id: "fresh" }]);
    await load;
    expect(state.projects).toEqual([{ project_id: "fresh" }]);
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("awaits fresh dependencies after invalidation during route-module loading", async () => {
    const route = deferred();
    const fresh = deferred();
    const { controller, state, api, onViewDataLoaded } = createHarness(() => (
      api.mock.calls.length === 1 ? Promise.resolve([{ task_id: "old" }]) : fresh.promise
    ));
    let settled = false;
    const load = controller.loadData({ entities: ["tasks"], routeReady: route.promise, silent: true });
    void load.then(() => { settled = true; });
    await vi.waitFor(() => expect(state.loadedEntities.has("tasks")).toBe(true));
    await controller.refreshFromServer("tasks");
    route.resolve({});
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    expect(settled).toBe(false);
    expect(onViewDataLoaded).not.toHaveBeenCalled();
    fresh.resolve([{ task_id: "fresh" }]);
    await load;
    expect(state.tasks).toEqual([{ task_id: "fresh" }]);
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("keeps a refresh awaiting a collection invalidated after its early response", async () => {
    const tasks = deferred();
    const freshProjects = deferred();
    let projectReads = 0;
    const { controller, state, api } = createHarness((path) => {
      if (path === "/tasks") return tasks.promise;
      if (path === "/projects") {
        projectReads += 1;
        return projectReads === 1 ? Promise.resolve([{ project_id: "old" }]) : freshProjects.promise;
      }
      return Promise.resolve([]);
    });
    let settled = false;
    const refresh = controller.refreshFromServer("all");
    void refresh.then(() => { settled = true; });
    await vi.waitFor(() => expect(state.loadedEntities.has("projects")).toBe(true));
    await controller.refreshFromServer("projects");
    tasks.resolve([]);
    await vi.waitFor(() => expect(projectReads).toBe(2));
    expect(settled).toBe(false);
    freshProjects.resolve([{ project_id: "fresh" }]);
    await refresh;
    expect(state.projects).toEqual([{ project_id: "fresh" }]);
    expect(api).toHaveBeenCalledTimes(8);
  });

  it("lets a cached route replace a slow load without inheriting its loading state", async () => {
    const slow = deferred();
    const { controller, state, renderActiveView, onViewDataLoaded } = createHarness(() => slow.promise);
    const first = controller.loadData({ entities: ["tasks"], silent: true });
    state.currentView = "cached";
    state.loadedEntities.add("projects");
    await controller.loadData({ entities: ["projects"], silent: true });
    expect(state.loading).toBe(false);
    expect(onViewDataLoaded).toHaveBeenCalledExactlyOnceWith({ view: "cached", durationMs: 0, changed: false });
    slow.resolve([{ task_id: "old-route" }]);
    await first;
    expect(renderActiveView).toHaveBeenCalledTimes(1);
  });

  it.each([false, true])("settles the visible loading status when a silent replacement is cached=%s", async (cached) => {
    const old = deferred();
    const { controller, state, api, setStatus } = createHarness(() => (
      api.mock.calls.length === 1 ? old.promise : Promise.resolve([{ task_id: "new" }])
    ));
    const first = controller.loadData({ entities: ["tasks"] });
    expect(setStatus).toHaveBeenLastCalledWith("Loading...", "warn");
    if (cached) state.loadedEntities.add("users");
    const entities = cached ? ["users"] : ["tasks"];
    await controller.loadData({ entities, force: !cached, silent: true });
    expect(setStatus).toHaveBeenLastCalledWith("Online", "positive");
    old.resolve([]);
    await first;
    expect(setStatus).toHaveBeenLastCalledWith("Online", "positive");
  });

  it("synchronizes controls when a cached route consumes a superseded load's partial results", async () => {
    const tasks = deferred();
    const { controller, state, populateSelects, restoreSelections } = createHarness((path) => (
      path === "/tasks" ? tasks.promise : Promise.resolve([{ project_id: "loaded-project" }])
    ));
    const first = controller.loadData({ entities: ["projects", "tasks"], silent: true });
    await vi.waitFor(() => expect(state.loadedEntities.has("projects")).toBe(true));
    expect(populateSelects).not.toHaveBeenCalled();
    state.currentView = "kanban";
    await controller.loadData({ entities: ["projects"], silent: true });
    expect(populateSelects).toHaveBeenCalledTimes(1);
    expect(restoreSelections).not.toHaveBeenCalled();

    state.currentView = "calendar";
    await controller.loadData({ entities: ["projects"], silent: true });
    expect(populateSelects).toHaveBeenCalledTimes(1);
    expect(restoreSelections).not.toHaveBeenCalled();
    tasks.resolve([]);
    await first;
  });

  it("restores current form selections rather than the selection from request start", async () => {
    const data = deferred();
    const projectId = { value: "before" };
    const { controller, restoreSelections } = createHarness(() => data.promise, {
      els: { projectForm: { querySelector: () => projectId } },
    });
    const load = controller.loadData({ entities: ["projects"], silent: true });
    projectId.value = "selected-while-loading";
    data.resolve([{ project_id: "selected-while-loading" }]);
    await load;
    expect(restoreSelections).toHaveBeenCalledExactlyOnceWith("selected-while-loading", "", "");
  });

  it.each(["all", "unknown-change"])("retains the complete-refresh fallback for %s", async (entity) => {
    const { controller, api } = createHarness(() => Promise.resolve([]));
    await controller.refreshFromServer(entity);
    expect(api.mock.calls.map(([path]) => path)).toEqual([
      "/phases", "/programs", "/projects", "/solutions", "/tasks", "/teams", "/users",
    ]);
  });

  it("bounds speculative reads and stops starting more when navigation takes priority", async () => {
    vi.useFakeTimers();
    const reads = { "/phases": deferred(), "/programs": deferred(), "/users": deferred() };
    const { controller, api, state } = createHarness((path) => reads[path].promise, {
      entitiesForView: () => ["phases", "programs", "projects", "tasks"],
      viewPrefetchTarget: { master: "next" },
    });
    controller.scheduleViewPrefetch("master");
    await vi.advanceTimersByTimeAsync(450);
    expect(api.mock.calls.map(([path]) => path)).toEqual(["/phases", "/programs"]);
    state.currentView = "spaces";
    const load = controller.loadData({ entities: ["users"], silent: true });
    expect(api.mock.calls.map(([path]) => path)).toEqual(["/phases", "/programs", "/users"]);
    reads["/phases"].resolve([]);
    reads["/programs"].resolve([]);
    await vi.advanceTimersByTimeAsync(0);
    expect(api).toHaveBeenCalledTimes(3);
    reads["/users"].resolve([]);
    await load;
  });

  it("does not let a canceled prefetch retry an invalidated read ahead of the foreground route", async () => {
    vi.useFakeTimers();
    const oldProjects = deferred();
    const users = deferred();
    const { controller, state, api } = createHarness((path) => {
      if (path === "/users") return users.promise;
      return api.mock.calls.length === 1 ? oldProjects.promise : Promise.resolve([]);
    }, {
      entitiesForView: () => ["projects"],
      viewPrefetchTarget: { master: "next" },
    });
    controller.scheduleViewPrefetch("master");
    await vi.advanceTimersByTimeAsync(450);
    state.currentView = "spaces";
    const load = controller.loadData({ entities: ["users"], silent: true });
    await controller.refreshFromServer("projects");
    oldProjects.reject(new DOMException("Aborted", "AbortError"));
    await vi.advanceTimersByTimeAsync(0);
    expect(api.mock.calls.map(([path]) => path)).toEqual(["/projects", "/users"]);
    expect(state.loading).toBe(true);

    users.resolve([]);
    await load;
    await vi.advanceTimersByTimeAsync(0);
    expect(api.mock.calls.map(([path]) => path)).toEqual(["/projects", "/users", "/projects"]);
  });

  it("does not prefetch on hidden tabs or save-data connections", async () => {
    vi.useFakeTimers();
    const { controller, api } = createHarness(() => Promise.resolve([]), {
      viewPrefetchTarget: { master: "next" },
    });
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    controller.scheduleViewPrefetch("master");
    await vi.advanceTimersByTimeAsync(450);
    visibility.mockRestore();
    vi.stubGlobal("navigator", { connection: { saveData: true } });
    try {
      controller.scheduleViewPrefetch("master");
      await vi.advanceTimersByTimeAsync(450);
      expect(api).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
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

  it("awaits the replacement load and its route readiness without rendering the superseded route", async () => {
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
    expect(renderActiveView).not.toHaveBeenCalled();

    routeReady.resolve({});
    await queuedLoad;

    expect(queuedLoadSettled).toBe(true);
    expect(renderActiveView).toHaveBeenCalledTimes(1);
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
