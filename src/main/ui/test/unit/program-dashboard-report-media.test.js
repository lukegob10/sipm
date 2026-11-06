import { afterEach, describe, expect, it, vi } from "vitest";
import { createProgramDashboardState, renderProgramDashboardView } from "../../js/routes/program-dashboard/render.js";

const PDF = "application/pdf";
const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  document.body.innerHTML = "";
});

function harness(response) {
  document.body.innerHTML = '<section id="view-program-dashboard"><div id="root"></div></section>';
  const createObjectURL = vi.fn(() => "blob:test");
  vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL: vi.fn() });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
  const setStatus = vi.fn();
  const trackWorkflow = vi.fn();
  renderProgramDashboardView(createProgramDashboardState(), {
    state: { activeSpace: { space_id: "space" }, programs: [{ program_id: "p", program_name: "Program" }], projects: [{ project_id: "project", program_id: "p", project_name: "Project" }], solutions: [] },
    els: { programDashboardRoot: document.querySelector("#root") },
    formatStatus: String, solutionProgress: () => 0, setStatus, trackWorkflow,
  });
  return { createObjectURL, setStatus, trackWorkflow };
}

describe("program report response media", () => {
  it.each([["pdf", PDF], ["excel", XLSX]])("downloads valid %s media", async (type, mediaType) => {
    const h = harness({ ok: true, headers: new Headers({ "content-type": `${mediaType}; charset=binary` }), blob: async () => new Blob(["report"]) });
    document.querySelector(`[data-program-dashboard-action="download-${type}"]`).click();
    await vi.waitFor(() => expect(h.createObjectURL).toHaveBeenCalledTimes(1));
    expect(h.trackWorkflow).toHaveBeenCalledWith("program_dashboard", "report_download", "success", expect.any(Object));
  });

  it.each([["pdf", "application/json"], ["pdf", "text/html"], ["excel", "application/json"], ["excel", "text/html"]])(
    "rejects a 200 %s response containing %s", async (type, mediaType) => {
      const h = harness({ ok: true, headers: new Headers({ "content-type": mediaType }), blob: async () => new Blob(["not a report"]) });
      document.querySelector(`[data-program-dashboard-action="download-${type}"]`).click();
      await vi.waitFor(() => expect(h.setStatus).toHaveBeenCalledWith(expect.stringContaining("server did not return"), "danger"));
      expect(h.createObjectURL).not.toHaveBeenCalled();
      expect(h.trackWorkflow).toHaveBeenCalledWith("program_dashboard", "report_download", "failure", expect.any(Object));
    },
  );

  it("retains the server's error message on non-success responses", async () => {
    const h = harness({ ok: false, status: 403, text: async () => JSON.stringify({ detail: "Access denied" }) });
    document.querySelector('[data-program-dashboard-action="download-pdf"]').click();
    await vi.waitFor(() => expect(h.setStatus).toHaveBeenCalledWith("Access denied", "danger"));
    expect(h.createObjectURL).not.toHaveBeenCalled();
  });
});
