import { describe, expect, it, vi } from "vitest";
import { createSessionBoundFetch } from "../../js/utils/form-state.js";

describe("session-bound fetch", () => {
  it("sends the captured binding and preserves other request headers", async () => {
    const response = { ok: true };
    const fetchImpl = vi.fn().mockResolvedValue(response);
    const handleMismatch = vi.fn().mockReturnValue(false);
    const request = createSessionBoundFetch({ fetchImpl, getBinding: () => "session-a", handleMismatch });
    await expect(request("/report", { headers: { "X-Space-Id": "space-a" } })).resolves.toBe(response);
    expect(fetchImpl.mock.calls[0][1].headers.get("X-SIPM-Session")).toBe("session-a");
    expect(fetchImpl.mock.calls[0][1].headers.get("X-Space-Id")).toBe("space-a");
    expect(handleMismatch).toHaveBeenCalledWith(response, "session-a");
  });

  it("rejects a mismatch using the original binding even if the session changes while waiting", async () => {
    let release;
    const pending = new Promise((resolve) => { release = resolve; });
    let binding = "session-a";
    const handleMismatch = vi.fn().mockReturnValue(true);
    const request = createSessionBoundFetch({ fetchImpl: () => pending, getBinding: () => binding, handleMismatch });
    const result = request("/report");
    binding = "session-b";
    const response = { status: 409 };
    release(response);
    await expect(result).rejects.toMatchObject({ code: "REQUEST_CONTEXT_CHANGED" });
    expect(handleMismatch).toHaveBeenCalledWith(response, "session-a");
  });
});
