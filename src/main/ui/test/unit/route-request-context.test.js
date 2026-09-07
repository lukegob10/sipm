import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderMyWork } from "../../js/routes/my-work.js";
import { renderRepositories } from "../../js/routes/repositories.js";
import { createDataStoreController } from "../../js/shell/data-store.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const routes = [
  {
    name: "My Work",
    stateKey: "myWork",
    rootKey: "myWorkRoot",
    path: "/my-work",
    render: renderMyWork,
    record: (name) => ({ task: { task_id: name, task_name: name, status: "to_do" } }),
  },
  {
    name: "Repositories",
    stateKey: "repositoryInventory",
    rootKey: "repositoryInventoryRoot",
    path: "/repository-inventory",
    render: renderRepositories,
    record: (name) => ({ repository_name: name, github_repo_url: `https://github.com/example/${name}` }),
  },
];

function harness(route) {
  document.body.innerHTML = '<div id="route-root"></div>';
  const root = document.getElementById("route-root");
  const state = {
    authed: true,
    user: { user_id: "user-a" },
    activeSpace: { space_id: "space-a" },
    users: [],
  };
  const ctx = {
    state,
    els: { [route.rootKey]: root },
    api: vi.fn(),
    escapeHtml: (value) => String(value ?? ""),
    formatStatus: (value) => String(value ?? ""),
    renderExternalRepoLink: (_url, options) => options.label,
  };
  const { clearDataState } = createDataStoreController({ state, els: {} });
  return { ctx, root, clearDataState };
}

async function settle(request, outcome, records) {
  if (outcome === "success") request.resolve(records);
  else request.reject(new Error("Old request failed"));
  await request.promise.catch(() => {});
}

describe.each(routes)("$name route request context", (route) => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("keeps one request pending and renders its successful result", async () => {
    const { ctx, root } = harness(route);
    const request = deferred();
    ctx.api.mockReturnValue(request.promise);

    route.render(ctx);
    const pendingMarkup = root.innerHTML;
    route.render(ctx);

    expect(ctx.api).toHaveBeenCalledExactlyOnceWith(route.path);
    expect(ctx.state[route.stateKey].loading).toBe(true);
    expect(root.querySelector(".spinner")).toBeTruthy();
    expect(root.innerHTML).toBe(pendingMarkup);

    await settle(request, "success", [route.record("Current result")]);
    expect(ctx.state[route.stateKey].loading).toBe(false);
    expect(root.textContent).toContain("Current result");
    expect(root.querySelector(".spinner")).toBeNull();
  });

  it("renders a failure from the current request and clears pending state", async () => {
    const { ctx, root } = harness(route);
    const request = deferred();
    ctx.api.mockReturnValue(request.promise);
    route.render(ctx);

    await settle(request, "failure");

    expect(ctx.state[route.stateKey].loading).toBe(false);
    expect(ctx.state[route.stateKey].records).toEqual([]);
    expect(root.textContent).toContain("Old request failed");
  });

  it.each([
    ["success", "space-b"],
    ["failure", "space-b"],
    ["success", "space-a"],
    ["failure", "space-a"],
  ])("ignores superseded %s while replacement data for %s is pending", async (outcome, spaceId) => {
    const { ctx, root, clearDataState } = harness(route);
    const oldRequest = deferred();
    const newRequest = deferred();
    ctx.api.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    route.render(ctx);

    ctx.state.activeSpace = { space_id: spaceId };
    clearDataState();
    route.render(ctx);
    const pendingMarkup = root.innerHTML;

    await settle(oldRequest, outcome, [route.record("Old space result")]);

    expect(ctx.state[route.stateKey].records).toBeNull();
    expect(ctx.state[route.stateKey].loading).toBe(true);
    expect(ctx.state[route.stateKey].error).toBe("");
    expect(root.innerHTML).toBe(pendingMarkup);

    await settle(newRequest, "success", [route.record("New space result")]);
    expect(root.textContent).toContain("New space result");
    expect(root.textContent).not.toContain("Old space result");
    expect(ctx.api).toHaveBeenCalledTimes(2);
  });

  it.each(["success", "failure"])("ignores older same-context reload %s after the replacement has rendered", async (outcome) => {
    const { ctx, root, clearDataState } = harness(route);
    const oldRequest = deferred();
    const newRequest = deferred();
    ctx.api.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    route.render(ctx);

    clearDataState();
    route.render(ctx);
    const currentRecords = [route.record("Current result")];
    await settle(newRequest, "success", currentRecords);
    const search = root.querySelector('input[type="search"]');
    search.focus();
    const currentMarkup = root.innerHTML;

    await settle(oldRequest, outcome, [route.record("Old result")]);

    expect(ctx.state[route.stateKey].records).toBe(currentRecords);
    expect(ctx.state[route.stateKey].loading).toBe(false);
    expect(ctx.state[route.stateKey].error).toBe("");
    expect(root.innerHTML).toBe(currentMarkup);
    expect(document.activeElement).toBe(search);
    expect(ctx.api).toHaveBeenCalledTimes(2);
  });

  it.each(["success", "failure"])("discards pending %s when logout clears session data", async (outcome) => {
    const { ctx, root, clearDataState } = harness(route);
    const request = deferred();
    ctx.api.mockReturnValue(request.promise);
    route.render(ctx);
    ctx.state.authed = false;
    ctx.state.user = null;
    ctx.state.activeSpace = null;
    clearDataState();
    const markupAfterClear = root.innerHTML;

    await settle(request, outcome, [route.record("Private result")]);

    expect(ctx.state[route.stateKey].records).toBeNull();
    expect(ctx.state[route.stateKey].loading).toBe(false);
    expect(ctx.state[route.stateKey].error).toBe("");
    expect(root.innerHTML).toBe(markupAfterClear);
    expect(ctx.api).toHaveBeenCalledTimes(1);
  });

  it.each(["success", "failure"])("ignores %s for a previous user in the same space", async (outcome) => {
    const { ctx, root, clearDataState } = harness(route);
    const oldRequest = deferred();
    const newRequest = deferred();
    ctx.api.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    route.render(ctx);
    ctx.state.user = { user_id: "user-b" };
    clearDataState();
    route.render(ctx);

    await settle(oldRequest, outcome, [route.record("Previous user result")]);
    expect(ctx.state[route.stateKey].records).toBeNull();
    expect(ctx.state[route.stateKey].loading).toBe(true);

    await settle(newRequest, "success", [route.record("Current user result")]);
    expect(root.textContent).toContain("Current user result");
    expect(root.textContent).not.toContain("Previous user result");
  });
});
