import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { Linter } from "eslint";
import { expect, it, vi } from "vitest";

function createActivityRenderer(api) {
  const source = readFileSync(resolve("src/main/ui/js/app.js"), "utf8");
  let activitySource;
  const diagnostics = new Linter().verify(source, [{
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    plugins: { extract: { rules: { activity: { create: () => ({
      FunctionDeclaration(node) {
        if (node.id.name === "renderSolutionActivity") activitySource = source.slice(...node.range);
      },
    }) } } } },
    rules: { "extract/activity": "error" },
  }]);
  expect(diagnostics).toEqual([]);
  expect(activitySource).toBeTruthy();

  const field = { value: "solution/one" };
  const els = { solutionActivity: { innerHTML: "" } };
  els.solutionForm = { querySelector: () => field };
  els.solutionModal = { classList: { contains: () => false } };
  const state = { user: { user_id: "user" }, activeSpace: { space_id: "space" } };
  const render = runInNewContext(`(${activitySource})`, {
    api, els, renderSolutionActivityItems: () => "<p>Activity</p>",
    state, solutionActivityRequestId: 0,
    captureEntityMutationContext: () => ({ spaceId: state.activeSpace.space_id }),
    isEntityMutationContextCurrent: (_state, context) => state.activeSpace.space_id === context.spaceId,
  });
  return { render, els, field, state };
}

it("loads the selected solution's scoped activity", async () => {
  const api = vi.fn().mockResolvedValue([{ action: "update" }]);
  const { render, els } = createActivityRenderer(api);
  await render("solution/one");
  expect(api).toHaveBeenCalledWith("/solutions/solution%2Fone/activity");
  expect(els.solutionActivity.innerHTML).toBe("<p>Activity</p>");
});

it("ignores an older request when a different solution is selected", async () => {
  let finishOld;
  const api = vi.fn()
    .mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }))
    .mockResolvedValueOnce([]);
  const { render, els, field } = createActivityRenderer(api);
  field.value = "old";
  const oldRequest = render("old");
  field.value = "new";
  await render("new");
  expect(els.solutionActivity.innerHTML).toContain("No activity yet");
  finishOld([{ action: "update" }]);
  await oldRequest;
  expect(els.solutionActivity.innerHTML).toContain("No activity yet");
});

it("ignores older failures for the same solution", async () => {
  let failOld;
  const api = vi.fn()
    .mockImplementationOnce(() => new Promise((_resolve, reject) => { failOld = reject; }))
    .mockResolvedValueOnce([]);
  const { render, els } = createActivityRenderer(api);
  const oldRequest = render("solution/one");
  await render("solution/one");
  failOld(new Error("old request failed"));
  await oldRequest;
  expect(els.solutionActivity.innerHTML).toContain("No activity yet");
});

it("ignores a response after the active space changes", async () => {
  let finish;
  const api = vi.fn().mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const { render, els, state } = createActivityRenderer(api);
  const request = render("solution/one");
  state.activeSpace = { space_id: "other" };
  els.solutionActivity.innerHTML = "New space";
  finish([{ action: "update" }]);
  await request;
  expect(els.solutionActivity.innerHTML).toBe("New space");
});
