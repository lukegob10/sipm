import { describe, expect, it, vi } from "vitest";

import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";
import { createSpaceGovernanceRenderer } from "../../js/routes/spaces/render.js";


function createHarness() {
  delete document._spaceGovernanceEscapeBound;
  document.body.innerHTML = `<div id="space-governance-shell"></div>`;
  const state = {
    currentView: "spaces",
    activeSpace: { space_id: "space-1", space_name: "Space 1", space_role: "member" },
    spaceAdminSection: "agent-approvals",
    spaceGovernanceNotice: { text: "", tone: "", timeoutId: null },
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
    if (path === "/agent/change-requests?status=pending") {
      return Promise.resolve({ pending_count: 0, failed_count: 0, records: [] });
    }
    return Promise.resolve({});
  });
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
    userIsGlobalAdmin: () => false,
    activeSpaceId: () => "space-1",
    canManageSpaceMembership: () => false,
    effectiveDirectorySpaces: () => [],
    spaceNameForId: () => "Space 1",
    clearDeliverableFormNotice: vi.fn(),
    setDeliverableFormNotice: vi.fn(),
    setSpaceGovernanceNotice: vi.fn(),
    renderGovernanceHub,
    renderSpaceDirectoryModal: vi.fn(),
    isSpaceGovernanceView: () => true,
    refreshSpaceContext: vi.fn(),
    refreshFromServer: vi.fn().mockResolvedValue(undefined),
    switchActiveSpace: vi.fn(),
    showConfirmModal: vi.fn().mockResolvedValue(true),
    copyText: vi.fn(),
    buildResetPageUrl: vi.fn(),
  });
  renderer = createSpaceGovernanceRenderer({
    state,
    els,
    normalize: (value) => String(value || "").trim().toLowerCase(),
    normalizeSpaceRole: (value) => String(value || "").trim().toLowerCase(),
    activeSpaceId: () => "space-1",
    userIsGlobalAdmin: () => false,
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
  return { api, controller, els, renderCalls, state, renderGovernanceHub };
}


describe("agent approvals governance UI", () => {
  it("renders pending requests in a full-width table without inline field diffs", () => {
    const { els, renderGovernanceHub } = createHarness();

    renderGovernanceHub();

    expect(els.spaceGovernanceShell.textContent).toContain("Agent Approvals");
    expect(els.spaceGovernanceShell.textContent).toContain("Update delivery status");
    expect(els.spaceGovernanceShell.textContent).not.toContain("cr-1");
    expect(els.spaceGovernanceShell.textContent).toContain("1 change across Project One");
    expect(els.spaceGovernanceShell.textContent).not.toContain("complete");
    expect(els.spaceGovernanceShell.querySelector(".agent-approval-layout")).toBeNull();
    expect(els.spaceGovernanceShell.querySelector(".agent-approval-table")).not.toBeNull();
    expect(els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]")).not.toBeNull();
  });

  it("opens and closes proposal details in a modal", () => {
    const { els, renderGovernanceHub, state } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='open-agent-change-request']")
      .click();

    expect(state.agentChangeRequestModalId).toBe("cr-1");
    expect(els.spaceGovernanceShell.querySelector(".agent-proposal-modal")).not.toBeNull();
    expect(els.spaceGovernanceShell.textContent).toContain("Project One");
    expect(els.spaceGovernanceShell.textContent).toContain("active");
    expect(els.spaceGovernanceShell.textContent).toContain("complete");

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));

    expect(state.agentChangeRequestModalId).toBe("");
    expect(els.spaceGovernanceShell.querySelector(".agent-proposal-modal")).toBeNull();
  });

  it("approves the selected operations in the current proposal", async () => {
    const { api, els, renderGovernanceHub } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='open-agent-change-request']")
      .click();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='approve-agent-change-request']")
      .click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        "/agent/change-requests/cr-1/approve-selected-operations",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ client_operation_ids: ["op-1"] }),
        })
      );
    });
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
    els.spaceGovernanceShell
      .querySelector("[data-space-action='open-agent-change-request']")
      .click();

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
    expect(els.spaceGovernanceShell.textContent).toContain("Approve selected (2)");
  });

  it("rejects the current modal proposal through the bulk endpoint", async () => {
    const { api, els, renderGovernanceHub } = createHarness();

    renderGovernanceHub();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='open-agent-change-request']")
      .click();
    els.spaceGovernanceShell
      .querySelector("[data-space-action='reject-agent-change-request']")
      .click();

    await vi.waitFor(() => {
      expect(api).toHaveBeenCalledWith(
        "/agent/change-requests/actions/reject-selected",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ change_request_ids: ["cr-1"] }),
        })
      );
    });
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
          body: JSON.stringify({ change_request_ids: ["cr-1"] }),
        })
      );
    });
    expect(renderCalls).toContain("agent-approvals");
  });
});
