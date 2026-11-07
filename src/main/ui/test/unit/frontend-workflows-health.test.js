import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderMyWork } from "../../js/routes/my-work.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function record() {
  return {
    task: { task_id: "one", task_name: "Current task", status: "to_do", priority: 1 },
    private_bucket: "later",
    private_sort_rank: 100,
    private_note: "Original note",
    private_reminder_at: null,
    reminder_due: false,
    needs_attention: false,
  };
}

function harness() {
  document.body.innerHTML = '<div id="my-work-root"></div>';
  const ctx = {
    state: {
      authed: true,
      user: { user_id: "user-one" },
      activeSpace: { space_id: "space-one" },
      users: [],
      myWork: {
        records: [record()], loading: false, error: "", selectedTaskId: "one",
        search: "", repository: "",
      },
    },
    els: { myWorkRoot: document.getElementById("my-work-root") },
    escapeHtml: (value) => String(value ?? ""),
    formatStatus: (value) => String(value),
    api: vi.fn(),
  };
  return ctx;
}

function prepareMutation(ctx, kind) {
  renderMyWork(ctx);
  if (kind === "note") ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
}

function startMutation(ctx, kind) {
  const root = ctx.els.myWorkRoot;
  if (kind === "note") {
    root.querySelector('[name="private_note"]').value = "Saved note";
    root.querySelector("[data-my-work-private-form]").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  } else if (kind === "order") {
    root.querySelector('[data-my-work-move="today"]').click();
  } else {
    root.querySelector('[data-my-work-action="start"]').click();
  }
}

function savedRecord(kind) {
  const saved = record();
  if (kind === "note") saved.private_note = "Saved note";
  if (kind === "order") saved.private_bucket = "today";
  if (kind === "task") saved.task.status = "in_progress";
  return saved;
}

function writeResponse(kind, saved) {
  return kind === "task" ? saved.task : {
    task_id: "one", bucket: saved.private_bucket, sort_rank: saved.private_sort_rank,
    private_note: saved.private_note, reminder_at: null,
  };
}

