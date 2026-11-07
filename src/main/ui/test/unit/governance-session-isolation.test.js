import { describe, expect, it, vi } from "vitest";
import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";

function harness() {
  const state = {
    user: { user_id: "same-user" }, activeSpace: { space_id: "space" }, currentView: "spaces",
    globalAdmins: [], globalAdminsLoaded: false,
    requestableSpaces: [], requestableSpacesLoaded: false, requestableSpacesError: "",
    spaceAccessRequests: [], spaceAccessRequestsLoaded: false, spaceAccessRequestsError: "",
    reviewableAccessRequests: [], reviewableAccessRequestsLoaded: false,
    spaceMembersBySpace: {}, spaceMembersLoadedBySpace: {},
  };
  const api = vi.fn();
  const controller = createSpaceGovernanceController({
    state, api, els: {}, activeSpaceId: () => state.activeSpace?.space_id,
    userIsGlobalAdmin: () => true, isSpaceGovernanceView: () => false,
  });
  return { state, api, controller };
}

const cases = [
  ["admins", (controller) => controller.refreshGlobalAdmins(), (state) => state.globalAdmins],
  ["requestable", (controller) => controller.refreshRequestableSpaces({ force: true }), (state) => state.requestableSpaces],
  ["requests", (controller) => controller.refreshAccessRequests({ force: true }), (state) => state.spaceAccessRequests],
  ["reviewable", (controller) => controller.refreshReviewableAccessRequests({ force: true }), (state) => state.reviewableAccessRequests],
  ["members", (controller) => controller.refreshSpaceMembers("target", { force: true }), (state) => state.spaceMembersBySpace.target],
];

describe("governance reads across sessions", () => {
  it.each(cases)("does not share or apply an old %s request to a replacement session", async (_label, load, value) => {
    const { state, api, controller } = harness();
    let finishOld;
    api.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }));
    api.mockResolvedValueOnce([{ marker: "new" }]);
    const old = load(controller);
    state.user = { user_id: "same-user" };
    const current = load(controller);
    finishOld([{ marker: "old" }]);
    await Promise.all([old, current]);
    expect(api).toHaveBeenCalledTimes(2);
    expect(value(state)).toEqual([{ marker: "new" }]);
  });

  it.each(cases)("ignores an old %s failure after a replacement session succeeds", async (_label, load, value) => {
    const { state, api, controller } = harness();
    let failOld;
    api.mockImplementationOnce(() => new Promise((_, reject) => { failOld = reject; }));
    api.mockResolvedValueOnce([{ marker: "new" }]);
    const old = load(controller);
    state.user = { user_id: "same-user" };
    const current = load(controller);
    failOld(new Error("old failure"));
    await Promise.all([old, current]);
    expect(value(state)).toEqual([{ marker: "new" }]);
    expect(state.requestableSpacesError).toBe("");
    expect(state.spaceAccessRequestsError).toBe("");
  });

  it("does not reuse a cached list in a replacement session", async () => {
    const { state, api, controller } = harness();
    api.mockResolvedValueOnce([{ marker: "old" }]).mockResolvedValueOnce([{ marker: "new" }]);
    await controller.refreshRequestableSpaces();
    state.user = { user_id: "same-user" };
    await controller.refreshRequestableSpaces();
    expect(api).toHaveBeenCalledTimes(2);
    expect(state.requestableSpaces).toEqual([{ marker: "new" }]);
  });

  it.each(cases)("does not treat a malformed %s response as a successful list", async (_label, load) => {
    const { api, controller } = harness();
    api.mockResolvedValueOnce({ error: "malformed" });
    await expect(load(controller)).rejects.toThrow();
  });
});

describe("reviewable access request failures", () => {
  it("keeps prior data but marks a failed forced refresh and clears the error after retry", async () => {
    const { state, api, controller } = harness();
    const prior = [{ request_id: "old" }];
    api.mockResolvedValueOnce(prior).mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce([{ request_id: "new" }]);
    await controller.refreshReviewableAccessRequests({ force: true });
    await expect(controller.refreshReviewableAccessRequests({ force: true })).rejects.toThrow("unavailable");
    expect(state.reviewableAccessRequests).toEqual(prior);
    expect(state.reviewableAccessRequestsError).toBeTruthy();
    await controller.refreshReviewableAccessRequests({ force: true });
    expect(state.reviewableAccessRequests).toEqual([{ request_id: "new" }]);
    expect(state.reviewableAccessRequestsError).toBe("");
  });

  it("does not apply an old session's failed refresh to its replacement", async () => {
    const { state, api, controller } = harness();
    let rejectOld;
    api.mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; }))
      .mockResolvedValueOnce([{ request_id: "new" }]);
    const old = controller.refreshReviewableAccessRequests({ force: true });
    state.user = { user_id: "same-user" };
    await controller.refreshReviewableAccessRequests({ force: true });
    rejectOld(new Error("old failure"));
    await old;
    expect(state.reviewableAccessRequestsError).toBe("");
    expect(state.reviewableAccessRequests).toEqual([{ request_id: "new" }]);
  });
});
