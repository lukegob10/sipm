import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderMyWork } from "../../js/routes/my-work.js";

function context(records) {
  document.body.innerHTML = '<div id="my-work-root"></div>';
  return {
    state: {
      myWork: {
        records,
        loading: false,
        error: "",
        selectedTaskId: records[0]?.task?.task_id || "",
        search: "",
        repository: "",
      },
    },
    els: { myWorkRoot: document.getElementById("my-work-root") },
    api: vi.fn(),
    escapeHtml: (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;"),
    formatStatus: (value) => String(value).replaceAll("_", " "),
    renderExternalRepoLink: (url, options) => `<a href="${url}">${options.label}</a>`,
    setView: vi.fn(),
  };
}

describe("My Work", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("renders a clean task queue while retaining full shared context in the detail pane", () => {
    const ctx = context([
      {
        task: {
          task_id: "task-1",
          task_name: "Resolve <contract>",
          status: "in_progress",
          priority: 1,
          blocked: true,
          blocker_note: "Product decision",
          description: "Clarify the API behavior",
          due_date: "2026-07-22",
          is_due_soon: true,
          acceptance_criteria: "Decision is recorded",
          effective_github_repo_url: "https://github.com/example/sipm",
          repo_source: "inherited",
        },
        program_name: "Developer Experience",
        project_name: "Developer Mode",
        solution_name: "My Work",
        needs_attention: true,
      },
      {
        task: {
          task_id: "task-2",
          task_name: "Build queue",
          status: "to_do",
          priority: 2,
        },
        program_name: "Developer Experience",
        project_name: "Developer Mode",
        solution_name: "My Work",
        needs_attention: false,
      },
    ]);

    renderMyWork(ctx);

    expect(ctx.els.myWorkRoot.textContent).toContain("Task queue");
    expect(ctx.els.myWorkRoot.textContent).toContain("Resolve <contract>");
    expect(ctx.els.myWorkRoot.textContent).toContain("Developer Experience / Developer Mode / My Work");
    expect(ctx.els.myWorkRoot.textContent).toContain("Product decision");
    const attentionCard = ctx.els.myWorkRoot.querySelector(".my-work-card.needs-attention");
    expect(attentionCard).toBeTruthy();
    expect(attentionCard.textContent).toContain("Clarify the API behavior");
    expect(attentionCard.textContent).toContain("Due soon");
    expect(attentionCard.textContent).not.toContain("In Progress");
    expect(attentionCard.textContent).not.toContain("Developer Experience");
    expect(attentionCard.querySelector(".pill")).toBeNull();
    expect(ctx.els.myWorkRoot.querySelectorAll(".my-work-card")).toHaveLength(2);
    expect(ctx.els.myWorkRoot.innerHTML).toContain("Resolve &lt;contract&gt;");
    expect(ctx.els.myWorkRoot.querySelector(".my-work-detail-view")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelectorAll(".my-work-detail-copy-section")).toHaveLength(2);
    expect(ctx.els.myWorkRoot.querySelector(".my-work-detail-footer .my-work-detail-actions")).toBeTruthy();
  });

  it("shows the non-destructive empty state", () => {
    const ctx = context([]);
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.textContent).toContain("You are clear");
    expect(ctx.els.myWorkRoot.textContent).toContain("No active Tasks are assigned to you");
  });

  it("uses the queue itself for private ordering instead of a separate focus control", () => {
    const ctx = context([{
      task: { task_id: "task-1", task_name: "Build queue", status: "to_do", priority: 2 },
      program_name: "Developer Experience",
      project_name: "Developer Mode",
      solution_name: "My Work",
      needs_attention: false,
    }]);

    renderMyWork(ctx);

    const card = ctx.els.myWorkRoot.querySelector("[data-my-work-select='task-1']");
    expect(card.getAttribute("draggable")).toBe("true");
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-drop-zone='queue']")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-focus]")).toBeNull();
  });

  it("opens a shared Task context editor from the detail pane", () => {
    const ctx = context([{
      task: {
        task_id: "task-1",
        task_name: "Clarify the contract",
        status: "in_progress",
        priority: 1,
        description: "Original context",
        blocked: true,
        blocker_note: "Needs a decision",
      },
      program_name: "Developer Experience",
      project_name: "Developer Mode",
      solution_name: "My Work",
      needs_attention: true,
    }]);

    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit]").click();

    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-edit-form]")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector('[name="description"]').value).toBe("Original context");
    expect(ctx.els.myWorkRoot.querySelector('[name="description"]').classList).toContain("my-work-longform-editor");
    expect(ctx.els.myWorkRoot.querySelector('[name="acceptance_criteria"]').classList).toContain("my-work-longform-editor");
    expect(ctx.els.myWorkRoot.querySelector('[name="acceptance_criteria"]').classList).toContain("my-work-acceptance-editor");
    expect(ctx.els.myWorkRoot.querySelector('[name="blocked"]').checked).toBe(true);
    expect(ctx.els.myWorkRoot.querySelector('[name="blocker_note"]').value).toBe("Needs a decision");
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-grid").nextElementSibling.querySelector('[name="description"]')).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-blocked-toggle").textContent).toContain("Task is blocked");
    expect(ctx.els.myWorkRoot.querySelectorAll("[data-my-work-edit-cancel]")).toHaveLength(1);
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-heading button[type='submit']")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-actions")).toBeNull();
  });

  it("persists a dragged card in its target queue lane", async () => {
    const records = [
      {
        task: { task_id: "task-now", task_name: "Current work", status: "in_progress", priority: 1 },
        program_name: "Developer Experience",
        project_name: "Developer Mode",
        solution_name: "My Work",
        needs_attention: false,
      },
      {
        task: { task_id: "task-next", task_name: "Upcoming work", status: "to_do", priority: 2 },
        program_name: "Developer Experience",
        project_name: "Developer Mode",
        solution_name: "My Work",
        needs_attention: false,
      },
    ];
    const ctx = context(records);
    ctx.api.mockImplementation(async (path) => path === "/my-work" ? records : {});
    renderMyWork(ctx);
    const source = ctx.els.myWorkRoot.querySelector("[data-my-work-select='task-now']");
    const target = ctx.els.myWorkRoot.querySelector("[data-my-work-drop-zone='queue']");
    const targetCard = ctx.els.myWorkRoot.querySelector("[data-my-work-select='task-next']");
    const dataTransfer = {
      effectAllowed: "",
      dropEffect: "",
      setData: vi.fn(),
      getData: vi.fn(() => "task-now"),
    };
    const dragStart = new Event("dragstart", { bubbles: true });
    Object.defineProperty(dragStart, "dataTransfer", { value: dataTransfer });
    source.dispatchEvent(dragStart);
    const dragOver = new MouseEvent("dragover", { bubbles: true, clientY: 100 });
    Object.defineProperty(dragOver, "dataTransfer", { value: dataTransfer });
    targetCard.dispatchEvent(dragOver);
    expect(targetCard.classList.contains("drop-after")).toBe(true);
    const drop = new MouseEvent("drop", { bubbles: true, clientY: 100 });
    Object.defineProperty(drop, "dataTransfer", { value: dataTransfer });
    targetCard.dispatchEvent(drop);
    expect(target.querySelector(".drop-before, .drop-after")).toBeNull();

    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledWith(
        "/my-work/tasks/task-now/state",
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining('"sort_rank":'),
        }),
      );
    });
  });
});
