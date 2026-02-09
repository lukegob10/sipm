function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function urgencyPill(score) {
  const n = Number(score || 0);
  if (n >= 75) return "danger";
  if (n >= 45) return "warn";
  if (n <= 0) return "muted";
  return "positive";
}

export function renderSubcomponentsWorkbench(ctx) {
  const {
    els,
    rows,
    activeSubcomponentId,
    selectedIds,
    formatStatus,
    summary,
  } = ctx;

  if (els.subcomponentsWorkbenchKpis) {
    const total = Number(summary?.total || 0);
    const visible = Number(summary?.visible || 0);
    const overdue = Number(summary?.overdue || 0);
    const dueSoon = Number(summary?.dueSoon || 0);
    const blocked = Number(summary?.blocked || 0);
    const unassigned = Number(summary?.unassigned || 0);
    els.subcomponentsWorkbenchKpis.innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Visible Queue</div><div class="kpi-value">${visible}</div><div class="kpi-label">of ${total} in space</div></div>
      <div class="kpi-card"><div class="kpi-label">Overdue</div><div class="kpi-value">${overdue}</div><div class="kpi-label">action now</div></div>
      <div class="kpi-card"><div class="kpi-label">Due Soon (14d)</div><div class="kpi-value">${dueSoon}</div><div class="kpi-label">upcoming load</div></div>
      <div class="kpi-card"><div class="kpi-label">Blocked</div><div class="kpi-value">${blocked}</div><div class="kpi-label">needs unblock</div></div>
      <div class="kpi-card"><div class="kpi-label">Unassigned</div><div class="kpi-value">${unassigned}</div><div class="kpi-label">needs owner</div></div>
    `;
  }

  if (!els.subcomponentsWorkbenchTable) return;

  if (!rows.length) {
    els.subcomponentsWorkbenchTable.innerHTML = "<p class='muted'>No subcomponents match the current filters in this space.</p>";
    return;
  }

  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.has(row.subcomponent_id));
  const rowsHtml = rows
    .map((row) => {
      const isSelected = selectedIds.has(row.subcomponent_id);
      const isActive = row.subcomponent_id === activeSubcomponentId;
      const statusLabel = formatStatus(row.status);
      const urgencyClass = urgencyPill(row.urgency_score);
      const blocker = row.blocked ? "<span class='pill warn'>Blocked</span>" : "";
      const due = row.due_date || "—";
      return `
        <tr data-id="${row.subcomponent_id}" class="${isActive ? "active-row" : ""}">
          <td><input type="checkbox" class="scwb-select-row" data-id="${row.subcomponent_id}" ${isSelected ? "checked" : ""} /></td>
          <td><button type="button" class="icon-btn scwb-edit-btn" data-id="${row.subcomponent_id}" title="Edit">✎</button></td>
          <td>
            <strong>${esc(row.subcomponent_name || "—")}</strong>
            <span class="sub-workbench-context">${esc(row.project_name || "—")} / ${esc(row.solution_name || "—")}</span>
          </td>
          <td class="sub-workbench-status-cell">${statusLabel} ${blocker}</td>
          <td>${esc(row.assignee || "Unassigned")}</td>
          <td>${due}</td>
          <td>${Number(row.priority ?? 0) || "—"}</td>
          <td><span class="pill ${urgencyClass} sub-workbench-urgency">${Number(row.urgency_score || 0).toFixed(0)}</span></td>
        </tr>
      `;
    })
    .join("");

  els.subcomponentsWorkbenchTable.innerHTML = `
    <table class="sub-workbench-table">
      <thead>
        <tr>
          <th><input type="checkbox" id="scwb-select-all" ${allSelected ? "checked" : ""} /></th>
          <th></th>
          <th>Subcomponent</th>
          <th>Status</th>
          <th>Assignee</th>
          <th>Due</th>
          <th>Priority</th>
          <th>Urgency</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}
