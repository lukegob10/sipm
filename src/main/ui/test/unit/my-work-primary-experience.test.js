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
  const api = vi.fn(async (path, options = {}) => {
    if (path === "/my-work") return records;
    if (path.startsWith("/my-work/tasks/") && options.method === "PATCH") {
      const taskId = decodeURIComponent(path.split("/").at(-2));
      const record = records.find((item) => item.task.task_id === taskId);
      const payload = JSON.parse(options.body);
      return {
        task_id: taskId,
        bucket: payload.bucket ?? record.private_bucket,
        sort_rank: payload.sort_rank ?? record.private_sort_rank,
        reminder_at: Object.hasOwn(payload, "reminder_at") ? payload.reminder_at : record.private_reminder_at,
        private_note: Object.hasOwn(payload, "private_note") ? payload.private_note : record.private_note,
      };
    }
    return {};
  });
  return {
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
        detailTab: "task",
        privateNotice: null,
      },
    },
    els: { myWorkRoot: document.getElementById("my-work-root") },
    api,
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

function laneTaskIds(root, lane) {
  return [...root.querySelectorAll(`[data-my-work-lane-panel="${lane}"] [data-my-work-select]`)]
    .map((card) => card.dataset.myWorkSelect);
}

function card(root, taskId) {
  return root.querySelector(`[data-my-work-card="${taskId}"]`);
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

describe("My Work simplified planning", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    window.localStorage.clear();
  });

  it("uses only Today and Later while retaining urgency as card context", () => {
    const records = [
      taskRecord("blocked-today", {
        task: { blocked: true, urgency_score: 40 },
        private_bucket: "today",
        needs_attention: true,
      }),
      taskRecord("waiting-today", {
        task: { status: "on_hold" },
        private_bucket: "today",
      }),
      taskRecord("upcoming", { task: { is_due_soon: true, due_date: "2026-08-02" } }),
      taskRecord("later"),
    ];
    const ctx = context(records);

    renderMyWork(ctx);

    expect(laneTaskIds(ctx.els.myWorkRoot, "today")).toEqual(expect.arrayContaining([
      "blocked-today",
      "waiting-today",
    ]));
    expect(laneTaskIds(ctx.els.myWorkRoot, "later")).toEqual(expect.arrayContaining([
      "upcoming",
      "later",
    ]));
    expect(ctx.els.myWorkRoot.querySelectorAll("[data-my-work-select]")).toHaveLength(records.length);
    expect([...ctx.els.myWorkRoot.querySelectorAll(".my-work-lane-heading h2")].map((node) => node.textContent)).toEqual([
      "Today",
      "Later",
    ]);
    expect(card(ctx.els.myWorkRoot, "blocked-today").textContent).toContain("Blocked");
    expect(card(ctx.els.myWorkRoot, "upcoming").textContent).toContain("Due soon");
  });

  it("gives both lanes useful, action-oriented empty states", () => {
    const ctx = context([]);
    ctx.state.myWork.search = "anything";

    renderMyWork(ctx);

    expect(ctx.els.myWorkRoot.textContent).toContain("No work matches these filters");

    const oneTaskCtx = context([taskRecord("today", { private_bucket: "today" })]);
    renderMyWork(oneTaskCtx);
    expect(oneTaskCtx.els.myWorkRoot.textContent).toContain("No tasks are waiting for later");
  });

  it("moves selection to the first visible filtered result", () => {
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
  });

  it("keeps completed work hidden by default and stages visible closed work in Later", () => {
    const records = [
      taskRecord("closed", {
        task: { status: "complete", updated_at: "2026-07-29T14:00:00Z" },
        private_bucket: "today",
      }),
      taskRecord("active", { private_bucket: "later" }),
    ];

    const defaultCtx = context(records);
    renderMyWork(defaultCtx);
    expect(card(defaultCtx.els.myWorkRoot, "closed")).toBeNull();

    const completedCtx = context(records, { showCompleted: true });
    renderMyWork(completedCtx);
    expect(laneTaskIds(completedCtx.els.myWorkRoot, "today")).toEqual([]);
    expect(laneTaskIds(completedCtx.els.myWorkRoot, "later")).toEqual(["active", "closed"]);
    expect(card(completedCtx.els.myWorkRoot, "closed").hasAttribute("draggable")).toBe(false);
  });

  it("makes every active unfiltered task draggable regardless of urgency", () => {
    const records = [
      taskRecord("attention", { task: { blocked: true }, needs_attention: true }),
      taskRecord("today", { private_bucket: "today" }),
      taskRecord("upcoming", { task: { is_due_soon: true } }),
    ];
    const ctx = context(records);
    renderMyWork(ctx);

    records.forEach((record) => {
      expect(card(ctx.els.myWorkRoot, record.task.task_id).getAttribute("draggable")).toBe("true");
    });

    const search = ctx.els.myWorkRoot.querySelector("[data-my-work-search]");
    search.value = "Task";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    expect(ctx.els.myWorkRoot.querySelectorAll('[draggable="true"]')).toHaveLength(0);
    expect(ctx.els.myWorkRoot.querySelectorAll("[data-my-work-move]")).toHaveLength(3);
  });

  it("moves a card immediately and persists its cross-lane order", async () => {
    const records = [
      taskRecord("today-1", { private_bucket: "today", private_sort_rank: 100 }),
      taskRecord("today-2", { private_bucket: "today", private_sort_rank: 200 }),
      taskRecord("later-1", { private_bucket: "later", private_sort_rank: 100 }),
    ];
    const ctx = context(records);
    renderMyWork(ctx);

    drag(card(ctx.els.myWorkRoot, "today-2"), card(ctx.els.myWorkRoot, "later-1"), "today-2");

    expect(laneTaskIds(ctx.els.myWorkRoot, "later")).toEqual(["later-1", "today-2"]);
    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledWith(
        "/my-work/tasks/today-2/state",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ bucket: "later", sort_rank: 200 }),
        }),
      );
    });
  });

  it("separates task-attached private notes from shared task details", async () => {
    const record = taskRecord("private-note", {
      private_note: "Initial private note",
      private_reminder_at: "2026-07-29T14:00:00Z",
    });
    const ctx = context([record]);
    renderMyWork(ctx);

    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-private-form]")).toBeNull();
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();

    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-private-form]");
    expect(form).toBeTruthy();
    expect(ctx.els.myWorkRoot.textContent).toContain("They stay attached to this task");
    expect(form.querySelector('[name="bucket"]')).toBeNull();
    form.querySelector('[name="reminder_at"]').value = "2026-07-30T09:15";
    form.querySelector('[name="private_note"]').value = "Remember the edge case";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() => {
      const patchCall = ctx.api.mock.calls.find(([path, options]) => (
        path === "/my-work/tasks/private-note/state"
        && options?.method === "PATCH"
      ));
      expect(JSON.parse(patchCall[1].body)).toEqual({
        reminder_at: new Date("2026-07-30T09:15").toISOString(),
        private_note: "Remember the edge case",
      });
      expect(ctx.els.myWorkRoot.textContent).toContain("Private note saved");
    });
  });

  it("provides a working Move button even for attention tasks", async () => {
    const records = [taskRecord("blocked", {
      task: { blocked: true },
      needs_attention: true,
    })];
    const ctx = context(records);
    renderMyWork(ctx);

    ctx.els.myWorkRoot.querySelector('[data-my-work-task="blocked"][data-my-work-move="today"]').click();

    expect(laneTaskIds(ctx.els.myWorkRoot, "today")).toEqual(["blocked"]);
    expect(card(ctx.els.myWorkRoot, "blocked").textContent).toContain("Blocked");
    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledWith(
        "/my-work/tasks/blocked/state",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ bucket: "today", sort_rank: 100 }),
        }),
      );
    });
  });
});
