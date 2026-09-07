// @vitest-environment node
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Linter } from "eslint";
import { describe, expect, it } from "vitest";

const root = fileURLToPath(new URL("../../js/", import.meta.url));

function staticModuleGraph(entry) {
  const files = new Map();
  const linter = new Linter();
  function visit(path) {
    if (files.has(path)) return;
    // Compare source budgets independently of Git's platform-specific line endings.
    const source = readFileSync(path, "utf8").replace(/\r\n?/g, "\n");
    files.set(path, Buffer.byteLength(source));
    const dependencies = [];
    const collect = (node) => {
      if (node.source?.value.startsWith(".")) dependencies.push(node.source.value);
    };
    const diagnostics = linter.verify(source, [{
      languageOptions: { ecmaVersion: "latest", sourceType: "module" },
      plugins: { graph: { rules: { imports: { create: () => ({
        ImportDeclaration: collect,
        ExportNamedDeclaration: collect,
        ExportAllDeclaration: collect,
      }) } } } },
      rules: { "graph/imports": "error" },
    }]);
    expect(diagnostics).toEqual([]);
    dependencies.forEach((dependency) => visit(resolve(dirname(path), dependency.split("?")[0])));
  }
  visit(resolve(root, entry));
  return files;
}

describe("startup assets", () => {
  it("keeps the large governance and deliverables bindings outside the static app graph", () => {
    const graph = staticModuleGraph("app.js");
    for (const deferred of [
      "routes/spaces/interactions.js", "routes/spaces/render.js",
      "routes/master/interactions.js",
      "routes/master/quickstart.js",
    ]) {
      expect(graph.has(resolve(root, deferred)), deferred).toBe(false);
    }
    // Baseline commit: 41 static modules, 547,782 LF-normalized bytes. Allow bounded shell growth.
    expect(graph.size).toBeLessThanOrEqual(37);
    expect([...graph.values()].reduce((sum, bytes) => sum + bytes, 0)).toBeLessThan(425_000);
  });

  it.each([
    ["master.js", "master/interactions.js"],
    ["master.js", "master/quickstart.js"],
    ["spaces.js", "spaces/interactions.js"],
    ["spaces.js", "spaces/render.js"],
    ["access.js", "spaces/interactions.js"],
    ["access.js", "spaces/render.js"],
  ])("loads %s with its %s dependency before initialization", (entry, dependency) => {
    expect(staticModuleGraph(`routes/${entry}`).has(resolve(root, "routes", dependency))).toBe(true);
  });
});
