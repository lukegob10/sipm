import { describe, expect, it, vi } from "vitest";

import { createSpaceGovernanceController } from "../../js/routes/spaces/interactions.js";
import { createSpaceGovernanceRenderer } from "../../js/routes/spaces/render.js";


function createHarness() {
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
    agentChangeRequestActiveId: "cr-1",
    agentChangeRequests: [
      {
        change_request_id: "cr-1",
        status: "pending",
        reason: "Update delivery status",
        proposed_by_label: "Scheduler",
        created_at: "2026-05-28T10:00:00Z",
        operation_count: 1,
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
    if (path === "/agent/change-requests?status=pending") {
      return Promise.resolve({ pending_count: 0, failed_count: 0, records: [] });
    }
    return Promise.resolve({});
  });
  let renderer;
  const renderGovernanceHub = (section = "agent-approvals") => renderer.renderGovernanceHub(section);
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
  return { api, controller, els, state, renderGovernanceHub };
}


describe("agent approvals governance UI", () => {
  it("renders pending requests with checkboxes and field diffs", () => {
    const { els, renderGovernanceHub } = createHarness();

    renderGovernanceHub();

    expect(els.spaceGovernanceShell.textContent).toContain("Agent Approvals");
    expect(els.spaceGovernanceShell.textContent).toContain("Update delivery status");
    expect(els.spaceGovernanceShell.textContent).toContain("Project One");
    expect(els.spaceGovernanceShell.textContent).toContain("active");
    expect(els.spaceGovernanceShell.textContent).toContain("complete");
    expect(els.spaceGovernanceShell.querySelector("[data-agent-change-request-checkbox]")).not.toBeNull();
  });

  it("approves selected requests through the bulk endpoint", async () => {
    const { api, els, renderGovernanceHub } = createHarness();

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
  });
});
