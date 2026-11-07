import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderMyWork } from "../../js/routes/my-work.js";
import { createDataStoreController } from "../../js/shell/data-store.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";
import { invalidateMyWorkRecords } from "../../js/utils/my-work-state.js";

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
    window.localStorage.clear();
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

    expect(ctx.els.myWorkRoot.textContent).toContain("Plan");
    expect([...ctx.els.myWorkRoot.querySelectorAll(".my-work-lane-heading h2")].map((node) => node.textContent)).toEqual([
      "Today",
      "Later",
    ]);
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

  it("does not restore a deleted task from a read started before invalidation", async () => {
    const ctx = context([]);
    ctx.state.myWork.records = null;
    let resolveOldRead;
    let resolveNewRead;
    ctx.api
      .mockReturnValueOnce(new Promise((resolve) => { resolveOldRead = resolve; }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveNewRead = resolve; }));

    renderMyWork(ctx);
    expect(ctx.api).toHaveBeenCalledTimes(1);
    invalidateMyWorkRecords(ctx.state);
    renderMyWork(ctx);
    expect(ctx.api).toHaveBeenCalledTimes(2);

    resolveNewRead([]);
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));
    resolveOldRead([{
      task: { task_id: "deleted-task", task_name: "Deleted task", status: "to_do" },
    }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(ctx.state.myWork.records).toEqual([]);
    expect(ctx.els.myWorkRoot.textContent).toContain("You are clear");
    expect(ctx.els.myWorkRoot.textContent).not.toContain("Deleted task");
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

    const card = ctx.els.myWorkRoot.querySelector("[data-my-work-card='task-1']");
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

  it("keeps shared task actions usable across a same-session refresh", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    let finish;
    ctx.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderMyWork(ctx);
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]').click();
    expect(ctx.api).toHaveBeenCalledOnce();
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    finish({ ...records[0].task, status: "in_progress" });
    await vi.waitFor(() => expect(ctx.state.myWork.sharedActions.pendingTaskId).toBe(""));
    expect(records[0].task.status).toBe("in_progress");
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="complete"]').disabled).toBe(false);
  });

  it("completes a private note save after a same-session refresh", async () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }]);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    let finish;
    ctx.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "saved note";
    ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    finish({ private_note: "saved note", reminder_at: null, bucket: "today", sort_rank: 100 });
    await vi.waitFor(() => expect(ctx.state.myWork.savingPrivateTaskId).toBe(""));
    expect(ctx.state.myWork.records[0].private_note).toBe("saved note");
    expect(ctx.els.myWorkRoot.textContent).toContain("Private note saved.");
  });

  it("preserves a draft across refresh but not across a new session or space lifetime", () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }]);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(ctx.state, () => lifetime);
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "draft";
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("draft");
    lifetime.session += 1;
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("");
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "new draft";
    lifetime.space += 1;
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("");
  });

  it.each(["task", "note"])("keeps a %s draft during same-space data recovery", async (kind) => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    ctx.api.mockResolvedValue(records);
    renderMyWork(ctx);
    if (kind === "task") ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    else ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    const selector = kind === "task" ? '[name="description"]' : '[name="private_note"]';
    ctx.els.myWorkRoot.querySelector(selector).value = "unsaved draft";
    const store = createDataStoreController({ state: ctx.state, els: ctx.els });
    store.clearDataState({ preserveEditors: true });
    renderMyWork(ctx);
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/my-work"));
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));
    expect(ctx.els.myWorkRoot.querySelector(selector)?.value).toBe("unsaved draft");
  });

  it("discards a read started before same-space recovery", async () => {
    const ctx = context([]);
    ctx.state.myWork.records = null;
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    let finishOld;
    let finishNew;
    ctx.api.mockReturnValueOnce(new Promise((resolve) => { finishOld = resolve; }))
      .mockReturnValueOnce(new Promise((resolve) => { finishNew = resolve; }));
    renderMyWork(ctx);
    const store = createDataStoreController({ state: ctx.state, els: ctx.els });
    store.clearDataState({ preserveEditors: true });
    renderMyWork(ctx);
    finishOld([{ task: { task_id: "old", task_name: "Stale", status: "to_do" } }]);
    await Promise.resolve();
    expect(ctx.state.myWork.records).toBeNull();
    finishNew([{ task: { task_id: "new", task_name: "Current", status: "to_do" } }]);
    await vi.waitFor(() => expect(ctx.state.myWork.records[0].task.task_id).toBe("new"));
  });

  it("waits for a pending note save before same-space recovery reload", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    let finish;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve(records)
      : new Promise((resolve) => { finish = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "saved note";
    ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    const store = createDataStoreController({ state: ctx.state, els: ctx.els });
    store.clearDataState({ preserveEditors: true });
    renderMyWork(ctx);
    expect(ctx.api).toHaveBeenCalledTimes(1);
    finish({ private_note: "saved note", reminder_at: null, bucket: "today", sort_rank: 100 });
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/my-work"));
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));
    expect(ctx.state.myWork.records[0].private_note).toBe("saved note");
    expect(ctx.state.myWork.savingPrivateTaskId).toBe("");
  });

  it("clears a private draft and pending save on an actual context reset", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "user-1" };
    ctx.state.activeSpace = { space_id: "space-1" };
    let finishOld;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve(records)
      : new Promise((resolve) => { finishOld = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "old private note";
    ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    const store = createDataStoreController({ state: ctx.state, els: ctx.els });
    store.clearDataState();
    ctx.state.user = { user_id: "new-user" };
    renderMyWork(ctx);
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));
    finishOld({ private_note: "old private note", reminder_at: null });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.state.myWork.savingPrivateTaskId).toBe("");
    expect(ctx.els.myWorkRoot.textContent).not.toContain("old private note");
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]')).toBeNull();
  });

  it("preserves task and note drafts when the view rerenders", () => {
    const ctx = context([{ task: { task_id: "task-1", task_name: "First", status: "to_do", priority: 1 } }]);
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit]").click();
    const description = ctx.els.myWorkRoot.querySelector('[name="description"]');
    description.value = "draft task";
    description.focus();
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="description"]').value).toBe("draft task");
    expect(document.activeElement).toBe(ctx.els.myWorkRoot.querySelector('[name="description"]'));
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit-cancel]").click();
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "draft note";
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("draft note");
    ctx.state.user = { user_id: "another-user" };
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("");
  });

  it("does not carry a note draft to another task or space", () => {
    const ctx = context([
      { task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } },
      { task: { task_id: "two", task_name: "Two", status: "to_do", priority: 1 }, private_note: "saved two" },
    ]);
    ctx.state.activeSpace = { space_id: "one" };
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "private draft";
    ctx.state.myWork.selectedTaskId = "two";
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("saved two");
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "other draft";
    ctx.state.activeSpace = { space_id: "two" };
    renderMyWork(ctx);
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("saved two");
  });

  it("keeps edits made while a private note is saving and blocks duplicate submits", async () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }]);
    let resolveSave;
    ctx.api.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    const form = ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]');
    const note = form.querySelector('[name="private_note"]');
    note.value = "first version";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(ctx.api).toHaveBeenCalledTimes(1);
    note.value = "newer version";
    resolveSave({ private_note: "first version", reminder_at: null, bucket: "today", sort_rank: 100 });
    await vi.waitFor(() => expect(ctx.state.myWork.records[0].private_note).toBe("first version"));
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("newer version");
    expect(ctx.els.myWorkRoot.textContent).toContain("Newer edits are not saved.");
  });

  it("ignores a note save response after the session changes", async () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }]);
    ctx.state.user = { user_id: "old" };
    let resolveSave;
    ctx.api.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    ctx.state.user = { user_id: "new" };
    ctx.state.myWork.records = [{ task: { task_id: "one", task_name: "New session", status: "to_do", priority: 1 }, private_note: "new session note" }];
    resolveSave({ private_note: "old session note", reminder_at: null });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.state.myWork.records[0].private_note).toBe("new session note");
    expect(ctx.state.myWork.privateNotice).toBeNull();
  });

  it("keeps a different task's draft when an earlier save completes", async () => {
    const ctx = context([
      { task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } },
      { task: { task_id: "two", task_name: "Two", status: "to_do", priority: 1 } },
    ]);
    let resolveSave;
    ctx.api.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    ctx.state.myWork.selectedTaskId = "two";
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "other task draft";
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-private-form] button[type="submit"]').disabled).toBe(true);
    resolveSave({ private_note: null, reminder_at: null, bucket: "today", sort_rank: 100 });
    await vi.waitFor(() => expect(ctx.state.myWork.savingPrivateTaskId).toBe(""));
    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("other task draft");
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-private-form] button[type="submit"]').disabled).toBe(false);
  });

  it("allows retry after a private note save fails", async () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }]);
    ctx.api.mockRejectedValueOnce(new Error("Save failed"));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
    const form = ctx.els.myWorkRoot.querySelector('[data-my-work-private-form]');
    form.querySelector('[name="private_note"]').value = "keep me";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(form.textContent).toContain("Save failed"));
    expect(form.querySelector('[name="private_note"]').value).toBe("keep me");
    expect(form.querySelector('button[type="submit"]').disabled).toBe(false);
  });

  it("ignores a shared task save response after a session change", async () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }]);
    ctx.state.user = { user_id: "old" };
    let resolveSave;
    ctx.api.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    ctx.state.user = { user_id: "new" };
    ctx.state.myWork.records = [{ task: { task_id: "new", task_name: "New", status: "to_do", priority: 1 } }];
    ctx.state.myWork.editingTaskId = "new";
    resolveSave({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.state.myWork.records[0].task.task_id).toBe("new");
    expect(ctx.state.myWork.editingTaskId).toBe("new");
    expect(ctx.api).toHaveBeenCalledTimes(1);
  });

  it("preserves another task's edit while a shared task save finishes", async () => {
    const records = [
      { task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } },
      { task: { task_id: "two", task_name: "Two", status: "to_do", priority: 1 } },
    ];
    const ctx = context(records);
    let resolveSave;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve(records) : new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    const firstForm = ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]');
    firstForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    firstForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(ctx.api).toHaveBeenCalledTimes(1);
    ctx.state.myWork.selectedTaskId = "two";
    ctx.state.myWork.editingTaskId = "two";
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[name="description"]').value = "second draft";
    resolveSave({});
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/my-work"));
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));
    expect(ctx.state.myWork.editingTaskId).toBe("two");
    expect(ctx.els.myWorkRoot.querySelector('[name="description"]').value).toBe("second draft");
  });

  it("keeps later edits to the saved task after its refresh", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    let resolveSave;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve(records) : new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    const form = ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]');
    form.querySelector('[name="description"]').value = "submitted";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.querySelector('[name="description"]').value = "newer draft";
    resolveSave({});
    await vi.waitFor(() => expect(ctx.els.myWorkRoot.textContent).toContain("Newer edits are not saved."));
    expect(ctx.els.myWorkRoot.querySelector('[name="description"]').value).toBe("newer draft");
  });

  it("closes a submitted edit while the saved task is refreshing", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    let resolveSave;
    let resolveRefresh;
    ctx.api.mockImplementation((path) => path === "/my-work"
      ? new Promise((resolve) => { resolveRefresh = resolve; })
      : new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    resolveSave({});
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/my-work"));
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]')).toBeNull();
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]').disabled).toBe(true);
    resolveRefresh(records);
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));
  });

  it("retains an edit if refreshing after a successful save fails", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    let resolveSave;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.reject(new Error("Refresh failed")) : new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    const form = ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]');
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.querySelector('[name="description"]').value = "newer draft";
    resolveSave({});
    await vi.waitFor(() => expect(ctx.els.myWorkRoot.textContent).toContain("Refresh failed"));
    expect(ctx.els.myWorkRoot.querySelector('[name="description"]').value).toBe("newer draft");
  });

  it("waits for every reorder write before reconciling a partial failure", async () => {
    const records = [
      { task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 }, private_bucket: "today", private_sort_rank: 100 },
      { task: { task_id: "two", task_name: "Two", status: "to_do", priority: 1 }, private_bucket: "later", private_sort_rank: 0 },
    ];
    const ctx = context(records);
    let finishSecond;
    const second = new Promise((resolve) => { finishSecond = resolve; });
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve(records)
      : path.includes("/two/") ? Promise.reject(new Error("write failed")) : second);
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-move][data-my-work-task="one"]').click();
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledTimes(2));
    expect(ctx.els.myWorkRoot.querySelectorAll('[data-my-work-move]:not(:disabled)')).toHaveLength(0);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.api.mock.calls.some(([path]) => path === "/my-work")).toBe(false);
    finishSecond({});
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/my-work"));
    expect(ctx.state.myWork.error).toContain("write failed");
  });

  it("does not apply an old reorder result after a session change", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 }, private_bucket: "today" }];
    const ctx = context(records);
    ctx.state.user = { user_id: "old" };
    let finish;
    ctx.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-move][data-my-work-task="one"]').click();
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledTimes(1));
    ctx.state.user = { user_id: "new" };
    ctx.state.myWork.records = [{ task: { task_id: "new", task_name: "New", status: "to_do", priority: 1 } }];
    ctx.state.myWork.savingPrivateTaskId = "new-request";
    finish({});
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.state.myWork.records[0].task.task_id).toBe("new");
    expect(ctx.state.myWork.savingPrivateTaskId).toBe("new-request");
    expect(ctx.api).toHaveBeenCalledTimes(1);
  });

  it("does not dispatch queued lane writes after the session changes", async () => {
    const ctx = context([{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 }, private_bucket: "today" }]);
    ctx.state.user = { user_id: "old" };
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-move][data-my-work-task="one"]').click();
    ctx.state.user = { user_id: "new" };
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.api).not.toHaveBeenCalled();
  });

  it("retains the best known lane state when reconciliation fails", async () => {
    const records = [
      { task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 }, private_bucket: "today", private_sort_rank: 100 },
      { task: { task_id: "two", task_name: "Two", status: "to_do", priority: 1 }, private_bucket: "later", private_sort_rank: 0 },
    ];
    const ctx = context(records);
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.reject(new Error("refresh failed"))
      : path.includes("/two/") ? Promise.reject(new Error("write failed")) : Promise.resolve({}));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-move][data-my-work-task="one"]').click();
    await vi.waitFor(() => expect(ctx.state.myWork.error).toContain("may be out of date"));
    expect(ctx.state.myWork.records).toHaveLength(2);
    expect(records[0].private_bucket).toBe("later");
    expect(records[1].private_sort_rank).toBe(0);
  });

  it("waits for a shared action before opening the task editor", async () => {
    const records = [{ task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } }];
    const ctx = context(records);
    let finish;
    ctx.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]').click();
    const edit = ctx.els.myWorkRoot.querySelector('[data-my-work-edit]');
    expect(edit.disabled).toBe(true);
    edit.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]')).toBeNull();
    finish({ ...records[0].task, status: "in_progress" });
    await vi.waitFor(() => expect(ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').disabled).toBe(false));
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    expect(ctx.els.myWorkRoot.querySelector('[name="status"]').value).toBe("in_progress");
  });

  it("blocks shared actions while another task edit is saving", async () => {
    const records = [
      { task: { task_id: "one", task_name: "One", status: "to_do", priority: 1 } },
      { task: { task_id: "two", task_name: "Two", status: "to_do", priority: 1 } },
    ];
    const ctx = context(records);
    let finish;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve(records) : new Promise((resolve) => { finish = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit]').click();
    ctx.els.myWorkRoot.querySelector('[data-my-work-edit-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    ctx.els.myWorkRoot.querySelector('[data-my-work-select="two"]').click();
    const start = ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]');
    expect(start.disabled).toBe(true);
    start.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(ctx.api).toHaveBeenCalledTimes(1);
    finish({});
    await vi.waitFor(() => expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]').disabled).toBe(false));
  });

  it("sends only changed task fields, preserving concurrent updates to untouched fields", () => {
    const records = [{ task: { task_id: "task-1", task_name: "Original", status: "to_do", priority: 3, description: "Old" } }];
    const ctx = context(records);
    ctx.api.mockReturnValue(new Promise(() => {}));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit]").click();
    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-edit-form]");
    form.querySelector('[name="description"]').value = "Changed";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(JSON.parse(ctx.api.mock.calls[0][1].body)).toEqual({ description: "Changed" });
  });

  it("sends grouped assignment and blocker clears", () => {
    const records = [{ task: { task_id: "task-1", task_name: "One", status: "to_do", priority: 3, assignee: "Developer One", assignee_user_soeid: "dev1", blocked: true, blocker_note: "Blocked" } }];
    const ctx = context(records);
    ctx.api.mockReturnValue(new Promise(() => {}));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit]").click();
    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-edit-form]");
    const assignee = form.querySelector('[name="assignee"]');
    assignee.value = "";
    assignee.dispatchEvent(new Event("change"));
    form.querySelector('[name="blocked"]').checked = false;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(JSON.parse(ctx.api.mock.calls[0][1].body)).toEqual({ assignee: null, assignee_user_soeid: null, blocked: false, blocker_note: null });
  });

  it("retains an edit back to the previous baseline while saving", async () => {
    const records = [{ task: { task_id: "task-1", task_name: "One", status: "to_do", priority: 3, description: "Old" } }];
    const ctx = context(records);
    let resolveSave;
    ctx.api.mockImplementation((path) => path === "/my-work" ? Promise.resolve([{ task: { ...records[0].task, description: "Submitted" } }]) : new Promise((resolve) => { resolveSave = resolve; }));
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-edit]").click();
    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-edit-form]");
    const description = form.querySelector('[name="description"]');
    description.value = "Submitted";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    description.value = "Old";
    resolveSave({});
    await vi.waitFor(() => expect(ctx.els.myWorkRoot.querySelector('[name="description"]')?.value).toBe("Old"));
    await vi.waitFor(() => expect(ctx.els.myWorkRoot.textContent).toContain("Newer edits are not saved"));
  });

  it("saves changed shared Task fields from My Work with canonical FTE conversions", async () => {
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
    const source = ctx.els.myWorkRoot.querySelector("[data-my-work-card='task-now']");
    const target = ctx.els.myWorkRoot.querySelector("[data-my-work-drop-zone='later']");
    const targetCard = ctx.els.myWorkRoot.querySelector("[data-my-work-card='task-next']");
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
