import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderRepositories } from "../../js/routes/repositories.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";

function context(records) {
  document.body.innerHTML = '<div id="repository-inventory-root"></div>';
  return {
    state: {
      repositoryInventory: {
        records,
        loading: false,
        error: "",
        search: "",
      },
    },
    els: { repositoryInventoryRoot: document.getElementById("repository-inventory-root") },
    api: vi.fn(),
    escapeHtml: (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;"),
    renderExternalRepoLink: (url, options) => `<a class="${options.className}" href="${url}">${options.label}</a>`,
  };
}

describe("Repository inventory", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("keeps the search input and its caret during invalidation and loading", async () => {
    const ctx = context([]);
    let finish;
    ctx.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderRepositories(ctx);
    const input = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]");
    input.focus(); input.value = "draft search"; input.dispatchEvent(new Event("input", { bubbles: true }));
    const current = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]");
    current.setSelectionRange(2, 5);
    ctx.state.repositoryInventory.records = null;
    renderRepositories(ctx);
    expect(ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]")).toBe(current);
    expect(document.activeElement).toBe(current);
    expect([current.selectionStart, current.selectionEnd]).toEqual([2, 5]);
    current.value = "new search"; current.dispatchEvent(new Event("input", { bubbles: true }));
    finish([]);
    await vi.waitFor(() => expect(ctx.state.repositoryInventory.loading).toBe(false));
    const replacement = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]");
    expect(document.activeElement).toBe(replacement);
    expect(replacement.value).toBe("new search");
  });

  it("returns keyboard retry focus after loading without stealing focus from elsewhere", async () => {
    const ctx = context(null);
    let finish;
    ctx.api.mockRejectedValueOnce(new Error("offline")).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    renderRepositories(ctx);
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.querySelector("[data-repository-retry]")).not.toBeNull());
    const retry = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-retry]");
    retry.focus(); retry.click();
    expect(document.activeElement).toBe(ctx.els.repositoryInventoryRoot.querySelector("[data-repository-loading-focus]"));
    const outside = document.createElement("button"); document.body.appendChild(outside); outside.focus();
    finish([]);
    await vi.waitFor(() => expect(ctx.state.repositoryInventory.loading).toBe(false));
    expect(document.activeElement).toBe(outside);
  });

  it("moves retry focus to the search after a successful retry", async () => {
    const ctx = context(null);
    ctx.api.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([]);
    renderRepositories(ctx);
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.querySelector("[data-repository-retry]")).not.toBeNull());
    const retry = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-retry]");
    retry.focus(); retry.click();
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("No repositories attached"));
    expect(document.activeElement).toBe(ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]"));
  });

  it("renders one repository row with its workspace entities and reference counts", () => {
    const ctx = context([{
      github_repo_url: "https://github.com/example/sipm",
      repository_name: "example/sipm",
      program_names: ["Developer Experience"],
      project_names: ["Developer Mode"],
      solution_names: ["My Work", "Repository inventory"],
      solution_count: 2,
      task_count: 5,
      solution_attachment_count: 1,
      task_override_count: 1,
      last_updated_at: "2026-07-21T12:00:00Z",
    }]);

    renderRepositories(ctx);

    const rows = ctx.els.repositoryInventoryRoot.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("example/sipm");
    expect(rows[0].textContent).toContain("Developer Experience");
    expect(rows[0].textContent).toContain("Developer Mode");
    expect(rows[0].textContent).toContain("Repository inventory");
    expect(rows[0].textContent).toContain("5 tasks");
    expect(rows[0].textContent).toContain("1 Solution attachment · 1 Task override");
    expect(rows[0].querySelector("a").getAttribute("href")).toBe("https://github.com/example/sipm");
    expect(rows[0].querySelectorAll("td")).toHaveLength(6);
  });

  it("filters repositories by entity context", () => {
    const ctx = context([
      {
        github_repo_url: "https://github.com/example/sipm",
        repository_name: "example/sipm",
        program_names: ["Developer Experience"],
        project_names: ["Developer Mode"],
        solution_names: ["My Work"],
        solution_count: 1,
        task_count: 4,
      },
      {
        github_repo_url: "https://github.com/example/payments",
        repository_name: "example/payments",
        program_names: ["Payments"],
        project_names: ["Modernization"],
        solution_names: ["Settlement API"],
        solution_count: 1,
        task_count: 2,
      },
    ]);

    renderRepositories(ctx);
    const search = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]");
    search.value = "settlement";
    search.dispatchEvent(new Event("input", { bubbles: true }));

    expect(ctx.els.repositoryInventoryRoot.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(ctx.els.repositoryInventoryRoot.textContent).toContain("example/payments");
    expect(ctx.els.repositoryInventoryRoot.textContent).not.toContain("example/sipm");
  });

  it("reports a malformed response and lets the user retry", async () => {
    const ctx = context(null);
    ctx.api.mockResolvedValueOnce({ unexpected: true }).mockResolvedValueOnce([]);
    renderRepositories(ctx);
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("invalid response"));
    expect(ctx.state.repositoryInventory.records).toEqual([]);
    ctx.els.repositoryInventoryRoot.querySelector('[data-repository-retry]').click();
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("No repositories attached"));
    expect(ctx.api).toHaveBeenCalledTimes(2);
  });

  it.each([[null], [{ repository_name: "broken", program_names: "not a list" }]])(
    "reports malformed inventory rows: %j", async (response) => {
      const ctx = context(null);
      ctx.api.mockResolvedValue(response);
      renderRepositories(ctx);
      await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("invalid response"));
      expect(ctx.els.repositoryInventoryRoot.querySelector('[data-repository-retry]')).toBeTruthy();
    }
  );

  it("escapes task counts when rendering inventory rows", () => {
    const ctx = context([{ github_repo_url: "https://github.com/example/repo", repository_name: "repo", task_count: '<img src=x onerror=alert(1)>' }]);
    renderRepositories(ctx);
    expect(ctx.els.repositoryInventoryRoot.querySelector('img')).toBeNull();
    expect(ctx.els.repositoryInventoryRoot.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it("keeps the search focused during a background rerender", () => {
    const ctx = context([]);
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    renderRepositories(ctx);
    const search = ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]');
    search.focus();
    search.value = "partial";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    const current = ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]');
    current.setSelectionRange(2, 5);
    renderRepositories(ctx);
    const replacement = ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]');
    expect(document.activeElement).toBe(replacement);
    expect(replacement.value).toBe("partial");
    expect(replacement.selectionStart).toBe(2);
    expect(replacement.selectionEnd).toBe(5);
    ctx.state.user = { user_id: "two" };
    renderRepositories(ctx);
    expect(document.activeElement).not.toBe(ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]'));
  });

  it("keeps search and its selection working across a same-session refresh", () => {
    const ctx = context([]);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    renderRepositories(ctx);
    const search = ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]');
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    search.value = "hello";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    expect(ctx.state.repositoryInventory.search).toBe("hello");
    const input = ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]');
    input.focus();
    input.setSelectionRange(1, 3);
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    renderRepositories(ctx);
    const replacement = ctx.els.repositoryInventoryRoot.querySelector('[data-repository-search]');
    expect(document.activeElement).toBe(replacement);
    expect([replacement.selectionStart, replacement.selectionEnd]).toEqual([1, 3]);
  });

  it("allows retry after a same-session refresh", async () => {
    const ctx = context(null);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    registerMutationContextLifetime(ctx.state, () => ({ session: 1, space: 1 }));
    ctx.api.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([]);
    renderRepositories(ctx);
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("offline"));
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    ctx.els.repositoryInventoryRoot.querySelector('[data-repository-retry]').click();
    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("No repositories attached"));
  });

  it.each(["session", "space"])("ignores an old inventory response after the same-ID %s changes", async (changed) => {
    const ctx = context(null);
    ctx.state.authed = true;
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(ctx.state, () => lifetime);
    let finish;
    ctx.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderRepositories(ctx);
    lifetime[changed] += 1;
    // Simulate returning to the same user/space IDs with a replacement session/context.
    ctx.state.user = { user_id: "one" };
    ctx.state.activeSpace = { space_id: "space" };
    finish([{ repository_name: "old private repo" }]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(ctx.state.repositoryInventory.records).toBeNull();
    expect(ctx.els.repositoryInventoryRoot.textContent).not.toContain("old private repo");
  });

  it("preserves the search caret while filtering rerenders the inventory", () => {
    const ctx = context([{
      github_repo_url: "https://github.com/example/payments",
      repository_name: "example/payments",
      program_names: [],
      project_names: [],
      solution_names: ["Settlement API"],
      solution_count: 1,
      task_count: 2,
    }]);
    renderRepositories(ctx);
    const search = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]");
    search.value = "settlement";
    search.setSelectionRange(3, 7, "backward");
    search.dispatchEvent(new Event("input", { bubbles: true }));

    const rerenderedSearch = ctx.els.repositoryInventoryRoot.querySelector("[data-repository-search]");
    expect(document.activeElement).toBe(rerenderedSearch);
    expect(rerenderedSearch.selectionStart).toBe(3);
    expect(rerenderedSearch.selectionEnd).toBe(7);
    expect(rerenderedSearch.selectionDirection).toBe("backward");
  });
  it("does not display an empty search result below a load error", async () => {
    const ctx = context(null);
    ctx.api.mockRejectedValue(new Error("offline"));
    renderRepositories(ctx);
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("offline"));
    expect(ctx.els.repositoryInventoryRoot.textContent).not.toContain("No repositories match this search");
    expect(ctx.els.repositoryInventoryRoot.querySelector("table")).toBeNull();
  });

  it.each([
    { task_count: "<img src=x onerror=alert(1)>" },
    { solution_attachment_count: "1" },
    { task_override_count: -1 },
    { github_repo_url: null },
    { program_names: [null] },
  ])("rejects malformed repository row fields %j", async (patch) => {
    const ctx = context(null);
    const row = { github_repo_url:"https://github.com/a/b", repository_name:"a/b", program_names:[], project_names:[], solution_names:[], solution_count:1, task_count:0, solution_attachment_count:1, task_override_count:0, last_updated_at:null, ...patch };
    ctx.api.mockResolvedValue([row]);
    renderRepositories(ctx);
    await vi.waitFor(() => expect(ctx.els.repositoryInventoryRoot.textContent).toContain("invalid response"));
    expect(ctx.els.repositoryInventoryRoot.querySelector("img")).toBeNull();
  });

  it("treats a naive server timestamp as UTC and displays a fallback for invalid timestamps", () => {
    const date = vi.spyOn(Date.prototype, "toLocaleDateString").mockImplementation(function () { return this.toISOString(); });
    try {
      const ctx = context([{ github_repo_url:"https://github.com/a/b", repository_name:"a/b", program_names:[], project_names:[], solution_names:[], task_count:0, last_updated_at:"2026-01-01T00:30:00" }]);
      renderRepositories(ctx);
      expect(ctx.els.repositoryInventoryRoot.textContent).toContain("2026-01-01T00:30:00.000Z");
      ctx.state.repositoryInventory.records[0].last_updated_at = "invalid";
      renderRepositories(ctx);
      expect(ctx.els.repositoryInventoryRoot.textContent).toContain("Update time unavailable");
    } finally { date.mockRestore(); }
  });

});
