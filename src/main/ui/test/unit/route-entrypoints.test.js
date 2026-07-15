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

vi.mock("../../js/routes/program-dashboard/render.js?v=program-dashboard-escalation-grid-v1", () => ({
  createProgramDashboardState: programDashboardMock.createProgramDashboardState,
  renderProgramDashboardView: programDashboardMock.renderProgramDashboardView,
}));

vi.mock("../../js/routes/master/table.js", () => ({
  bindMasterTableInteractions: masterTableMock.bindMasterTableInteractions,
  buildMasterTable: masterTableMock.buildMasterTable,
}));


dashboardMock.createDashboardState.mockReturnValue(dashboardMock.dashboardState);
pmDashboardMock.createPMDashboardState.mockReturnValue(pmDashboardMock.pmDashboardState);
programDashboardMock.createProgramDashboardState.mockReturnValue(programDashboardMock.programDashboardState);

const dashboardRoute = await import("../../js/routes/dashboard.js");
const pmDashboardRoute = await import("../../js/routes/pm-dashboard.js");
const programDashboardRoute = await import("../../js/routes/program-dashboard.js");
const masterRoute = await import("../../js/routes/master.js");

describe("route entrypoints", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    masterTableMock.buildMasterTable.mockReturnValue({ html: "<table><tbody><tr><td>row</td></tr></tbody></table>", rowCount: 1 });
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

  it("renders compact master filters and outline actions above the table", () => {
    const masterFilters = document.createElement("section");
    masterFilters.innerHTML = "<button>stale</button>";
    const ctx = {
      els: { masterFilters },
      state: { filters: { query: "project:Alpha" }, programs: [], projects: [] },
      persistMasterViewState: vi.fn(),
      renderMasterTable: vi.fn(),
    };

    masterRoute.renderMasterFilters(ctx);
    masterRoute.renderMasterFilters({ els: {} });

    expect(masterFilters.querySelector("#filter-query")?.value).toBe("project:Alpha");
    expect(masterFilters.querySelector("#filter-query")?.placeholder).toContain("field:value");
    expect(masterFilters.querySelector("[data-master-outline-action='expand-all']")).toBeTruthy();
    expect(masterFilters.querySelector("[data-master-outline-action='collapse-all']")).toBeTruthy();
  });

  it("waits for Enter before applying deliverables search text", () => {
    const masterFilters = document.createElement("section");
    const ctx = {
      els: { masterFilters },
      state: { filters: { query: "" }, programs: [], projects: [] },
      persistMasterViewState: vi.fn(),
      renderMasterTable: vi.fn(),
      renderKanban: vi.fn(),
      renderCalendar: vi.fn(),
      renderGantt: vi.fn(),
    };

    masterRoute.renderMasterFilters(ctx);

    const input = masterFilters.querySelector("#filter-query");
    input.value = "gamma";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    expect(ctx.state.filters.query).toBe("");
    expect(ctx.renderMasterTable).not.toHaveBeenCalled();

    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));

    expect(ctx.state.filters.query).toBe("gamma");
    expect(ctx.persistMasterViewState).toHaveBeenCalledTimes(1);
    expect(ctx.renderMasterTable).toHaveBeenCalledTimes(1);
    expect(ctx.renderKanban).toHaveBeenCalledTimes(1);
    expect(ctx.renderCalendar).toHaveBeenCalledTimes(1);
    expect(ctx.renderGantt).toHaveBeenCalledTimes(1);
  });

  it("renders the master table and wires table interactions", () => {
    const masterTable = document.createElement("section");
    const ctx = {
      els: { masterTable },
      renderMasterQuickstart: vi.fn(),
    };

    masterRoute.renderMasterTable(ctx);

    expect(masterTableMock.buildMasterTable).toHaveBeenCalledWith(ctx);
    expect(ctx.renderMasterQuickstart).toHaveBeenCalledWith(1);
    expect(masterTable.innerHTML).toContain("<table>");
    expect(masterTableMock.bindMasterTableInteractions).toHaveBeenCalledWith(ctx);
  });

  it("skips master table work when the table root is absent", () => {
    masterRoute.renderMasterTable({
      els: {},
      renderMasterQuickstart: vi.fn(),
    });

    expect(masterTableMock.buildMasterTable).not.toHaveBeenCalled();
  });
});
