import { describe, expect, it, vi } from "vitest";

import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";
import { createSpaceGovernanceRenderer } from "../../js/routes/spaces/render.js";
import { captureAgentChangeRequestContext } from "../../js/routes/spaces/change-request-context.js";


function createHarness({ isGlobalAdmin = false } = {}) {
  delete document._spaceGovernanceEscapeBound;
  document.body.innerHTML = `<div id="space-governance-shell"></div>`;
  const state = {
    currentView: "spaces",
    user: { user_id: "user-1" },
    activeSpace: { space_id: "space-1", space_name: "Space 1", space_role: "member" },
    spaceAdminSection: "agent-approvals",
    spaceGovernanceNotice: { text: "", tone: "", timeoutId: null },
    apiTokensByUser: {},
    apiTokensLoadedByUser: {},
    agentChangeRequestsLoaded: true,
    agentChangeRequestPendingCount: 1,
    agentChangeRequestFailedCount: 0,
    agentChangeRequestSelectedIds: new Set(),
    agentChangeRequestSelectedOperationIds: {},
    agentChangeRequestActiveId: "cr-1",
    agentChangeRequestModalId: "",
    agentChangeRequests: [
      {
        change_request_id: "cr-1",
        content_fingerprint: "a".repeat(64),
        status: "pending",
        reason: "Update delivery status",
        proposed_by_label: "Scheduler",
        created_at: "2026-05-28T10:00:00Z",
        operation_count: 1,
        operations: [
          {
            client_operation_id: "op-1",
            op: "update",
            entity: "project",
            id: "project-1",
            fields: { status: "complete" },
          },
        ],
        diff: [
          {
            client_operation_id: "op-1",
            op: "update",
            entity: "project",
            entity_id: "project-1",
            entity_label: "Project One",
            fields: {
              status: { old: "active", new: "complete" },
            },
          },
        ],
      },
    ],
  };
  let selectedSpaceId = "space-1";
  state.agentChangeRequestsContext = captureAgentChangeRequestContext(state, () => selectedSpaceId);
  const els = {
    spaceGovernanceShell: document.getElementById("space-governance-shell"),
  };
  const api = vi.fn((path) => {
    if (path === "/agent/change-requests/actions/approve-selected") {
      return Promise.resolve({ approved: 1, failed: 0 });
    }
    if (path === "/agent/change-requests/actions/reject-selected") {
      return Promise.resolve({ rejected: 1, failed: 0 });
    }
    if (path === "/agent/change-requests/cr-1/approve-selected-operations") {
      return Promise.resolve({ status: "approved" });
    }
    if (path === "/agent/change-requests?status=pending") {
      return Promise.resolve({ pending_count: 0, failed_count: 0, records: [] });
    }
    return Promise.resolve({});
  });
  const showConfirmModal = vi.fn().mockResolvedValue(true);
  const refreshFromServer = vi.fn().mockResolvedValue(undefined);
  const setSpaceGovernanceNotice = vi.fn();
  let renderer;
  const renderCalls = [];
  const renderGovernanceHub = (section = "agent-approvals") => {
    renderCalls.push(section);
    return renderer.renderGovernanceHub(section);
  };
  const controller = createSpaceGovernanceController({
    state,
    els,
    api,
    normalize: (value) => String(value || "").trim().toLowerCase(),
    normalizeGovernanceSection: (value) => String(value || "agent-approvals").trim().toLowerCase(),
    userIsGlobalAdmin: () => isGlobalAdmin,
    activeSpaceId: () => selectedSpaceId,
    canManageSpaceMembership: () => false,
    effectiveDirectorySpaces: () => [],
    spaceNameForId: () => "Space 1",
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    setSpaceGovernanceNotice,
    renderGovernanceHub,
    renderSpaceDirectoryModal: vi.fn(),
    isSpaceGovernanceView: () => true,
    refreshSpaceContext: vi.fn(),
    refreshFromServer,
    switchActiveSpace: vi.fn(),
    showConfirmModal,
    copyText: vi.fn(),
    buildResetPageUrl: vi.fn(),
  });
  renderer = createSpaceGovernanceRenderer({
    state,
    els,
    normalize: (value) => String(value || "").trim().toLowerCase(),
    normalizeSpaceRole: (value) => String(value || "").trim().toLowerCase(),
    activeSpaceId: () => selectedSpaceId,
    userIsGlobalAdmin: () => isGlobalAdmin,
    currentSpaceRoleLabel: () => "Member",
    canManageSpaceMembership: () => false,
    esc: (value) => String(value ?? ""),
    escapeAttr: (value) => String(value ?? ""),
    formatDateTime: (value) => value || "",
    effectiveDirectorySpaces: () => [],
    governanceSections: () => [{ id: "agent-approvals", label: "Agent Approvals (1)" }],
    resolveGovernanceSection: () => "agent-approvals",
    refreshGlobalAdmins: vi.fn(),
    refreshAgentChangeRequests: (...args) => controller.refreshAgentChangeRequests(...args),
    refreshApiTokens: vi.fn(),
    refreshSpaceMembers: vi.fn(),
    closeSpaceDirectoryModal: vi.fn(),
    setSpaceGovernanceNotice: vi.fn(),
  });
  controller.bindSpaceAdminControls();
  return {
    api,
    controller,
    els,
    renderCalls,
    refreshFromServer,
    setSpaceGovernanceNotice,
    showConfirmModal,
    state,
    renderGovernanceHub,
    setActiveSpaceId(spaceId) {
      selectedSpaceId = spaceId;
      state.activeSpace = spaceId ? { space_id: spaceId, space_name: spaceId, space_role: "member" } : null;
    },
  };
}


