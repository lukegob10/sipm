import { describe, expect, it, vi } from "vitest";
import { requestCsvExport, requestCsvImport } from "../../js/utils/csv-import.js";
import { createCsvImportGate } from "../../js/utils/form-state.js";

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}
function state() {
  return { user: { user_id: "user" }, activeSpace: { space_id: "one" } };
}

describe("CSV import request context", () => {
  it("does not upload a file read under a different space", async () => {
    const current = state();
    const read = deferred();
    const fetchImpl = vi.fn();
    const result = requestCsvImport({ state: current, file: { text: () => read.promise }, kind: "tasks", apiBase: "/api", fetchImpl });
    current.activeSpace = { space_id: "two" };
    read.resolve("task_name\nOne");
    expect(await result).toEqual({ stale: true });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("ignores a response after the session changes", async () => {
    const current = state();
    const response = deferred();
    const fetchImpl = vi.fn(() => response.promise);
    const result = requestCsvImport({ state: current, file: { text: async () => "csv" }, kind: "tasks", apiBase: "/api", fetchImpl });
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    expect(fetchImpl.mock.calls[0][1].headers["X-Space-Id"]).toBe("one");
    current.user = { user_id: "user" };
    response.resolve({ status: 401, ok: false });
    expect(await result).toEqual({ stale: true });
  });

  it("ignores a decoded response when the space changes during parsing", async () => {
    const current = state();
    const body = deferred();
    const fetchImpl = vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => body.promise });
    const result = requestCsvImport({ state: current, file: { text: async () => "csv" }, kind: "tasks", apiBase: "/api", fetchImpl });
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    current.activeSpace = { space_id: "two" };
    body.resolve({ created: 1, errors: [] });
    expect(await result).toEqual({ stale: true });
  });

  it("surfaces a current-context HTTP error", async () => {
    const current = state();
    const fetchImpl = vi.fn().mockResolvedValue({ status: 403, ok: false, text: async () => "Forbidden" });
    await expect(requestCsvImport({ state: current, file: { text: async () => "csv" }, kind: "tasks", apiBase: "/api", fetchImpl }))
      .rejects.toThrow("Forbidden");
  });

  it("serializes imports per session without an old completion releasing a new request", () => {
    const gate = createCsvImportGate();
    const firstUser = {};
    const secondUser = {};
    const first = gate.begin({ userRef: firstUser });
    expect(gate.begin({ userRef: firstUser })).toBeNull();
    const second = gate.begin({ userRef: secondUser });
    gate.finish(first);
    expect(gate.begin({ userRef: secondUser })).toBeNull();
    gate.finish(second);
    expect(gate.begin({ userRef: secondUser })).not.toBeNull();
  });

  it("returns a successful result for the original context", async () => {
    const current = state();
    const fetchImpl = vi.fn().mockResolvedValue({ status: 200, ok: true, json: async () => ({ created: 1, errors: [] }) });
    await expect(requestCsvImport({ state: current, file: { text: async () => "csv" }, kind: "projects", apiBase: "/api", fetchImpl }))
      .resolves.toEqual({ data: { created: 1, errors: [] } });
  });
});

describe("CSV export request context", () => {
  it("discards a response body after the active space changes", async () => {
    const current = state();
    const body = deferred();
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200, blob: () => body.promise });
    const result = requestCsvExport({ state: current, kind: "projects", apiBase: "/api", fetchImpl });
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    expect(fetchImpl.mock.calls[0][1].headers["X-Space-Id"]).toBe("one");
    current.activeSpace = { space_id: "two" };
    body.resolve(new Blob(["private"]));
    expect(await result).toEqual({ stale: true });
  });

  it("returns a CSV blob in the originating session", async () => {
    const blob = new Blob(["project_name\nExample"], { type: "text/csv" });
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200, blob: async () => blob });
    await expect(requestCsvExport({ state: state(), kind: "projects", apiBase: "/api", fetchImpl })).resolves.toEqual({ blob });
  });
});
