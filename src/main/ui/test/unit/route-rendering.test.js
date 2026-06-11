import { beforeEach, describe, expect, it, vi } from "vitest";

import { createShellContext } from "../../js/shell/context.js";
import {
  createProgramDashboardState,
  renderProgramDashboardView,
  splitProgramName,
} from "../../js/routes/program-dashboard/render.js";
import { renderAccess } from "../../js/routes/access.js";
import { renderSpaces } from "../../js/routes/spaces.js";
import { renderTasksWorkbench } from "../../js/routes/tasks-workbench.js";
import { renderTeamCapacity } from "../../js/routes/team-capacity.js";

describe("simple route rendering", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = "";
  });

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

  it("renders tasks workbench empty states and summary cards", () => {
    const tasksWorkbenchKpis = document.createElement("section");
    const tasksWorkbenchTable = document.createElement("section");

    renderTasksWorkbench({
      els: { tasksWorkbenchKpis, tasksWorkbenchTable },
      rows: [],
      activeTaskId: "",
      selectedIds: new Set(),
      formatStatus: (status) => status,
      summary: { total: 3, visible: 0, overdue: 1, dueSoon: 2, blocked: 1, unassigned: 1, hiddenClosed: 2 },
    });

    expect(tasksWorkbenchKpis.textContent).toContain("Visible Queue");
    expect(tasksWorkbenchKpis.textContent).toContain("Blocked");
    expect(tasksWorkbenchTable.textContent).toContain("No open tasks match");
    expect(tasksWorkbenchTable.textContent).toContain("2 completed or abandoned items");
  });

  it("renders tasks rows with escaped links, status, and selection state", () => {
    const tasksWorkbenchKpis = document.createElement("section");
    const tasksWorkbenchTable = document.createElement("section");

    renderTasksWorkbench({
      els: { tasksWorkbenchKpis, tasksWorkbenchTable },
      rows: [
        {
          task_id: "task-1",
          task_name: "API <Gateway>",
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
      activeTaskId: "task-1",
      selectedIds: new Set(["task-1"]),
      formatStatus: (status) => `Status: ${status}`,
      summary: { total: 1, visible: 1, overdue: 0, dueSoon: 1, blocked: 1, unassigned: 1 },
    });

    expect(tasksWorkbenchTable.querySelector("tr.active-row")?.dataset.id).toBe("task-1");
    expect(tasksWorkbenchTable.querySelector(".scwb-select-row")?.checked).toBe(true);
    expect(tasksWorkbenchTable.querySelector("#scwb-select-all")?.checked).toBe(true);
    expect(tasksWorkbenchTable.textContent).toContain("Status: in_progress");
    expect(tasksWorkbenchTable.textContent).toContain("Blocked");
    expect(tasksWorkbenchTable.textContent).toContain("Unassigned");
    expect(tasksWorkbenchTable.innerHTML).toContain("API &lt;Gateway&gt;");
    expect(tasksWorkbenchTable.innerHTML).toContain("Project &amp; One");
    expect(tasksWorkbenchTable.textContent).toContain("Solution 'A'");
    expect(tasksWorkbenchTable.querySelector("[data-project-id='proj-1']")).toBeTruthy();
    expect(tasksWorkbenchTable.querySelector(".task-workbench-urgency")?.className).toContain("danger");
  });

  it("splits program names into dashboard team and sub-area labels", () => {
    expect(splitProgramName("TAP - Data Sourcing")).toEqual({ team: "TAP", subArea: "Data Sourcing" });
    expect(splitProgramName("Transformation / Risk")).toEqual({ team: "Transformation", subArea: "Risk" });
    expect(splitProgramName("Default Program")).toEqual({ team: "", subArea: "Default Program" });
  });

  it("renders program project groups and child solutions for the selected program", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    const programDashboardState = createProgramDashboardState();

    renderProgramDashboardView(programDashboardState, {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "TAP - Data Sourcing" }],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Data Sourcing - APIs", status: "active", sponsor: "Sam Sponsor" },
          { project_id: "project-2", program_id: "program-2", project_name: "Other Program Project", status: "active" },
        ],
        solutions: [
          {
            solution_id: "solution-1",
            project_id: "project-1",
            solution_name: "CitiVelocity",
            status: "active",
            planned_start_date: "2026-05-01",
            due_date: "2026-06-26",
            owner: "Spencer Emma",
            current_phase: "build_docs",
          },
        ],
        tasks: [],
      },
      formatStatus: (value) => `Status: ${value}`,
      phaseDisplayName: (phaseId) => (phaseId === "build_docs" ? "Build / Docs" : phaseId),
      solutionProgress: () => 50,
      showCompletedOperationalWork: () => false,
    });

    const root = document.getElementById("program-dashboard-root");
    expect(root.textContent).toContain("TAP");
    expect(root.textContent).toContain("Data Sourcing");
    expect(root.textContent).toContain("Data Sourcing - APIs");
    expect(root.textContent).toContain("CitiVelocity");
    expect(root.textContent).toContain("Spencer Emma");
    expect(root.textContent).toContain("Build / Docs");
    expect(root.textContent).not.toContain("build_docs");
    expect(root.textContent).toContain("50%");
    expect(root.textContent).not.toContain("Other Program Project");
    expect(root.textContent).not.toContain("Confidential");
    expect(root.textContent).not.toContain("Internal Use Only");
    expect([...root.querySelectorAll("th")].map((th) => th.textContent)).toContain("Program");
    expect([...root.querySelectorAll("th")].map((th) => th.textContent)).not.toContain("Team");
    expect(root.querySelector(".program-dashboard-group-row .program-dashboard-tag")?.textContent).toBe("TAP - Data Sourcing");
    expect(root.querySelectorAll(".program-dashboard-group-row")).toHaveLength(1);
    expect(root.querySelectorAll(".program-dashboard-child-row")).toHaveLength(1);
  });

  it("restores persisted program and tab choices for the active space", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramId: "program-2",
      activeTab: "tasks",
    }));

    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [
          { program_id: "program-1", program_name: "Program One" },
          { program_id: "program-2", program_name: "TAP - Data Sourcing" },
        ],
        projects: [{ project_id: "project-2", program_id: "program-2", project_name: "Selected Project", status: "active" }],
        solutions: [],
        tasks: [],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
      showCompletedOperationalWork: () => false,
    });

    const root = document.getElementById("program-dashboard-root");
    expect(root.querySelector("select")?.value).toBe("program-2");
    expect(root.querySelector('[data-program-dashboard-tab="tasks"]')?.className).toContain("active");
    expect(root.textContent).toContain("No tasks match");
  });

  it("filters task rows by selected program and hides completed tasks when global visibility is off", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramId: "program-1",
      activeTab: "tasks",
    }));
    const openTask = vi.fn();

    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "TAP - Data Sourcing" }],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Program Project" },
          { project_id: "project-2", program_id: "program-2", project_name: "Other Project" },
        ],
        solutions: [{ solution_id: "solution-1", project_id: "project-1", solution_name: "Solution One" }],
        tasks: [
          {
            task_id: "task-1",
            project_id: "project-1",
            solution_id: "solution-1",
            task_name: "Connect source",
            status: "in_progress",
            assignee: "Nilesh",
            due_date: "2026-06-12",
            priority: 2,
          },
          {
            task_id: "task-2",
            project_id: "project-1",
            solution_id: "solution-1",
            task_name: "Closed task",
            status: "complete",
          },
          {
            task_id: "task-3",
            project_id: "project-2",
            solution_id: "solution-2",
            task_name: "Other task",
            status: "in_progress",
          },
        ],
      },
      formatStatus: (value) => `Status: ${value}`,
      solutionProgress: () => 0,
      showCompletedOperationalWork: () => false,
      openProgramDashboardTaskDrilldown: openTask,
    });

    const root = document.getElementById("program-dashboard-root");
    expect(root.textContent).toContain("Connect source");
    expect(root.textContent).toContain("1 closed hidden");
    expect(root.textContent).not.toContain("Closed task");
    expect(root.textContent).not.toContain("Other task");

    root.querySelector('[data-program-dashboard-action="open-task"]')?.click();
    expect(openTask).toHaveBeenCalledWith("task-1");
  });

  it("renders program dashboard empty states for missing programs and empty task lists", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    const root = document.getElementById("program-dashboard-root");

    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: root },
      state: { activeSpace: { space_id: "space-1" }, programs: [], projects: [], solutions: [], tasks: [] },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
      showCompletedOperationalWork: () => false,
    });

    expect(root.textContent).toContain("Create a program");

    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramId: "program-1",
      activeTab: "tasks",
    }));
    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: root },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "Program One" }],
        projects: [{ project_id: "project-1", program_id: "program-1", project_name: "Project One" }],
        solutions: [],
        tasks: [],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
      showCompletedOperationalWork: () => false,
    });

    expect(root.textContent).toContain("No tasks match");
  });
});
