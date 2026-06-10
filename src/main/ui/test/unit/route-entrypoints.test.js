import { beforeEach, describe, expect, it, vi } from "vitest";

const dashboardMock = vi.hoisted(() => ({
  dashboardState: { route: "dashboard" },
  createDashboardState: vi.fn(),
  renderDashboardView: vi.fn(),
}));

const pmDashboardMock = vi.hoisted(() => ({
  pmDashboardState: { route: "pm-dashboard" },
  createPMDashboardState: vi.fn(),
  renderPMDashboardView: vi.fn(),
}));

const programDashboardMock = vi.hoisted(() => ({
  programDashboardState: { route: "program-dashboard" },
  createProgramDashboardState: vi.fn(),
  renderProgramDashboardView: vi.fn(),
}));

const masterTableMock = vi.hoisted(() => ({
  bindMasterTableInteractions: vi.fn(),
  buildMasterTable: vi.fn(),
}));

const planningMock = vi.hoisted(() => ({
  loadBoard: vi.fn(),
  bindPlanningBoardEvents: vi.fn(),
  renderPlanningView: vi.fn(),
  syncDetailDraft: vi.fn(),
  selectedTask: vi.fn(),
  boardState: {
    ctx: null,
    detailDraft: {},
    loaded: false,
    loading: false,
    spaceId: "",
  },
  setPlanningRerender: vi.fn(),
  resetBoardState: vi.fn(),
}));

vi.mock("../../js/routes/dashboard/render.js", () => ({
  createDashboardState: dashboardMock.createDashboardState,
  renderDashboardView: dashboardMock.renderDashboardView,
}));

vi.mock("../../js/routes/pm-dashboard/render.js", () => ({
  createPMDashboardState: pmDashboardMock.createPMDashboardState,
  renderPMDashboardView: pmDashboardMock.renderPMDashboardView,
}));

vi.mock("../../js/routes/program-dashboard/render.js", () => ({
  createProgramDashboardState: programDashboardMock.createProgramDashboardState,
  renderProgramDashboardView: programDashboardMock.renderProgramDashboardView,
}));

vi.mock("../../js/routes/master/table.js", () => ({
  bindMasterTableInteractions: masterTableMock.bindMasterTableInteractions,
  buildMasterTable: masterTableMock.buildMasterTable,
}));

vi.mock("../../js/routes/planning/api.js", () => ({
  loadBoard: planningMock.loadBoard,
}));

vi.mock("../../js/routes/planning/interactions.js", () => ({
  bindPlanningBoardEvents: planningMock.bindPlanningBoardEvents,
}));

vi.mock("../../js/routes/planning/render.js", () => ({
  renderPlanningView: planningMock.renderPlanningView,
}));

vi.mock("../../js/routes/planning/selection.js", () => ({
  selectedTask: planningMock.selectedTask,
  syncDetailDraft: planningMock.syncDetailDraft,
}));

vi.mock("../../js/routes/planning/state.js", () => ({
  boardState: planningMock.boardState,
  setPlanningRerender: planningMock.setPlanningRerender,
}));

vi.mock("../../js/routes/planning/storage.js", () => ({
  resetBoardState: planningMock.resetBoardState,
}));

dashboardMock.createDashboardState.mockReturnValue(dashboardMock.dashboardState);
pmDashboardMock.createPMDashboardState.mockReturnValue(pmDashboardMock.pmDashboardState);
programDashboardMock.createProgramDashboardState.mockReturnValue(programDashboardMock.programDashboardState);

const dashboardRoute = await import("../../js/routes/dashboard.js");
const pmDashboardRoute = await import("../../js/routes/pm-dashboard.js");
const programDashboardRoute = await import("../../js/routes/program-dashboard.js");
const masterRoute = await import("../../js/routes/master.js");
const planningRoute = await import("../../js/routes/planning.js");

