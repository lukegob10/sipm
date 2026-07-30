import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderMyWork } from "../../js/routes/my-work.js";

function context(records, { showCompleted = false } = {}) {
  document.body.innerHTML = '<div id="my-work-root"></div>';
  return {
    state: {
      users: [
        { soeid: "dev1", display_name: "Developer One" },
        { soeid: "dev2", display_name: "Developer Two" },
      ],
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
    showCompletedOperationalWork: () => showCompleted,
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

    expect(ctx.els.myWorkRoot.textContent).toContain("Your workday");
    expect(ctx.els.myWorkRoot.textContent).toContain("Resolve <contract>");
    expect(ctx.els.myWorkRoot.textContent).toContain("Developer Experience / Developer Mode / My Work");
    expect(ctx.els.myWorkRoot.textContent).toContain("Product decision");
    const attentionCard = ctx.els.myWorkRoot.querySelector(".my-work-card.needs-attention");
    expect(attentionCard).toBeTruthy();
    expect(attentionCard.textContent).toContain("Clarify the API behavior");
    expect(attentionCard.textContent).toContain("Blocked");
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

  it("uses the shared Show completed work preference", () => {
    const records = [
      {
        task: { task_id: "task-open", task_name: "Open task", status: "to_do", priority: 1 },
        project_name: "Project",
        solution_name: "Solution",
        needs_attention: false,
      },
      {
        task: { task_id: "task-complete", task_name: "Completed task", status: "complete", priority: 2 },
        project_name: "Project",
        solution_name: "Solution",
        needs_attention: false,
      },
      {
        task: { task_id: "task-abandoned", task_name: "Abandoned task", status: "abandoned", priority: 3 },
        project_name: "Project",
        solution_name: "Solution",
        needs_attention: false,
      },
    ];

    const defaultCtx = context(records);
    renderMyWork(defaultCtx);
    expect(defaultCtx.els.myWorkRoot.textContent).toContain("Open task");
    expect(defaultCtx.els.myWorkRoot.textContent).not.toContain("Completed task");
    expect(defaultCtx.els.myWorkRoot.textContent).not.toContain("Abandoned task");

    const completedCtx = context(records, { showCompleted: true });
    renderMyWork(completedCtx);
    expect(completedCtx.els.myWorkRoot.textContent).toContain("Open task");
    expect(completedCtx.els.myWorkRoot.textContent).toContain("Completed task");
    expect(completedCtx.els.myWorkRoot.textContent).toContain("Abandoned task");
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
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-drop-zone='later']")).toBeTruthy();
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
        github_repo_url: "https://github.com/example/task-override",
        effective_github_repo_url: "https://github.com/example/task-override",
        repo_source: "override",
        assignee: "Developer One",
        assignee_user_soeid: "dev1",
        estimate_hours: 80,
        capacity_hours: 160,
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
    expect(ctx.els.myWorkRoot.querySelector('[name="status"]').value).toBe("in_progress");
    expect(ctx.els.myWorkRoot.querySelector('[name="assignee"]').value).toBe("dev1");
    expect(ctx.els.myWorkRoot.querySelector('[name="assignee_user_soeid"]').value).toBe("dev1");
    expect(ctx.els.myWorkRoot.querySelector('[name="github_repo_url"]').value).toBe("https://github.com/example/task-override");
    expect(ctx.els.myWorkRoot.querySelector('[name="estimate_hours"]').value).toBe("0.50");
    expect(ctx.els.myWorkRoot.querySelector('[name="capacity_hours"]').value).toBe("1.00");
    expect(ctx.els.myWorkRoot.querySelector('[name="blocked"]').checked).toBe(true);
    expect(ctx.els.myWorkRoot.querySelector('[name="blocker_note"]').value).toBe("Needs a decision");
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-copy-grid [name='description']")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-copy-grid [name='acceptance_criteria']")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-blocked-toggle").textContent).toContain("Task is blocked");
    expect(ctx.els.myWorkRoot.querySelectorAll("[data-my-work-edit-cancel]")).toHaveLength(1);
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-heading button[type='submit']")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-edit-actions")).toBeNull();
  });

  it("saves every shared Task field from My Work with canonical FTE conversions", async () => {
    const records = [{
      task: {
        task_id: "task-1",
        task_name: "Clarify the contract",
        status: "to_do",
        priority: 3,
        assignee: "Developer One",
        assignee_user_soeid: "dev1",
        blocked: false,
      },
      program_name: "Developer Experience",
      project_name: "Developer Mode",
      solution_name: "My Work",
      needs_attention: false,
    }];
    const ctx = context(records);
    ctx.api.mockImplementation(async (path) => path === "/my-work" ? records : {});

    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit]").click();
    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-edit-form]");
    form.querySelector('[name="status"]').value = "in_progress";
    form.querySelector('[name="due_date"]').value = "2026-08-15";
    form.querySelector('[name="priority"]').value = "2";
    form.querySelector('[name="assignee"]').value = "dev2";
    form.querySelector('[name="assignee"]').dispatchEvent(new Event("change", { bubbles: true }));
    form.querySelector('[name="github_repo_url"]').value = "https://github.com/example/sipm";
    form.querySelector('[name="estimate_hours"]').value = "0.50";
    form.querySelector('[name="capacity_hours"]').value = "1.25";
    form.querySelector('[name="description"]').value = "Updated context";
    form.querySelector('[name="acceptance_criteria"]').value = "Contract is verified";
    form.querySelector('[name="blocked"]').checked = true;
    form.querySelector('[name="blocker_note"]').disabled = false;
    form.querySelector('[name="blocker_note"]').value = "Waiting on review";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() => {
      const updateCall = ctx.api.mock.calls.find(([path]) => path === "/tasks/task-1");
      expect(updateCall).toBeTruthy();
      expect(JSON.parse(updateCall[1].body)).toEqual(expect.objectContaining({
        task_name: "Clarify the contract",
        description: "Updated context",
        github_repo_url: "https://github.com/example/sipm",
        status: "in_progress",
        priority: 2,
        due_date: "2026-08-15",
        assignee: "Developer Two",
        assignee_user_soeid: "dev2",
        estimate_hours: 80,
        capacity_hours: 200,
        blocked: true,
        blocker_note: "Waiting on review",
        acceptance_criteria: "Contract is verified",
      }));
    });
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
    const target = ctx.els.myWorkRoot.querySelector("[data-my-work-drop-zone='later']");
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
