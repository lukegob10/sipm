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
    currentView: "master",
    loading: false,
    pendingRefresh: false,
    loadedEntities: new Set(),
    phases: [],
    projects: [],
    solutions: [],
    solutionPhases: {},
    tasks: [],
    teams: [],
    users: [],
    allocations: [],
    planningWindows: [],
    capacitySelectedSoeid: "",
    teamCapacity: {},
    tasksWorkbench: null,
  };
  const setStatus = overrides.setStatus || vi.fn();
  const renderActiveView = overrides.renderActiveView || vi.fn();
  const populateSelects = overrides.populateSelects || vi.fn();
  const restoreSelections = overrides.restoreSelections || vi.fn();
  const controller = createDataStoreController({
    state,
    els: {
      projectForm: null,
      solutionForm: null,
      taskForm: null,
    },
    api: vi.fn(apiImpl),
    setStatus,
    setAuthVisible: vi.fn(),
    renderActiveView,
    populateSelects,
    restoreSelections,
    handleAuthError: vi.fn(() => false),
    loadTeamCapacityData: vi.fn(),
    entitiesForView: overrides.entitiesForView || vi.fn(() => ["projects", "solutions"]),
    isKnownEntity: (entity) => ["phases", "projects", "solutions", "tasks", "teams", "users", "allocations", "windows"].includes(entity),
    dataEntities: ["phases", "projects", "solutions", "tasks", "teams", "users", "allocations", "windows"],
    viewPrefetchTarget: overrides.viewPrefetchTarget || {},
  });
  return { controller, state, setStatus, renderActiveView, populateSelects, restoreSelections };
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

  it("preserves queued route readiness when a route load starts during another load", async () => {
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
    await controller.loadData({ entities: ["tasks"], routeReady: routeReady.promise, silent: true });

    firstProjects.resolve([{ project_id: "project-1" }]);
    await firstLoad;
    await vi.waitFor(() => expect(api).toHaveBeenCalledWith("/tasks"));
    secondTasks.resolve([{ task_id: "task-1" }]);
    await vi.waitFor(() => expect(state.tasks).toEqual([{ task_id: "task-1" }]));

    expect(renderActiveView).toHaveBeenCalledTimes(1);

    routeReady.resolve({});
    await vi.waitFor(() => expect(renderActiveView).toHaveBeenCalledTimes(2));
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
});
