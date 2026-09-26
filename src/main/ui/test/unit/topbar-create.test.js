import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTopbarCreateController } from "../../js/shell/topbar-create.js";

function buildHarness() {
  document.body.innerHTML = `
    <div id="topbar-create-shell">
      <button id="topbar-create-toggle" aria-expanded="false"></button>
      <div id="topbar-create-panel" class="hidden" role="menu">
        <button id="topbar-create-program" role="menuitem">Program</button>
        <button id="topbar-create-project" role="menuitem">Project</button>
        <button id="topbar-create-solution" role="menuitem">Solution</button>
        <button id="topbar-create-task" role="menuitem">Task</button>
      </div>
    </div>
    <button id="outside"></button>
  `;
  const els = {
    topbarCreateToggle: document.getElementById("topbar-create-toggle"),
    topbarCreatePanel: document.getElementById("topbar-create-panel"),
    topbarCreateProgram: document.getElementById("topbar-create-program"),
    topbarCreateProject: document.getElementById("topbar-create-project"),
    topbarCreateSolution: document.getElementById("topbar-create-solution"),
    topbarCreateTask: document.getElementById("topbar-create-task"),
  };
  const controller = createTopbarCreateController({
    state: { solutions: [], projects: [] },
    els,
    escapeHtml: String,
    openProgramForm: vi.fn(),
    openProjectForm: vi.fn(),
    openSolutionModal: vi.fn(),
    showTaskForm: vi.fn(),
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
  });
  controller.bindTopbarCreateMenu();
  return { controller, els, outside: document.getElementById("outside") };
}

describe("topbar create menu", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("closes when keyboard focus moves out of the menu", () => {
    const { els, outside } = buildHarness();
    els.topbarCreateToggle.click();
    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(false);
    expect(document.activeElement).toBe(els.topbarCreateProgram);

    outside.focus();

    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(true);
    expect(els.topbarCreateToggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(outside);
  });

  it("keeps the menu open while keyboard focus moves between menu items", () => {
    const { els } = buildHarness();
    els.topbarCreateToggle.click();

    els.topbarCreateProject.focus();

    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(false);
    expect(els.topbarCreateToggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("closes when its toggle is clicked after focus returns from a menu item", () => {
    const { els } = buildHarness();
    els.topbarCreateToggle.click();

    els.topbarCreateToggle.focus();
    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(false);
    els.topbarCreateToggle.click();

    expect(els.topbarCreatePanel.classList.contains("hidden")).toBe(true);
    expect(els.topbarCreateToggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(els.topbarCreateToggle);
  });
});
