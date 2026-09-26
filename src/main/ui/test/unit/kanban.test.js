import { describe, expect, it, vi } from "vitest";

import { renderKanban } from "../../js/routes/kanban.js";

describe("kanban route", () => {
  it("escapes backend-provided card and lane text before rendering", () => {
    document.body.innerHTML = '<div id="view-kanban"><div id="kanban-board"></div></div>';

    const ctx = {
      state: {
        phases: [
          {
            phase_id: "phase-1",
            phase_group: '<img src=x onerror="alert(1)">',
            phase_name: "<b>Design</b>",
            sequence: 1,
          },
        ],
        projects: [
          {
            project_id: "project-1",
            project_name: "Project",
          },
        ],
      },
      els: {
        kanbanBoard: document.getElementById("kanban-board"),
      },
      filteredSolutionsForKanban: () => [
        {
          solution_id: "solution-1",
          solution_name: "<script>alert(1)</script>",
          project_id: "project-1",
          current_phase: "phase-1",
          version: "<em>v1</em>",
          owner: '<img src=x onerror="alert(2)">',
          assignee: "<svg onload=alert(3)>",
          priority: '<iframe src="bad"></iframe>',
          due_date: '<a href="javascript:alert(4)">today</a>',
          status: '<marquee>active</marquee>',
        },
      ],
      phaseDisplayName: (phaseId) =>
        ctx.state.phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
      formatStatus: (status) => status,
    };

    renderKanban(ctx);

    const board = ctx.els.kanbanBoard;
    expect(board.querySelector("script")).toBeNull();
    expect(board.querySelector("img")).toBeNull();
    expect(board.querySelector("svg")).toBeNull();
    expect(board.querySelector("iframe")).toBeNull();
    expect(board.innerHTML).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(board.innerHTML).toContain("&lt;img src=x onerror=");
    expect(board.innerHTML).toContain("&lt;b&gt;Design&lt;/b&gt;");
    expect(board.innerHTML).toContain("&lt;marquee&gt;active&lt;/marquee&gt;");
  });

  it("renders one ordered column per phase even when phase groups match", () => {
    document.body.innerHTML = '<div id="view-kanban"><div id="kanban-board"></div></div>';

    const phases = [
      { phase_id: "testing", phase_group: "Delivery", phase_name: "Testing", sequence: 4 },
      { phase_id: "development", phase_group: "Delivery", phase_name: "Development", sequence: 3 },
    ];
    const ctx = {
      state: {
        phases,
        projects: [{ project_id: "project-1", project_name: "Project" }],
      },
      els: { kanbanBoard: document.getElementById("kanban-board") },
      filteredSolutionsForKanban: () => [
        {
          solution_id: "solution-1",
          solution_name: "Build",
          project_id: "project-1",
          current_phase: "development",
          status: "in_progress",
        },
      ],
      phaseDisplayName: (phaseId) => phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
      formatStatus: (status) => status,
    };

    renderKanban(ctx);

    const columns = [...ctx.els.kanbanBoard.querySelectorAll(".kanban-column")];
    expect(columns.map((column) => column.dataset.phaseId)).toEqual(["development", "testing"]);
    expect(columns.map((column) => column.querySelector("h4").textContent)).toEqual(["Development", "Testing"]);
    expect(columns[0].textContent).toContain("Build");
    expect(columns[1].textContent).toContain("Empty");
  });

  it("moves a solution with its labelled native phase control and disables it while pending", () => {
    document.body.innerHTML = '<div id="view-kanban"><div id="kanban-board"></div></div>';

    const phases = [
      { phase_id: "development", phase_name: "Development", sequence: 1 },
      { phase_id: "testing", phase_name: "Testing", sequence: 2 },
    ];
    const moveKanbanSolutionToPhase = vi.fn();
    let pending = false;
    const ctx = {
      state: {
        phases,
        projects: [{ project_id: "project-1", project_name: "Project" }],
      },
      els: { kanbanBoard: document.getElementById("kanban-board") },
      filteredSolutionsForKanban: () => [
        {
          solution_id: "solution-1",
          solution_name: "Build",
          project_id: "project-1",
          current_phase: "development",
          status: "in_progress",
        },
      ],
      phaseDisplayName: (phaseId) => phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
      formatStatus: (status) => status,
      isKanbanSolutionMovePending: () => pending,
      moveKanbanSolutionToPhase,
    };

    renderKanban(ctx);

    const phaseSelect = ctx.els.kanbanBoard.querySelector("[data-kanban-phase-select]");
    expect(phaseSelect.getAttribute("aria-label")).toBe("Move Build to phase");
    expect(phaseSelect.value).toBe("development");
    expect(phaseSelect.querySelectorAll("option")).toHaveLength(1);
    phaseSelect.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    expect(phaseSelect.querySelectorAll("option")).toHaveLength(2);
    expect(phaseSelect.value).toBe("development");
    phaseSelect.value = "testing";
    phaseSelect.dispatchEvent(new Event("change", { bubbles: true }));
    expect(moveKanbanSolutionToPhase).toHaveBeenCalledWith("solution-1", "testing");

    pending = true;
    renderKanban(ctx);
    expect(ctx.els.kanbanBoard.querySelector("[data-kanban-phase-select]").disabled).toBe(true);
    expect(ctx.els.kanbanBoard.querySelector('[data-kanban-draggable="solution"]').getAttribute("draggable")).toBe("false");
  });

  it("restores focus after keyboard phase changes only when focus stays on the board", async () => {
    document.body.innerHTML = '<div id="view-kanban"><div id="kanban-board"></div></div><button id="outside">Outside</button>';

    const phases = [
      { phase_id: "development", phase_name: "Development", sequence: 1 },
      { phase_id: "testing", phase_name: "Testing", sequence: 2 },
    ];
    let pending = false;
    let finishMove;
    let ctx;
    const moveKanbanSolutionToPhase = vi.fn(() => {
      pending = true;
      renderKanban(ctx);
      return new Promise((resolve) => {
        finishMove = () => {
          pending = false;
          renderKanban(ctx);
          resolve(true);
        };
      });
    });
    ctx = {
      state: {
        phases,
        projects: [{ project_id: "project-1", project_name: "Project" }],
      },
      els: { kanbanBoard: document.getElementById("kanban-board") },
      filteredSolutionsForKanban: () => [
        {
          solution_id: "solution-1",
          solution_name: "Build",
          project_id: "project-1",
          current_phase: "development",
          status: "in_progress",
        },
      ],
      phaseDisplayName: (phaseId) => phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
      formatStatus: (status) => status,
      isKanbanSolutionMovePending: () => pending,
      moveKanbanSolutionToPhase,
    };
    renderKanban(ctx);

    let phaseSelect = ctx.els.kanbanBoard.querySelector("[data-kanban-phase-select]");
    phaseSelect.focus();
    phaseSelect.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    phaseSelect.value = "testing";
    phaseSelect.dispatchEvent(new Event("change", { bubbles: true }));
    finishMove();
    await vi.waitFor(() => {
      expect(document.activeElement).toBe(ctx.els.kanbanBoard.querySelector("[data-kanban-phase-select]"));
    });

    phaseSelect = ctx.els.kanbanBoard.querySelector("[data-kanban-phase-select]");
    phaseSelect.focus();
    phaseSelect.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    phaseSelect.value = "testing";
    phaseSelect.dispatchEvent(new Event("change", { bubbles: true }));
    finishMove();
    await Promise.resolve();
    await Promise.resolve();
    expect(document.activeElement).toBe(document.body);

    phaseSelect = ctx.els.kanbanBoard.querySelector("[data-kanban-phase-select]");
    phaseSelect.focus();
    phaseSelect.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    phaseSelect.value = "testing";
    phaseSelect.dispatchEvent(new Event("change", { bubbles: true }));
    const outside = document.getElementById("outside");
    outside.focus();
    finishMove();
    await Promise.resolve();
    await Promise.resolve();
    expect(document.activeElement).toBe(outside);
  });

  it("moves a dragged solution to a different phase in the same project", () => {
    document.body.innerHTML = '<div id="view-kanban"><div id="kanban-board"></div></div>';

    const phases = [
      { phase_id: "development", phase_name: "Development", sequence: 3 },
      { phase_id: "testing", phase_name: "Testing", sequence: 4 },
    ];
    const moveKanbanSolutionToPhase = vi.fn();
    const ctx = {
      state: {
        phases,
        projects: [{ project_id: "project-1", project_name: "Project" }],
      },
      els: { kanbanBoard: document.getElementById("kanban-board") },
      filteredSolutionsForKanban: () => [
        {
          solution_id: "solution-1",
          solution_name: "Build",
          project_id: "project-1",
          current_phase: "development",
          status: "in_progress",
        },
      ],
      phaseDisplayName: (phaseId) => phases.find((phase) => phase.phase_id === phaseId)?.phase_name || "",
      formatStatus: (status) => status,
      isKanbanSolutionMovePending: () => false,
      moveKanbanSolutionToPhase,
    };

    renderKanban(ctx);

    const card = ctx.els.kanbanBoard.querySelector('[data-solution-id="solution-1"]');
    const sourceColumn = ctx.els.kanbanBoard.querySelector('[data-phase-id="development"]');
    const targetColumn = ctx.els.kanbanBoard.querySelector('[data-phase-id="testing"]');
    const dataTransfer = {
      effectAllowed: "",
      dropEffect: "",
      setData: vi.fn(),
      getData: vi.fn(() => "solution-1"),
    };
    const dragStart = new Event("dragstart", { bubbles: true, cancelable: true });
    Object.defineProperty(dragStart, "dataTransfer", { value: dataTransfer });
    card.dispatchEvent(dragStart);

    expect(dataTransfer.setData).toHaveBeenCalledWith("text/plain", "solution-1");
    expect(sourceColumn.classList.contains("is-drop-eligible")).toBe(false);
    expect(targetColumn.classList.contains("is-drop-eligible")).toBe(true);

    const dragOver = new Event("dragover", { bubbles: true, cancelable: true });
    Object.defineProperty(dragOver, "dataTransfer", { value: dataTransfer });
    targetColumn.dispatchEvent(dragOver);
    expect(dragOver.defaultPrevented).toBe(true);
    expect(targetColumn.classList.contains("is-drop-target")).toBe(true);

    const drop = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(drop, "dataTransfer", { value: dataTransfer });
    targetColumn.dispatchEvent(drop);

    expect(moveKanbanSolutionToPhase).toHaveBeenCalledWith("solution-1", "testing");
    expect(ctx.els.kanbanBoard.querySelector(".is-drop-eligible, .is-drop-target, .is-dragging")).toBeNull();
  });
});
