export function createSpaceGovernanceController({
  state,
  els,
  api,
  normalize,
  normalizeGovernanceSection,
  userIsGlobalAdmin,
  activeSpaceId,
  canManageSpaceMembership,
  effectiveDirectorySpaces,
  spaceNameForId,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  setSpaceGovernanceNotice,
  renderGovernanceHub,
  renderSpaceDirectoryModal,
  isSpaceGovernanceView,
  refreshSpaceContext,
  refreshFromServer,
  switchActiveSpace,
  showConfirmModal,
  copyText,
  buildAppUrl,
  buildResetPageUrl,
  trackWorkflow = null,
}) {
  let globalAdminsInFlight = null;
  const spaceMembersInFlight = {};
  const apiTokensInFlight = {};
  let agentChangeRequestsInFlight = null;
  let requestableSpacesInFlight = null;
  let accessRequestsInFlight = null;
  let reviewableAccessRequestsInFlight = null;

  function openSpaceCreateModal() {
    if (!userIsGlobalAdmin() || !els.spaceCreateModal) return;
    els.spaceCreateModal.classList.remove("hidden");
    els.spaceCreateModalForm?.reset();
    clearDeliverableFormNotice(els.spaceCreateStatus);
    window.setTimeout(() => {
      els.spaceCreateModalForm?.querySelector('[name="name"]')?.focus();
    }, 0);
  }

  function closeSpaceCreateModal() {
    els.spaceCreateModal?.classList.add("hidden");
  }

  function openSpaceMemberModal(spaceId = activeSpaceId()) {
    const targetSpaceId = String(spaceId || "").trim();
    if (!targetSpaceId || !canManageSpaceMembership(targetSpaceId) || !els.spaceMemberModalForm) return;
    const targetSpace = effectiveDirectorySpaces().find((space) => space.space_id === targetSpaceId)
      || (state.activeSpace?.space_id === targetSpaceId ? state.activeSpace : null);
    if (targetSpace?.space_kind === "personal") {
      setSpaceGovernanceNotice("Private spaces cannot add members.", "error", 5000);
      return;
    }
    els.spaceMemberModalForm.reset();
    els.spaceMemberModalForm.querySelector('[name="space_id"]').value = targetSpaceId;
    if (els.spaceMemberModalContext) {
      els.spaceMemberModalContext.textContent = `Adding a member to ${targetSpace?.name || targetSpaceId}.`;
    }
    clearDeliverableFormNotice(els.spaceMemberStatus);
    els.spaceMemberModal.classList.remove("hidden");
    window.setTimeout(() => {
      els.spaceMemberModalForm?.querySelector('[name="soeid"]')?.focus();
    }, 0);
  }

  function closeSpaceMemberModal() {
    els.spaceMemberModal?.classList.add("hidden");
  }

  function openSpaceDirectoryModal(spaceId) {
    const targetSpaceId = String(spaceId || state.spaceMembershipSpaceId || "").trim();
    if (!targetSpaceId || !els.spaceDirectoryModal) return;
    state.spaceMembershipSpaceId = targetSpaceId;
    state.spaceDirectoryModalOpen = true;
    renderSpaceDirectoryModal();
    els.spaceDirectoryModal.classList.remove("hidden");
    window.setTimeout(() => {
      els.spaceDirectoryModalClose?.focus();
    }, 0);
  }

  function closeSpaceDirectoryModal() {
    state.spaceDirectoryModalOpen = false;
    els.spaceDirectoryModal?.classList.add("hidden");
  }

  async function refreshGlobalAdmins() {
    if (!userIsGlobalAdmin()) {
      state.globalAdmins = [];
      state.globalAdminsLoaded = false;
      return;
    }
    if (globalAdminsInFlight) return globalAdminsInFlight;
    globalAdminsInFlight = api("/users/global-admins?active_only=false")
      .then((rows) => {
        state.globalAdmins = Array.isArray(rows) ? rows : [];
        state.globalAdminsLoaded = true;
        if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
        return state.globalAdmins;
      })
      .finally(() => {
        globalAdminsInFlight = null;
      });
    return globalAdminsInFlight;
  }

  async function issuePasswordResetForSoeid(soeid, expiresMinutes = null) {
    const soeidNorm = String(soeid || "").trim().toLowerCase();
    if (!soeidNorm) {
      throw new Error("SOEID is required.");
    }
    const body = {};
    if (expiresMinutes !== null && expiresMinutes !== undefined && String(expiresMinutes).trim() !== "") {
      body.expires_minutes = Number(expiresMinutes);
    }
    const issued = await api(`/users/by-soeid/${encodeURIComponent(soeidNorm)}/password-reset-request`, {
      method: "POST",
      ...(Object.keys(body).length ? { body: JSON.stringify(body) } : {}),
    });
    state.platformPasswordReset = {
      soeid: soeidNorm,
      temp_password: issued?.temp_password || "",
      expires_at: issued?.expires_at || "",
      reset_url: buildResetPageUrl(),
    };
    if (isSpaceGovernanceView(state.currentView)) {
      renderGovernanceHub();
    }
    return state.platformPasswordReset;
  }

  async function refreshApiTokens(userId, options = {}) {
    const targetUserId = String(userId || "").trim();
    if (!targetUserId || !userIsGlobalAdmin()) return [];
    const force = !!options.force;
    if (!force && state.apiTokensLoadedByUser[targetUserId]) {
      return state.apiTokensByUser[targetUserId] || [];
    }
    if (apiTokensInFlight[targetUserId]) return apiTokensInFlight[targetUserId];
    apiTokensInFlight[targetUserId] = api(`/users/${encodeURIComponent(targetUserId)}/api-tokens`)
      .then((rows) => {
        state.apiTokensByUser[targetUserId] = Array.isArray(rows) ? rows : [];
        state.apiTokensLoadedByUser[targetUserId] = true;
        if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
        return state.apiTokensByUser[targetUserId];
      })
      .finally(() => {
        delete apiTokensInFlight[targetUserId];
      });
    return apiTokensInFlight[targetUserId];
  }

  async function refreshAgentChangeRequests(options = {}) {
    const force = !!options.force;
    if (!force && state.agentChangeRequestsLoaded) return state.agentChangeRequests || [];
    if (agentChangeRequestsInFlight) return agentChangeRequestsInFlight;
    agentChangeRequestsInFlight = api("/agent/change-requests?status=pending")
      .then((payload) => {
        state.agentChangeRequests = Array.isArray(payload?.records) ? payload.records : [];
        state.agentChangeRequestPendingCount = Number(payload?.pending_count || 0);
        state.agentChangeRequestFailedCount = Number(payload?.failed_count || 0);
        state.agentChangeRequestsLoaded = true;
        const knownIds = new Set(state.agentChangeRequests.map((row) => row.change_request_id));
        state.agentChangeRequestSelectedIds = new Set(
          [...(state.agentChangeRequestSelectedIds || new Set())].filter((id) => knownIds.has(id))
        );
        state.agentChangeRequestSelectedOperationIds = Object.fromEntries(
          Object.entries(state.agentChangeRequestSelectedOperationIds || {})
            .filter(([id]) => knownIds.has(id))
        );
        if (!knownIds.has(state.agentChangeRequestModalId)) {
          state.agentChangeRequestModalId = "";
        }
        if (!knownIds.has(state.agentChangeRequestActiveId)) {
          state.agentChangeRequestActiveId = state.agentChangeRequests[0]?.change_request_id || "";
        }
        if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
        return state.agentChangeRequests;
      })
      .finally(() => {
        agentChangeRequestsInFlight = null;
      });
    return agentChangeRequestsInFlight;
  }

  async function refreshRequestableSpaces(options = {}) {
    const force = !!options.force;
    if (!force && state.requestableSpacesLoaded) return state.requestableSpaces || [];
    if (requestableSpacesInFlight) return requestableSpacesInFlight;
    requestableSpacesInFlight = api("/spaces/requestable")
      .then((rows) => {
        state.requestableSpaces = Array.isArray(rows) ? rows : [];
        state.requestableSpacesLoaded = true;
        if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
        return state.requestableSpaces;
      })
      .finally(() => {
        requestableSpacesInFlight = null;
      });
    return requestableSpacesInFlight;
  }

  async function refreshAccessRequests(options = {}) {
    const force = !!options.force;
    if (!force && state.spaceAccessRequestsLoaded) return state.spaceAccessRequests || [];
    if (accessRequestsInFlight) return accessRequestsInFlight;
    accessRequestsInFlight = api("/spaces/access-requests")
      .then((rows) => {
        state.spaceAccessRequests = Array.isArray(rows) ? rows : [];
        state.spaceAccessRequestsLoaded = true;
        if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
        return state.spaceAccessRequests;
      })
      .finally(() => {
        accessRequestsInFlight = null;
      });
    return accessRequestsInFlight;
  }

  async function refreshReviewableAccessRequests(options = {}) {
    const force = !!options.force;
    if (!force && state.reviewableAccessRequestsLoaded) return state.reviewableAccessRequests || [];
    if (reviewableAccessRequestsInFlight) return reviewableAccessRequestsInFlight;
    reviewableAccessRequestsInFlight = api("/spaces/access-requests/reviewable")
      .then((rows) => {
        state.reviewableAccessRequests = Array.isArray(rows) ? rows : [];
        state.reviewableAccessRequestsLoaded = true;
        if (isSpaceGovernanceView(state.currentView)) renderGovernanceHub();
        return state.reviewableAccessRequests;
      })
      .finally(() => {
        reviewableAccessRequestsInFlight = null;
      });
    return reviewableAccessRequestsInFlight;
  }

  async function refreshSpaceMembers(spaceId, options = {}) {
    const targetSpaceId = String(spaceId || "").trim();
    if (!targetSpaceId) return [];
    const force = !!options.force;
    if (!force && state.spaceMembersLoadedBySpace[targetSpaceId]) {
      return state.spaceMembersBySpace[targetSpaceId] || [];
    }
    if (spaceMembersInFlight[targetSpaceId]) {
      return spaceMembersInFlight[targetSpaceId];
    }
    spaceMembersInFlight[targetSpaceId] = api(`/spaces/${encodeURIComponent(targetSpaceId)}/members`)
      .then((rows) => {
        state.spaceMembersBySpace[targetSpaceId] = Array.isArray(rows) ? rows : [];
        state.spaceMembersLoadedBySpace[targetSpaceId] = true;
        if (isSpaceGovernanceView(state.currentView) && state.spaceMembershipSpaceId === targetSpaceId) {
          renderGovernanceHub();
        } else if (isSpaceGovernanceView(state.currentView) && targetSpaceId === activeSpaceId()) {
          renderGovernanceHub();
        }
        return state.spaceMembersBySpace[targetSpaceId];
      })
      .finally(() => {
        delete spaceMembersInFlight[targetSpaceId];
      });
    return spaceMembersInFlight[targetSpaceId];
  }

  async function handleSpaceGovernanceAction(button) {
    if (!button) return false;
    const action = button.getAttribute("data-space-action") || "";
    const spaceId = button.getAttribute("data-space-id") || "";
    const membershipId = button.getAttribute("data-membership-id") || "";
    const soeid = button.getAttribute("data-soeid") || "";
    const userId = button.getAttribute("data-user-id") || "";
    const tokenId = button.getAttribute("data-token-id") || "";
    const launchedFromDirectoryModal = !!button.closest("#space-directory-modal");
    if (action !== "toggle-member-menu") {
      state.spaceMembershipActionMenuId = "";
    }
    if (action === "select-section") {
      state.spaceAdminSection = normalizeGovernanceSection(button.getAttribute("data-section"));
      renderGovernanceHub();
      return true;
    }
    if (action === "select-platform-tool" && userIsGlobalAdmin()) {
      state.platformAccessPanel = button.getAttribute("data-platform-tool") || "administrators";
      renderGovernanceHub("platform-access");
      return true;
    }
    if (action === "open-agent-change-request") {
      state.agentChangeRequestActiveId = button.getAttribute("data-change-request-id") || "";
      const request = (state.agentChangeRequests || []).find(
        (row) => row.change_request_id === state.agentChangeRequestActiveId
      );
      if (request && !(state.agentChangeRequestSelectedOperationIds?.[request.change_request_id] instanceof Set)) {
        state.agentChangeRequestSelectedOperationIds = {
          ...(state.agentChangeRequestSelectedOperationIds || {}),
          [request.change_request_id]: new Set(
            (request.operations || []).map((operation) => operation.client_operation_id)
          ),
        };
      }
      renderGovernanceHub("agent-approvals");
      return true;
    }
    if (action === "toggle-agent-change-request-selection") {
      const rows = state.agentChangeRequests || [];
      const selected = new Set(state.agentChangeRequestSelectedIds || []);
      const allSelected = rows.length > 0 && rows.every(
        (row) => selected.has(row.change_request_id)
      );
      state.agentChangeRequestSelectedIds = allSelected
        ? new Set()
        : new Set(rows.map((row) => row.change_request_id));
      renderGovernanceHub("agent-approvals");
      return true;
    }
    if (
      action === "select-all-agent-change-request-operations"
      || action === "clear-agent-change-request-operations"
    ) {
      const id = state.agentChangeRequestActiveId || "";
      const request = (state.agentChangeRequests || []).find((row) => row.change_request_id === id);
      if (!request) return true;
      const selected = action === "select-all-agent-change-request-operations"
        ? new Set((request.operations || []).map((operation) => operation.client_operation_id))
        : new Set();
      state.agentChangeRequestSelectedOperationIds = {
        ...(state.agentChangeRequestSelectedOperationIds || {}),
        [id]: selected,
      };
      renderGovernanceHub("agent-approvals");
      return true;
    }
    if (action === "approve-agent-change-request" || action === "reject-agent-change-request") {
      const id = button.getAttribute("data-change-request-id") || state.agentChangeRequestActiveId || "";
      if (!id) return true;
      const approving = action === "approve-agent-change-request";
      const request = (state.agentChangeRequests || []).find(
        (row) => row.change_request_id === id
      );
      const storedSelection = state.agentChangeRequestSelectedOperationIds?.[id];
      const selectedOperationIds = [
        ...(storedSelection instanceof Set
          ? storedSelection
          : new Set((request?.operations || []).map((operation) => operation.client_operation_id))),
      ];
      if (approving && !selectedOperationIds.length) {
        setSpaceGovernanceNotice("Select at least one proposed change first.", "error", 5000);
        return true;
      }
      const operationCount = Number(request?.operation_count || 0);
      const partialApproval = approving && selectedOperationIds.length !== operationCount;
      if (!approving || partialApproval) {
        const confirmed = await showConfirmModal({
          title: approving ? "Approve Selected Changes" : "Reject Agent Proposal",
          message: approving
            ? `Approve ${selectedOperationIds.length} selected change${selectedOperationIds.length === 1 ? "" : "s"}? ${operationCount - selectedOperationIds.length} unselected change${operationCount - selectedOperationIds.length === 1 ? "" : "s"} will not be applied.`
            : "Reject this entire agent proposal?",
          confirmLabel: approving ? "Approve selected" : "Reject proposal",
        });
        if (!confirmed) return true;
      }
      try {
        const endpoint = approving
          ? `/agent/change-requests/${encodeURIComponent(id)}/approve-selected-operations`
          : "/agent/change-requests/actions/reject-selected";
        const result = await api(endpoint, {
          method: "POST",
          body: JSON.stringify(
            approving
              ? { client_operation_ids: selectedOperationIds }
              : { change_request_ids: [id] }
          ),
        });
        const selected = new Set(state.agentChangeRequestSelectedIds || []);
        selected.delete(id);
        state.agentChangeRequestSelectedIds = selected;
        delete state.agentChangeRequestSelectedOperationIds?.[id];
        state.agentChangeRequestsLoaded = false;
        await refreshAgentChangeRequests({ force: true });
        await refreshFromServer("all");
        renderGovernanceHub("agent-approvals");
        const completed = approving ? selectedOperationIds.length : Number(result?.rejected || 0);
        const approvalFailed = approving && result?.status !== "approved";
        const failed = approvalFailed ? 1 : Number(result?.failed || 0);
        setSpaceGovernanceNotice(
          approvalFailed
            ? "Selected changes failed revalidation and were not applied."
            : approving
            ? `Approved ${completed} selected change${completed === 1 ? "" : "s"}.`
            : `Rejected ${completed || 1} proposal${failed ? `; ${failed} failed revalidation` : ""}.`,
          failed ? "error" : "success",
          7000
        );
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Agent proposal review failed.", "error", 7000);
      }
      return true;
    }
    if (action === "approve-agent-change-requests" || action === "reject-agent-change-requests") {
      const ids = [...(state.agentChangeRequestSelectedIds || new Set())];
      if (!ids.length) {
        setSpaceGovernanceNotice("Select at least one agent proposal first.", "error", 5000);
        return true;
      }
      const approving = action === "approve-agent-change-requests";
      const confirmed = await showConfirmModal({
        title: approving ? "Approve Agent Proposals" : "Reject Agent Proposals",
        message: `${approving ? "Approve" : "Reject"} ${ids.length} selected agent proposal${ids.length === 1 ? "" : "s"}?`,
        confirmLabel: approving ? "Approve selected" : "Reject selected",
      });
      if (!confirmed) return true;
      try {
        const endpoint = approving
          ? "/agent/change-requests/actions/approve-selected"
          : "/agent/change-requests/actions/reject-selected";
        const result = await api(endpoint, {
          method: "POST",
          body: JSON.stringify({ change_request_ids: ids }),
        });
        state.agentChangeRequestSelectedIds = new Set();
        state.agentChangeRequestsLoaded = false;
        await refreshAgentChangeRequests({ force: true });
        await refreshFromServer("all");
        renderGovernanceHub("agent-approvals");
        const completed = approving
          ? Number(result?.approved || 0)
          : Number(result?.rejected || 0);
        const failed = Number(result?.failed || 0);
        setSpaceGovernanceNotice(
          `${approving ? "Approved" : "Rejected"} ${completed} proposal${completed === 1 ? "" : "s"}${failed ? `; ${failed} failed revalidation` : ""}.`,
          failed ? "error" : "success",
          7000
        );
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Agent proposal review failed.", "error", 7000);
      }
      return true;
    }
    if (action === "open-directory-space") {
      openSpaceDirectoryModal(spaceId);
      return true;
    }
    if (action === "close-directory-space-modal") {
      closeSpaceDirectoryModal();
      return true;
    }
    if (action === "preview-space") {
      state.spaceMembershipSpaceId = spaceId;
      renderGovernanceHub();
      return true;
    }
    if (action === "open-create-space-modal") {
      openSpaceCreateModal();
      return true;
    }
    if (action === "request-space-access") {
      if (!spaceId) return true;
      state.accessRequestSubmittingSpaceId = spaceId;
      renderGovernanceHub();
      try {
        await api(`/spaces/${encodeURIComponent(spaceId)}/access-requests`, {
          method: "POST",
          body: JSON.stringify({ requested_role: "member" }),
        });
        state.requestableSpacesLoaded = false;
        state.spaceAccessRequestsLoaded = false;
        await Promise.all([
          refreshRequestableSpaces({ force: true }),
          refreshAccessRequests({ force: true }),
        ]);
        setSpaceGovernanceNotice(`Requested access to ${spaceNameForId(spaceId) || "the selected space"}.`, "success", 4500);
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", "access_request", "success", { source: "lobby" });
        }
      } catch (err) {
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", "access_request", "failure", { source: "lobby" });
        }
        setSpaceGovernanceNotice(err?.message || "Access request failed.", "error", 7000);
      } finally {
        state.accessRequestSubmittingSpaceId = "";
        renderGovernanceHub();
      }
      return true;
    }
    if (action === "cancel-access-request") {
      const requestId = button.getAttribute("data-request-id") || "";
      if (!requestId) return true;
      try {
        await api(`/spaces/access-requests/${encodeURIComponent(requestId)}`, { method: "DELETE" });
        state.spaceAccessRequestsLoaded = false;
        state.requestableSpacesLoaded = false;
        await Promise.all([
          refreshAccessRequests({ force: true }),
          refreshRequestableSpaces({ force: true }),
        ]);
        setSpaceGovernanceNotice("Access request canceled.", "success", 3500);
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Cancel request failed.", "error", 7000);
      }
      return true;
    }
    if (action === "approve-access-request" || action === "reject-access-request") {
      const requestId = button.getAttribute("data-request-id") || "";
      if (!requestId) return true;
      const approving = action === "approve-access-request";
      try {
        await api(`/spaces/access-requests/${encodeURIComponent(requestId)}/${approving ? "approve" : "reject"}`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.reviewableAccessRequestsLoaded = false;
        await refreshReviewableAccessRequests({ force: true });
        if (approving && spaceId) {
          state.spaceMembersLoadedBySpace[spaceId] = false;
          await refreshSpaceMembers(spaceId, { force: true });
        }
        setSpaceGovernanceNotice(`Access request ${approving ? "approved" : "rejected"}.`, "success", 4500);
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Access request review failed.", "error", 7000);
      }
      return true;
    }
    if (action === "open-member-modal") {
      if (launchedFromDirectoryModal) {
        closeSpaceDirectoryModal();
      }
      openSpaceMemberModal(spaceId || activeSpaceId());
      return true;
    }
    if (action === "switch-space") {
      if (launchedFromDirectoryModal) {
        closeSpaceDirectoryModal();
      }
      await switchActiveSpace(spaceId);
      return true;
    }
    if (action === "toggle-member-menu") {
      state.spaceMembershipActionMenuId = state.spaceMembershipActionMenuId === membershipId ? "" : membershipId;
      renderGovernanceHub();
      return true;
    }
    if (action === "toggle-space-active" && userIsGlobalAdmin()) {
      const nextActive = normalize(button.getAttribute("data-next-active")) === "true";
      const targetName = spaceNameForId(spaceId) || "this space";
      const confirmed = await showConfirmModal({
        title: nextActive ? "Reactivate Space" : "Archive Space",
        message: nextActive
          ? `Reactivate ${targetName}?`
          : `Archive ${targetName}? It will stop appearing in active space lists until reactivated.`,
        confirmLabel: nextActive ? "Reactivate" : "Archive",
      });
      if (!confirmed) return true;
      try {
        const updated = await api(`/spaces/${encodeURIComponent(spaceId)}`, {
          method: "PATCH",
          body: JSON.stringify({ is_active: nextActive }),
        });
        if (updated?.is_active === false) {
          state.archivedSpacesById[updated.space_id] = updated;
        } else if (updated?.space_id) {
          delete state.archivedSpacesById[updated.space_id];
        }
        await refreshSpaceContext();
        state.spaceMembershipSpaceId = updated?.space_id || state.spaceMembershipSpaceId;
        state.spaceAdminSection = "space-directory";
        if (launchedFromDirectoryModal) {
          closeSpaceDirectoryModal();
        }
        setSpaceGovernanceNotice(
          `${nextActive ? "Reactivated" : "Archived"} ${updated?.name || targetName}.`,
          "success",
          4500
        );
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", "update", "success", { source: "space_governance" });
        }
      } catch (err) {
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", "update", "failure", { source: "space_governance" });
        }
        setSpaceGovernanceNotice(err?.message || "Space update failed.", "error", 7000);
      }
      return true;
    }
    if (action === "toggle-space-member-role" || action === "toggle-space-member-status" || action === "delete-space-member") {
      if (!membershipId || !spaceId || !canManageSpaceMembership(spaceId)) {
        setSpaceGovernanceNotice("Switch into this space to manage its memberships.", "error", 7000);
        return true;
      }
      try {
        if (action === "toggle-space-member-role") {
          const nextRole = (button.getAttribute("data-next-role") || "").trim();
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
            method: "PATCH",
            body: JSON.stringify({ role: nextRole }),
          });
        } else if (action === "toggle-space-member-status") {
          const nextStatus = (button.getAttribute("data-next-status") || "").trim();
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
            method: "PATCH",
            body: JSON.stringify({ status: nextStatus }),
          });
        } else {
          const confirmed = await showConfirmModal({
            title: "Remove Space Member",
            message: "Remove this member from the selected space?",
            confirmLabel: "Remove",
          });
          if (!confirmed) return true;
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/${encodeURIComponent(membershipId)}`, {
            method: "DELETE",
          });
        }
        state.spaceMembersLoadedBySpace[spaceId] = false;
        await refreshSpaceMembers(spaceId, { force: true });
        setSpaceGovernanceNotice("Membership updated.", "success", 3500);
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", action === "delete-space-member" ? "delete" : "update", "success", { source: "space_governance" });
        }
      } catch (err) {
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", action === "delete-space-member" ? "delete" : "update", "failure", { source: "space_governance" });
        }
        setSpaceGovernanceNotice(err?.message || "Membership update failed.", "error", 7000);
      }
      return true;
    }
    if (action === "issue-password-reset" && userIsGlobalAdmin()) {
      const confirmed = await showConfirmModal({
        title: "Issue Password Reset",
        message: `Issue a one-time password reset for ${soeid}? This will invalidate their active sessions.`,
        confirmLabel: "Issue Reset",
      });
      if (!confirmed) return true;
      try {
        await issuePasswordResetForSoeid(soeid);
        setSpaceGovernanceNotice(`Issued password reset for ${soeid}.`, "success", 4500);
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Password reset failed.", "error", 7000);
      }
      return true;
    }
    if (action === "copy-temp-password" || action === "copy-reset-link") {
      const issued = state.platformPasswordReset;
      const text = action === "copy-temp-password" ? issued?.temp_password : issued?.reset_url;
      try {
        await copyText(text);
        setSpaceGovernanceNotice(action === "copy-temp-password" ? "Temporary password copied." : "Reset page copied.", "success", 3000);
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Copy failed.", "error", 5000);
      }
      return true;
    }
    if (action === "toggle-public-program-dashboard") {
      if (!spaceId || !canManageSpaceMembership(spaceId)) {
        setSpaceGovernanceNotice("Space admin access is required to expose this dashboard.", "error", 7000);
        return true;
      }
      const nextEnabled = normalize(button.getAttribute("data-next-enabled")) === "true";
      const targetName = spaceNameForId(spaceId) || "this space";
      const confirmed = await showConfirmModal({
        title: nextEnabled ? "Expose Public Dashboard" : "Disable Public Dashboard",
        message: nextEnabled
          ? `Expose the public program dashboard for ${targetName}? Anyone with the URL can view it.`
          : `Disable the public program dashboard for ${targetName}? Existing links will stop working.`,
        confirmLabel: nextEnabled ? "Expose Dashboard" : "Disable Dashboard",
      });
      if (!confirmed) return true;
      try {
        const updated = await api(`/spaces/${encodeURIComponent(spaceId)}`, {
          method: "PATCH",
          body: JSON.stringify({ public_program_dashboard_enabled: nextEnabled }),
        });
        if (updated?.space_id) {
          state.spaces = (state.spaces || []).map((space) => space.space_id === updated.space_id ? updated : space);
          if (state.archivedSpacesById?.[updated.space_id]) state.archivedSpacesById[updated.space_id] = updated;
        }
        renderGovernanceHub();
        const publicUrl = updated?.slug
          ? new URL(buildAppUrl(`/public/program-dashboard/${encodeURIComponent(updated.slug)}`), window.location.origin).toString()
          : "";
        setSpaceGovernanceNotice(
          nextEnabled && publicUrl
            ? `Public dashboard exposed: ${publicUrl}`
            : `Public dashboard disabled for ${updated?.name || targetName}.`,
          "success",
          9000
        );
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", "update", "success", { source: "public_program_dashboard" });
        }
      } catch (err) {
        if (typeof trackWorkflow === "function") {
          trackWorkflow("spaces", "update", "failure", { source: "public_program_dashboard" });
        }
        setSpaceGovernanceNotice(err?.message || "Public dashboard setting update failed.", "error", 7000);
      }
      return true;
    }
    if (action === "copy-api-token") {
      try {
        await copyText(state.issuedApiToken?.token);
        setSpaceGovernanceNotice("API token copied.", "success", 3000);
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "Copy failed.", "error", 5000);
      }
      return true;
    }
    if (action === "clear-api-token-result") {
      state.issuedApiToken = null;
      renderGovernanceHub("platform-access");
      return true;
    }
    if (action === "refresh-api-tokens" && userIsGlobalAdmin()) {
      await refreshApiTokens(userId, { force: true });
      return true;
    }
    if (action === "revoke-api-token" && userIsGlobalAdmin()) {
      const confirmed = await showConfirmModal({
        title: "Revoke API Token",
        message: "Revoke this service-account API token?",
        confirmLabel: "Revoke",
      });
      if (!confirmed) return true;
      try {
        await api(`/users/${encodeURIComponent(userId)}/api-tokens/${encodeURIComponent(tokenId)}`, { method: "DELETE" });
        state.apiTokensLoadedByUser[userId] = false;
        await refreshApiTokens(userId, { force: true });
        setSpaceGovernanceNotice("API token revoked.", "success", 4500);
      } catch (err) {
        setSpaceGovernanceNotice(err?.message || "API token revoke failed.", "error", 7000);
      }
      return true;
    }
    if (action === "clear-reset-result") {
      state.platformPasswordReset = null;
      renderGovernanceHub();
      return true;
    }
    if (action === "revoke-global-admin" && userIsGlobalAdmin()) {
      const confirmed = await showConfirmModal({
        title: "Revoke Global Admin",
        message: `Revoke global admin from ${soeid}?`,
        confirmLabel: "Revoke",
      });
      if (!confirmed) return true;
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "DELETE" });
        state.globalAdminsLoaded = false;
        await refreshGlobalAdmins();
        await refreshFromServer("users");
        setSpaceGovernanceNotice(`Revoked global admin from ${soeid}.`, "success", 4500);
        if (typeof trackWorkflow === "function") {
          trackWorkflow("users", "update", "success", { source: "space_governance" });
        }
      } catch (err) {
        if (typeof trackWorkflow === "function") {
          trackWorkflow("users", "update", "failure", { source: "space_governance" });
        }
        setSpaceGovernanceNotice(err?.message || "Revoke failed.", "error", 7000);
      }
      return true;
    }
    if (action === "grant-global-admin" && userIsGlobalAdmin()) {
      const confirmed = await showConfirmModal({
        title: "Grant Global Admin",
        message: `Grant global admin to ${soeid}?`,
        confirmLabel: "Grant",
      });
      if (!confirmed) return true;
      try {
        await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "POST" });
        state.globalAdminsLoaded = false;
        await refreshGlobalAdmins();
        await refreshFromServer("users");
        setSpaceGovernanceNotice(`Granted global admin to ${soeid}.`, "success", 4500);
        if (typeof trackWorkflow === "function") {
          trackWorkflow("users", "update", "success", { source: "space_governance" });
        }
      } catch (err) {
        if (typeof trackWorkflow === "function") {
          trackWorkflow("users", "update", "failure", { source: "space_governance" });
        }
        setSpaceGovernanceNotice(err?.message || "Grant failed.", "error", 7000);
      }
      return true;
    }
    return false;
  }

  function bindSpaceAdminControls() {
    if (els.spaceCreateModalClose && !els.spaceCreateModalClose._bound) {
      els.spaceCreateModalClose.addEventListener("click", closeSpaceCreateModal);
      els.spaceCreateModalClose._bound = true;
    }
    if (els.spaceCreateModal && !els.spaceCreateModal._bound) {
      els.spaceCreateModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSpaceCreateModal);
      els.spaceCreateModal._bound = true;
    }
    if (els.spaceCreateModalForm && !els.spaceCreateModalForm._bound) {
      els.spaceCreateModalForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!userIsGlobalAdmin()) return;
        const data = new FormData(els.spaceCreateModalForm);
        const name = String(data.get("name") || "").trim();
        const slug = String(data.get("slug") || "").trim();
        if (!name) {
          setDeliverableFormNotice(els.spaceCreateStatus, "Space name is required.", "error");
          return;
        }
        try {
          const created = await api("/spaces", {
            method: "POST",
            body: JSON.stringify({ name, slug: slug || null }),
          });
          clearDeliverableFormNotice(els.spaceCreateStatus);
          closeSpaceCreateModal();
          setSpaceGovernanceNotice(`Created ${created?.name || name}.`, "success", 4500);
          await refreshSpaceContext();
          state.spaceMembershipSpaceId = created?.space_id || state.spaceMembershipSpaceId;
          state.spaceAdminSection = "space-directory";
          renderGovernanceHub();
          if (typeof trackWorkflow === "function") {
            trackWorkflow("spaces", "create", "success", { source: "space_governance" });
          }
        } catch (err) {
          if (typeof trackWorkflow === "function") {
            trackWorkflow("spaces", "create", "failure", { source: "space_governance" });
          }
          setDeliverableFormNotice(els.spaceCreateStatus, err?.message || "Space create failed.", "error");
        }
      });
      els.spaceCreateModalForm._bound = true;
    }

    if (els.spaceMemberModalClose && !els.spaceMemberModalClose._bound) {
      els.spaceMemberModalClose.addEventListener("click", closeSpaceMemberModal);
      els.spaceMemberModalClose._bound = true;
    }
    if (els.spaceMemberModal && !els.spaceMemberModal._bound) {
      els.spaceMemberModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSpaceMemberModal);
      els.spaceMemberModal._bound = true;
    }
    if (els.spaceMemberModalForm && !els.spaceMemberModalForm._bound) {
      els.spaceMemberModalForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(els.spaceMemberModalForm);
        const spaceId = String(data.get("space_id") || "").trim();
        const soeid = String(data.get("soeid") || "").trim().toLowerCase();
        const role = String(data.get("role") || "member");
        const status = String(data.get("status") || "active");
        if (!spaceId) {
          setDeliverableFormNotice(els.spaceMemberStatus, "Select a space first.", "error");
          return;
        }
        if (!canManageSpaceMembership(spaceId)) {
          setDeliverableFormNotice(els.spaceMemberStatus, "Switch into this space to manage its memberships.", "error");
          return;
        }
        if (!soeid) {
          setDeliverableFormNotice(els.spaceMemberStatus, "SOEID is required.", "error");
          return;
        }
        try {
          await api(`/spaces/${encodeURIComponent(spaceId)}/members/by-soeid`, {
            method: "POST",
            body: JSON.stringify({ soeid, role, status }),
          });
          state.spaceMembersLoadedBySpace[spaceId] = false;
          await refreshSpaceMembers(spaceId, { force: true });
          closeSpaceMemberModal();
          setSpaceGovernanceNotice(`Added ${soeid} to ${spaceNameForId(spaceId) || "the selected space"}.`, "success", 4500);
          if (typeof trackWorkflow === "function") {
            trackWorkflow("spaces", "create", "success", { source: "space_governance" });
          }
        } catch (err) {
          if (typeof trackWorkflow === "function") {
            trackWorkflow("spaces", "create", "failure", { source: "space_governance" });
          }
          setDeliverableFormNotice(els.spaceMemberStatus, err?.message || "Add member failed.", "error");
        }
      });
      els.spaceMemberModalForm._bound = true;
    }

    if (els.spaceDirectoryModalClose && !els.spaceDirectoryModalClose._bound) {
      els.spaceDirectoryModalClose.addEventListener("click", closeSpaceDirectoryModal);
      els.spaceDirectoryModalClose._bound = true;
    }
    if (els.spaceDirectoryModal && !els.spaceDirectoryModal._bound) {
      els.spaceDirectoryModal.querySelector(".modal-backdrop")?.addEventListener("click", closeSpaceDirectoryModal);
      els.spaceDirectoryModal.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-space-action]");
        if (!button) return;
        await handleSpaceGovernanceAction(button);
      });
      els.spaceDirectoryModal._bound = true;
    }

    if (els.spaceGovernanceShell && !els.spaceGovernanceShell._bound) {
      els.spaceGovernanceShell.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-space-action]");
        if (!button) return;
        await handleSpaceGovernanceAction(button);
      });
      els.spaceGovernanceShell.addEventListener("input", (event) => {
        const input = event.target.closest("#lobby-request-space-search");
        if (!input) return;
        state.lobbyRequestSearch = input.value || "";
        const query = normalize(state.lobbyRequestSearch);
        let visibleCount = 0;
        els.spaceGovernanceShell.querySelectorAll("[data-lobby-request-row]").forEach((row) => {
          const matches = !query || normalize(row.getAttribute("data-search-text") || "").includes(query);
          row.hidden = !matches;
          if (matches) visibleCount += 1;
        });
        const empty = els.spaceGovernanceShell.querySelector("[data-lobby-request-empty]");
        if (empty) empty.hidden = !query || visibleCount > 0;
      });
      els.spaceGovernanceShell.addEventListener("submit", async (event) => {
        const form = event.target.closest("form");
        if (!form) return;
        if (form.id === "space-personal-create-form") {
          event.preventDefault();
          state.lobbyPersonalSpaceCreating = true;
          renderGovernanceHub();
          try {
            const created = await api("/spaces/personal", {
              method: "POST",
              body: JSON.stringify({}),
            });
            if (created?.space_id && !state.spaces.some((space) => space.space_id === created.space_id)) {
              state.spaces = [...state.spaces, created];
            }
            let switched = false;
            if (created?.space_id) {
              switched = await switchActiveSpace(created.space_id);
            }
            if (!switched) {
              await refreshSpaceContext();
            }
            form.reset();
            state.requestableSpacesLoaded = false;
            state.spaceAccessRequestsLoaded = false;
            setSpaceGovernanceNotice(`Created ${created?.name || "your private space"}.`, "success", 4500);
            if (typeof trackWorkflow === "function") {
              trackWorkflow("spaces", "create_personal", "success", { source: "lobby" });
            }
          } catch (err) {
            if (typeof trackWorkflow === "function") {
              trackWorkflow("spaces", "create_personal", "failure", { source: "lobby" });
            }
            setSpaceGovernanceNotice(err?.message || "Private space create failed.", "error", 7000);
          } finally {
            state.lobbyPersonalSpaceCreating = false;
            if (isSpaceGovernanceView(state.currentView)) {
              renderGovernanceHub();
            }
          }
          return;
        }
        if (form.id === "space-platform-access-form") {
          event.preventDefault();
          if (!userIsGlobalAdmin()) return;
          const data = new FormData(form);
          const soeid = String(data.get("soeid") || "").trim().toLowerCase();
          if (!soeid) {
            setSpaceGovernanceNotice("SOEID is required.", "error", 5000);
            return;
          }
          try {
            await api(`/users/by-soeid/${encodeURIComponent(soeid)}/global-admin`, { method: "POST" });
            state.globalAdminsLoaded = false;
            await refreshGlobalAdmins();
            await refreshFromServer("users");
            form.reset();
            setSpaceGovernanceNotice(`Granted global admin to ${soeid}.`, "success", 4500);
            if (typeof trackWorkflow === "function") {
              trackWorkflow("users", "update", "success", { source: "space_governance" });
            }
          } catch (err) {
            if (typeof trackWorkflow === "function") {
              trackWorkflow("users", "update", "failure", { source: "space_governance" });
            }
            setSpaceGovernanceNotice(err?.message || "Grant failed.", "error", 7000);
          }
          return;
        }
        if (form.id === "space-password-reset-form") {
          event.preventDefault();
          if (!userIsGlobalAdmin()) return;
          const data = new FormData(form);
          const soeid = String(data.get("soeid") || "").trim().toLowerCase();
          const expiresMinutesRaw = String(data.get("expires_minutes") || "").trim();
          if (!soeid) {
            setSpaceGovernanceNotice("SOEID is required.", "error", 5000);
            return;
          }
          if (expiresMinutesRaw) {
            const expiresMinutes = Number(expiresMinutesRaw);
            if (!Number.isInteger(expiresMinutes) || expiresMinutes < 5 || expiresMinutes > 1440) {
              setSpaceGovernanceNotice("Expiration must be a whole number between 5 and 1440 minutes.", "error", 6000);
              return;
            }
          }
          try {
            await issuePasswordResetForSoeid(soeid, expiresMinutesRaw || null);
            form.reset();
            setSpaceGovernanceNotice(`Issued password reset for ${soeid}.`, "success", 4500);
          } catch (err) {
            setSpaceGovernanceNotice(err?.message || "Password reset failed.", "error", 7000);
          }
          return;
        }
        if (form.id === "service-account-token-form") {
          event.preventDefault();
          if (!userIsGlobalAdmin()) return;
          const data = new FormData(form);
          const soeid = String(data.get("soeid") || "").trim();
          const name = String(data.get("name") || "").trim();
          const expiresRaw = String(data.get("expires_at") || "").trim();
          if (!soeid) {
            setSpaceGovernanceNotice("SOEID is required.", "error", 5000);
            return;
          }
          if (!name) {
            setSpaceGovernanceNotice("Token name is required.", "error", 5000);
            return;
          }
          const body = { name };
          if (expiresRaw) body.expires_at = new Date(expiresRaw).toISOString();
          try {
            state.spaceAdminSection = "platform-access";
            const user = await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, {
              method: "PATCH",
              body: JSON.stringify({ is_service_account: true }),
            });
            const issued = await api(`/users/${encodeURIComponent(user.user_id)}/api-tokens`, {
              method: "POST",
              body: JSON.stringify(body),
            });
            state.issuedApiToken = {
              ...issued,
              user_label: user?.display_name || user?.soeid || soeid,
            };
            form.reset();
            state.apiTokensLoadedByUser[user.user_id] = false;
            await refreshFromServer("users");
            state.spaceAdminSection = "platform-access";
            await refreshApiTokens(user.user_id, { force: true });
            renderGovernanceHub("platform-access");
            setSpaceGovernanceNotice("API token generated. Copy it now.", "success", 7000);
          } catch (err) {
            setSpaceGovernanceNotice(err?.message || "Token generation failed.", "error", 7000);
          }
          return;
        }
        if (form.classList.contains("api-token-issue-form")) {
          event.preventDefault();
          if (!userIsGlobalAdmin()) return;
          const userId = String(form.getAttribute("data-user-id") || "").trim();
          const data = new FormData(form);
          const name = String(data.get("name") || "").trim();
          const expiresRaw = String(data.get("expires_at") || "").trim();
          if (!name) {
            setSpaceGovernanceNotice("Token name is required.", "error", 5000);
            return;
          }
          const body = { name };
          if (expiresRaw) body.expires_at = new Date(expiresRaw).toISOString();
          try {
            state.spaceAdminSection = "platform-access";
            const issued = await api(`/users/${encodeURIComponent(userId)}/api-tokens`, {
              method: "POST",
              body: JSON.stringify(body),
            });
            const user = (state.users || []).find((row) => row.user_id === userId);
            state.issuedApiToken = {
              ...issued,
              user_label: user?.display_name || user?.soeid || userId,
            };
            form.reset();
            state.apiTokensLoadedByUser[userId] = false;
            await refreshApiTokens(userId, { force: true });
            renderGovernanceHub("platform-access");
            setSpaceGovernanceNotice("API token generated. Copy it now.", "success", 7000);
          } catch (err) {
            setSpaceGovernanceNotice(err?.message || "Token generation failed.", "error", 7000);
          }
          return;
        }
      });
      els.spaceGovernanceShell.addEventListener("input", (event) => {
        if (event.target.id === "space-directory-search") {
          const nextValue = event.target.value || "";
          state.spaceDirectoryQuery = nextValue;
          renderGovernanceHub();
          const input = els.spaceGovernanceShell?.querySelector("#space-directory-search");
          if (input) {
            input.focus();
            input.value = nextValue;
            input.setSelectionRange(nextValue.length, nextValue.length);
          }
        }
      });
      els.spaceGovernanceShell.addEventListener("change", (event) => {
        if (event.target.id === "space-directory-show-archived") {
          state.spaceDirectoryShowArchived = !!event.target.checked;
          renderGovernanceHub();
        }
        if (event.target.matches("[data-agent-change-request-checkbox]")) {
          const id = event.target.getAttribute("data-change-request-id") || "";
          const selected = new Set(state.agentChangeRequestSelectedIds || []);
          if (event.target.checked) selected.add(id);
          else selected.delete(id);
          state.agentChangeRequestSelectedIds = selected;
          renderGovernanceHub("agent-approvals");
        }
        if (event.target.matches("[data-agent-change-operation-checkbox]")) {
          const requestId = state.agentChangeRequestActiveId || "";
          const operationId = event.target.getAttribute("data-client-operation-id") || "";
          const request = (state.agentChangeRequests || []).find(
            (row) => row.change_request_id === requestId
          );
          const storedSelection = state.agentChangeRequestSelectedOperationIds?.[requestId];
          const selected = new Set(
            storedSelection instanceof Set
              ? storedSelection
              : (request?.operations || []).map((operation) => operation.client_operation_id)
          );
          if (event.target.checked) selected.add(operationId);
          else selected.delete(operationId);
          state.agentChangeRequestSelectedOperationIds = {
            ...(state.agentChangeRequestSelectedOperationIds || {}),
            [requestId]: selected,
          };
          renderGovernanceHub("agent-approvals");
        }
      });
      els.spaceGovernanceShell._bound = true;
    }

    if (!document._spaceGovernanceEscapeBound) {
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        if (els.spaceCreateModal && !els.spaceCreateModal.classList.contains("hidden")) {
          closeSpaceCreateModal();
          return;
        }
        if (els.spaceDirectoryModal && !els.spaceDirectoryModal.classList.contains("hidden")) {
          closeSpaceDirectoryModal();
          return;
        }
        if (els.spaceMemberModal && !els.spaceMemberModal.classList.contains("hidden")) {
          closeSpaceMemberModal();
          return;
        }
        if (state.issuedApiToken?.token) {
          state.issuedApiToken = null;
          renderGovernanceHub("platform-access");
          return;
        }
        if (state.agentChangeRequestModalId) {
          state.agentChangeRequestModalId = "";
          renderGovernanceHub("agent-approvals");
        }
      });
      document.addEventListener("click", (event) => {
        if (!state.spaceMembershipActionMenuId) return;
        const eventPath = typeof event.composedPath === "function" ? event.composedPath() : [];
        const clickedInsideMemberActions = eventPath.some((node) => (
          node
          && node.classList
          && (node.classList.contains("space-member-actions") || node.classList.contains("space-action-menu"))
        ));
        if (clickedInsideMemberActions) return;
        state.spaceMembershipActionMenuId = "";
        renderGovernanceHub();
      });
      document._spaceGovernanceEscapeBound = true;
    }
  }

  return {
    bindSpaceAdminControls,
    closeSpaceCreateModal,
    closeSpaceDirectoryModal,
    closeSpaceMemberModal,
    openSpaceCreateModal,
    openSpaceDirectoryModal,
    openSpaceMemberModal,
    refreshApiTokens,
    refreshAccessRequests,
    refreshAgentChangeRequests,
    refreshGlobalAdmins,
    refreshRequestableSpaces,
    refreshReviewableAccessRequests,
    refreshSpaceMembers,
  };
}
