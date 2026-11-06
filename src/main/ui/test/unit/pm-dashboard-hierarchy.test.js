import { afterEach, expect, it } from "vitest";
import { createPMDashboardState, renderPMDashboardView } from "../../js/routes/pm-dashboard/render.js";

afterEach(() => {
  window.localStorage.clear();
  document.body.innerHTML = "";
});

it("counts only tasks belonging to their solution's project", () => {
  document.body.innerHTML = '<section id="view-pm-dashboard"><div id="summary"></div></section>';
  renderPMDashboardView(createPMDashboardState(), {
    state: {
      activeSpace: { space_id: "space", space_name: "Space" },
      projects: [{ project_id: "p1" }, { project_id: "p2" }],
      solutions: [{ solution_id: "s1", project_id: "p1" }],
      tasks: [
        { task_id: "valid", project_id: "p1", solution_id: "s1" },
        { task_id: "mismatch", project_id: "p2", solution_id: "s1" },
      ],
      users: [],
      allocations: [],
    },
    els: { pmDashboardSummary: document.getElementById("summary") },
    formatStatus: (status) => status,
    formatFte: (value) => String(value),
  });
  const cards = Array.from(document.querySelectorAll(".pm-kpi-card"));
  const deliverables = cards.find((card) => card.querySelector(".pm-kpi-label")?.textContent === "Open Deliverables");
  expect(deliverables.querySelector(".pm-kpi-value").textContent).toBe("1");
});

it("excludes work beneath programs that are no longer visible", () => {
  document.body.innerHTML = '<section id="view-pm-dashboard"><div id="summary"></div></section>';
  renderPMDashboardView(createPMDashboardState(), {
    state: {
      activeSpace: { space_id: "space" },
      loadedEntities: new Set(["programs"]),
      programs: [{ program_id: "active" }],
      projects: [
        { project_id: "p1", program_id: "active" },
        { project_id: "p2", program_id: "hidden" },
      ],
      solutions: [
        { solution_id: "s1", project_id: "p1" },
        { solution_id: "s2", project_id: "p2" },
      ],
      tasks: [
        { task_id: "t1", project_id: "p1", solution_id: "s1" },
        { task_id: "t2", project_id: "p2", solution_id: "s2" },
      ],
      users: [], allocations: [],
    },
    els: { pmDashboardSummary: document.getElementById("summary") },
    formatStatus: (status) => status,
    formatFte: (value) => String(value),
  });
  const cards = Array.from(document.querySelectorAll(".pm-kpi-card"));
  const value = (label) => cards.find((card) => card.querySelector(".pm-kpi-label")?.textContent === label)
    .querySelector(".pm-kpi-value").textContent;
  expect(value("Active Workstreams")).toBe("1");
  expect(value("Open Deliverables")).toBe("1");
});

it("shows each project's own open workstreams in project health", () => {
  document.body.innerHTML = '<section id="view-pm-dashboard"><div id="health"></div></section>';
  renderPMDashboardView(createPMDashboardState(), {
    state: {
      activeSpace: { space_id: "space" },
      projects: [
        { project_id: "p1", project_name: "First" },
        { project_id: "p2", project_name: "Second" },
      ],
      solutions: [
        { solution_id: "s1", project_id: "p1", status: "in_progress" },
        { solution_id: "s2", project_id: "p1", status: "complete" },
        { solution_id: "s3", project_id: "p2", status: "in_progress" },
        { solution_id: "s4", project_id: "p2", status: "in_progress" },
      ],
      tasks: [], users: [], allocations: [],
    },
    els: { pmDashboardHealth: document.getElementById("health") },
    formatStatus: (status) => status,
    formatFte: (value) => String(value),
  });
  const rows = Array.from(document.querySelectorAll("#health tbody tr"));
  const workstreams = (name) => Array.from(rows.find((row) => row.textContent.includes(name)).cells)[2].textContent;
  expect(workstreams("First")).toBe("1");
  expect(workstreams("Second")).toBe("2");
});
