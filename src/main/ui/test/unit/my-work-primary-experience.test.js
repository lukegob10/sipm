import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderMyWork } from "../../js/routes/my-work.js";

function taskRecord(taskId, overrides = {}) {
  const taskOverrides = overrides.task || {};
  return {
    task: {
      task_id: taskId,
      task_name: `Task ${taskId}`,
      status: "to_do",
      priority: 3,
      urgency_score: 0,
      ...taskOverrides,
    },
    program_name: "Developer Experience",
    project_name: "Developer Mode",
    solution_name: "My Work",
    private_bucket: "later",
    private_sort_rank: 0,
    private_reminder_at: null,
    private_note: null,
    reminder_due: false,
    needs_attention: false,
    ...overrides,
    task: {
      task_id: taskId,
      task_name: `Task ${taskId}`,
      status: "to_do",
      priority: 3,
      urgency_score: 0,
      ...taskOverrides,
    },
  };
}

function context(records, { showCompleted = false } = {}) {
  document.body.innerHTML = '<div id="my-work-root"></div>';
  const ctx = {
    state: {
      myWork: {
        records,
        loading: false,
        error: "",
        selectedTaskId: records[0]?.task?.task_id || "",
        search: "",
        repository: "",
        editingTaskId: "",
        draggingTaskId: "",
        savingPrivateTaskId: "",
      },
    },
    els: { myWorkRoot: document.getElementById("my-work-root") },
    api: vi.fn(async (path) => path === "/my-work" ? records : {}),
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
  return ctx;
}

function sectionTaskIds(root, section) {
  return [...root.querySelectorAll(`[data-my-work-section-panel="${section}"] [data-my-work-select]`)]
    .map((card) => card.dataset.myWorkSelect);
}

function drag(source, target, taskId) {
  const dataTransfer = {
    effectAllowed: "",
    dropEffect: "",
    setData: vi.fn(),
    getData: vi.fn(() => taskId),
  };
  const dragStart = new Event("dragstart", { bubbles: true });
  Object.defineProperty(dragStart, "dataTransfer", { value: dataTransfer });
  source.dispatchEvent(dragStart);
  const dragOver = new MouseEvent("dragover", { bubbles: true, clientY: 100 });
  Object.defineProperty(dragOver, "dataTransfer", { value: dataTransfer });
  target.dispatchEvent(dragOver);
  const drop = new MouseEvent("drop", { bubbles: true, clientY: 100 });
  Object.defineProperty(drop, "dataTransfer", { value: dataTransfer });
  target.dispatchEvent(drop);
}

describe("My Work", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("classifies every task once using Attention, Waiting, Today, Upcoming, Later precedence", () => {
    const records = [
      taskRecord("blocked-today", {
        task: { blocked: true, urgency_score: 40 },
        private_bucket: "today",
        needs_attention: true,
      }),
      taskRecord("overdue-waiting", {
        task: { status: "on_hold", is_overdue: true, due_date: "2026-07-20", urgency_score: 60 },
        needs_attention: true,
      }),
      taskRecord("reminder", {
        private_reminder_at: "2026-07-29T12:00:00Z",
        reminder_due: true,
      }),
      taskRecord("waiting-today", {
        task: { status: "on_hold" },
        private_bucket: "today",
      }),
      taskRecord("today-upcoming", {
        task: { is_due_soon: true, due_date: "2026-08-01" },
        private_bucket: "today",
      }),
      taskRecord("upcoming", {
        task: { is_due_soon: true, due_date: "2026-08-02" },
      }),
      taskRecord("later"),
    ];
    const ctx = context(records);

    renderMyWork(ctx);

    expect(sectionTaskIds(ctx.els.myWorkRoot, "attention")).toEqual([
      "overdue-waiting",
      "blocked-today",
      "reminder",
    ]);
    expect(sectionTaskIds(ctx.els.myWorkRoot, "waiting")).toEqual(["waiting-today"]);
    expect(sectionTaskIds(ctx.els.myWorkRoot, "today")).toEqual(["today-upcoming"]);
    expect(sectionTaskIds(ctx.els.myWorkRoot, "upcoming")).toEqual(["upcoming"]);
    expect(sectionTaskIds(ctx.els.myWorkRoot, "later")).toEqual(["later"]);
    expect(ctx.els.myWorkRoot.querySelectorAll("[data-my-work-select]")).toHaveLength(records.length);
    expect([...ctx.els.myWorkRoot.querySelectorAll(".my-work-section-heading h2")].map((node) => node.textContent)).toEqual([
      "Attention",
      "Today",
      "Upcoming",
      "Waiting",
      "Later",
    ]);
  });

  it("shows useful empty messages for all five sections", () => {
    const ctx = context([taskRecord("today", { private_bucket: "today" })]);

    renderMyWork(ctx);

    expect(ctx.els.myWorkRoot.textContent).toContain("Nothing needs attention");
    expect(ctx.els.myWorkRoot.textContent).toContain("No work due in the next 14 days");
    expect(ctx.els.myWorkRoot.textContent).toContain("Nothing is on hold");
    expect(ctx.els.myWorkRoot.textContent).toContain("No other assigned work");
  });

  it("shows one filtered-empty state and moves selection to the first visible result", () => {
    const records = [
      taskRecord("alpha", { task: { task_name: "Alpha work" } }),
      taskRecord("beta", { task: { task_name: "Beta work" }, private_bucket: "today" }),
    ];
    const ctx = context(records);
    renderMyWork(ctx);

    const search = ctx.els.myWorkRoot.querySelector("[data-my-work-search]");
    search.value = "Beta";
    search.dispatchEvent(new Event("input", { bubbles: true }));

    expect(ctx.state.myWork.selectedTaskId).toBe("beta");
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-select='alpha']")).toBeNull();
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-select='beta']")).toBeTruthy();

    const filteredSearch = ctx.els.myWorkRoot.querySelector("[data-my-work-search]");
    filteredSearch.value = "no match";
    filteredSearch.dispatchEvent(new Event("input", { bubbles: true }));

    expect(ctx.els.myWorkRoot.querySelectorAll(".my-work-filter-empty")).toHaveLength(1);
    expect(ctx.els.myWorkRoot.querySelectorAll(".my-work-section")).toHaveLength(0);
  });

  it("keeps completed work hidden by default and puts it after active Later work when enabled", () => {
    const records = [
      taskRecord("closed-blocked", {
        task: {
          status: "complete",
          blocked: true,
          updated_at: "2026-07-29T14:00:00Z",
        },
        private_bucket: "today",
        needs_attention: true,
      }),
      taskRecord("active-later"),
    ];

    const defaultCtx = context(records);
    renderMyWork(defaultCtx);
    expect(defaultCtx.els.myWorkRoot.querySelector("[data-my-work-select='closed-blocked']")).toBeNull();

    const completedCtx = context(records, { showCompleted: true });
    renderMyWork(completedCtx);
    expect(sectionTaskIds(completedCtx.els.myWorkRoot, "attention")).toEqual([]);
    expect(sectionTaskIds(completedCtx.els.myWorkRoot, "today")).toEqual([]);
    expect(sectionTaskIds(completedCtx.els.myWorkRoot, "later")).toEqual(["active-later", "closed-blocked"]);
  });

  it("makes only unfiltered Today and Later cards draggable", () => {
    const records = [
      taskRecord("attention", { task: { blocked: true }, needs_attention: true }),
      taskRecord("today", { private_bucket: "today" }),
      taskRecord("upcoming", { task: { is_due_soon: true } }),
      taskRecord("later"),
    ];
    const ctx = context(records);
    renderMyWork(ctx);

    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-select='attention']").hasAttribute("draggable")).toBe(false);
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-select='upcoming']").hasAttribute("draggable")).toBe(false);
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-select='today']").getAttribute("draggable")).toBe("true");
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-select='later']").getAttribute("draggable")).toBe("true");

    const search = ctx.els.myWorkRoot.querySelector("[data-my-work-search]");
    search.value = "Task";
    search.dispatchEvent(new Event("input", { bubbles: true }));

    expect(ctx.els.myWorkRoot.querySelectorAll('[draggable="true"]')).toHaveLength(0);
  });

  it("persists cross-bucket drag order in rank increments of 100", async () => {
    const records = [
      taskRecord("today-1", { private_bucket: "today", private_sort_rank: 100 }),
      taskRecord("today-2", { private_bucket: "today", private_sort_rank: 200 }),
      taskRecord("later-1", { private_bucket: "later", private_sort_rank: 100 }),
    ];
    const ctx = context(records);
    renderMyWork(ctx);

    const source = ctx.els.myWorkRoot.querySelector("[data-my-work-select='today-2']");
    const target = ctx.els.myWorkRoot.querySelector("[data-my-work-select='later-1']");
    drag(source, target, "today-2");

    await vi.waitFor(() => {
      const movingCall = ctx.api.mock.calls.find(([path, options]) => (
        path === "/my-work/tasks/today-2/state"
        && options?.method === "PATCH"
      ));
      expect(movingCall).toBeTruthy();
      expect(JSON.parse(movingCall[1].body)).toEqual({ bucket: "later", sort_rank: 200 });
    });
    const sourceCall = ctx.api.mock.calls.find(([path, options]) => (
      path === "/my-work/tasks/today-1/state"
      && options?.method === "PATCH"
    ));
    expect(JSON.parse(sourceCall[1].body)).toEqual({ bucket: "today", sort_rank: 100 });
  });

  it("saves a timezone-aware reminder, bucket, and private note", async () => {
    const record = taskRecord("private-plan", {
      private_note: "Initial private note",
      private_reminder_at: "2026-07-29T14:00:00Z",
    });
    const records = [record];
    const ctx = context(records);
    renderMyWork(ctx);
    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-private-form]");
    form.querySelector('[name="bucket"]').value = "today";
    form.querySelector('[name="reminder_at"]').value = "2026-07-30T09:15";
    form.querySelector('[name="private_note"]').value = "Remember the edge case";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() => {
      const patchCall = ctx.api.mock.calls.find(([path, options]) => (
        path === "/my-work/tasks/private-plan/state"
        && options?.method === "PATCH"
      ));
      expect(patchCall).toBeTruthy();
      expect(JSON.parse(patchCall[1].body)).toEqual({
        bucket: "today",
        reminder_at: new Date("2026-07-30T09:15").toISOString(),
        private_note: "Remember the edge case",
      });
    });
  });

  it("uses quick private planning without overriding a derived Attention section", async () => {
    const records = [taskRecord("blocked", {
      task: { blocked: true },
      needs_attention: true,
    })];
    const ctx = context(records);
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-private-bucket='today']").click();

    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledWith(
        "/my-work/tasks/blocked/state",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ bucket: "today" }),
        }),
      );
      expect(sectionTaskIds(ctx.els.myWorkRoot, "attention")).toEqual(["blocked"]);
    });
  });
});
