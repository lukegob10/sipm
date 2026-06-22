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
import { filteredDeliverables } from "../../js/routes/master/filters.js";
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
    expect(root.textContent).toContain("Build / Docs");
    expect(root.textContent).toContain("Needs management unblock");
    expect(root.textContent).not.toContain("build_docs");
    expect(root.textContent).toContain("50%");
    expect(root.textContent).not.toContain("Other Program Project");
    expect(root.textContent).not.toContain("Confidential");
    expect(root.textContent).not.toContain("Internal Use Only");
    expect([...root.querySelectorAll(".program-dashboard-grid-header [role='columnheader']")].map((cell) => cell.textContent)).toEqual([
      "Deliverable",
      "Solution / Owner",
      "Start",
      "End",
      "Status",
      "Phase",
      "Escalation",
      "% Complete",
    ]);
    root.querySelectorAll(".program-dashboard-grid-row").forEach((row) => {
      expect(row.querySelectorAll(":scope > .program-dashboard-grid-cell")).toHaveLength(8);
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

    root.querySelector('[data-program-dashboard-action="toggle-project"]')?.click();
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-child-row")).toHaveLength(1);
    expect(root.querySelector(".program-dashboard-group-row")?.className).toContain("program-dashboard-group-row-collapsed");
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.collapsedProjectIds).toEqual(["project-1"]);

    root.querySelector('[data-program-dashboard-action="expand-projects"]')?.click();
    expect(root.querySelectorAll(".program-dashboard-grid-row.program-dashboard-child-row")).toHaveLength(2);
    expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space-1"))?.collapsedProjectIds).toEqual([]);
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
