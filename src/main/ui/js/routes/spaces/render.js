export function createSpaceGovernanceRenderer({
  state,
  els,
  normalize,
  normalizeSpaceRole,
  activeSpaceId,
  userIsGlobalAdmin,
  currentSpaceRoleLabel,
  canManageSpaceMembership,
  esc,
  escapeAttr,
  formatDateTime,
  effectiveDirectorySpaces,
  governanceSections,
  resolveGovernanceSection,
  refreshGlobalAdmins,
  refreshAccessRequests,
  refreshAgentChangeRequests,
  refreshApiTokens,
  refreshRequestableSpaces,
  refreshReviewableAccessRequests,
  refreshSpaceMembers,
  closeSpaceDirectoryModal,
  setSpaceGovernanceNotice,
  buildAppUrl,
}) {
  function memberLabel(member) {
    const row = member || {};
    const userId = row.user_id || "";
    const soeid = row.user_soeid || "";
    const displayName = row.user_display_name || "";
    const email = row.user_email || "";
    if (displayName && soeid) return `${displayName} (${soeid})`;
    if (displayName) return displayName;
    if (soeid) return soeid;
    if (email) return email;
    const user = state.users.find((item) => item.user_id === userId);
    if (!user) return userId;
    const title = user.display_name || user.soeid || user.user_id;
    if (user.soeid) return `${title} (${user.soeid})`;
    return title;
  }

  function directorySpaceById(spaceId) {
    const targetSpaceId = String(spaceId || "").trim();
    if (!targetSpaceId) return null;
    return effectiveDirectorySpaces().find((space) => space.space_id === targetSpaceId)
      || (state.spaces || []).find((space) => space.space_id === targetSpaceId)
      || Object.values(state.archivedSpacesById || {}).find((space) => space?.space_id === targetSpaceId)
      || null;
  }

  function ensureSelectedDirectorySpace() {
    const spaces = effectiveDirectorySpaces();
    const availableIds = new Set(spaces.map((space) => space.space_id));
    if (!state.spaceMembershipSpaceId || !availableIds.has(state.spaceMembershipSpaceId)) {
      state.spaceMembershipSpaceId = activeSpaceId() || spaces[0]?.space_id || "";
    }
    return spaces.find((space) => space.space_id === state.spaceMembershipSpaceId) || null;
  }

  function roleBadgeLabelForSpace(space) {
    if (!space) return "";
    if (space.space_id === activeSpaceId()) return currentSpaceRoleLabel(state.activeSpace);
    if (userIsGlobalAdmin()) return "Global Admin";
    return "Accessible";
  }

  function roleBadgeClass(label) {
    const normalizedLabel = normalize(label);
    if (normalizedLabel.includes("admin")) return "";
    if (normalizedLabel === "accessible") return "muted";
    return "muted";
  }

  function disabledReasonAttr(disabled, reason) {
    if (!disabled) return "";
    const text = escapeAttr(reason);
    return ` disabled title="${text}" aria-label="${text}"`;
  }

  function membershipSummaryForSpace(spaceId) {
    const members = state.spaceMembersBySpace[spaceId] || [];
    return {
      total: members.length,
      active: members.filter((row) => normalize(row.status) === "active").length,
      admins: members.filter((row) => normalizeSpaceRole(row.role) === "space_admin" && normalize(row.status) === "active").length,
      inactive: members.filter((row) => normalize(row.status) === "inactive").length,
    };
  }

  function renderGovernanceNotice() {
    if (!state.spaceGovernanceNotice?.text) return "";
    const toneClass = state.spaceGovernanceNotice.tone === "error"
      ? " notice-error"
      : (state.spaceGovernanceNotice.tone === "success" ? " notice-success" : "");
    return `<p class="form-notice space-governance-notice${toneClass}" role="status" aria-live="polite">${esc(state.spaceGovernanceNotice.text)}</p>`;
  }

  function renderMembershipTable(spaceId) {
    const canManage = canManageSpaceMembership(spaceId) && !state.spaceSwitching;
    const members = state.spaceMembersBySpace[spaceId] || [];
    if (!members.length) {
      return `
        <div class="space-empty-card">
          <h3>No members yet</h3>
          <p class="muted">Add people to this space so ownership, roles, and access can be managed without leaving the governance hub.</p>
        </div>
      `;
    }
    const rows = members.map((row) => {
      const nextRole = normalizeSpaceRole(row.role) === "space_admin" ? "member" : "space_admin";
      const nextStatus = normalize(row.status) === "active" ? "inactive" : "active";
      const menuOpen = state.spaceMembershipActionMenuId === row.membership_id;
      const soeid = row.user_soeid ? `<span>${esc(row.user_soeid)}</span>` : "";
      const email = row.user_email ? `<span>${esc(row.user_email)}</span>` : "";
      return `<tr data-membership-id="${escapeAttr(row.membership_id)}">
        <td>
          <div class="space-member-cell">
            <strong>${esc(memberLabel(row))}</strong>
            <div class="space-member-meta">${soeid}${soeid && email ? " / " : ""}${email}</div>
          </div>
        </td>
        <td><span class="pill ${normalizeSpaceRole(row.role) === "space_admin" ? "" : "muted"}">${esc(row.role)}</span></td>
        <td><span class="pill ${normalize(row.status) === "active" ? "positive" : "muted"}">${esc(row.status)}</span></td>
        <td>
          ${canManage ? `
            <div class="space-member-actions">
              <button type="button" class="secondary" data-space-action="toggle-member-menu" data-membership-id="${escapeAttr(row.membership_id)}" aria-expanded="${menuOpen ? "true" : "false"}">Manage</button>
              ${menuOpen ? `
                <div class="space-action-menu" role="menu">
                  <button type="button" class="secondary" data-space-action="toggle-space-member-role" data-membership-id="${escapeAttr(row.membership_id)}" data-space-id="${escapeAttr(spaceId)}" data-next-role="${escapeAttr(nextRole)}">${nextRole === "space_admin" ? "Promote to space_admin" : "Demote to member"}</button>
                  <button type="button" class="secondary" data-space-action="toggle-space-member-status" data-membership-id="${escapeAttr(row.membership_id)}" data-space-id="${escapeAttr(spaceId)}" data-next-status="${escapeAttr(nextStatus)}">${nextStatus === "active" ? "Activate membership" : "Deactivate membership"}</button>
                  <button type="button" class="secondary danger" data-space-action="delete-space-member" data-membership-id="${escapeAttr(row.membership_id)}" data-space-id="${escapeAttr(spaceId)}">Remove from space</button>
                </div>
              ` : ""}
            </div>
          ` : "<span class='muted'>Read-only</span>"}
        </td>
      </tr>`;
    }).join("");
    return `
      <div class="table">
        <table>
          <thead>
            <tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  function statusPillClass(status) {
    const normalizedStatus = normalize(status);
    if (normalizedStatus === "approved") return "positive";
    if (normalizedStatus === "rejected" || normalizedStatus === "canceled") return "muted";
    return "warn";
  }

  function renderAccessRequestReviewPanel() {
    if (!userIsGlobalAdmin() && !canManageSpaceMembership(activeSpaceId())) return "";
    if (!state.reviewableAccessRequestsLoaded) {
      refreshReviewableAccessRequests().catch((err) => {
        console.warn("Failed to load access requests", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load access requests.", "error", 7000);
      });
    }
    const rows = state.reviewableAccessRequests || [];
    const body = state.reviewableAccessRequestsLoaded
      ? (rows.length ? rows.map((row) => `
        <tr>
          <td>
            <strong>${esc(row.requester_display_name || row.requester_soeid || row.requester_user_id)}</strong>
            <div class="muted">${esc(row.requester_soeid || "")}</div>
          </td>
          <td>${esc(row.space_name || row.space_id)}</td>
          <td>${esc(formatDateTime(row.created_at) || "")}</td>
          <td class="space-request-actions-cell">
            <div class="platform-access-actions">
              <button type="button" class="primary" data-space-action="approve-access-request" data-request-id="${escapeAttr(row.request_id)}" data-space-id="${escapeAttr(row.space_id)}">Approve</button>
              <button type="button" class="secondary" data-space-action="reject-access-request" data-request-id="${escapeAttr(row.request_id)}" data-space-id="${escapeAttr(row.space_id)}">Reject</button>
            </div>
          </td>
        </tr>
      `).join("") : "<tr><td colspan='4' class='muted'>No pending access requests.</td></tr>")
      : "<tr><td colspan='4' class='muted'>Loading access requests...</td></tr>";
    return `
      <div class="panel soft">
        <div class="panel-header">
          <div>
            <h3>Access Requests</h3>
            <p class="muted">Approve pending users into collaboration spaces.</p>
          </div>
        </div>
        <div class="table">
          <table>
            <thead><tr><th>User</th><th>Space</th><th>Requested</th><th class="space-request-actions-heading">Actions</th></tr></thead>
            <tbody>${body}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  function isOwnPersonalSpace(space) {
    return space?.space_kind === "personal" && space.owner_user_id === state.user?.user_id;
  }

  function displaySpaceName(space) {
    if (isOwnPersonalSpace(space)) return "Personal";
    if (space?.space_kind === "lobby") return "Space Access";
    return space?.name || space?.space_id || "";
  }

  function displaySpaceMeta(space) {
    if (isOwnPersonalSpace(space)) return `${state.user?.soeid || "Your"} personal space`;
    if (space?.space_kind === "lobby") return "Join or manage spaces";
    return space?.slug || space?.space_id || "workspace";
  }

  function renderLobbySection() {
    if (!state.requestableSpacesLoaded) {
      refreshRequestableSpaces().catch((err) => {
        console.warn("Failed to load requestable spaces", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load available spaces.", "error", 7000);
      });
    }
    if (!state.spaceAccessRequestsLoaded) {
      refreshAccessRequests().catch((err) => {
        console.warn("Failed to load user access requests", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load access requests.", "error", 7000);
      });
    }
    const currentUserId = state.user?.user_id || "";
    const personalSpace = (state.spaces || []).find((space) => (
      space.space_kind === "personal" && space.owner_user_id === currentUserId
    ));
    const pendingBySpaceId = new Map(
      (state.spaceAccessRequests || [])
        .filter((row) => normalize(row.status) === "pending")
        .map((row) => [row.space_id, row])
    );
    const requestSearch = normalize(state.lobbyRequestSearch);
    const requestableSpaces = state.requestableSpaces || [];
    const requestableVisibleCount = requestableSpaces.filter((space) => {
      if (!requestSearch) return true;
      return normalize(`${space.name || ""} ${space.slug || ""} ${space.space_id || ""}`).includes(requestSearch);
    }).length;
    const requestRows = state.spaceAccessRequestsLoaded
      ? ((state.spaceAccessRequests || []).length
        ? (state.spaceAccessRequests || []).map((row) => `
          <tr>
            <td>${esc(row.space_name || row.space_id)}</td>
            <td><span class="pill ${statusPillClass(row.status)}">${esc(row.status)}</span></td>
            <td>${esc(formatDateTime(row.created_at) || "")}</td>
            <td>
              ${normalize(row.status) === "pending"
                ? `<button type="button" class="secondary" data-space-action="cancel-access-request" data-request-id="${escapeAttr(row.request_id)}">Cancel</button>`
                : "<span class='muted'>Closed</span>"}
            </td>
          </tr>
        `).join("")
        : "<tr><td colspan='4' class='muted'>No access requests yet.</td></tr>")
      : "<tr><td colspan='4' class='muted'>Loading requests...</td></tr>";
    const requestableRows = state.requestableSpacesLoaded
      ? ((state.requestableSpaces || []).length
        ? `${requestableSpaces.map((space) => {
          const pending = pendingBySpaceId.get(space.space_id);
          const submitting = state.accessRequestSubmittingSpaceId === space.space_id;
          const searchText = normalize(`${space.name || ""} ${space.slug || ""} ${space.space_id || ""}`);
          const hiddenAttr = requestSearch && !searchText.includes(requestSearch) ? " hidden" : "";
          return `<tr data-lobby-request-row data-search-text="${escapeAttr(searchText)}"${hiddenAttr}>
            <td>
              <div class="space-directory-space-cell">
                <strong class="space-directory-space-name">${esc(space.name || space.space_id)}</strong>
                <span class="space-directory-space-meta">${esc(space.slug || "workspace")}</span>
              </div>
            </td>
            <td><span class="pill muted">${esc(space.space_kind || "collaboration")}</span></td>
            <td>
              <button type="button" class="primary" data-space-action="request-space-access" data-space-id="${escapeAttr(space.space_id)}"${disabledReasonAttr(!!pending || submitting, pending ? "Access request already pending." : "Request in progress.")}>${pending ? "Pending" : (submitting ? "Requesting..." : "Request Access")}</button>
            </td>
          </tr>`;
        }).join("")}<tr data-lobby-request-empty${requestSearch && !requestableVisibleCount ? "" : " hidden"}><td colspan='3' class='muted'>No matching collaboration spaces.</td></tr>`
        : "<tr><td colspan='3' class='muted'>No collaboration spaces are available to request.</td></tr>")
      : "<tr><td colspan='3' class='muted'>Loading spaces...</td></tr>";
    return `
      <div class="space-section-stack">
        <div class="space-hero-card">
          <div>
            <p class="space-card-kicker">Space Access</p>
            <h3>Join or create a working space</h3>
            <p class="muted">This area is for access management. You do not have access to a working space yet, so create Personal or request access to a collaboration space.</p>
          </div>
          <div class="space-hero-actions">
            <span class="pill muted">Lobby</span>
          </div>
        </div>
        <div class="space-summary-grid">
          <div class="panel soft space-summary-card"><span class="muted">Private Space</span><strong>${personalSpace ? "Created" : "Available"}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Requests</span><strong>${(state.spaceAccessRequests || []).length}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Available Spaces</span><strong>${(state.requestableSpaces || []).length}</strong></div>
        </div>
        <div class="panel soft">
          <div class="panel-header">
            <div>
              <h3>Private Space</h3>
              <p class="muted">A private working area owned by your account.</p>
            </div>
          </div>
          ${personalSpace ? `
            <div class="space-inline-callout">
              <div>
                <strong>${esc(displaySpaceName(personalSpace))}</strong>
                <p class="muted">${esc(displaySpaceMeta(personalSpace))}</p>
              </div>
              <button type="button" class="primary" data-space-action="switch-space" data-space-id="${escapeAttr(personalSpace.space_id)}"${disabledReasonAttr(state.spaceSwitching, "Finish switching spaces before choosing another space.")}>Open Private Space</button>
            </div>
          ` : `
            <form id="space-personal-create-form" class="form compact">
              <div class="form-actions full-span platform-command-actions">
                <button type="submit"${disabledReasonAttr(state.lobbyPersonalSpaceCreating, "Private space creation is in progress.")}>${state.lobbyPersonalSpaceCreating ? "Creating..." : "Create Private Space"}</button>
              </div>
            </form>
          `}
        </div>
        <div class="panel soft">
          <div class="panel-header">
            <div>
              <h3>Request Collaboration Access</h3>
              <p class="muted">Ask space admins to add you to an existing collaboration space.</p>
            </div>
          </div>
          <div class="space-directory-toolbar">
            <label class="space-directory-search-field">Search <input id="lobby-request-space-search" value="${escapeAttr(state.lobbyRequestSearch || "")}" placeholder="Space name or slug" /></label>
          </div>
          <div class="table space-directory-table-shell">
            <table class="space-directory-table">
              <thead><tr><th>Space</th><th>Kind</th><th>Action</th></tr></thead>
              <tbody>${requestableRows}</tbody>
            </table>
          </div>
        </div>
        <div class="panel soft">
          <div class="panel-header">
            <div>
              <h3>Your Requests</h3>
              <p class="muted">Track pending and completed access requests.</p>
            </div>
          </div>
          <div class="table">
            <table>
              <thead><tr><th>Space</th><th>Status</th><th>Requested</th><th>Actions</th></tr></thead>
              <tbody>${requestRows}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }

  function renderCurrentSpaceSection() {
    const active = state.activeSpace;
    const currentSpaceId = activeSpaceId();
    if (!active || !currentSpaceId) {
      return "<p class='muted'>Select a space to manage memberships and scoped administration.</p>";
    }
    const canManageCurrentSpace = canManageSpaceMembership(currentSpaceId) || userIsGlobalAdmin();
    if (canManageCurrentSpace && !state.spaceMembersLoadedBySpace[currentSpaceId]) {
      refreshSpaceMembers(currentSpaceId).catch((err) => {
        console.warn("Failed to load active space memberships", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load space memberships.", "error", 7000);
      });
    }
    const loading = canManageCurrentSpace && !state.spaceMembersLoadedBySpace[currentSpaceId];
    const summary = loading ? { total: 0, active: 0, admins: 0, inactive: 0 } : membershipSummaryForSpace(currentSpaceId);
    const isPersonalSpace = active.space_kind === "personal";
    return `
      <div class="space-section-stack">
        <div class="space-hero-card">
          <div>
            <p class="space-card-kicker">Active workspace</p>
            <h3>${esc(active.space_kind === "personal" ? "Personal" : (active.space_name || currentSpaceId))}</h3>
            <p class="muted">This is the space that powers the data, assignments, and membership edits in the rest of the app.</p>
          </div>
          <div class="space-hero-actions">
            <span class="pill">${esc(currentSpaceRoleLabel(active))}</span>
            ${isPersonalSpace ? "<span class='pill muted'>Private</span>" : ""}
            ${canManageCurrentSpace && !isPersonalSpace ? `<button type="button" class="primary" data-space-action="open-member-modal" data-space-id="${escapeAttr(currentSpaceId)}"${disabledReasonAttr(state.spaceSwitching, "Finish switching spaces before adding a member.")}>Add Member</button>` : ""}
          </div>
        </div>
        ${canManageCurrentSpace ? `<div class="space-summary-grid">
          <div class="panel soft space-summary-card"><span class="muted">Members</span><strong>${loading ? "..." : summary.total}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Active</span><strong>${loading ? "..." : summary.active}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Active Admins</span><strong>${loading ? "..." : summary.admins}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Inactive</span><strong>${loading ? "..." : summary.inactive}</strong></div>
        </div>` : ""}
        <div class="panel soft space-membership-card">
          <div class="panel-header">
            <div>
              <h3>Space Memberships</h3>
              <p class="muted">${canManageCurrentSpace ? `Manage the people who can work inside ${esc(active.space_name || currentSpaceId)}.` : "Space admin access is required to view or change memberships."}</p>
            </div>
          </div>
          ${canManageCurrentSpace
            ? (loading ? "<p class='muted'>Loading memberships...</p>" : renderMembershipTable(currentSpaceId))
            : "<p class='muted'>You can work in this space, but membership management is limited to space admins.</p>"}
        </div>
        ${canManageCurrentSpace && !isPersonalSpace ? renderAccessRequestReviewPanel() : ""}
      </div>
    `;
  }

  function renderDirectoryDetailSurface(selectedSpace) {
    if (!selectedSpace) {
      return `
        <div class="space-empty-card">
          <h3>Select a space</h3>
          <p class="muted">Choose a space from the directory to inspect its status, switch into it, or continue governance work.</p>
        </div>
      `;
    }
    const isCurrent = selectedSpace.space_id === activeSpaceId();
    const canManage = canManageSpaceMembership(selectedSpace.space_id);
    const canSwitchToManage = !userIsGlobalAdmin() && normalizeSpaceRole(state.activeSpace?.space_role) === "space_admin" && !isCurrent;
    const isArchived = selectedSpace.is_active === false;
    const isPersonalSpace = selectedSpace.space_kind === "personal";
    const canToggleActive = userIsGlobalAdmin() && (isArchived || !isCurrent);
    const archiveLabel = isArchived ? "Reactivate" : "Archive";
    const publicDashboardEnabled = selectedSpace.public_program_dashboard_enabled === true;
    const publicDashboardUrl = selectedSpace.slug && typeof buildAppUrl === "function"
      ? new URL(buildAppUrl(`/public/program-dashboard/${encodeURIComponent(selectedSpace.slug)}`), window.location.origin).toString()
      : "";
    const previewMode = isCurrent
      ? "Current workspace"
      : (canManage ? "Ready to manage" : (canSwitchToManage ? "Switch to manage" : "Read-only preview"));
    if (!state.spaceMembersLoadedBySpace[selectedSpace.space_id] && (canManage || userIsGlobalAdmin()) && !state.spaceSwitching) {
      refreshSpaceMembers(selectedSpace.space_id).catch((err) => {
        console.warn("Failed to load directory space memberships", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load selected space details.", "error", 7000);
      });
    }
    const summary = state.spaceMembersLoadedBySpace[selectedSpace.space_id]
      ? membershipSummaryForSpace(selectedSpace.space_id)
      : null;
    return `
      <div class="space-directory-modal-shell">
        <div class="panel soft space-directory-preview space-directory-modal-preview">
          <div class="space-directory-preview-hero">
            <div>
              <p class="space-card-kicker">Space details</p>
              <h3>${esc(selectedSpace.name || selectedSpace.space_id)}</h3>
              <p class="space-directory-preview-id">${esc(selectedSpace.space_id)}</p>
              <p class="muted">Review the current state first, then take the next action from this layer without cluttering the directory.</p>
            </div>
            <div class="space-hero-actions">
              <span class="pill ${roleBadgeClass(roleBadgeLabelForSpace(selectedSpace))}">${esc(roleBadgeLabelForSpace(selectedSpace))}</span>
              ${isCurrent ? "<span class='pill positive'>Current</span>" : ""}
              ${isArchived ? "<span class='pill danger'>Archived</span>" : "<span class='pill muted'>Active</span>"}
            </div>
          </div>
          <div class="space-directory-preview-grid">
            <div class="space-summary-card panel">
              <span class="muted">Slug</span>
              <strong>${esc(selectedSpace.slug || "Not set")}</strong>
            </div>
            <div class="space-summary-card panel">
              <span class="muted">Members</span>
              <strong>${summary ? summary.total : "Preview after load"}</strong>
            </div>
            <div class="space-summary-card panel">
              <span class="muted">Active Admins</span>
              <strong>${summary ? summary.admins : "Preview after load"}</strong>
            </div>
            <div class="space-summary-card panel">
              <span class="muted">Mode</span>
              <strong>${esc(previewMode)}</strong>
            </div>
            <div class="space-summary-card panel">
              <span class="muted">Public Dashboard</span>
              <strong>${publicDashboardEnabled ? "Exposed" : "Off"}</strong>
            </div>
          </div>
          ${(canManage || userIsGlobalAdmin()) ? `
            <div class="space-inline-callout">
              <div>
                <strong>Public program dashboard</strong>
                <p class="muted">${publicDashboardEnabled && publicDashboardUrl
                  ? esc(publicDashboardUrl)
                  : "Expose a read-only program dashboard for anyone with the URL."}</p>
              </div>
              <button type="button" class="secondary" data-space-action="toggle-public-program-dashboard" data-space-id="${escapeAttr(selectedSpace.space_id)}" data-next-enabled="${publicDashboardEnabled ? "false" : "true"}"${disabledReasonAttr(isArchived, "Reactivate this space before exposing its public dashboard.")}>${publicDashboardEnabled ? "Disable Public Dashboard" : "Expose Public Dashboard"}</button>
            </div>
          ` : ""}
          ${canSwitchToManage ? `
            <div class="space-inline-callout">
              <div>
                <strong>Read-only preview</strong>
                <p class="muted">Switch into ${esc(selectedSpace.name || selectedSpace.space_id)} to manage memberships and work with full governance controls.</p>
              </div>
              <button type="button" class="primary" data-space-action="switch-space" data-space-id="${escapeAttr(selectedSpace.space_id)}">Switch to manage</button>
            </div>
          ` : ""}
          ${isArchived ? `
            <p class="muted">Archived spaces remain visible here for review. Reactivate the space before adding or changing memberships.</p>
          ` : ""}
          ${(canManage || userIsGlobalAdmin()) ? `
            <div class="space-directory-preview-actions">
              <button type="button" class="secondary" data-space-action="switch-space" data-space-id="${escapeAttr(selectedSpace.space_id)}"${disabledReasonAttr(isCurrent || state.spaceSwitching, isCurrent ? "This space is already current." : "Finish switching spaces before choosing another space.")}>${isCurrent ? "Already current" : "Switch to this space"}</button>
              ${isPersonalSpace ? "" : `<button type="button" class="primary" data-space-action="open-member-modal" data-space-id="${escapeAttr(selectedSpace.space_id)}"${disabledReasonAttr(!(canManage && !isArchived), isArchived ? "Reactivate this space before adding members." : "Switch to this space or ask a space admin to add members.")}>Add Member</button>`}
              ${userIsGlobalAdmin() ? `<button type="button" class="secondary${!canToggleActive ? " muted-action" : ""}" data-space-action="toggle-space-active" data-space-id="${escapeAttr(selectedSpace.space_id)}" data-next-active="${isArchived ? "true" : "false"}"${disabledReasonAttr(!canToggleActive, isCurrent ? "Switch to another active space before archiving this one." : "Only global admins can archive or reactivate spaces.")}>${archiveLabel}</button>` : ""}
            </div>
          ` : ""}
        </div>
        <div class="form-actions space-directory-modal-footer">
          <button type="button" class="secondary" data-space-action="close-directory-space-modal">Close</button>
        </div>
      </div>
    `;
  }

  function renderSpaceDirectoryModal() {
    if (!els.spaceDirectoryModal || !els.spaceDirectoryModalBody) return;
    if (!state.spaceDirectoryModalOpen) {
      els.spaceDirectoryModal.classList.add("hidden");
      els.spaceDirectoryModalBody.innerHTML = "";
      return;
    }
    const selectedSpace = directorySpaceById(state.spaceMembershipSpaceId);
    if (!selectedSpace) {
      closeSpaceDirectoryModal();
      els.spaceDirectoryModalBody.innerHTML = "";
      return;
    }
    els.spaceDirectoryModalBody.innerHTML = renderDirectoryDetailSurface(selectedSpace);
    els.spaceDirectoryModal.classList.remove("hidden");
  }

  function renderDirectorySection() {
    const allSpaces = effectiveDirectorySpaces();
    const spaces = allSpaces.filter((space) => {
      const query = normalize(state.spaceDirectoryQuery);
      if (!query) return true;
      return [space.name, space.slug, space.space_id].some((value) => normalize(value).includes(query));
    });
    const totalSpaces = allSpaces.length;
    const activeSpaces = allSpaces.filter((space) => space.is_active !== false).length;
    const archivedSpaces = allSpaces.filter((space) => space.is_active === false).length;
    const ensuredSelected = ensureSelectedDirectorySpace();
    const selectedSpace = spaces.length
      ? (spaces.find((space) => space.space_id === state.spaceMembershipSpaceId) || spaces[0] || ensuredSelected)
      : null;
    if (selectedSpace?.space_id && selectedSpace.space_id !== state.spaceMembershipSpaceId) {
      state.spaceMembershipSpaceId = selectedSpace.space_id;
    }
    const directoryRows = spaces.length
      ? spaces.map((space) => {
        const isCurrent = space.space_id === activeSpaceId();
        const isSelected = space.space_id === state.spaceMembershipSpaceId;
        const isArchived = space.is_active === false;
        const workspaceState = isArchived ? "Archived" : (isCurrent ? "Current" : "Active");
        return `<tr class="space-directory-row${isSelected ? " is-selected" : ""}${isCurrent ? " is-current" : ""}${isArchived ? " is-archived" : ""}">
          <td>
            <div class="space-directory-space-cell">
              <strong class="space-directory-space-name">${esc(displaySpaceName(space))}</strong>
              <span class="space-directory-space-meta">${esc(displaySpaceMeta(space))} &middot; ${esc(space.space_id)}</span>
            </div>
          </td>
          <td><span class="pill ${roleBadgeClass(roleBadgeLabelForSpace(space))}">${esc(roleBadgeLabelForSpace(space))}</span></td>
          <td>
            ${isCurrent ? "<span class='pill positive'>Current</span>" : ""}
            ${isArchived ? "<span class='pill danger'>Archived</span>" : (!isCurrent ? "<span class='pill muted'>Active</span>" : "")}
          </td>
          <td>${esc(isCurrent ? "Current workspace" : workspaceState)}</td>
          <td>
            <div class="space-directory-actions">
              <button type="button" class="primary" data-space-action="open-directory-space" data-space-id="${escapeAttr(space.space_id)}">${isSelected ? "Reopen details" : (isCurrent ? "Open current space" : "View details")}</button>
            </div>
          </td>
        </tr>`;
      }).join("")
      : `
        <div class="space-empty-card">
          <h3>No spaces found</h3>
          <p class="muted">${userIsGlobalAdmin() ? "Try a different search or switch off archived filtering to widen the directory." : "Try a different search to widen the directory."}</p>
        </div>
      `;
    const directorySurface = spaces.length
      ? `<div class="table space-directory-table-shell">
          <table class="space-directory-table">
            <thead>
              <tr>
                <th>Space</th>
                <th>Role</th>
                <th>Status</th>
                <th>Mode</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>${directoryRows}</tbody>
          </table>
        </div>`
      : directoryRows;
    return `
      <div class="space-section-stack">
        <div class="panel soft space-directory-overview">
          <div class="space-directory-overview-copy">
            <p class="space-card-kicker">Workspace atlas</p>
            <h3>Space Directory</h3>
            <p class="muted">Scan every space, inspect the current state, and move into the right workspace without losing your governance context.</p>
          </div>
          <div class="space-directory-overview-stats">
            <div class="space-directory-stat">
              <span>Total spaces</span>
              <strong>${totalSpaces}</strong>
            </div>
            <div class="space-directory-stat">
              <span>Active</span>
              <strong>${activeSpaces}</strong>
            </div>
            <div class="space-directory-stat">
              <span>Archived</span>
              <strong>${archivedSpaces}</strong>
            </div>
            <div class="space-directory-stat">
              <span>In view</span>
              <strong>${spaces.length}</strong>
            </div>
          </div>
          <div class="space-directory-toolbar">
            <label class="space-directory-search-field">Search spaces
              <input type="search" id="space-directory-search" placeholder="Name, slug, or ID" value="${escapeAttr(state.spaceDirectoryQuery)}" />
            </label>
            ${userIsGlobalAdmin() ? `<label class="checkbox-row space-directory-toggle"><input type="checkbox" id="space-directory-show-archived" ${state.spaceDirectoryShowArchived ? "checked" : ""} /> Show archived</label>` : ""}
            ${userIsGlobalAdmin() ? `<button type="button" class="primary" data-space-action="open-create-space-modal">Create Space</button>` : ""}
          </div>
        </div>
        <div class="space-directory-layout">
          ${directorySurface}
        </div>
      </div>
    `;
  }

  function renderPlatformPasswordResetResult() {
    const issued = state.platformPasswordReset;
    if (!issued?.temp_password) return "";
    const expiresText = formatDateTime(issued.expires_at) || "Unknown expiration";
    return `
      <div class="panel soft platform-reset-output">
        <div class="platform-reset-output-head">
          <div>
            <p class="space-card-kicker">Temporary password issued</p>
            <h3>Share the temporary password</h3>
            <p class="muted">Issued for ${esc(issued.soeid || "user")} and valid until ${esc(expiresText)}. Send them to the reset page with this temporary password.</p>
          </div>
          <span class="pill positive">Ready</span>
        </div>
        <div class="platform-reset-grid">
          <label class="wide">Temporary password
            <input type="text" readonly value="${escapeAttr(issued.temp_password)}" />
          </label>
          <label class="wide">Reset page
            <input type="text" readonly value="${escapeAttr(issued.reset_url || "")}" />
          </label>
        </div>
        <div class="form-actions">
          <button type="button" class="secondary" data-space-action="copy-temp-password">Copy temp password</button>
          <button type="button" class="secondary" data-space-action="copy-reset-link">Copy reset page</button>
          <button type="button" class="secondary" data-space-action="clear-reset-result">Clear</button>
        </div>
      </div>
    `;
  }

  function renderAgentDiff(request, selectedOperationIds) {
    const items = request?.diff || [];
    if (!items.length) return "<p class='muted'>No field-level diff available.</p>";
    return items.map((item) => {
      const checked = selectedOperationIds.has(item.client_operation_id);
      const fields = Object.entries(item.fields || {}).map(([field, values]) => `
        <tr>
          <td>${esc(field)}</td>
          <td>${esc(values?.old ?? "")}</td>
          <td>${esc(values?.new ?? "")}</td>
        </tr>
      `).join("");
      return `
        <div class="agent-diff-card ${checked ? "is-selected" : ""}">
          <div class="agent-diff-card-head">
            <label class="agent-diff-card-selector">
              <input type="checkbox" data-agent-change-operation-checkbox data-client-operation-id="${escapeAttr(item.client_operation_id)}" ${checked ? "checked" : ""} />
              <span class="pill">${esc(item.op)} ${esc(item.entity)}</span>
              <strong>${esc(item.entity_label || "New item")}</strong>
            </label>
          </div>
          <div class="table compact-table">
            <table>
              <thead><tr><th>Field</th><th>Current</th><th>Proposed</th></tr></thead>
              <tbody>${fields || "<tr><td colspan='3' class='muted'>No changed fields</td></tr>"}</tbody>
            </table>
          </div>
        </div>
      `;
    }).join("");
  }

  function agentProposalSummary(row) {
    const diff = Array.isArray(row?.diff) ? row.diff : [];
    if (!diff.length) {
      return `${row?.operation_count || 0} proposed operation${row?.operation_count === 1 ? "" : "s"}`;
    }
    const labels = diff
      .map((item) => item.entity_label || item.entity || "")
      .filter(Boolean);
    const uniqueLabels = [...new Set(labels)];
    const visibleLabels = uniqueLabels.slice(0, 3).join(", ");
    const remaining = uniqueLabels.length > 3 ? ` +${uniqueLabels.length - 3} more` : "";
    return `${diff.length} change${diff.length === 1 ? "" : "s"} across ${visibleLabels || "work items"}${remaining}`;
  }

  function renderAgentProposalModal(request) {
    if (!request) return "";
    const operationCount = Number(request.operation_count || 0);
    const storedSelection = state.agentChangeRequestSelectedOperationIds?.[request.change_request_id];
    const selectedOperationIds = storedSelection instanceof Set
      ? storedSelection
      : new Set((request.operations || []).map((operation) => operation.client_operation_id));
    const selectedCount = selectedOperationIds.size;
    const allSelected = operationCount > 0 && selectedCount === operationCount;
    return `
      <div class="modal agent-proposal-modal" role="dialog" aria-modal="true" aria-labelledby="agent-proposal-modal-title">
        <button type="button" class="modal-backdrop" data-space-action="close-agent-change-request-modal" aria-label="Close proposal review"></button>
        <div class="modal-content wide agent-proposal-modal-content">
          <div class="modal-header">
            <div>
              <p class="space-card-kicker">Agent proposal</p>
              <h3 id="agent-proposal-modal-title">${esc(request.reason || "Agent proposal")}</h3>
              <p class="muted">${esc(request.proposed_by_label || request.proposed_by_user_id || "Service account")} - ${esc(formatDateTime(request.created_at) || "No date")} - ${esc(operationCount)} proposed operation${operationCount === 1 ? "" : "s"}</p>
            </div>
            <button type="button" class="secondary modal-close-x" data-space-action="close-agent-change-request-modal" aria-label="Close proposal review" title="Close" data-tooltip="Close">
              <svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12"></path><path d="M18 6L6 18"></path></svg>
            </button>
          </div>
          <div class="agent-proposal-modal-meta">
            <span class="pill">${esc(request.status || "pending")}</span>
            <span class="pill muted">${esc(agentProposalSummary(request))}</span>
            <span class="pill muted">${esc(selectedCount)} selected</span>
          </div>
          <div class="agent-proposal-selection-actions" role="group" aria-label="Proposal change selection">
            <button type="button" class="secondary" data-space-action="select-all-agent-change-request-operations" ${allSelected ? "disabled" : ""}>Select all</button>
            <button type="button" class="secondary" data-space-action="clear-agent-change-request-operations" ${selectedCount ? "" : "disabled"}>Clear selection</button>
          </div>
          <div class="agent-proposal-modal-body">
            ${renderAgentDiff(request, selectedOperationIds)}
          </div>
          <div class="form-actions agent-proposal-modal-actions">
            <button type="button" class="primary" data-space-action="approve-agent-change-request" data-change-request-id="${escapeAttr(request.change_request_id)}"${disabledReasonAttr(!selectedCount, "Select at least one change before approving.")}>Approve selected (${esc(selectedCount)})</button>
            <button type="button" class="secondary danger" data-space-action="reject-agent-change-request" data-change-request-id="${escapeAttr(request.change_request_id)}">Reject proposal</button>
            <button type="button" class="secondary" data-space-action="close-agent-change-request-modal">Close</button>
          </div>
        </div>
      </div>
    `;
  }

  function renderAgentApprovalsSection() {
    if (!state.agentChangeRequestsLoaded) {
      refreshAgentChangeRequests({ force: true }).catch((err) => {
        console.warn("Failed to load agent approvals", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load agent approvals.", "error", 7000);
      });
    }
    const rows = state.agentChangeRequests || [];
    const selected = state.agentChangeRequestSelectedIds || new Set();
    const modalProposal = rows.find((row) => row.change_request_id === state.agentChangeRequestModalId) || null;
    const newest = rows[0]?.created_at ? formatDateTime(rows[0].created_at) : "None";
    const tableRows = rows.length
      ? rows.map((row) => {
        const checked = selected.has(row.change_request_id);
        const isOpen = modalProposal?.change_request_id === row.change_request_id;
        return `<tr class="${isOpen ? "is-selected" : ""}">
          <td><input type="checkbox" data-agent-change-request-checkbox data-change-request-id="${escapeAttr(row.change_request_id)}" ${checked ? "checked" : ""} /></td>
          <td>
            <button type="button" class="text-link agent-proposal-link" data-space-action="open-agent-change-request" data-change-request-id="${escapeAttr(row.change_request_id)}">${esc(row.reason || "Agent proposal")}</button>
            <div class="muted">${esc(agentProposalSummary(row))}</div>
          </td>
          <td>${esc(row.proposed_by_label || row.proposed_by_user_id || "Service account")}</td>
          <td>${esc(formatDateTime(row.created_at) || "")}</td>
          <td>${esc(row.operation_count || 0)}</td>
          <td><span class="pill">${esc(row.status)}</span></td>
        </tr>`;
      }).join("")
      : "<tr><td colspan='6' class='muted'>No pending agent proposals.</td></tr>";
    return `
      <div class="space-section-stack">
        <div class="space-hero-card">
          <div>
            <p class="space-card-kicker">Controlled automation</p>
            <h3>Agent Approvals</h3>
            <p class="muted">Review proposed agent changes before they update work data in this space.</p>
          </div>
          <div class="space-hero-actions">
            <button type="button" class="primary" data-space-action="approve-agent-change-requests"${disabledReasonAttr(!selected.size, "Select at least one pending proposal before approving.")}>Approve selected</button>
            <button type="button" class="secondary danger" data-space-action="reject-agent-change-requests"${disabledReasonAttr(!selected.size, "Select at least one pending proposal before rejecting.")}>Reject selected</button>
          </div>
        </div>
        <div class="space-summary-grid">
          <div class="panel soft space-summary-card"><span class="muted">Pending</span><strong>${state.agentChangeRequestPendingCount || 0}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Failed</span><strong>${state.agentChangeRequestFailedCount || 0}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Selected</span><strong>${selected.size}</strong></div>
          <div class="panel soft space-summary-card"><span class="muted">Newest</span><strong>${esc(newest)}</strong></div>
        </div>
        <div class="panel soft agent-approval-table-panel">
          <div class="table">
            <table class="agent-approval-table">
                <thead><tr><th></th><th>Proposal</th><th>Proposed By</th><th>Created</th><th>Ops</th><th>Status</th></tr></thead>
                <tbody>${tableRows}</tbody>
            </table>
          </div>
        </div>
        ${renderAgentProposalModal(modalProposal)}
      </div>
    `;
  }

  function renderIssuedApiToken() {
    const issued = state.issuedApiToken;
    if (!issued?.token) return "";
    return `
      <div class="modal api-token-modal" role="dialog" aria-modal="true" aria-labelledby="api-token-modal-title">
        <div class="modal-backdrop"></div>
        <div class="modal-content api-token-modal-content">
          <div class="modal-header">
            <div>
              <p class="space-card-kicker">API token issued</p>
              <h3 id="api-token-modal-title">Copy this token now</h3>
            </div>
            <button type="button" class="secondary modal-close-x" data-space-action="clear-api-token-result" aria-label="Close API token dialog" title="Close" data-tooltip="Close">
              <svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12"></path><path d="M18 6L6 18"></path></svg>
            </button>
          </div>
          <div class="api-token-modal-body">
            <p class="muted">This token is shown once for ${esc(issued.user_label || "the service account")}.</p>
            <label class="wide">Personal access token
              <input type="text" readonly value="${escapeAttr(issued.token)}" />
            </label>
            <div class="form-actions api-token-modal-actions">
              <button type="button" data-space-action="copy-api-token">Copy token</button>
              <button type="button" class="secondary" data-space-action="clear-api-token-result">Done</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function renderApiTokenRows(user) {
    const rows = state.apiTokensByUser[user.user_id] || [];
    if (!state.apiTokensLoadedByUser[user.user_id]) {
      refreshApiTokens(user.user_id).catch((err) => {
        console.warn("Failed to load API tokens", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load API tokens.", "error", 7000);
      });
      return "<tr><td colspan='5' class='muted'>Loading tokens...</td></tr>";
    }
    if (!rows.length) return "<tr><td colspan='5' class='muted'>No API tokens issued</td></tr>";
    return rows.map((token) => {
      const revoked = !!token.revoked_at;
      const expired = token.expires_at && new Date(token.expires_at).getTime() <= Date.now();
      const status = revoked ? "revoked" : (expired ? "expired" : "active");
      return `<tr data-token-id="${escapeAttr(token.token_id)}">
        <td>${esc(token.name)}</td>
        <td>${esc(status)}</td>
        <td>${esc(formatDateTime(token.expires_at) || "Never")}</td>
        <td>${esc(formatDateTime(token.last_used_at) || "Never")}</td>
        <td>${revoked ? "<span class='muted'>Revoked</span>" : `<button type="button" class="secondary danger" data-space-action="revoke-api-token" data-user-id="${escapeAttr(user.user_id)}" data-token-id="${escapeAttr(token.token_id)}">Revoke</button>`}</td>
      </tr>`;
    }).join("");
  }

  function renderServiceAccountTokens() {
    const serviceUsers = (state.users || []).filter((user) => user.is_service_account);
    const sections = serviceUsers.length
      ? serviceUsers.map((user) => `
        <div class="panel soft">
          <div class="panel-header">
            <div>
              <h3>${esc(user.display_name || user.soeid || user.user_id)}</h3>
              <p class="muted">${esc(user.soeid || user.email || user.user_id)}</p>
            </div>
            <button type="button" class="secondary" data-space-action="refresh-api-tokens" data-user-id="${escapeAttr(user.user_id)}">Refresh</button>
          </div>
          <form class="form compact inline-form api-token-issue-form" data-user-id="${escapeAttr(user.user_id)}">
            <label class="wide">Token name <input name="name" placeholder="Automation token" /></label>
            <label>Expires at <input name="expires_at" type="datetime-local" /></label>
            <div class="form-actions full-span platform-command-actions"><button type="submit">Issue Token</button></div>
          </form>
          <div class="table">
            <table>
              <thead><tr><th>Name</th><th>Status</th><th>Expires</th><th>Last Used</th><th>Actions</th></tr></thead>
              <tbody>${renderApiTokenRows(user)}</tbody>
            </table>
          </div>
        </div>
      `).join("")
      : "";
    return `
      <div class="panel soft">
        <form id="service-account-token-form" class="form compact inline-form">
          <label>User SOEID <input name="soeid" placeholder="e.g. lgo12345" /></label>
          <label class="wide">Token name <input name="name" placeholder="Automation token" /></label>
          <label>Expires at <input name="expires_at" type="datetime-local" /></label>
          <div class="form-actions full-span platform-command-actions"><button type="submit">Generate Token</button></div>
        </form>
      </div>
      ${sections}
    `;
  }

  function renderUserDirectoryRows() {
    const users = [...(state.users || [])]
      .sort((a, b) => (a.display_name || a.soeid || "").localeCompare(b.display_name || b.soeid || ""));
    if (!users.length) {
      return "<tr><td colspan='9' class='muted'>No users loaded for the active space.</td></tr>";
    }
    return users.map((user) => {
      const isGlobalAdmin = String(user.role || "").trim().toLowerCase().replace(/[\s-]+/g, "_") === "global_admin";
      const statusText = user.is_active ? "active" : "inactive";
      const serviceText = user.is_service_account ? "service" : "interactive";
      return `<tr data-user-id="${escapeAttr(user.user_id)}" data-soeid="${escapeAttr(user.soeid)}">
        <td>${esc(user.display_name || user.soeid || user.user_id)}</td>
        <td>${esc(user.soeid || "-")}</td>
        <td>${esc(user.email || "-")}</td>
        <td>${esc(user.role || "user")}</td>
        <td><span class="pill ${user.is_active ? "positive" : "muted"}">${esc(statusText)}</span></td>
        <td><span class="pill ${user.is_service_account ? "warn" : "muted"}">${esc(serviceText)}</span></td>
        <td>${esc(user.team_tag || "-")}</td>
        <td>${esc(formatDateTime(user.last_login_at) || "Never")}</td>
        <td>
          <div class="platform-access-actions">
            <button type="button" class="secondary" data-space-action="issue-password-reset" data-soeid="${escapeAttr(user.soeid)}">Issue Reset</button>
            ${isGlobalAdmin
              ? `<button type="button" class="secondary" data-space-action="revoke-global-admin" data-soeid="${escapeAttr(user.soeid)}">Revoke Admin</button>`
              : `<button type="button" class="secondary" data-space-action="grant-global-admin" data-soeid="${escapeAttr(user.soeid)}">Grant Admin</button>`}
          </div>
        </td>
      </tr>`;
    }).join("");
  }

  function renderPlatformAccessSection() {
    if (!userIsGlobalAdmin()) {
      return `
        <div class="space-empty-card">
          <h3>Platform Access</h3>
          <p class="muted">Global admin access is managed centrally and is only visible to global admins.</p>
        </div>
      `;
    }
    if (!state.globalAdminsLoaded) {
      refreshGlobalAdmins().catch((err) => {
        console.warn("Failed to load global admins", err);
        setSpaceGovernanceNotice(err?.message || "Failed to load platform access.", "error", 7000);
      });
    }
    const rows = state.globalAdminsLoaded
      ? (state.globalAdmins || []).map((user) => {
        const statusText = user.is_active ? "active" : "inactive";
        return `<tr data-user-id="${escapeAttr(user.user_id)}" data-soeid="${escapeAttr(user.soeid)}">
          <td>${esc(user.display_name || user.soeid || user.user_id)}</td>
          <td>${esc(user.soeid || "-")}</td>
          <td><span class="pill ${user.is_active ? "positive" : "muted"}">${esc(statusText)}</span></td>
          <td>
            <div class="platform-access-actions">
              <button type="button" class="secondary" data-space-action="issue-password-reset" data-soeid="${escapeAttr(user.soeid)}">Issue Reset</button>
              <button type="button" class="secondary" data-space-action="revoke-global-admin" data-soeid="${escapeAttr(user.soeid)}">Revoke</button>
            </div>
          </td>
        </tr>`;
      }).join("")
      : "<tr><td colspan='4' class='muted'>Loading global admins...</td></tr>";
    return `
      <div class="space-section-stack">
        <div class="space-hero-card">
          <div>
            <p class="space-card-kicker">Platform-wide access</p>
            <h3>Global Admins</h3>
            <p class="muted">Grant platform-wide access and revoke it when needed without leaving the governance hub.</p>
          </div>
        </div>
        <div class="panel soft">
          <form id="space-platform-access-form" class="form compact inline-form">
            <label class="wide">User SOEID <input name="soeid" placeholder="e.g. lgo12345" /></label>
            <div class="form-actions full-span platform-command-actions">
              <button type="submit">Grant Global Admin</button>
            </div>
          </form>
        </div>
        <div class="panel soft">
          <form id="space-password-reset-form" class="form compact inline-form">
            <label class="wide">User SOEID <input name="soeid" placeholder="e.g. lgo12345" /></label>
            <label>Expires in minutes <input type="number" name="expires_minutes" min="5" max="1440" placeholder="30" /></label>
            <p class="muted full-span">Issuing a reset signs the user out, generates a temporary password on this screen, and requires them to choose a new password on the reset page.</p>
            <div class="form-actions full-span platform-command-actions">
              <button type="submit">Issue Password Reset</button>
            </div>
          </form>
        </div>
        ${renderPlatformPasswordResetResult()}
        <div class="space-hero-card">
          <div>
            <p class="space-card-kicker">Automation access</p>
            <h3>Service Account API Tokens</h3>
            <p class="muted">Issue bearer tokens only for accounts explicitly marked as service accounts.</p>
          </div>
        </div>
        ${renderServiceAccountTokens()}
        <div class="space-hero-card">
          <div>
            <p class="space-card-kicker">Local user table</p>
            <h3>Users</h3>
            <p class="muted">Review local-auth users, issue temporary password resets, and manage platform admin access.</p>
          </div>
        </div>
        <div class="panel soft">
          <div class="table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>SOEID</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Account Type</th>
                  <th>Team</th>
                  <th>Last Login</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>${renderUserDirectoryRows()}</tbody>
            </table>
          </div>
        </div>
        <div class="panel soft">
          <div class="table">
            <table>
              <thead><tr><th>Name</th><th>SOEID</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>${rows || "<tr><td colspan='4' class='muted'>No global admins found</td></tr>"}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }

  function renderGovernanceHub(preferredSection = "") {
    if (!els.spaceGovernanceShell) return;
    if (state.activeSpace?.space_kind === "lobby") {
      els.spaceGovernanceShell.innerHTML = `
        <div class="space-governance-header">
          <div>
            <p class="space-card-kicker">Shared landing space</p>
            <h3>Space Access</h3>
            <p class="muted">Choose where your work should live.</p>
          </div>
        </div>
        ${renderGovernanceNotice()}
        <div class="space-governance-body">${renderLobbySection()}</div>
      `;
      closeSpaceDirectoryModal();
      return;
    }
    const activeSection = resolveGovernanceSection(
      preferredSection || (state.currentView === "access" ? "platform-access" : state.spaceAdminSection || "current-space")
    );
    const sectionTabs = governanceSections()
      .map((section) => `
        <button
          type="button"
          class="secondary${activeSection === section.id ? " active" : ""}"
          data-space-action="select-section"
          data-section="${escapeAttr(section.id)}"
        >${esc(section.label)}</button>
      `)
      .join("");
    let body = "";
    if (activeSection === "agent-approvals") body = renderAgentApprovalsSection();
    if (activeSection === "current-space") body = renderCurrentSpaceSection();
    if (activeSection === "space-directory") body = renderDirectorySection();
    if (activeSection === "platform-access") body = renderPlatformAccessSection();
    const introCopy = activeSection === "platform-access"
      ? "Manage platform-wide admins without leaving the same governance hub."
      : "Switch spaces quickly, stay oriented, and handle access work without leaving the current admin context.";
    els.spaceGovernanceShell.innerHTML = `
      <div class="space-governance-header">
        <div>
          <p class="space-card-kicker">Unified admin hub</p>
          <h3>Manage Current Space, Directory, and Platform Access</h3>
          <p class="muted">${esc(introCopy)}</p>
        </div>
        <div class="space-governance-header-actions">
          ${activeSection !== "current-space" && canManageSpaceMembership(activeSpaceId()) && state.activeSpace?.space_kind !== "personal" ? `<button type="button" class="primary" data-space-action="open-member-modal" data-space-id="${escapeAttr(activeSpaceId())}">Add Member</button>` : ""}
          ${activeSection !== "space-directory" && userIsGlobalAdmin() ? `<button type="button" class="secondary" data-space-action="open-create-space-modal">Create Space</button>` : ""}
        </div>
      </div>
      <div class="space-governance-tabs">${sectionTabs}</div>
      ${renderGovernanceNotice()}
      <div class="space-governance-body">${body}</div>
      ${renderIssuedApiToken()}
    `;
    if (activeSection !== "space-directory") {
      closeSpaceDirectoryModal();
    } else {
      renderSpaceDirectoryModal();
    }
  }

  return {
    renderGovernanceHub,
    renderSpaceDirectoryModal,
  };
}
