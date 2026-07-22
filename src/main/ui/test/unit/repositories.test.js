import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderRepositories } from "../../js/routes/repositories.js";

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
});