describe("route entrypoints", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    masterTableMock.buildMasterTable.mockReturnValue({ html: "<table><tbody><tr><td>row</td></tr></tbody></table>", rowCount: 1 });
    planningMock.boardState.ctx = null;
    planningMock.boardState.detailDraft = {};
    planningMock.boardState.loaded = false;
    planningMock.boardState.loading = false;
    planningMock.boardState.spaceId = "";
    planningMock.selectedTask.mockReturnValue(null);
    planningMock.loadBoard.mockResolvedValue(undefined);
    vi.spyOn(performance, "now").mockReturnValue(100);
  });

  it("creates stable dashboard state and delegates dashboard rendering", () => {
    const ctx = { state: { activeSpace: { space_id: "space-1" } } };

    dashboardRoute.renderDashboard(ctx);
    dashboardRoute.render(ctx);

    expect(dashboardMock.renderDashboardView).toHaveBeenNthCalledWith(1, dashboardMock.dashboardState, ctx);
    expect(dashboardMock.renderDashboardView).toHaveBeenNthCalledWith(2, dashboardMock.dashboardState, ctx);
  });

  it("creates stable PM dashboard state and delegates PM rendering", () => {
    const ctx = { state: { projects: [] } };

    pmDashboardRoute.renderPMDashboard(ctx);
    pmDashboardRoute.render(ctx);

    expect(pmDashboardMock.renderPMDashboardView).toHaveBeenNthCalledWith(1, pmDashboardMock.pmDashboardState, ctx);
    expect(pmDashboardMock.renderPMDashboardView).toHaveBeenNthCalledWith(2, pmDashboardMock.pmDashboardState, ctx);
  });

  it("creates stable program dashboard state and delegates program dashboard rendering", () => {
    const ctx = { state: { programs: [] } };

    programDashboardRoute.renderProgramDashboard(ctx);
    programDashboardRoute.render(ctx);

    expect(programDashboardMock.renderProgramDashboardView).toHaveBeenNthCalledWith(
      1,
      programDashboardMock.programDashboardState,
      ctx
    );
    expect(programDashboardMock.renderProgramDashboardView).toHaveBeenNthCalledWith(
      2,
      programDashboardMock.programDashboardState,
      ctx
    );
  });

  it("clears master filters because filters live in the table header", () => {
    const masterFilters = document.createElement("section");
    masterFilters.innerHTML = "<button>stale</button>";

    masterRoute.renderMasterFilters({ els: { masterFilters } });
    masterRoute.renderMasterFilters({ els: {} });

    expect(masterFilters.innerHTML).toBe("");
  });

  it("renders the master table and wires table interactions", () => {
    const masterTable = document.createElement("section");
    const ctx = {
      els: { masterTable },
      renderMasterQuickstart: vi.fn(),
      updateBulkSelectionCount: vi.fn(),
    };

    masterRoute.renderMasterTable(ctx);

    expect(masterTableMock.buildMasterTable).toHaveBeenCalledWith(ctx);
    expect(ctx.renderMasterQuickstart).toHaveBeenCalledWith(1);
    expect(masterTable.innerHTML).toContain("<table>");
    expect(masterTableMock.bindMasterTableInteractions).toHaveBeenCalledWith(ctx, {
      rerenderMasterTable: expect.any(Function),
    });
    expect(ctx.updateBulkSelectionCount).toHaveBeenCalledTimes(1);
  });

  it("skips master table work when the table root is absent", () => {
    masterRoute.renderMasterTable({
      els: {},
      renderMasterQuickstart: vi.fn(),
      updateBulkSelectionCount: vi.fn(),
    });

    expect(masterTableMock.buildMasterTable).not.toHaveBeenCalled();
  });

  it("resets planning state, starts loading, syncs detail draft, renders, and records timing", () => {
    const planningBoard = document.createElement("section");
    const activeTask = { id: "task-1", title: "Build API" };
    planningMock.selectedTask.mockReturnValue(activeTask);
    planningMock.boardState.spaceId = "old-space";
    planningMock.boardState.detailDraft = { taskId: "other-task" };
    vi.mocked(performance.now).mockReturnValueOnce(100).mockReturnValueOnce(116);
    const ctx = {
      els: { planningBoard },
      state: { activeSpace: { space_id: "space-1" } },
      noteViewRendered: vi.fn(),
    };

    planningRoute.renderPlanning(ctx);

    expect(planningMock.boardState.ctx).toBe(ctx);
    expect(planningMock.resetBoardState).toHaveBeenCalledWith("space-1");
    expect(planningMock.bindPlanningBoardEvents).toHaveBeenCalledTimes(1);
    expect(planningMock.loadBoard).toHaveBeenCalledWith(ctx, { allocationsOnly: false });
    expect(planningMock.syncDetailDraft).toHaveBeenCalledWith(activeTask);
    expect(planningMock.renderPlanningView).toHaveBeenCalledWith(planningBoard);
    expect(ctx.noteViewRendered).toHaveBeenCalledWith(16);
  });

  it("skips planning loads while already loaded or loading", () => {
    const planningBoard = document.createElement("section");
    const ctx = { els: { planningBoard }, state: { activeSpace: { space_id: "" } } };

    planningMock.boardState.loaded = true;
    planningRoute.render(ctx);
    planningMock.boardState.loaded = false;
    planningMock.boardState.loading = true;
    planningRoute.renderPlanning(ctx);

    expect(planningMock.loadBoard).not.toHaveBeenCalled();
    expect(planningMock.resetBoardState).not.toHaveBeenCalled();
  });

  it("returns early when the planning board root is unavailable", () => {
    const ctx = { els: {}, state: { activeSpace: { space_id: "space-1" } } };

    planningRoute.renderPlanning(ctx);

    expect(planningMock.boardState.ctx).toBe(ctx);
    expect(planningMock.bindPlanningBoardEvents).not.toHaveBeenCalled();
    expect(planningMock.renderPlanningView).not.toHaveBeenCalled();
  });
});
