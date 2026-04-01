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
    subcomponents: [],
    teams: [],
    users: [],
    allocations: [],
    planningWindows: [],
    capacitySelectedSoeid: "",
    teamCapacity: {},
    subcomponentsWorkbench: null,
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
      subcomponentForm: null,
    },
    api: vi.fn(apiImpl),
    setStatus,
    setAuthVisible: vi.fn(),
    renderActiveView,
    populateSelects,
    restoreSelections,
    handleAuthError: vi.fn(() => false),
    loadTeamCapacityData: vi.fn(),
    entitiesForView: vi.fn(() => ["projects", "solutions"]),
    isKnownEntity: (entity) => ["phases", "projects", "solutions", "subcomponents", "teams", "users", "allocations", "windows"].includes(entity),
    dataEntities: ["phases", "projects", "solutions", "subcomponents", "teams", "users", "allocations", "windows"],
    viewPrefetchTarget: {},
  });
  return { controller, state, setStatus, renderActiveView, populateSelects, restoreSelections };
}


describe("data store controller", () => {
  afterEach(() => {
    vi.restoreAllMocks();
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
});
