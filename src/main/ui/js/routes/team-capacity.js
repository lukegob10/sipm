function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function refreshLabel(isoValue) {
  if (!isoValue) return "";
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function renderTeamCapacity(ctx) {
  const {
    state,
    els,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
    teamCapacityState,
    selectedSoeid,
  } = ctx;
  if (!els.capacityUserList) return;
  const loading = !!teamCapacityState?.loading;
  const loadError = teamCapacityState?.error || "";
  const refreshedAt = refreshLabel(teamCapacityState?.lastLoadedAt);
  const activeSpaceName = String(state.activeSpace?.space_name || "").trim();
  const activeSpaceId = String(state.activeSpace?.space_id || "").trim();
  const loadedSpaceName = String(teamCapacityState?.lastLoadedSpaceName || "").trim();
  const loadedSpaceId = String(teamCapacityState?.lastLoadedSpaceId || "").trim();

  const teamFilter = normalize(els.capacityTeamFilter?.value || "");
  const nameFilter = normalize(els.capacityNameFilter?.value || "");
  const fteByUser = new Map();
  (state.allocations || []).forEach((row) => {
    const soeid = normalize(row?.assignee_user_soeid);
    if (!soeid) return;
    fteByUser.set(soeid, (fteByUser.get(soeid) || 0) + allocationFteMonths(row));
  });

  const users = (state.users || [])
    .filter((u) => {
      const teamTag = normalize(u.team_tag || "");
      const displayName = normalize(u.display_name || "");
      const soeid = normalize(u.soeid || "");
      const teamOk = !teamFilter || teamTag.includes(teamFilter);
      const nameOk = !nameFilter || displayName.includes(nameFilter) || soeid.includes(nameFilter);
      return teamOk && nameOk;
    })
    .sort((a, b) => (a.display_name || a.soeid || "").localeCompare(b.display_name || b.soeid || ""));
  const hasActiveFilters = !!(teamFilter || nameFilter);
  const totalUsersLoaded = Array.isArray(state.users) ? state.users.length : 0;

  const summary = users.reduce(
    (acc, u) => {
      const soeid = normalize(u.soeid || "");
      const cap = userCapacityFteMonth(u);
      const allocated = fteByUser.get(soeid) || 0;
      acc.members += 1;
      acc.capacity += cap;
      acc.allocated += allocated;
      return acc;
    },
    { members: 0, capacity: 0, allocated: 0 }
  );
  const remaining = Math.max(summary.capacity - summary.allocated, 0);

  const teams = new Map();
  users.forEach((u) => {
    const soeid = normalize(u.soeid || "");
    const teamLabel = String(u.team_tag || "").trim() || "Unassigned";
    const teamKey = normalize(teamLabel);
    const cap = userCapacityFteMonth(u);
    const allocated = fteByUser.get(soeid) || 0;
    const existing = teams.get(teamKey) || {
      label: teamLabel,
      members: 0,
      capacity: 0,
      allocated: 0,
    };
    existing.members += 1;
    existing.capacity += cap;
    existing.allocated += allocated;
    teams.set(teamKey, existing);
  });

  const teamRows = Array.from(teams.values()).sort((a, b) => a.label.localeCompare(b.label));
  const teamBody = teamRows.length
    ? teamRows
        .map((row) => {
          const teamRemaining = Math.max(row.capacity - row.allocated, 0);
          const teamLoadPct = row.capacity > 0
            ? Math.min(999, Math.round((row.allocated / row.capacity) * 100))
            : (row.allocated > 0 ? 999 : 0);
          const teamLoadClass = teamLoadPct >= 101 ? "over" : (teamLoadPct >= 85 ? "warn" : "ok");
          return `<tr>
            <td>${esc(row.label)}</td>
            <td>${row.members}</td>
            <td>${formatFte(row.capacity)}</td>
            <td>${formatFte(row.allocated)}</td>
            <td>${formatFte(teamRemaining)}</td>
            <td><span class="capacity-badge ${teamLoadClass}">${teamLoadPct}%</span></td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="6" class="muted">No team rows available for current filters.</td></tr>`;

  let rosterBody = "";
  if (!users.length) {
    const emptyMessage = loading
      ? "Loading roster..."
      : (hasActiveFilters && totalUsersLoaded > 0
        ? "No users match current filters. Clear Team Tag/Search filters."
        : "No users found in the active space.");
    rosterBody = `<tr><td colspan="7" class="muted">${emptyMessage}</td></tr>`;
  } else {
    rosterBody = users
      .map((u) => {
        const soeid = normalize(u.soeid || "");
        const cap = userCapacityFteMonth(u);
        const allocated = fteByUser.get(soeid) || 0;
        const remainingUser = Math.max(cap - allocated, 0);
        const loadPct = cap > 0 ? Math.min(999, Math.round((allocated / cap) * 100)) : (allocated > 0 ? 999 : 0);
        const loadClass = loadPct >= 101 ? "over" : (loadPct >= 85 ? "warn" : "ok");
        const selectedClass = selectedSoeid && normalize(selectedSoeid) === soeid ? "active-row" : "";
        return `<tr data-soeid="${esc(u.soeid || "")}" class="${selectedClass}">
          <td>${esc(u.display_name || u.soeid || "—")}</td>
          <td>${esc(u.soeid || "—")}</td>
          <td>${esc(u.team_tag || "—")}</td>
          <td>${formatFte(cap)}</td>
          <td>${formatFte(allocated)}</td>
          <td>${formatFte(remainingUser)}</td>
          <td><span class="capacity-badge ${loadClass}">${loadPct}%</span></td>
        </tr>`;
      })
      .join("");
  }

  const loadingNote = loading ? `<span class="pill warn">Refreshing...</span>` : "";
  const refreshNote = refreshedAt ? `<span class="muted">Last refreshed ${esc(refreshedAt)}</span>` : "";
  const activeSpaceNote = (activeSpaceName || activeSpaceId)
    ? `<span class="pill muted">Space: ${esc(activeSpaceName || activeSpaceId)}</span>`
    : "";
  const loadedSpaceMismatch =
    loadedSpaceId && activeSpaceId && loadedSpaceId !== activeSpaceId
      ? `<span class="pill warn">Loaded for ${esc(loadedSpaceName || loadedSpaceId)}</span>`
      : "";
  const errorNote = loadError ? `<span class="pill danger">${esc(loadError)}</span>` : "";
  const statusBits = [activeSpaceNote, loadedSpaceMismatch, refreshNote, loadingNote, errorNote].filter(Boolean).join(" ");
  els.capacityUserList.innerHTML = `
    <div class="panel-toolbar compact">
      <div class="toolbar-group">
        <h3>Team Capacity</h3>
      </div>
      <div class="toolbar-group">${statusBits}</div>
    </div>
    <div class="planning-kpis">
      <div class="kpi-card"><div class="kpi-label">Members</div><div class="kpi-value">${summary.members}</div></div>
      <div class="kpi-card"><div class="kpi-label">Loaded</div><div class="kpi-value">${totalUsersLoaded}</div></div>
      <div class="kpi-card"><div class="kpi-label">Capacity</div><div class="kpi-value">${formatFte(summary.capacity)}</div><div class="kpi-label">FTE-mo</div></div>
      <div class="kpi-card"><div class="kpi-label">Allocated</div><div class="kpi-value">${formatFte(summary.allocated)}</div><div class="kpi-label">FTE-mo</div></div>
      <div class="kpi-card"><div class="kpi-label">Remaining</div><div class="kpi-value">${formatFte(remaining)}</div><div class="kpi-label">FTE-mo</div></div>
    </div>
    <div class="panel-toolbar compact">
      <div class="toolbar-group">
        <h3>Team Summary</h3>
      </div>
      <div class="toolbar-group"><span class="muted">${teamRows.length} teams</span></div>
    </div>
    <div class="table">
      <table>
        <thead>
          <tr>
            <th>Team</th>
            <th>Members</th>
            <th>Capacity (FTE-mo)</th>
            <th>Allocated (FTE-mo)</th>
            <th>Remaining (FTE-mo)</th>
            <th>Load</th>
          </tr>
        </thead>
        <tbody>${teamBody}</tbody>
      </table>
    </div>
    <div class="panel-toolbar compact">
      <div class="toolbar-group">
        <h3>Roster</h3>
      </div>
      <div class="toolbar-group"><span class="muted">${users.length} visible</span></div>
    </div>
    <div class="table">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>SOEID</th>
            <th>Team Tag</th>
            <th>Capacity (FTE-mo)</th>
            <th>Allocated (FTE-mo)</th>
            <th>Remaining (FTE-mo)</th>
            <th>Load</th>
          </tr>
        </thead>
        <tbody>${rosterBody}</tbody>
      </table>
    </div>
  `;
}

export function render(ctx) {
  renderTeamCapacity(ctx);
}
