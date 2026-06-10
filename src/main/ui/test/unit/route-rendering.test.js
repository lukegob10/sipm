import { describe, expect, it, vi } from "vitest";

import { createShellContext } from "../../js/shell/context.js";
import { renderAccess } from "../../js/routes/access.js";
import { renderSpaces } from "../../js/routes/spaces.js";
import { renderSubcomponentsWorkbench } from "../../js/routes/subcomponents-workbench.js";
import { renderTeamCapacity } from "../../js/routes/team-capacity.js";

describe("simple route rendering", () => {
  it("builds shell context by applying route overrides last", () => {
    const base = { state: { currentView: "master" }, render: "base", stable: true };
    const context = createShellContext(base, { render: "route", transient: true });

    expect(context).toEqual({
      state: { currentView: "master" },
      render: "route",
      stable: true,
      transient: true,
    });
  });

  it("delegates access and spaces routes to the governance hub mode", () => {
    const renderGovernanceHub = vi.fn();

    renderAccess({ renderGovernanceHub });
    renderSpaces({ renderGovernanceHub });
    renderAccess({});
    renderSpaces({});

    expect(renderGovernanceHub).toHaveBeenNthCalledWith(1, "platform-access");
    expect(renderGovernanceHub).toHaveBeenNthCalledWith(2, "current-space");
    expect(renderGovernanceHub).toHaveBeenCalledTimes(2);
  });

  it("renders team capacity summaries with filters, allocation load, and escaped labels", () => {
    const capacityUserList = document.createElement("section");
    const capacityTeamFilter = document.createElement("input");
    const capacityNameFilter = document.createElement("input");
    capacityTeamFilter.value = "platform";
    capacityNameFilter.value = "sam";

    renderTeamCapacity({
      state: {
        activeSpace: { space_id: "space-1", space_name: "Core <Space>" },
        users: [
          { soeid: "sam1", display_name: "Sam <One>", team_tag: "Platform", capacity_hours: 160 },
          { soeid: "lee2", display_name: "Lee Two", team_tag: "Delivery", capacity_hours: 160 },
        ],
        allocations: [
          { assignee_user_soeid: "sam1", effort_hours: 80 },
          { assignee_user_soeid: "sam1", effort_hours: 120 },
        ],
      },
      els: { capacityUserList, capacityTeamFilter, capacityNameFilter },
      allocationFteMonths: (row) => Number(row.effort_hours || 0) / 160,
      userCapacityFteMonth: (user) => Number(user.capacity_hours || 0) / 160,
      formatFte: (value) => Number(value).toFixed(2),
      teamCapacityState: {
        loading: true,
        error: "Network <down>",
        lastLoadedAt: "2026-06-08T12:00:00Z",
        lastLoadedSpaceId: "old-space",
        lastLoadedSpaceName: "Old Space",
      },
      selectedSoeid: "sam1",
    });

    expect(capacityUserList.textContent).toContain("Team Capacity");
    expect(capacityUserList.textContent).toContain("1 visible");
    expect(capacityUserList.textContent).toContain("125%");
    expect(capacityUserList.innerHTML).toContain("Sam &lt;One&gt;");
    expect(capacityUserList.innerHTML).toContain("Core &lt;Space&gt;");
    expect(capacityUserList.innerHTML).toContain("Network &lt;down&gt;");
    expect(capacityUserList.querySelector("tr.active-row")?.dataset.soeid).toBe("sam1");
  });

  it("renders team capacity empty states for loading and filtered rosters", () => {
    const capacityUserList = document.createElement("section");
    const capacityTeamFilter = document.createElement("input");
    const capacityNameFilter = document.createElement("input");
    capacityNameFilter.value = "missing";

    renderTeamCapacity({
      state: {
        activeSpace: { space_id: "space-1" },
        users: [{ soeid: "sam1", display_name: "Sam One", team_tag: "Platform" }],
        allocations: [],
      },
      els: { capacityUserList, capacityTeamFilter, capacityNameFilter },
      allocationFteMonths: () => 0,
      userCapacityFteMonth: () => 1,
      formatFte: (value) => String(value),
      teamCapacityState: { loading: false },
      selectedSoeid: "",
    });

    expect(capacityUserList.textContent).toContain("No users match current filters");

    renderTeamCapacity({
      state: { activeSpace: {}, users: [], allocations: [] },
      els: { capacityUserList, capacityTeamFilter, capacityNameFilter },
      allocationFteMonths: () => 0,
      userCapacityFteMonth: () => 1,
      formatFte: (value) => String(value),
      teamCapacityState: { loading: true },
      selectedSoeid: "",
    });

    expect(capacityUserList.textContent).toContain("Loading roster");
  });

  it("renders subcomponents workbench empty states and summary cards", () => {
    const subcomponentsWorkbenchKpis = document.createElement("section");
    const subcomponentsWorkbenchTable = document.createElement("section");

    renderSubcomponentsWorkbench({
      els: { subcomponentsWorkbenchKpis, subcomponentsWorkbenchTable },
      rows: [],
      activeSubcomponentId: "",
      selectedIds: new Set(),
      formatStatus: (status) => status,
      summary: { total: 3, visible: 0, overdue: 1, dueSoon: 2, blocked: 1, unassigned: 1, hiddenClosed: 2 },
    });

    expect(subcomponentsWorkbenchKpis.textContent).toContain("Visible Queue");
    expect(subcomponentsWorkbenchKpis.textContent).toContain("Blocked");
    expect(subcomponentsWorkbenchTable.textContent).toContain("No open subcomponents match");
    expect(subcomponentsWorkbenchTable.textContent).toContain("2 completed or abandoned items");
  });

  it("renders subcomponents rows with escaped links, status, and selection state", () => {
    const subcomponentsWorkbenchKpis = document.createElement("section");
    const subcomponentsWorkbenchTable = document.createElement("section");

    renderSubcomponentsWorkbench({
      els: { subcomponentsWorkbenchKpis, subcomponentsWorkbenchTable },
      rows: [
        {
          subcomponent_id: "sub-1",
          subcomponent_name: "API <Gateway>",
          project_id: "proj-1",
          project_name: "Project & One",
          solution_id: "sol-1",
          solution_name: "Solution 'A'",
          status: "in_progress",
          blocked: true,
          assignee: "",
          due_date: "2026-07-01",
          priority: 2,
          urgency_score: 88,
        },
      ],
      activeSubcomponentId: "sub-1",
      selectedIds: new Set(["sub-1"]),
      formatStatus: (status) => `Status: ${status}`,
      summary: { total: 1, visible: 1, overdue: 0, dueSoon: 1, blocked: 1, unassigned: 1 },
    });

    expect(subcomponentsWorkbenchTable.querySelector("tr.active-row")?.dataset.id).toBe("sub-1");
    expect(subcomponentsWorkbenchTable.querySelector(".scwb-select-row")?.checked).toBe(true);
    expect(subcomponentsWorkbenchTable.querySelector("#scwb-select-all")?.checked).toBe(true);
    expect(subcomponentsWorkbenchTable.textContent).toContain("Status: in_progress");
    expect(subcomponentsWorkbenchTable.textContent).toContain("Blocked");
    expect(subcomponentsWorkbenchTable.textContent).toContain("Unassigned");
    expect(subcomponentsWorkbenchTable.innerHTML).toContain("API &lt;Gateway&gt;");
    expect(subcomponentsWorkbenchTable.innerHTML).toContain("Project &amp; One");
    expect(subcomponentsWorkbenchTable.textContent).toContain("Solution 'A'");
    expect(subcomponentsWorkbenchTable.querySelector("[data-project-id='proj-1']")).toBeTruthy();
    expect(subcomponentsWorkbenchTable.querySelector(".sub-workbench-urgency")?.className).toContain("danger");
  });
});
