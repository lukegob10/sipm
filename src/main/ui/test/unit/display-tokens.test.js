import { describe, expect, it } from "vitest";

import { statusPillMarkup, statusTone } from "../../js/utils/display-tokens.js";

describe("status display tokens", () => {
  it("uses the blue info tone for completed progress", () => {
    expect(statusTone("complete")).toBe("info");
    expect(statusPillMarkup("complete", "Complete")).toContain("pill status-pill info");
  });

  it("keeps active progress green", () => {
    expect(statusTone("active")).toBe("positive");
    expect(statusTone("in_progress")).toBe("positive");
  });
});
