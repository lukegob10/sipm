import { beforeEach, describe, expect, it, vi } from "vitest";

import { createShellContext } from "../../js/shell/context.js";
import {
  createProgramDashboardState,
  renderProgramDashboardView,
  splitProgramName,
} from "../../js/routes/program-dashboard/render.js";
import { renderAccess } from "../../js/routes/access.js";
import { calculateTableMinWidth, renderSectionTable } from "../../js/routes/dashboard/common.js";
import { createDashboardState, renderDashboardView } from "../../js/routes/dashboard/render.js";
import { renderSpaces } from "../../js/routes/spaces.js";
import { renderTasksWorkbench } from "../../js/routes/tasks-workbench.js";
import { renderTeamCapacity } from "../../js/routes/team-capacity.js";
import { filteredDeliverables } from "../../js/routes/master/filters.js";
import { bindDeliverablesTable } from "../../js/routes/master/interactions.js";
import { buildMasterTable } from "../../js/routes/master/table.js";

describe("simple route rendering", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
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
    expect(renderGovernanceHub.mock.calls[1]).toEqual([]);
    expect(renderGovernanceHub).toHaveBeenCalledTimes(2);
  });

  it("keeps dashboard tables wide enough for long solution names when extra columns are selected", () => {
    const compactColumns = ["solution", "completed"];
    const expandedColumns = ["solution", "project", "status", "rag", "timing", "completed", "fte", "owner"];
    const columnDefs = {
      solution: { label: "Solution", render: (row) => row.solutionName },
      project: { label: "Project", render: (row) => row.projectName },
      status: { label: "Status", render: (row) => row.status },
      rag: { label: "RAG", render: (row) => row.rag },
      timing: { label: "Timing", render: (row) => row.timing },
      completed: { label: "Completed", render: (row) => row.completed },
      fte: { label: "FTE-mo", render: (row) => row.fte },
      owner: { label: "Owner", render: (row) => row.owner },
    };

    const html = renderSectionTable({
      columns: expandedColumns,
      rows: [{
        solutionName: "A very long solution name that should not force the card into a compressed table",
        projectName: "Project",
        status: "Complete",
        rag: "Green",
        timing: "Due in 2d",
        completed: "2026-06-25",
        fte: "1.00",
        owner: "Owner",
      }],
      columnDefs,
      tableClass: "dashboard-mini-table",
      emptyText: "No rows",
    });

    expect(calculateTableMinWidth(expandedColumns)).toBeGreaterThan(calculateTableMinWidth(compactColumns));
    expect(html).toContain(`min-width:${calculateTableMinWidth(expandedColumns)}px;`);
  });

  it("paginates current dashboard deliverables with centered caret controls", () => {
    document.body.innerHTML = `
      <section id="view-dashboard">
        <div id="dashboard-space-capacity"></div>
        <div id="dashboard-top-projects"></div>
        <div id="dashboard-completed-quarter"></div>
        <div id="dashboard-upcoming-quarter"></div>
        <div id="dashboard-backlog"></div>
      </section>
    `;
    vi.stubGlobal("innerHeight", 760);
    const dashboardState = createDashboardState();
    const solutions = Array.from({ length: 7 }, (_, index) => ({
      solution_id: `solution-${index + 1}`,
      project_id: "project-1",
      solution_name: `Solution ${String(index + 1).padStart(2, "0")}`,
      status: "active",
      due_date: "2026-07-15",
    }));

    renderDashboardView(dashboardState, {
      state: {
        activeSpace: { space_id: "space-1" },
        projects: [{ project_id: "project-1", project_name: "Project One" }],
        solutions,
        tasks: [],
        users: [],
      },
      els: {
        dashboardSpaceCapacity: document.getElementById("dashboard-space-capacity"),
        dashboardTopProjects: document.getElementById("dashboard-top-projects"),
        dashboardCompletedQuarter: document.getElementById("dashboard-completed-quarter"),
        dashboardUpcomingQuarter: document.getElementById("dashboard-upcoming-quarter"),
        dashboardBacklog: document.getElementById("dashboard-backlog"),
      },
      formatStatus: (value) => value,
    });

    const root = document.getElementById("dashboard-top-projects");
    expect(root.textContent).toContain("Solution 01");
    expect(root.textContent).not.toContain("Solution 07");
    expect(root.querySelector(".dashboard-pagination")?.textContent).toContain("Page 1 of 2");
    expect(root.querySelector(".dashboard-page-range")?.textContent).toBe("1-5 of 7");
    expect(root.querySelector("[data-dashboard-page-direction='prev']")?.disabled).toBe(true);

    root.querySelector("[data-dashboard-page-direction='next']")?.click();

    expect(root.textContent).not.toContain("Solution 01");
    expect(root.textContent).toContain("Solution 07");
    expect(root.querySelector(".dashboard-pagination")?.textContent).toContain("Page 2 of 2");
    expect(root.querySelector(".dashboard-page-range")?.textContent).toBe("6-7 of 7");
    expect(root.querySelector("[data-dashboard-page-direction='next']")?.disabled).toBe(true);
  });

  it("renders team capacity summaries with filters and escaped labels", () => {
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
      },
      els: { capacityUserList, capacityTeamFilter, capacityNameFilter },
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
    expect(capacityUserList.textContent).toContain("Capacity1.00FTE-mo");
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
      sort: "name-asc",
      formatStatus: (status) => `Status: ${status}`,
      summary: { total: 1, visible: 1, overdue: 0, dueSoon: 1, blocked: 1, unassigned: 1 },
    });

    expect(tasksWorkbenchTable.querySelector("tr.active-row")?.dataset.id).toBe("task-1");
    expect(tasksWorkbenchTable.querySelector(".scwb-select-row")?.checked).toBe(true);
    expect(tasksWorkbenchTable.querySelector("#scwb-select-all")?.checked).toBe(true);
    expect(tasksWorkbenchTable.querySelector("th[aria-sort='ascending']")).toBeTruthy();
    expect(tasksWorkbenchTable.querySelector("[data-twb-task-sort]")?.textContent).toContain("A–Z");
    expect(tasksWorkbenchTable.textContent).toContain("Status: in_progress");
    expect(tasksWorkbenchTable.textContent).toContain("Blocked");
    expect(tasksWorkbenchTable.textContent).toContain("Unassigned");
    expect(tasksWorkbenchTable.innerHTML).toContain("API &lt;Gateway&gt;");
    expect(tasksWorkbenchTable.innerHTML).toContain("Project &amp; One");
    expect(tasksWorkbenchTable.textContent).toContain("Solution 'A'");
    expect(tasksWorkbenchTable.querySelector("[data-project-id='proj-1']")).toBeTruthy();
    expect(tasksWorkbenchTable.querySelector(".task-workbench-urgency")?.className).toContain("danger");
  });

  it("builds deliverables as a program, project, solution outline with contextual filters", () => {
    const ctx = {
      state: {
        filters: { query: "program:TAP sponsor:Sam" },
        programs: [
          { program_id: "program-1", program_name: "TAP - Data" },
          { program_id: "program-2", program_name: "Risk" },
        ],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "API Build", status: "active", sponsor: "Sam Sponsor", priority: 1 },
          { project_id: "project-2", program_id: "program-2", project_name: "Risk Build", status: "active", sponsor: "Risk Sponsor", priority: 2 },
        ],
        solutions: [
          { solution_id: "solution-1", project_id: "project-1", solution_name: "Gateway", status: "active", rag_status: "green" },
          { solution_id: "solution-2", project_id: "project-2", solution_name: "Risk UI", status: "active", rag_status: "green" },
        ],
      },
      hideClosedDeliverables: () => false,
      isClosedProjectStatus: () => false,
      isClosedSolutionStatus: () => false,
      formatStatus: (value) => value,
      phaseDisplayName: (value) => value,
      solutionProgress: () => 50,
    };

    const rows = filteredDeliverables(ctx);

    expect(rows.map((row) => row.type)).toEqual(["program-header", "project-header", "solution"]);
    expect(rows[0].program.program_name).toBe("TAP - Data");
    expect(rows[0].projectCount).toBe(1);
    expect(rows[1].project.project_name).toBe("API Build");
    expect(rows[2].solution.solution_name).toBe("Gateway");
  });

  it("filters deliverables with free text, field tokens, quoted values, and numeric thresholds", () => {
    const baseCtx = {
      state: {
        filters: { query: "" },
        programs: [{ program_id: "program-1", program_name: "Home Projects" }],
        projects: [
          {
            project_id: "project-1",
            program_id: "program-1",
            project_name: "Homelab Server",
            status: "active",
            sponsor: "Sam Sponsor",
            priority: 1,
          },
        ],
        solutions: [
          {
            solution_id: "solution-1",
            project_id: "project-1",
            solution_name: "Alpha Gateway",
            status: "active",
            rag_status: "amber",
            owner: "Alex Owner",
            current_phase: "build",
            priority: 2,
          },
          {
            solution_id: "solution-2",
            project_id: "project-1",
            solution_name: "Beta Portal",
            status: "blocked",
            rag_status: "red",
            owner: "Blair Owner",
            current_phase: "plan",
            priority: 4,
          },
        ],
      },
      hideClosedDeliverables: () => false,
      isClosedProjectStatus: () => false,
      isClosedSolutionStatus: () => false,
      formatStatus: (value) => value,
      phaseDisplayName: (value) => value,
      solutionProgress: (solution) => (solution.solution_id === "solution-1" ? 45 : 75),
    };
    const solutionNamesFor = (query) => {
      const rows = filteredDeliverables({
        ...baseCtx,
        state: { ...baseCtx.state, filters: { query } },
      });
      return rows.filter((row) => row.type === "solution").map((row) => row.solution.solution_name);
    };

    expect(solutionNamesFor("gateway")).toEqual(["Alpha Gateway"]);
    expect(solutionNamesFor("project:server status:active")).toEqual(["Alpha Gateway"]);
    expect(solutionNamesFor('project:"Homelab Server" owner:alex')).toEqual(["Alpha Gateway"]);
    expect(solutionNamesFor("priority:2 progress:50")).toEqual(["Alpha Gateway"]);
  });

  it("searches deliverables across all program and project groups including child task text", () => {
    const ctx = {
      state: {
        filters: { query: "task:cross-region" },
        programs: [
          { program_id: "program-1", program_name: "Alpha Program" },
          { program_id: "program-2", program_name: "Beta Program" },
          { program_id: "program-3", program_name: "Gamma Program" },
        ],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Alpha Project", status: "active", sponsor: "Sam", priority: 1 },
          { project_id: "project-2", program_id: "program-2", project_name: "Beta Project", status: "active", sponsor: "Taylor", priority: 2 },
          { project_id: "project-3", program_id: "program-3", project_name: "Gamma Project", status: "active", sponsor: "Riley", priority: 3 },
        ],
        solutions: [
          { solution_id: "solution-1", project_id: "project-1", solution_name: "Alpha Solution", status: "active", rag_status: "green" },
          { solution_id: "solution-2", project_id: "project-2", solution_name: "Beta Solution", status: "active", rag_status: "green" },
          { solution_id: "solution-3", project_id: "project-3", solution_name: "Gamma Solution", status: "active", rag_status: "green" },
        ],
        tasks: [
          { task_id: "task-1", project_id: "project-1", solution_id: "solution-1", task_name: "First group setup", status: "to_do" },
          { task_id: "task-2", project_id: "project-3", solution_id: "solution-3", task_name: "Cross-region launch checklist", status: "in_progress" },
        ],
      },
      hideClosedDeliverables: () => false,
      isClosedProjectStatus: () => false,
      isClosedSolutionStatus: () => false,
      formatStatus: (value) => value,
      phaseDisplayName: (value) => value,
      solutionProgress: () => 50,
    };

    const rows = filteredDeliverables(ctx);

    expect(rows.map((row) => row.type)).toEqual(["program-header", "project-header", "solution"]);
    expect(rows[0].program.program_name).toBe("Gamma Program");
    expect(rows[1].project.project_name).toBe("Gamma Project");
    expect(rows[2].solution.solution_name).toBe("Gamma Solution");
  });

  it("keeps live programs visible in deliverables even when they have no projects", () => {
    const ctx = {
      state: {
        filters: { query: "" },
        programs: [
          { program_id: "program-empty", program_name: "Empty Live Program" },
          { program_id: "program-filled", program_name: "Filled Program" },
        ],
        projects: [
          { project_id: "project-1", program_id: "program-filled", project_name: "Project One", status: "active", sponsor: "Sam", priority: 1 },
        ],
        solutions: [],
      },
      hideClosedDeliverables: () => false,
      isClosedProjectStatus: () => false,
      isClosedSolutionStatus: () => false,
      formatStatus: (value) => value,
      phaseDisplayName: (value) => value,
      solutionProgress: () => 0,
    };

    const rows = filteredDeliverables(ctx);
    const { html, rowCount } = buildMasterTable({
      state: ctx.state,
      filteredDeliverables: () => rows,
      phaseDisplayName: (value) => value,
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    expect(rows.filter((row) => row.type === "program-header").map((row) => row.program.program_name)).toEqual([
      "Empty Live Program",
      "Filled Program",
    ]);
    expect(rows[0]).toMatchObject({ type: "program-header", projectCount: 0, solutionCount: 0 });
    expect(html).toContain("Empty Live Program");
    expect(rowCount).toBe(3);
  });

  it("renders deliverables collapse state without losing parent orientation", () => {
    const rows = [
      {
        type: "program-header",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        programKey: "program-1",
        projectCount: 1,
        solutionCount: 1,
        atRiskCount: 0,
        dueSoonCount: 0,
      },
      {
        type: "project-header",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        project: { project_id: "project-1", project_name: "API Build", status: "active", sponsor: "Sam Sponsor", priority: 1 },
        projectKey: "project-1",
        solutionCount: 1,
        progress: 50,
      },
      {
        type: "solution",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        project: { project_id: "project-1", project_name: "API Build" },
        solution: { solution_id: "solution-1", solution_name: "Gateway", status: "active", rag_status: "green", priority: 2 },
      },
    ];
    const baseCtx = {
      state: { masterCollapsed: new Set(["project:project-1"]) },
      filteredDeliverables: () => rows,
      phaseDisplayName: (value) => value,
      formatStatus: (value) => value,
      solutionProgress: () => 50,
    };

    const { html } = buildMasterTable(baseCtx);

    expect(html).toContain("deliverable-row-program-header");
    expect(html).toContain("deliverable-row-project-header");
    expect(html).not.toContain("deliverable-row-solution");
    expect(html).toContain("master-tree-toggle");
    expect(html).toContain("deliverable-tree-depth-program");
    expect(html).toContain("deliverable-tree-depth-project");
    expect(html).toContain("deliverable-outline-summary");
    expect(html).not.toContain('class="pill');
    expect(html).not.toContain("deliverable-outline-meta");
    expect(html).toContain('data-master-collapse-key="project:project-1"');
    expect(html).toContain('aria-expanded="false"');
  });

  it("keeps the deliverables table viewport stable when expanding outline groups", () => {
    const masterTable = document.createElement("section");
    Object.defineProperty(masterTable, "clientHeight", { configurable: true, value: 120 });
    Object.defineProperty(masterTable, "scrollHeight", { configurable: true, value: 1200 });
    masterTable.innerHTML = `
      <table>
        <tbody>
          <tr data-master-row-key="project:project-1">
            <td>
              <button type="button" data-action="toggle-master-collapse" data-master-collapse-key="project:project-1" aria-expanded="false">Expand</button>
            </td>
          </tr>
        </tbody>
      </table>
    `;
    document.body.appendChild(masterTable);
    masterTable.scrollTop = 420;
    masterTable.scrollLeft = 18;
    const renderMasterTable = vi.fn(() => {
      masterTable.innerHTML = `
        <table>
          <tbody>
            <tr data-master-row-key="project:project-1">
              <td>
                <button type="button" data-action="toggle-master-collapse" data-master-collapse-key="project:project-1" aria-expanded="true">Collapse</button>
              </td>
            </tr>
            <tr><td>Expanded child row</td></tr>
          </tbody>
        </table>
      `;
      masterTable.scrollTop = 0;
      masterTable.scrollLeft = 0;
    });
    const ctx = {
      els: { masterTable },
      state: { masterCollapsed: new Set(["project:project-1"]) },
      persistMasterViewState: vi.fn(),
      renderMasterTable,
      openProgramForm: vi.fn(),
      openProjectForm: vi.fn(),
      openSolutionModal: vi.fn(),
      showTaskForm: vi.fn(),
    };

    bindDeliverablesTable(ctx);
    masterTable.querySelector("[data-action='toggle-master-collapse']").click();

    expect(ctx.state.masterCollapsed.has("project:project-1")).toBe(false);
    expect(ctx.persistMasterViewState).toHaveBeenCalledTimes(1);
    expect(renderMasterTable).toHaveBeenCalledTimes(1);
    expect(masterTable.scrollTop).toBe(420);
    expect(masterTable.scrollLeft).toBe(18);
    expect(document.activeElement).toBe(masterTable.querySelector("[data-master-collapse-key='project:project-1']"));
  });

  it("expands collapsed deliverables groups while search is active", () => {
    const rows = [
      {
        type: "program-header",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        programKey: "program-1",
        projectCount: 1,
        solutionCount: 1,
      },
      {
        type: "project-header",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        project: { project_id: "project-1", project_name: "API Build", status: "active", sponsor: "Sam Sponsor", priority: 1 },
        projectKey: "project-1",
        solutionCount: 1,
        progress: 50,
      },
      {
        type: "solution",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        project: { project_id: "project-1", project_name: "API Build" },
        solution: { solution_id: "solution-1", solution_name: "Gateway Match", status: "active", rag_status: "green", priority: 2 },
      },
    ];

    const { html } = buildMasterTable({
      state: {
        filters: { query: "gateway" },
        masterCollapsed: new Set(["program:program-1", "project:project-1"]),
      },
      filteredDeliverables: () => rows,
      phaseDisplayName: (value) => value,
      formatStatus: (value) => value,
      solutionProgress: () => 50,
    });

    expect(html).toContain("Gateway Match");
    expect(html).toContain('data-master-collapse-key="program:program-1" aria-expanded="true"');
    expect(html).toContain('data-master-collapse-key="project:project-1" aria-expanded="true"');
  });

  it("escapes deliverables solution data before rendering table markup", () => {
    const rows = [
      {
        type: "program-header",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        programKey: "program-1",
        projectCount: 1,
        solutionCount: 1,
      },
      {
        type: "project-header",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        project: { project_id: "project-1", project_name: "API Build", status: "active", sponsor: "Sam Sponsor", priority: 1 },
        projectKey: "project-1",
        solutionCount: 1,
        progress: 50,
      },
      {
        type: "solution",
        program: { program_id: "program-1", program_name: "TAP - Data" },
        project: { project_id: "project-1", project_name: "API Build" },
        solution: {
          solution_id: 'solution-1" autofocus onfocus="alert(1)',
          solution_name: "<script>alert(1)</script>",
          version: "<img src=x onerror=alert(1)>",
          owner: "<b>Alex</b>",
          current_phase: "phase-1",
          due_date: "2026-06-21\"><script>alert(2)</script>",
          status: "active",
          rag_status: "green",
          priority: '2" oninput="alert(3)',
        },
      },
    ];

    const { html } = buildMasterTable({
      state: { filters: { query: "" } },
      filteredDeliverables: () => rows,
      phaseDisplayName: () => "<em>Discovery</em>",
      formatStatus: (value) => value,
      solutionProgress: () => "<svg/onload=alert(4)>",
    });

    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<b>Alex</b>");
    expect(html).not.toContain("<em>Discovery</em>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
    expect(html).toContain("&lt;em&gt;Discovery&lt;/em&gt;");
    expect(html).toContain("&lt;svg/onload=alert(4)&gt;%");
    const container = document.createElement("div");
    container.innerHTML = html;
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[autofocus]")).toBeNull();
    expect(container.querySelector("[onfocus]")).toBeNull();
    expect(container.querySelector("[oninput]")).toBeNull();
  });

  it("splits program names into dashboard team and sub-area labels", () => {
    expect(splitProgramName("TAP - Data Sourcing")).toEqual({ team: "TAP", subArea: "Data Sourcing" });
    expect(splitProgramName("Transformation / Risk")).toEqual({ team: "Transformation", subArea: "Risk" });
    expect(splitProgramName("Default Program")).toEqual({ team: "", subArea: "Default Program" });
  });

  it("renders program project groups and child solutions for selected programs", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    const programDashboardState = createProgramDashboardState();
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1", "program-2"],
    }));

    renderProgramDashboardView(programDashboardState, {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [
          { program_id: "program-1", program_name: "TAP - Data Sourcing" },
          { program_id: "program-2", program_name: "Transformation / Risk" },
        ],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Data Sourcing - APIs", status: "active", sponsor: "Sam Sponsor" },
          { project_id: "project-2", program_id: "program-2", project_name: "Risk Warehouse", status: "active", sponsor_user_soeid: "abc123" },
          { project_id: "project-3", program_id: "program-3", project_name: "Other Program Project", status: "active" },
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
            escalation: "Needs management unblock",
          },
          {
            solution_id: "solution-2",
            project_id: "project-2",
            solution_name: "Risk Controls",
            status: "not_started",
            owner_user_soeid: "owner123",
            current_phase: "plan",
          },
        ],
      },
      formatStatus: (value) => `Status: ${value}`,
      phaseDisplayName: (phaseId) => (phaseId === "build_docs" ? "Build / Docs" : phaseId),
      solutionProgress: () => 50,
    });

    const root = document.getElementById("program-dashboard-root");
    expect(root.textContent).toContain("Program Dashboard");
    expect(root.textContent).toContain("Multiple selected");
    expect(root.textContent).toContain("TAP - Data Sourcing");
    expect(root.textContent).toContain("Transformation / Risk");
    expect(root.textContent).toContain("Data Sourcing - APIs");
    expect(root.textContent).toContain("Risk Warehouse");
    expect(root.textContent).toContain("CitiVelocity");
    expect(root.textContent).toContain("Risk Controls");
    expect(root.textContent).toContain("Spencer Emma");
    expect(root.textContent).toContain("owner123");
    expect(root.textContent).toContain("Sam Sponsor");
    expect(root.textContent).toContain("abc123");
    expect(root.textContent).not.toContain("Build / Docs");
    expect(root.textContent).toContain("Needs management unblock");
    expect(root.textContent).not.toContain("build_docs");
    expect(root.textContent).toContain("50%");
    expect(root.textContent).not.toContain("Other Program Project");
    expect(root.textContent).not.toContain("Confidential");
    expect(root.textContent).not.toContain("Internal Use Only");
    expect([...root.querySelectorAll(".program-dashboard-grid-header [role='columnheader']")].map((cell) => cell.textContent)).toEqual([
      "Deliverable",
      "Function",
      "Area",
      "Solution / Owner",
      "Start",
      "End",
      "Status",
      "Escalation",
      "% Complete",
    ]);
    root.querySelectorAll(".program-dashboard-grid-row").forEach((row) => {
      expect(row.querySelectorAll(":scope > .program-dashboard-grid-cell")).toHaveLength(9);
    });
    expect(root.querySelector(".program-dashboard-program-row .program-dashboard-escalation-cell")?.textContent).toBe("");
    expect(root.querySelector(".program-dashboard-project-row .program-dashboard-escalation-cell")?.textContent).toBe("");
    expect(root.querySelector(".program-dashboard-child-row .program-dashboard-escalation-cell")?.textContent).toBe("Needs management unblock");
    expect([...root.querySelectorAll("th")].map((th) => th.textContent)).not.toContain("Program");
    expect(root.querySelector(".program-dashboard-project-grid")).not.toBeNull();
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-program-row")).toHaveLength(2);
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-group-row")).toHaveLength(2);
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-child-row")).toHaveLength(2);
    expect(root.querySelector('[data-program-dashboard-action="download-pdf"]')?.textContent).toBe("Download PDF");
    expect(root.querySelector('[data-program-dashboard-action="download-excel"]')?.textContent).toBe("Download Excel");
    expect(root.querySelector(".program-dashboard-table-download-actions")?.textContent).toContain("Download PDF");
    expect(root.querySelector(".program-dashboard-table-download-actions")?.textContent).toContain("Download Excel");
    expect(root.querySelector(".program-dashboard-table-outline-actions")?.textContent).toContain("Expand All");
    expect(root.querySelector(".program-dashboard-table-outline-actions")?.textContent).toContain("Collapse All");

    root.querySelector('[data-program-dashboard-action="toggle-project"]')?.click();
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-child-row")).toHaveLength(1);
    expect(root.querySelector(".program-dashboard-group-row")?.className).toContain("program-dashboard-group-row-collapsed");
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.collapsedProjectIds).toEqual(["project-1"]);

    root.querySelector('[data-program-dashboard-action="expand-projects"]')?.click();
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-child-row")).toHaveLength(2);
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.collapsedProjectIds).toEqual([]);
  });

  it("keeps the program dashboard viewport stable when expanding outline groups", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1"],
    }));
    const programDashboardState = createProgramDashboardState();
    const ctx = {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "Program One" }],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Project One", status: "active" },
        ],
        solutions: [
          { solution_id: "solution-1", project_id: "project-1", solution_name: "Solution One", status: "active" },
        ],
      },
      formatStatus: (value) => value,
      phaseDisplayName: (value) => value,
      solutionProgress: () => 25,
    };

    renderProgramDashboardView(programDashboardState, ctx);
    const shell = document.querySelector(".program-dashboard-table-shell");
    Object.defineProperty(shell, "clientHeight", { configurable: true, value: 160 });
    Object.defineProperty(shell, "scrollHeight", { configurable: true, value: 1200 });
    shell.scrollTop = 360;
    shell.scrollLeft = 22;

    document.querySelector('[data-program-dashboard-action="toggle-project"][data-project-id="project-1"]')?.click();

    const rerenderedShell = document.querySelector(".program-dashboard-table-shell");
    expect(rerenderedShell.scrollTop).toBe(360);
    expect(rerenderedShell.scrollLeft).toBe(22);
    expect(document.activeElement).toBe(
      document.querySelector('[data-program-dashboard-action="toggle-project"][data-project-id="project-1"]')
    );
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.collapsedProjectIds).toEqual(["project-1"]);
  });

  it("rolls up program dashboard percent complete without rendering phase", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1"],
    }));

    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "Program One" }],
        projects: [{ project_id: "project-1", program_id: "program-1", project_name: "Project One", status: "active" }],
        solutions: [
          {
            solution_id: "solution-1",
            project_id: "project-1",
            solution_name: "Planning Work",
            status: "active",
            current_phase: "plan",
          },
          {
            solution_id: "solution-2",
            project_id: "project-1",
            solution_name: "Build Work",
            status: "active",
            current_phase: "build",
          },
          {
            solution_id: "solution-3",
            project_id: "project-1",
            solution_name: "Done Work",
            status: "complete",
            current_phase: "deploy",
          },
        ],
      },
      formatStatus: (value) => value,
      phaseDisplayName: (phaseId) => ({ plan: "Plan", build: "Build", deploy: "Deploy" })[phaseId] || phaseId,
      solutionProgress: (solution) => ({
        "solution-1": 0,
        "solution-2": 33,
        "solution-3": 100,
      })[solution.solution_id] ?? 0,
    });

    const root = document.getElementById("program-dashboard-root");
    const programCells = root.querySelector(".program-dashboard-program-row")?.querySelectorAll(".program-dashboard-grid-cell");
    const projectCells = root.querySelector(".program-dashboard-project-row")?.querySelectorAll(".program-dashboard-grid-cell");
    expect(root.querySelector(".program-dashboard-phase-cell")).toBeNull();
    expect(programCells?.[8]?.textContent).toContain("44%");
    expect(projectCells?.[8]?.textContent).toContain("44%");
  });

  it("downloads the program dashboard PDF with selected and collapsed state", async () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1", "program-2"],
      collapsedProgramIds: ["program-2"],
      collapsedProjectIds: ["project-1"],
    }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(new Blob(["pdf"], { type: "application/pdf" })),
    });
    const createObjectUrl = vi.fn().mockReturnValue("blob:program-dashboard-report");
    const revokeObjectUrl = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: createObjectUrl,
      revokeObjectURL: revokeObjectUrl,
    });

    renderProgramDashboardView(createProgramDashboardState(), {
      apiBase: "/project-manager/api",
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [
          { program_id: "program-1", program_name: "Program One" },
          { program_id: "program-2", program_name: "Program Two" },
        ],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Project One", status: "active" },
          { project_id: "project-2", program_id: "program-2", project_name: "Project Two", status: "active" },
        ],
        solutions: [],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    document.querySelector('[data-program-dashboard-action="download-pdf"]')?.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(fetchMock).toHaveBeenCalledWith("/project-manager/api/programs/dashboard/report.pdf", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Space-Id": "space-1",
      },
      credentials: "include",
      body: JSON.stringify({
        selected_program_ids: ["program-1", "program-2"],
        collapsed_program_ids: ["program-2"],
        collapsed_project_ids: ["project-1"],
      }),
    });
    expect(createObjectUrl).toHaveBeenCalled();
  });

  it("downloads the program dashboard Excel report with selected and collapsed state", async () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1"],
      collapsedProjectIds: ["project-1"],
    }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(new Blob(["xlsx"], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      })),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue("blob:program-dashboard-excel-report"),
      revokeObjectURL: vi.fn(),
    });

    renderProgramDashboardView(createProgramDashboardState(), {
      apiBase: "/project-manager/api",
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "Program One" }],
        projects: [{ project_id: "project-1", program_id: "program-1", project_name: "Project One" }],
        solutions: [],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    document.querySelector('[data-program-dashboard-action="download-excel"]')?.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(fetchMock).toHaveBeenCalledWith("/project-manager/api/programs/dashboard/report.xlsx", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Space-Id": "space-1",
      },
      credentials: "include",
      body: JSON.stringify({
        selected_program_ids: ["program-1"],
        collapsed_program_ids: [],
        collapsed_project_ids: ["project-1"],
      }),
    });
  });

  it("reports program dashboard PDF download failures without changing collapse state", async () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1"],
      collapsedProjectIds: ["project-1"],
    }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: vi.fn().mockResolvedValue(JSON.stringify({ detail: "Report failed" })),
    }));
    const setStatus = vi.fn();
    const trackWorkflow = vi.fn();

    renderProgramDashboardView(createProgramDashboardState(), {
      apiBase: "/project-manager/api",
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "Program One" }],
        projects: [{ project_id: "project-1", program_id: "program-1", project_name: "Project One", status: "active" }],
        solutions: [{ solution_id: "solution-1", project_id: "project-1", solution_name: "Hidden While Collapsed" }],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
      setStatus,
      trackWorkflow,
    });

    document.querySelector('[data-program-dashboard-action="download-pdf"]')?.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(setStatus).toHaveBeenCalledWith("Report failed", "danger");
    expect(trackWorkflow).toHaveBeenCalledWith("program_dashboard", "report_download", "failure", {
      source: "program_dashboard",
    });
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.collapsedProjectIds).toEqual(["project-1"]);
  });

  it("restores persisted program choices for the active space", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-2"],
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
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    const root = document.getElementById("program-dashboard-root");
    const selectedCheckbox = root.querySelector("[data-program-dashboard-control='program'][value='program-2']");
    const unselectedCheckbox = root.querySelector("[data-program-dashboard-control='program'][value='program-1']");
    expect(selectedCheckbox?.checked).toBe(true);
    expect(unselectedCheckbox?.checked).toBe(false);
    expect(root.textContent).toContain("Selected Project");
  });

  it("keeps the program picker open while selecting multiple programs", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1"],
    }));
    const programDashboardState = createProgramDashboardState();

    renderProgramDashboardView(programDashboardState, {
      els: { programDashboardRoot: document.getElementById("program-dashboard-root") },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [
          { program_id: "program-1", program_name: "Program One" },
          { program_id: "program-2", program_name: "Program Two" },
        ],
        projects: [
          { project_id: "project-1", program_id: "program-1", project_name: "Project One", status: "active" },
          { project_id: "project-2", program_id: "program-2", project_name: "Project Two", status: "active" },
        ],
        solutions: [],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    const firstPicker = document.querySelector(".program-dashboard-picker-menu");
    firstPicker.open = true;
    document.querySelector("[data-program-dashboard-control='program'][value='program-2']")?.click();

    const rerenderedPicker = document.querySelector(".program-dashboard-picker-menu");
    expect(rerenderedPicker.open).toBe(true);
    expect(document.querySelector(".program-dashboard-picker summary")?.textContent).toBe("Multiple selected");
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.selectedProgramIds).toEqual([
      "program-1",
      "program-2",
    ]);

    document.body.click();

    expect(document.querySelector(".program-dashboard-picker-menu")?.open).toBe(false);
  });

  it("renders program dashboard empty states for missing programs and empty project lists", () => {
    document.body.innerHTML = `
      <section id="view-program-dashboard">
        <div id="program-dashboard-root"></div>
      </section>
    `;
    const root = document.getElementById("program-dashboard-root");

    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: root },
      state: { activeSpace: { space_id: "space-1" }, programs: [], projects: [], solutions: [] },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    expect(root.textContent).toContain("Create a program");

    localStorage.setItem("sipm-program-dashboard-v1:space-1", JSON.stringify({
      selectedProgramIds: ["program-1"],
    }));
    renderProgramDashboardView(createProgramDashboardState(), {
      els: { programDashboardRoot: root },
      state: {
        activeSpace: { space_id: "space-1" },
        programs: [{ program_id: "program-1", program_name: "Program One" }],
        projects: [],
        solutions: [],
      },
      formatStatus: (value) => value,
      solutionProgress: () => 0,
    });

    expect(root.textContent).toContain("No projects are assigned");
  });
});
