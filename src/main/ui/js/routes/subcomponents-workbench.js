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

function renderSubcomponentsWorkbenchProjectLink(label, projectId) {
  const text = String(label || "").trim() || "—";
  const targetId = String(projectId || "").trim();
  if (!targetId) return esc(text);
  return `<button type="button" class="sub-workbench-context-link" data-scwb-action="open-project" data-project-id="${esc(targetId)}">${esc(text)}</button>`;
}

function renderSubcomponentsWorkbenchSolutionLink(label, solutionId) {
  const text = String(label || "").trim() || "—";
  const targetId = String(solutionId || "").trim();
  if (!targetId) return esc(text);
  return `<button type="button" class="sub-workbench-context-link" data-scwb-action="open-solution" data-solution-id="${esc(targetId)}">${esc(text)}</button>`;
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
    const hiddenClosed = Number(summary?.hiddenClosed || 0);
    els.subcomponentsWorkbenchTable.innerHTML = hiddenClosed
      ? `<p class='muted'>No open subcomponents match the current filters. ${hiddenClosed} completed or abandoned item${hiddenClosed === 1 ? "" : "s"} are hidden. Use Show Completed in the top bar to review them.</p>`
      : "<p class='muted'>No subcomponents match the current filters in this space.</p>";
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
        <tr data-id="${row.subcomponent_id}" class="${isActive ? "active-row" : ""}" tabindex="-1">
          <td><input type="checkbox" class="scwb-select-row" data-id="${row.subcomponent_id}" ${isSelected ? "checked" : ""} /></td>
          <td>
            <strong>${esc(row.subcomponent_name || "—")}</strong>
            <span class="sub-workbench-context">${renderSubcomponentsWorkbenchProjectLink(row.project_name, row.project_id)} / ${renderSubcomponentsWorkbenchSolutionLink(row.solution_name, row.solution_id)}</span>
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
