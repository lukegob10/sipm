import { describe, expect, test } from "vitest";

import { safeExternalUrl } from "../../js/utils/external-url.js";

describe("safeExternalUrl", () => {
  test("allows clean GitHub repository URLs", () => {
    expect(safeExternalUrl("https://github.com/example/repo.git/")).toBe("https://github.com/example/repo");
  });

  test("rejects executable or non-repository URLs", () => {
    expect(safeExternalUrl("javascript:alert(1)")).toBe("");
    expect(safeExternalUrl("/relative")).toBe("");
    expect(safeExternalUrl("https://github.com/example/repo/issues/1")).toBe("");
    expect(safeExternalUrl("https://example.com/example/repo")).toBe("");
  });
});