describe("My Work refresh and write ordering", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it.each(["note", "order", "task"])("keeps a successful %s update when an older read finishes afterward", async (kind) => {
    const ctx = harness();
    const oldRead = deferred();
    const write = deferred();
    const saved = savedRecord(kind);
    let reads = 0;
    ctx.api.mockImplementation((path) => path === "/my-work"
      ? (++reads === 1 ? oldRead.promise : Promise.resolve([saved]))
      : write.promise);
    prepareMutation(ctx, kind);
    ctx.state.myWork.needsRefresh = true;
    renderMyWork(ctx);
    expect(reads).toBe(1);

    startMutation(ctx, kind);
    await vi.waitFor(() => expect(ctx.api.mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(true));
    write.resolve(writeResponse(kind, saved));
    await vi.waitFor(() => {
      expect(ctx.state.myWork.savingPrivateTaskId || ctx.state.myWork.sharedActions?.pendingTaskId || "").toBe("");
      expect(ctx.state.myWork.records).toEqual([saved]);
    });

    const stale = record();
    stale.task.task_name = "Stale task";
    oldRead.resolve([stale]);
    await Promise.resolve();
    await Promise.resolve();

    expect(ctx.state.myWork.records).toEqual([saved]);
    expect(ctx.els.myWorkRoot.textContent).not.toContain("Stale task");
    expect(reads).toBe(2);
  });

  it.each(["note", "order", "task"])("discards an older read while the %s update is still pending", async (kind) => {
    const ctx = harness();
    const oldRead = deferred();
    const write = deferred();
    const saved = savedRecord(kind);
    let reads = 0;
    ctx.api.mockImplementation((path) => path === "/my-work"
      ? (++reads === 1 ? oldRead.promise : Promise.resolve([saved]))
      : write.promise);
    prepareMutation(ctx, kind);
    ctx.state.myWork.needsRefresh = true;
    renderMyWork(ctx);
    startMutation(ctx, kind);
    await vi.waitFor(() => expect(ctx.api.mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(true));

    const stale = record();
    stale.task.task_name = "Stale task";
    oldRead.resolve([stale]);
    await Promise.resolve();
    await Promise.resolve();
    expect(ctx.state.myWork.records[0].task.task_name).toBe("Current task");
    expect(reads).toBe(1);

    write.resolve(writeResponse(kind, saved));
    await vi.waitFor(() => {
      expect(ctx.state.myWork.records).toEqual([saved]);
      expect(reads).toBe(2);
    });
  });

  it.each(["note", "order", "task"])("avoids another read for a %s update without a background refresh", async (kind) => {
    const ctx = harness();
    const saved = savedRecord(kind);
    ctx.api.mockResolvedValue(writeResponse(kind, saved));
    prepareMutation(ctx, kind);
    startMutation(ctx, kind);
    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledOnce();
      expect(ctx.state.myWork.savingPrivateTaskId || ctx.state.myWork.sharedActions?.pendingTaskId || "").toBe("");
    });
    expect(ctx.api.mock.calls[0][1].method).toBe("PATCH");
    expect(ctx.state.myWork.records).toEqual([saved]);
  });

  it.each(["note", "order"])("retains a newer private draft through the %s replacement refresh", async (kind) => {
    const ctx = harness();
    const oldRead = deferred();
    const freshRead = deferred();
    const write = deferred();
    const saved = savedRecord(kind);
    let reads = 0;
    ctx.api.mockImplementation((path) => path === "/my-work"
      ? (++reads === 1 ? oldRead.promise : freshRead.promise)
      : write.promise);
    prepareMutation(ctx, "note");
    ctx.state.myWork.needsRefresh = true;
    renderMyWork(ctx);
    startMutation(ctx, kind);
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "Newer private draft";
    await vi.waitFor(() => expect(ctx.api.mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(true));
    write.resolve(writeResponse(kind, saved));
    await vi.waitFor(() => expect(reads).toBe(2));

    oldRead.resolve([record()]);
    freshRead.resolve([saved]);
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));

    expect(ctx.els.myWorkRoot.querySelector('[name="private_note"]').value).toBe("Newer private draft");
    expect(ctx.state.myWork.records).toEqual([saved]);
  });

  it("uses the lane failure reconciliation as the replacement refresh", async () => {
    const ctx = harness();
    const oldRead = deferred();
    const write = deferred();
    let reads = 0;
    ctx.api.mockImplementation((path) => path === "/my-work"
      ? (++reads === 1 ? oldRead.promise : Promise.resolve([record()]))
      : write.promise);
    prepareMutation(ctx, "order");
    ctx.state.myWork.needsRefresh = true;
    renderMyWork(ctx);
    startMutation(ctx, "order");
    await vi.waitFor(() => expect(ctx.api.mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(true));

    write.reject(new Error("Write failed"));
    await vi.waitFor(() => expect(ctx.state.myWork.savingPrivateTaskId).toBe(""));
    oldRead.resolve([{ ...record(), private_bucket: "today" }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(ctx.state.myWork.records).toEqual([record()]);
    expect(ctx.state.myWork.error).toBe("Write failed");
    expect(reads).toBe(2);
  });

  it.each([
    ["same task", "succeeds"], ["same task", "fails"],
    ["another task", "succeeds"], ["another task", "fails"],
  ])("refreshes after a rejected note save when viewing %s and the replacement %s", async (selection, outcome) => {
    const ctx = harness();
    const other = record();
    other.task = { ...other.task, task_id: "two", task_name: "Other task" };
    ctx.state.myWork.records.push(other);
    const oldRead = deferred();
    const freshRead = deferred();
    const write = deferred();
    let reads = 0;
    ctx.api.mockImplementation((path) => path === "/my-work"
      ? (++reads === 1 ? oldRead.promise : freshRead.promise)
      : write.promise);
    prepareMutation(ctx, "note");
    ctx.state.myWork.needsRefresh = true;
    renderMyWork(ctx);
    startMutation(ctx, "note");
    ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "Newer private draft";
    if (selection === "another task") {
      ctx.els.myWorkRoot.querySelector('[data-my-work-select="two"]').click();
      ctx.els.myWorkRoot.querySelector('[data-my-work-detail-tab="notes"]').click();
      ctx.els.myWorkRoot.querySelector('[name="private_note"]').value = "Other private draft";
    }

    write.reject(new Error("Write failed"));
    await vi.waitFor(() => expect(reads).toBe(2));
    const refreshed = record();
    refreshed.task.task_name = "Refreshed task";
    oldRead.resolve([{ ...record(), private_note: "Stale note" }, other]);
    if (outcome === "succeeds") freshRead.resolve([refreshed, other]);
    else freshRead.reject(new Error("Reload failed"));
    await vi.waitFor(() => expect(ctx.state.myWork.loading).toBe(false));

    const root = ctx.els.myWorkRoot;
    expect(root.querySelector('[name="private_note"]').value).toBe(
      selection === "same task" ? "Newer private draft" : "Other private draft",
    );
    expect(root.querySelector('[data-my-work-private-feedback]').textContent).toBe(
      selection === "same task" ? "Write failed" : "",
    );
    expect(root.textContent).toContain("Write failed");
    expect(ctx.state.myWork.records[0].private_note).toBe("Original note");
    expect(ctx.state.myWork.records[0].task.task_name).toBe(outcome === "succeeds" ? "Refreshed task" : "Current task");
    if (outcome === "fails") expect(root.textContent).toContain("Reload failed");
    expect(ctx.state.myWork.savingPrivateTaskId).toBe("");
    expect(ctx.state.myWork.privateSaveRequest).toBeNull();
    expect(reads).toBe(2);
  });
});
