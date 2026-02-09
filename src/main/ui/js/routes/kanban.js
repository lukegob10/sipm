function renderSolutionCards(cards, ctx) {
  const { state, phaseDisplayName, formatStatus } = ctx;
  if (!cards.length) return "<p class='muted'>Empty</p>";
  return cards
    .map((s) => {
      const proj = state.projects.find((p) => p.project_id === s.project_id)?.project_name || "";
      const phaseLabel = phaseDisplayName(s.current_phase) || "No phase";
      return `<div class="kanban-card"><strong>${s.solution_name}</strong><div class="meta">${proj}${s.version ? " • " + s.version : ""}</div><div class="meta">Owner ${s.owner || "—"} • Assignee ${s.assignee || "—"}</div><div class="meta">P${s.priority ?? ""} • ${phaseLabel}</div><div class="meta">Due ${s.due_date || "—"} • ${formatStatus(s.status)}</div></div>`;
    })
    .join("");
}

function renderSolutionSwimlane(items, phaseGroups, ctx) {
  const { state } = ctx;
  let html = `<div class="kanban-swimlane">`;
  const unassigned = items.filter((s) => !s.current_phase || !state.phases.find((p) => p.phase_id === s.current_phase));
  if (unassigned.length) {
    html += `<div class="kanban-column"><h4>Unassigned</h4>${renderSolutionCards(unassigned, ctx)}</div>`;
  }
  phaseGroups.forEach((groupName) => {
    const groupCards = items.filter((s) => {
      const phase = state.phases.find((p) => p.phase_id === s.current_phase);
      return (phase?.phase_group || "Unassigned") === groupName;
    });
    html += `<div class="kanban-column"><h4>${groupName}</h4>${renderSolutionCards(groupCards, ctx)}</div>`;
  });
  html += `</div>`;
  return html;
}

export function renderKanban(ctx) {
  const { state, els, filteredSolutionsForKanban } = ctx;
  if (!els.kanbanBoard) return;

  const list = filteredSolutionsForKanban();
  const phaseGroups = Array.from(
    new Set((state.phases || []).sort((a, b) => a.sequence - b.sequence).map((p) => p.phase_group))
  );

  const byProject = {};
  list.forEach((s) => {
    const pid = s.project_id || "none";
    byProject[pid] = byProject[pid] || [];
    byProject[pid].push(s);
  });

  let html = "";
  Object.entries(byProject).forEach(([pid, items]) => {
    const projName = state.projects.find((p) => p.project_id === pid)?.project_name || "Unassigned Project";
    html += `<div class="kanban-project"><div class="kanban-project-title">${projName} <span class="pill">${items.length}</span></div>`;
    html += renderSolutionSwimlane(items, phaseGroups, ctx);
    html += `</div>`;
  });

  els.kanbanBoard.innerHTML = html || "<p class='muted'>No items</p>";
}
