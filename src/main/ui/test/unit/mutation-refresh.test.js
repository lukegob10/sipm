import { describe, expect, it, vi } from "vitest";
import { mutationCollections, requestWithMutationReconciliation } from "../../js/utils/mutation-refresh.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function harness() {
  const state = { user: { user_id: "u" }, activeSpace: { space_id: "s" } };
  const values = new Map();
  const store = {
    entityReadSnapshot: (entity) => values.get(entity) || { version: "0:0", pending: false },
    refreshFromServer: vi.fn(),
    invalidateRepositoryInventory: vi.fn(),
  };
  const scheduled = [];
  const pending = deferred();
  const invoke = (path = "/tasks/t1", method = "PATCH") => requestWithMutationReconciliation({
    state, path, options: { method }, request: () => pending.promise, getStore: () => store,
    schedule: (callback) => scheduled.push(callback),
  });
  return { state, values, store, scheduled, pending, invoke };
}

describe("mutation reconciliation", () => {
  it.each([
    ["/projects/p/solutions", "POST", ["solutions"]],
    ["/solutions/s/tasks", "POST", ["tasks"]],
    ["/tasks/actions/batch", "PATCH", ["tasks"]],
    ["/programs/p", "PATCH", ["programs", "projects"]],
    ["/solutions/s/documents", "POST", []],
    ["/tasks", "GET", []],
  ])("maps %s %s", (path, method, expected) => {
    expect(mutationCollections(path, method)).toEqual(expected);
  });

  it("does not add a read when no collection changed or was being read", async () => {
    const h = harness();
    const result = h.invoke();
    h.pending.resolve({ task_id: "t1" });
    expect(await result).toEqual({ task_id: "t1" });
    expect(h.scheduled).toHaveLength(1);
    h.scheduled[0]();
    expect(h.store.refreshFromServer).not.toHaveBeenCalled();
  });

  it("invalidates repository inventory after a related mutation without forcing collection reads", async () => {
    const h = harness();
    const result = h.invoke();
    h.pending.resolve({ task_id: "t1" });
    await result;
    expect(h.store.invalidateRepositoryInventory).toHaveBeenCalledTimes(1);
    expect(h.store.refreshFromServer).not.toHaveBeenCalled();
  });

  it("does not invalidate inventory after an unrelated mutation", async () => {
    const h = harness();
    const result = h.invoke("/teams/t1", "PATCH");
    h.pending.resolve({});
    await result;
    expect(h.store.invalidateRepositoryInventory).not.toHaveBeenCalled();
  });

  it("detects a read that completes while the response reaches its caller", async () => {
    const h = harness();
    const result = h.invoke();
    h.pending.resolve({});
    await result;
    h.values.set("tasks", { version: "0:1", pending: false });
    h.scheduled[0]();
    expect(h.store.refreshFromServer).toHaveBeenCalledExactlyOnceWith("tasks");
  });

  it.each(["changed", "pending-before", "pending-after"])("reconciles a %s read after the response", async (mode) => {
    const h = harness();
    if (mode === "pending-before") h.values.set("tasks", { version: "0:0", pending: true });
    const result = h.invoke();
    h.values.set("tasks", { version: mode === "changed" ? "1:0" : "0:0", pending: mode === "pending-after" });
    h.pending.resolve({ task_id: "t1" });
    await result;
    expect(h.store.refreshFromServer).not.toHaveBeenCalled();
    expect(h.scheduled).toHaveLength(1);
    h.scheduled[0]();
    expect(h.store.refreshFromServer).toHaveBeenCalledExactlyOnceWith("tasks");
  });

  it("does not refresh a replacement space or after a failed request", async () => {
    const h = harness();
    const result = h.invoke();
    h.values.set("tasks", { version: "1:0", pending: false });
    h.pending.resolve({});
    await result;
    h.state.activeSpace = { space_id: "other" };
    h.scheduled[0]();
    expect(h.store.refreshFromServer).not.toHaveBeenCalled();
    const failed = harness();
    const failure = failed.invoke();
    failed.pending.reject(new Error("failed"));
    await expect(failure).rejects.toThrow("failed");
    expect(failed.scheduled).toEqual([]);
  });

  it("does not refresh a replacement login even when the user ID matches", async () => {
    const h = harness();
    const result = h.invoke();
    h.values.set("tasks", { version: "1:0", pending: false });
    h.pending.resolve({});
    await result;
    h.state.user = { user_id: "u" };
    h.scheduled[0]();
    expect(h.store.refreshFromServer).not.toHaveBeenCalled();
  });
});
