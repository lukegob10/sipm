import { expect, it, vi } from "vitest";
import { bindDeliverablesTable } from "../../js/routes/master/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";
function deferred() { let resolve, reject; const promise = new Promise((res, rej) => { resolve = res; reject = rej; }); return { promise, resolve, reject }; }
function solution(id = "one") {
  const optional = ["github_repo_url", "rag_reason", "due_date", "planned_start_date", "current_phase", "description", "success_criteria", "problem_statement", "escalation", "owner", "owner_user_soeid", "assignee", "assignee_user_soeid", "approver", "approver_user_soeid", "key_stakeholder", "blockers", "risks", "impact_confidence", "rag_confidence", "completed_at", "capacity_hours"];
  return { ...Object.fromEntries(optional.map((key) => [key, null])), solution_id: id, project_id: "p", solution_name: "One", version: "1", status: "active", rag_status: "green", priority: 2, created_at: "2026-01-01", updated_at: "2026-01-01" };
}
function setup() {
  const root = document.createElement("div");
  root.innerHTML = '<select data-field="status" data-type="solution" data-id="one"><option value="active">Active</option></select><input data-field="priority" data-type="solution" data-id="one" value="2">';
  const state = { user: { user_id: "u" }, activeSpace: { space_id: "a" }, solutions: [] };
  const request = deferred();
  const ctx = { state, els: { masterTable: root }, api: vi.fn().mockReturnValue(request.promise), upsertById: vi.fn(), renderMasterTable: vi.fn(), renderDashboard: vi.fn(), renderKanban: vi.fn(), renderCalendar: vi.fn() };
  bindDeliverablesTable(ctx);
  return { ctx, root, request };
}
function change(el) { el.dispatchEvent(new Event("change", { bubbles: true })); }
it("ignores a response from a previous space", async () => {
  const { ctx, root, request } = setup();
  change(root.querySelector("select"));
  ctx.state.activeSpace = { space_id: "b" };
  request.resolve(solution());
  await Promise.resolve(); await Promise.resolve();
  expect(ctx.upsertById).not.toHaveBeenCalled();
});
it("prevents overlapping changes to one solution and explains why", async () => {
  const { ctx, root, request } = setup();
  change(root.querySelector("select"));
  change(root.querySelector("input"));
  expect(ctx.api).toHaveBeenCalledTimes(1);
  expect(root.querySelector('[role="alert"]').textContent).toMatch(/being updated/);
  request.resolve(solution());
  await vi.waitFor(() => expect(ctx.upsertById).toHaveBeenCalledOnce());
});
it("restores the table and shows a retryable error", async () => {
  const { ctx, root, request } = setup();
  change(root.querySelector("select"));
  request.reject(new Error("offline"));
  await vi.waitFor(() => expect(root.querySelector('[role="alert"]')?.textContent).toContain("offline"));
  expect(ctx.renderMasterTable).toHaveBeenCalled();
});
it("accepts a response after same-session refresh", async () => {
  const { ctx, root, request } = setup();
  registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
  change(root.querySelector("select"));
  ctx.state.user = { user_id: "u" }; ctx.state.activeSpace = { space_id: "a" };
  request.resolve(solution());
  await vi.waitFor(() => expect(ctx.upsertById).toHaveBeenCalledOnce());
});
it("allows an unrelated solution to update concurrently", async () => {
  const { ctx, root, request } = setup();
  const otherRequest = deferred();
  ctx.api.mockReturnValueOnce(request.promise).mockReturnValueOnce(otherRequest.promise);
  const other = document.createElement("input");
  other.setAttribute("data-field", "priority");
  other.setAttribute("data-type", "solution");
  other.setAttribute("data-id", "two");
  other.value = "3";
  root.append(other);
  change(root.querySelector("select"));
  change(other);
  expect(ctx.api).toHaveBeenCalledTimes(2);
  request.resolve(solution());
  otherRequest.resolve(solution("two"));
  await vi.waitFor(() => expect(ctx.upsertById).toHaveBeenCalledTimes(2));
});
it("does not display an old context failure", async () => {
  const { ctx, root, request } = setup();
  change(root.querySelector("select"));
  ctx.state.user = { user_id: "other" };
  request.reject(new Error("old space error"));
  await Promise.resolve(); await Promise.resolve();
  expect(root.querySelector('[role="alert"]')).toBeNull();
  expect(ctx.renderMasterTable).not.toHaveBeenCalled();
});
it("reconciles an ambiguous failure with the current server solution", async () => {
  const { ctx, root, request } = setup();
  const latest = solution();
  ctx.api.mockReturnValueOnce(request.promise).mockResolvedValueOnce(latest);
  change(root.querySelector("select"));
  request.reject(Object.assign(new Error("timed out"), { status: 408 }));
  await vi.waitFor(() => expect(ctx.upsertById).toHaveBeenCalledWith(ctx.state.solutions, latest, "solution_id"));
  expect(ctx.api).toHaveBeenCalledWith("/solutions/one");
  expect(root.querySelector('[role="alert"]').textContent).toMatch(/uncertain.*latest/i);
});
it("warns the result is unknown if reconciliation also fails", async () => {
  const { ctx, root, request } = setup();
  ctx.api.mockReturnValueOnce(request.promise).mockRejectedValueOnce(new Error("offline"));
  change(root.querySelector("select"));
  request.reject(Object.assign(new Error("offline"), { status: 0 }));
  await vi.waitFor(() => expect(root.querySelector('[role="alert"]')?.textContent).toMatch(/could not confirm/i));
  expect(ctx.upsertById).not.toHaveBeenCalled();
});
it("rejects an incomplete or mismatched reconciliation response", async () => {
  const { ctx, root, request } = setup();
  ctx.api.mockReturnValueOnce(request.promise).mockResolvedValueOnce({ solution_id: "other", status: "active" });
  change(root.querySelector("select"));
  request.reject(Object.assign(new Error("offline"), { status: 0 }));
  await vi.waitFor(() => expect(root.querySelector('[role="alert"]')?.textContent).toMatch(/refresh before retrying/i));
  expect(ctx.upsertById).not.toHaveBeenCalled();
});
it("ignores reconciliation after changing space", async () => {
  const { ctx, root, request } = setup();
  const refresh = deferred();
  ctx.api.mockReturnValueOnce(request.promise).mockReturnValueOnce(refresh.promise);
  change(root.querySelector("select"));
  request.reject(Object.assign(new Error("offline"), { status: 0 }));
  await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledTimes(2));
  ctx.state.activeSpace = { space_id: "new" };
  refresh.resolve({ solution_id: "one" });
  await Promise.resolve(); await Promise.resolve();
  expect(ctx.upsertById).not.toHaveBeenCalled();
  expect(root.querySelector('[role="alert"]')).toBeNull();
});
it.each([{}, { solution_id: "other" }])("reconciles an invalid successful PATCH response %o", async (invalid) => {
  const { ctx, root, request } = setup();
  const latest = solution();
  ctx.api.mockReturnValueOnce(request.promise).mockResolvedValueOnce(latest);
  change(root.querySelector("select"));
  request.resolve(invalid);
  await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/solutions/one"));
  expect(ctx.upsertById).toHaveBeenCalledOnce();
  expect(ctx.upsertById).toHaveBeenCalledWith(ctx.state.solutions, latest, "solution_id");
});
