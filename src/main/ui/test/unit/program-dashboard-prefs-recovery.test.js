import { afterEach, expect, it } from "vitest";
import { createProgramDashboardState, renderProgramDashboardView } from "../../js/routes/program-dashboard/render.js";

afterEach(() => {
  localStorage.clear();
  document.body.innerHTML = "";
});

function renderDashboard(programs) {
  document.body.innerHTML = '<section id="view-program-dashboard"><div id="root"></div></section>';
  const dashboard = createProgramDashboardState();
  renderProgramDashboardView(dashboard, {
    state: { activeSpace: { space_id: "space" }, programs, projects: [], solutions: [] },
    els: { programDashboardRoot: document.getElementById("root") },
    formatStatus: (status) => status,
    solutionProgress: () => 0,
  });
  return dashboard;
}

it.each(["null", "[]", "1", '"text"', "false", "{invalid"])("recovers invalid stored preferences %s", (stored) => {
  localStorage.setItem("sipm-program-dashboard-v1:space", stored);
  expect(() => renderDashboard([])).not.toThrow();
  expect(JSON.parse(localStorage.getItem("sipm-program-dashboard-v1:space"))).toEqual({});
  expect(document.getElementById("root").textContent).toContain("Create a program");
});

it("retains a valid saved program selection", () => {
  localStorage.setItem("sipm-program-dashboard-v1:space", JSON.stringify({ selectedProgramIds: ["second"] }));
  const dashboard = renderDashboard([{ program_id: "first", program_name: "First" }, { program_id: "second", program_name: "Second" }]);
  expect(dashboard.selectedProgramIds).toEqual(["second"]);
  expect(document.getElementById("root").textContent).toContain("Second");
});