describe("agent approvals governance UI", () => {
  it("does not let an old session overwrite a new session's token list", async () => {
    const { api, controller, state } = createHarness({ isGlobalAdmin: true });
    let finishOld;
    api.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }));
    api.mockResolvedValueOnce([{ token_id: "new" }]);
    const old = controller.refreshApiTokens("user-1", { force: true });
    state.user = { user_id: "user-1" };
    state.apiTokensByUser = {};
    state.apiTokensLoadedByUser = {};
    await controller.refreshApiTokens("user-1", { force: true });
    finishOld([{ token_id: "old" }]);
    await old;
    expect(api.mock.calls.filter(([path]) => path === "/users/user-1/api-tokens")).toHaveLength(2);
    expect(state.apiTokensByUser["user-1"]).toEqual([{ token_id: "new" }]);
  });

  it("does not reuse cached token data in a replacement session", async () => {
    const { api, controller, state } = createHarness({ isGlobalAdmin: true });
    api.mockImplementation((path) => path === "/users/user-1/api-tokens"
      ? Promise.resolve([{ token_id: state.user.label }])
      : Promise.resolve({ records: [], pending_count: 0, failed_count: 0 }));
    state.user.label = "old";
    await controller.refreshApiTokens("user-1");
    state.user = { user_id: "user-1", label: "new" };
    await controller.refreshApiTokens("user-1");
    expect(state.apiTokensByUser["user-1"]).toEqual([{ token_id: "new" }]);
    expect(api.mock.calls.filter(([path]) => path === "/users/user-1/api-tokens")).toHaveLength(2);
  });

  it("rejects a malformed token list without caching it", async () => {
    const { api, controller, state } = createHarness({ isGlobalAdmin: true });
    api.mockResolvedValueOnce({ error: "bad response" });
    await expect(controller.refreshApiTokens("user-1", { force: true })).rejects.toThrow();
    expect(state.apiTokensLoadedByUser["user-1"]).not.toBe(true);
  });

  it("loads all pages of the pending proposal queue", async () => {
    const { api, controller, state } = createHarness();
    const first = { ...state.agentChangeRequests[0], change_request_id: "first" };
    const second = { ...first, change_request_id: "second" };
    api.mockResolvedValueOnce({ records: [first], pending_count: 2, failed_count: 0, has_more: true, next_cursor: "next/+" });
    api.mockResolvedValueOnce({ records: [second], pending_count: 2, failed_count: 0, has_more: false, next_cursor: null });
    await controller.refreshAgentChangeRequests({ force: true });
    expect(state.agentChangeRequests.map((row) => row.change_request_id)).toEqual(["first", "second"]);
    expect(api).toHaveBeenNthCalledWith(2, "/agent/change-requests?status=pending&cursor=next%2F%2B");
  });

  it("preserves the queue when a later page is malformed", async () => {
    const { api, controller, state } = createHarness();
    const previous = state.agentChangeRequests;
    state.agentChangeRequestSelectedIds = new Set(["cr-1"]);
    api.mockResolvedValueOnce({ records: [], has_more: true, next_cursor: "next" });
    api.mockResolvedValueOnce({ error: "unexpected" });
    await expect(controller.refreshAgentChangeRequests({ force: true })).rejects.toThrow();
    expect(state.agentChangeRequests).toBe(previous);
    expect(state.agentChangeRequestSelectedIds.has("cr-1")).toBe(true);
  });

  it("stops paging when the active space changes", async () => {
    const { api, controller, setActiveSpaceId } = createHarness();
    let finishSecond;
    api.mockResolvedValueOnce({ records: [], has_more: true, next_cursor: "next" });
    api.mockImplementationOnce(() => new Promise((resolve) => { finishSecond = resolve; }));
    const loading = controller.refreshAgentChangeRequests({ force: true });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    setActiveSpaceId("space-2");
    finishSecond({ records: [], has_more: true, next_cursor: "another" });
    await expect(loading).resolves.toEqual([]);
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("rejects repeated pagination cursors without clearing the queue", async () => {
    const { api, controller, state } = createHarness();
    const previous = state.agentChangeRequests;
    api.mockResolvedValue({ records: [], has_more: true, next_cursor: "repeated" });
    await expect(controller.refreshAgentChangeRequests({ force: true })).rejects.toThrow("pagination");
    expect(api).toHaveBeenCalledTimes(2);
    expect(state.agentChangeRequests).toBe(previous);
  });

  it("selects no more than 50 proposals for one bulk review", async () => {
    const { state, els, renderGovernanceHub, setSpaceGovernanceNotice } = createHarness();
    const sample = state.agentChangeRequests[0];
    state.agentChangeRequests = Array.from({ length: 55 }, (_, index) => ({ ...sample, change_request_id: `cr-${index}` }));
    renderGovernanceHub();
    els.spaceGovernanceShell.querySelector("[data-space-action='toggle-agent-change-request-selection']").click();
    expect(state.agentChangeRequestSelectedIds.size).toBe(50);
    const last = els.spaceGovernanceShell.querySelector('[data-change-request-id="cr-54"][data-agent-change-request-checkbox]');
    last.checked = true;
    last.dispatchEvent(new Event("change", { bubbles: true }));
    expect(state.agentChangeRequestSelectedIds.size).toBe(50);
    expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(expect.stringContaining("50"), "error", expect.any(Number));
  });
  it("renders the queue and proposal details together in a review workbench", () => {
    const { els, renderGovernanceHub } = createHarness();

    renderGovernanceHub();

    expect(els.spaceGovernanceShell.textContent).toContain("Agent Approvals");
    expect(els.spaceGovernanceShell.textContent).toContain("Update delivery status");
    expect(els.spaceGovernanceShell.textContent).not.toContain("cr-1");
    expect(els.spaceGovernanceShell.textContent).toContain("1 change across Project One");
    expect(els.spaceGovernanceShell.textContent).toContain("active");
    expect(els.spaceGovernanceShell.textContent).toContain("complete");
    expect(els.spaceGovernanceShell.querySelector(".agent-approval-workbench")).not.toBeNull();
    expect(els.spaceGovernanceShell.querySelector(".agent-approval-queue")).not.toBeNull();
    expect(els.spaceGovernanceShell.querySelector(".agent-approval-review")).not.toBeNull();
    expect(els.spaceGovernanceShell.querySelector(".agent-approval-table")).toBeNull();
    expect(els.spaceGovernanceShell.querySelector(".agent-proposal-modal")).toBeNull();
    expect(els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]")).not.toBeNull();
    expect(els.spaceGovernanceShell.querySelector("[data-space-action='refresh-agent-change-requests']")).not.toBeNull();
  });

  it("manually refreshes the approval queue", async () => {
    const { api, els, renderGovernanceHub } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='refresh-agent-change-requests']")
      .click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith("/agent/change-requests?status=pending");
    });
  });

  it("stops automatic retries after a failed queue read and retries explicitly", async () => {
    const { api, els, renderGovernanceHub, state } = createHarness();
    state.agentChangeRequests = [];
    state.agentChangeRequestsLoaded = false;
    api.mockRejectedValueOnce(new Error("unavailable"));
    renderGovernanceHub();
    await vi.waitFor(() => expect(state.agentChangeRequestsError).toBeTruthy());
    renderGovernanceHub();
    renderGovernanceHub();
    expect(api).toHaveBeenCalledTimes(1);
    expect(els.spaceGovernanceShell.textContent).toContain("Could not load the approval queue");
    expect(els.spaceGovernanceShell.textContent).not.toContain("Nothing waiting");
    els.spaceGovernanceShell.querySelector("[data-space-action='refresh-agent-change-requests']").click();
    await vi.waitFor(() => expect(state.agentChangeRequestsError).toBe(""));
    expect(api).toHaveBeenCalledTimes(2);
    expect(els.spaceGovernanceShell.textContent).toContain("Nothing waiting");
  });

  it("hides stale queue data and actions when a refresh fails", async () => {
    const { api, controller, els, renderGovernanceHub, state } = createHarness();
    api.mockRejectedValueOnce(new Error("unavailable"));
    await expect(controller.refreshAgentChangeRequests({ force: true })).rejects.toThrow("unavailable");
    renderGovernanceHub();
    expect(state.agentChangeRequests).toHaveLength(1);
    expect(els.spaceGovernanceShell.textContent).toContain("Could not load the approval queue");
    expect(els.spaceGovernanceShell.textContent).not.toContain("Update delivery status");
    expect(els.spaceGovernanceShell.querySelector("[data-space-action='approve-agent-change-requests']")).toBeNull();
  });

  it("runs a follow-up refresh when an event arrives during an active request", async () => {
    const { api, controller } = createHarness();
    let resolveFirst;
    api
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveFirst = resolve;
      }))
      .mockResolvedValueOnce({ pending_count: 0, failed_count: 0, records: [] });

    const firstRefresh = controller.refreshAgentChangeRequests({ force: true });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    const eventRefresh = controller.refreshAgentChangeRequests({ force: true });
    resolveFirst({ pending_count: 1, failed_count: 0, records: [] });
    await Promise.all([firstRefresh, eventRefresh]);

    expect(api).toHaveBeenCalledTimes(2);
  });

  it("clears prior selections when a proposal's reviewed content changes", async () => {
    const { api, controller, state } = createHarness();
    state.agentChangeRequestSelectedIds = new Set(["cr-1"]);
    state.agentChangeRequestSelectedOperationIds = { "cr-1": new Set(["op-1"]) };
    api.mockResolvedValue({
      pending_count: 1, failed_count: 0,
      records: [{ ...state.agentChangeRequests[0], content_fingerprint: "b".repeat(64) }],
    });
    await controller.refreshAgentChangeRequests({ force: true });
    expect(state.agentChangeRequestSelectedIds.size).toBe(0);
    expect(state.agentChangeRequestSelectedOperationIds["cr-1"].size).toBe(0);
  });

  it("invalidates a loaded queue when the active space changes", async () => {
    const { api, els, renderGovernanceHub, state, setActiveSpaceId } = createHarness();
    api.mockResolvedValue({
      pending_count: 1,
      failed_count: 0,
      records: [{ change_request_id: "cr-space-2", reason: "Space 2 proposal", operations: [], diff: [] }],
    });

    renderGovernanceHub();
    setActiveSpaceId("space-2");
    renderGovernanceHub();

    expect(els.spaceGovernanceShell.textContent).not.toContain("Update delivery status");
    await vi.waitFor(() => expect(state.agentChangeRequests[0]?.change_request_id).toBe("cr-space-2"));
    expect(api).toHaveBeenCalledWith("/agent/change-requests?status=pending");
    expect(state.agentChangeRequestsContext.spaceId).toBe("space-2");
  });

  it("loads the new space queue while an older space request is still pending", async () => {
    const { api, controller, state, setActiveSpaceId } = createHarness();
    let resolveSpaceOne;
    api
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveSpaceOne = resolve;
      }))
      .mockResolvedValueOnce({
        pending_count: 1,
        failed_count: 0,
        records: [{ change_request_id: "cr-space-2", reason: "Space 2 proposal" }],
      });

    const spaceOneRefresh = controller.refreshAgentChangeRequests({ force: true });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    setActiveSpaceId("space-2");
    const spaceTwoRefresh = controller.refreshAgentChangeRequests();
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    await spaceTwoRefresh;

    expect(state.agentChangeRequests[0]?.change_request_id).toBe("cr-space-2");
    expect(state.agentChangeRequestsContext.spaceId).toBe("space-2");
    resolveSpaceOne({
      pending_count: 1,
      failed_count: 0,
      records: [{ change_request_id: "cr-space-1", reason: "Old proposal" }],
    });
    await spaceOneRefresh;

    expect(state.agentChangeRequests[0]?.change_request_id).toBe("cr-space-2");
    expect(state.agentChangeRequestsContext.spaceId).toBe("space-2");
  });

  it("isolates a replacement session with the same user and space IDs", async () => {
    const { api, controller, state } = createHarness();
    let resolveOldSession;
    api
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveOldSession = resolve;
      }))
      .mockResolvedValueOnce({
        pending_count: 1,
        failed_count: 0,
        records: [{ change_request_id: "cr-new-session", reason: "New session proposal" }],
      });

    const oldSessionRefresh = controller.refreshAgentChangeRequests({ force: true });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    state.user = { ...state.user };
    state.activeSpace = { ...state.activeSpace };
    const newSessionRefresh = controller.refreshAgentChangeRequests();
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    await newSessionRefresh;
    resolveOldSession({
      pending_count: 1,
      failed_count: 0,
      records: [{ change_request_id: "cr-old-session", reason: "Old session proposal" }],
    });
    await oldSessionRefresh;

    expect(state.agentChangeRequests[0]?.change_request_id).toBe("cr-new-session");
  });

  it("drops a pending queue response after logout instead of restoring old records", async () => {
    const { api, controller, state, setActiveSpaceId } = createHarness();
    let resolvePending;
    api.mockImplementationOnce(() => new Promise((resolve) => {
      resolvePending = resolve;
    }));

    const refresh = controller.refreshAgentChangeRequests({ force: true });
    await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    state.user = null;
    setActiveSpaceId("");
    resolvePending({
      pending_count: 1,
      failed_count: 0,
      records: [{ change_request_id: "cr-old", reason: "Old proposal" }],
    });
    await refresh;

    expect(state.agentChangeRequests).toEqual([]);
    expect(state.agentChangeRequestPendingCount).toBe(0);
    expect(state.agentChangeRequestsLoaded).toBe(true);
    expect(api).toHaveBeenCalledTimes(1);
  });

  it("keeps proposal selection in context without opening a modal", () => {
    const { els, renderGovernanceHub, state } = createHarness();
    state.agentChangeRequestActiveId = "";

    renderGovernanceHub();
    expect(els.spaceGovernanceShell.querySelector(".agent-queue-item.is-active")).not.toBeNull();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='open-agent-change-request']")
      .click();

    expect(state.agentChangeRequestActiveId).toBe("cr-1");
    expect(els.spaceGovernanceShell.querySelector(".agent-proposal-modal")).toBeNull();
    expect(els.spaceGovernanceShell.textContent).toContain("Project One");
    expect(els.spaceGovernanceShell.textContent).toContain("active");
    expect(els.spaceGovernanceShell.textContent).toContain("complete");
  });

  it("approves the selected operations in the current proposal", async () => {
    const { api, els, renderGovernanceHub, showConfirmModal } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='approve-agent-change-request']")
      .click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        "/agent/change-requests/cr-1/approve-selected-operations",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ client_operation_ids: ["op-1"], if_request_fingerprint: "a".repeat(64) }),
        })
      );
    });
    expect(showConfirmModal).not.toHaveBeenCalled();
  });

  it("lets reviewers clear individual changes and select all again", () => {
    const { els, renderGovernanceHub, state } = createHarness();
    state.agentChangeRequests[0].operation_count = 2;
    state.agentChangeRequests[0].operations.push({
      client_operation_id: "op-2",
      op: "update",
      entity: "project",
      id: "project-2",
      fields: { status: "active" },
    });
    state.agentChangeRequests[0].diff.push({
      client_operation_id: "op-2",
      op: "update",
      entity: "project",
      entity_id: "project-2",
      entity_label: "Project Two",
      fields: { status: { old: "paused", new: "active" } },
    });

    renderGovernanceHub();

    const operationCheckboxes = els.spaceGovernanceShell.querySelectorAll(
      "[data-agent-change-operation-checkbox]"
    );
    expect(operationCheckboxes).toHaveLength(2);
    expect([...operationCheckboxes].every((checkbox) => checkbox.checked)).toBe(true);

    operationCheckboxes[1].checked = false;
    operationCheckboxes[1].dispatchEvent(new Event("change", { bubbles: true }));
    expect(state.agentChangeRequestSelectedOperationIds["cr-1"]).toEqual(new Set(["op-1"]));
    expect(els.spaceGovernanceShell.textContent).toContain("Approve selected (1)");

    els.spaceGovernanceShell
      .querySelector("[data-space-action='select-all-agent-change-request-operations']")
      .click();
    expect(state.agentChangeRequestSelectedOperationIds["cr-1"]).toEqual(
      new Set(["op-1", "op-2"])
    );
    expect(els.spaceGovernanceShell.textContent).toContain("Approve proposal");
  });

  it("confirms a partial approval before applying only the included changes", async () => {
    const { api, els, renderGovernanceHub, showConfirmModal, state } = createHarness();
    state.agentChangeRequests[0].operation_count = 2;
    state.agentChangeRequests[0].operations.push({
      client_operation_id: "op-2",
      op: "update",
      entity: "project",
      id: "project-2",
      fields: { status: "active" },
    });
    state.agentChangeRequests[0].diff.push({
      client_operation_id: "op-2",
      op: "update",
      entity: "project",
      entity_id: "project-2",
      entity_label: "Project Two",
      fields: { status: { old: "paused", new: "active" } },
    });

    renderGovernanceHub();
    const operationCheckboxes = els.spaceGovernanceShell.querySelectorAll(
      "[data-agent-change-operation-checkbox]"
    );
    operationCheckboxes[1].checked = false;
    operationCheckboxes[1].dispatchEvent(new Event("change", { bubbles: true }));
    expect(els.spaceGovernanceShell.textContent).toContain("Unselected changes will remain pending.");
    els.spaceGovernanceShell
      .querySelector("[data-space-action='approve-agent-change-request']")
      .click();

    await vi.waitFor(() => {
      expect(showConfirmModal).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Approve Selected Changes",
          message: expect.stringContaining("will remain pending"),
        })
      );
      expect(api).toHaveBeenCalledWith(
        "/agent/change-requests/cr-1/approve-selected-operations",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ client_operation_ids: ["op-1"], if_request_fingerprint: "a".repeat(64) }),
        })
      );
    });
  });

  it("rejects the current proposal through the bulk endpoint", async () => {
    const { api, els, renderGovernanceHub, showConfirmModal } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='reject-agent-change-request']")
      .click();

    await vi.waitFor(() => {
      expect(showConfirmModal).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Reject Agent Proposal" })
      );
      expect(api).toHaveBeenCalledWith(
        "/agent/change-requests/actions/reject-selected",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ change_request_ids: ["cr-1"], if_request_fingerprints: { "cr-1": "a".repeat(64) } }),
        })
      );
    });
  });

  it("selects and clears the full queue from the queue header", () => {
    const { els, renderGovernanceHub, state } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='toggle-agent-change-request-selection']")
      .click();

    expect(state.agentChangeRequestSelectedIds).toEqual(new Set(["cr-1"]));
    expect(els.spaceGovernanceShell.textContent).toContain("Clear all");

    els.spaceGovernanceShell
      .querySelector("[data-space-action='toggle-agent-change-request-selection']")
      .click();

    expect(state.agentChangeRequestSelectedIds).toEqual(new Set());
    expect(els.spaceGovernanceShell.textContent).toContain("Select all");
  });

  it("approves selected requests through the bulk endpoint", async () => {
    const { api, els, renderCalls, renderGovernanceHub } = createHarness();

    renderGovernanceHub();
    const checkbox = els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]");
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    els.spaceGovernanceShell
      .querySelector("[data-space-action='approve-agent-change-requests']")
      .click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        "/agent/change-requests/actions/approve-selected",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ change_request_ids: ["cr-1"], if_request_fingerprints: { "cr-1": "a".repeat(64) } }),
        })
      );
    });
    expect(renderCalls).toContain("agent-approvals");
  });

  it.each(["approve", "reject"])("refreshes data after a failed bulk %s", async (action) => {
    const { api, els, refreshFromServer, renderGovernanceHub, setSpaceGovernanceNotice, state } = createHarness();
    const endpoint = `/agent/change-requests/actions/${action}-selected`;
    api.mockImplementation((path) => {
      if (path === endpoint) return Promise.reject(new Error("Review interrupted"));
      if (path === "/agent/change-requests?status=pending") {
        return Promise.resolve({ pending_count: 0, failed_count: 0, records: [] });
      }
      return Promise.resolve({});
    });
    renderGovernanceHub();
    const checkbox = els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]");
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    els.spaceGovernanceShell.querySelector(`[data-space-action='${action}-agent-change-requests']`).click();
    await vi.waitFor(() => expect(refreshFromServer).toHaveBeenCalledWith("all"));
    expect(api).toHaveBeenCalledWith("/agent/change-requests?status=pending");
    expect(state.agentChangeRequests).toEqual([]);
    expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(
      "Review interrupted Some changes may have been applied; review the refreshed queue.", "error", 7000,
    );
  });

  it.each(["space", "session"])("does not submit an approval after its confirmation changes %s", async (change) => {
    const { api, els, renderGovernanceHub, setActiveSpaceId, showConfirmModal, state } = createHarness();
    let confirm;
    showConfirmModal.mockReturnValue(new Promise((resolve) => { confirm = resolve; }));
    renderGovernanceHub();
    const checkbox = els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]");
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    els.spaceGovernanceShell.querySelector("[data-space-action='approve-agent-change-requests']").click();
    if (change === "space") setActiveSpaceId("space-2");
    else state.user = { ...state.user };
    confirm(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api).not.toHaveBeenCalledWith("/agent/change-requests/actions/approve-selected", expect.anything());
  });

  it("does not submit a single rejection after its confirmation changes spaces", async () => {
    const { api, els, renderGovernanceHub, setActiveSpaceId, showConfirmModal } = createHarness();
    let confirm;
    showConfirmModal.mockReturnValue(new Promise((resolve) => { confirm = resolve; }));
    renderGovernanceHub();
    els.spaceGovernanceShell.querySelector("[data-space-action='reject-agent-change-request']").click();
    setActiveSpaceId("space-2");
    confirm(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api).not.toHaveBeenCalledWith("/agent/change-requests/actions/reject-selected", expect.anything());
  });

  it("keeps the reviewed fingerprint when a proposal changes during confirmation", async () => {
    const { api, els, renderGovernanceHub, showConfirmModal, state } = createHarness();
    let confirm;
    showConfirmModal.mockReturnValue(new Promise((resolve) => { confirm = resolve; }));
    renderGovernanceHub();
    els.spaceGovernanceShell.querySelector("[data-space-action='reject-agent-change-request']").click();
    state.agentChangeRequests[0].content_fingerprint = "b".repeat(64);
    confirm(true);
    await vi.waitFor(() => expect(api).toHaveBeenCalledWith(
      "/agent/change-requests/actions/reject-selected",
      expect.objectContaining({
        body: JSON.stringify({ change_request_ids: ["cr-1"], if_request_fingerprints: { "cr-1": "a".repeat(64) } }),
      }),
    ));
  });

  it("explains how to recover when a proposal changed after review", async () => {
    const { api, els, renderGovernanceHub, setSpaceGovernanceNotice } = createHarness();
    api.mockImplementation((path) => {
      if (path.endsWith("/approve-selected-operations")) {
        return Promise.reject(Object.assign(new Error("changed"), { code: "CHANGE_REQUEST_CHANGED" }));
      }
      return Promise.resolve({ pending_count: 0, failed_count: 0, records: [] });
    });
    renderGovernanceHub();
    els.spaceGovernanceShell.querySelector("[data-space-action='approve-agent-change-request']").click();
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenLastCalledWith(
      expect.stringContaining("Review the refreshed proposal"), "error", 7000,
    ));
  });

  it("ignores an old approval response after switching spaces", async () => {
    const { api, els, refreshFromServer, renderGovernanceHub, setActiveSpaceId, state } = createHarness();
    let complete;
    api.mockImplementation((path) => {
      if (path === "/agent/change-requests/actions/approve-selected") {
        return new Promise((resolve) => { complete = resolve; });
      }
      return Promise.resolve({ pending_count: 0, failed_count: 0, records: [] });
    });
    renderGovernanceHub();
    const checkbox = els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]");
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    els.spaceGovernanceShell.querySelector("[data-space-action='approve-agent-change-requests']").click();
    await vi.waitFor(() => expect(complete).toBeTypeOf("function"));
    setActiveSpaceId("space-2");
    state.agentChangeRequestSelectedIds = new Set(["new-space-request"]);
    complete({ approved: 1, failed: 0 });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.agentChangeRequestSelectedIds).toEqual(new Set(["new-space-request"]));
    expect(refreshFromServer).not.toHaveBeenCalled();
  });

  it("warns when the queue cannot be refreshed after a failed review", async () => {
    const { api, els, renderGovernanceHub, setSpaceGovernanceNotice } = createHarness();
    api.mockRejectedValue(new Error("Review interrupted"));
    renderGovernanceHub();
    const checkbox = els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]");
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    els.spaceGovernanceShell.querySelector("[data-space-action='approve-agent-change-requests']").click();
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(
      "Review interrupted Refresh failed; reload to see current results.", "error", 7000,
    ));
  });

  it("reports the review failure while the queue refresh is still pending", async () => {
    const { api, els, renderGovernanceHub, setSpaceGovernanceNotice } = createHarness();
    let finishRefresh;
    api.mockImplementation((path) => {
      if (path === "/agent/change-requests/actions/approve-selected") {
        return Promise.reject(new Error("Review interrupted"));
      }
      if (path === "/agent/change-requests?status=pending") {
        return new Promise((resolve) => { finishRefresh = resolve; });
      }
      return Promise.resolve({});
    });
    renderGovernanceHub();
    const checkbox = els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]");
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    els.spaceGovernanceShell.querySelector("[data-space-action='approve-agent-change-requests']").click();
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(
      "Review interrupted Checking for applied changes...", "error", 7000,
    ));
    finishRefresh({ pending_count: 0, failed_count: 0, records: [] });
    await vi.waitFor(() => expect(setSpaceGovernanceNotice).toHaveBeenCalledWith(
      "Review interrupted Some changes may have been applied; review the refreshed queue.", "error", 7000,
    ));
  });
});
