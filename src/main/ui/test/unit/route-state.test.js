import { describe, expect, it } from "vitest";

import { renderRouteState } from "../../js/ui/route-state.js";

describe("route state renderer", () => {
  it("escapes state content and applies a supported semantic role", () => {
    const html = renderRouteState({
      kind: "error",
      kicker: "Could not load",
      title: "Retry <now>",
      message: "Request failed & was retained.",
    });

    expect(html).toContain('role="alert"');
    expect(html).toContain("Retry &lt;now&gt;");
    expect(html).toContain("Request failed &amp; was retained.");
  });
});
