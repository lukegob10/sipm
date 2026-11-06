import { afterEach, expect, it, vi } from "vitest";
import { createPMDashboardState, renderPMDashboardView } from "../../js/routes/pm-dashboard/render.js";

afterEach(() => {
  vi.useRealTimers();
  window.localStorage.clear();
  document.body.innerHTML = "";
});

it("counts UTC and offset completion timestamps in the current local month", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 4, 1, 12));
  document.body.innerHTML = '<section id="view-pm-dashboard"><div id="summary"></div></section>';
  const start = new Date(2026, 4, 1).getTime();
  const before = new Date(start - 1000).toISOString();
  const after = new Date(start + 1000).toISOString();
  const afterAtOffset = `${new Date(start + 1000 + 2 * 60 * 60 * 1000).toISOString().slice(0, -1)}+02:00`;
  const task = (id, fields) => ({ task_id: id, project_id: "p", solution_id: "s", status: "complete", ...fields });
  renderPMDashboardView(createPMDashboardState(), {
    state: {
      activeSpace: { space_id: "space" }, projects: [{ project_id: "p" }],
      solutions: [{ solution_id: "s", project_id: "p", status: "active" }],
      tasks: [
        task("previous", { completed_at: before.slice(0, -1) }),
        task("utc", { completed_at: after }),
        task("naive", { completed_at: after.slice(0, -1) }),
        task("offset", { completed_at: afterAtOffset }),
        task("fallback", { completed_at: null, updated_at: after.slice(0, -1) }),
      ],
      users: [], allocations: [],
    },
    els: { pmDashboardSummary: document.getElementById("summary") },
    formatStatus: (status) => status,
    formatFte: (value) => String(value),
  });
  const card = [...document.querySelectorAll(".pm-kpi-card")]
    .find((element) => element.querySelector(".pm-kpi-label")?.textContent === "Throughput (This Month)");
  expect(card.querySelector(".pm-kpi-value").textContent).toBe("4");
});
