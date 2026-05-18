const kanbanState = {
  bound: false,
  ctx: null,
};

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderKanbanSolutionLink(label, solutionId) {
  const text = String(label || "").trim() || "Untitled";
  const targetId = String(solutionId || "").trim();
  if (!targetId) return `<strong>${esc(text)}</strong>`;
  return `<button type="button" class="kanban-solution-link" data-kanban-action="open-solution" data-solution-id="${esc(targetId)}">${esc(text)}</button>`;
}

function renderKanbanProjectLink(label, projectId, className = "") {
  const text = String(label || "").trim() || "Unassigned Project";
  const targetId = String(projectId || "").trim();
  const classToken = className ? ` ${className.trim()}` : "";
  if (!targetId || targetId === "none") return `<span class="kanban-project-title-text">${esc(text)}</span>`;
  return `<button type="button" class="kanban-project-link${classToken}" data-kanban-action="open-project" data-project-id="${esc(targetId)}">${esc(text)}</button>`;
}

function bindKanbanEvents() {
  const viewRoot = document.getElementById("view-kanban");
  if (!viewRoot || kanbanState.bound) return;
  kanbanState.bound = true;
  viewRoot.addEventListener("click", (event) => {
    const actionEl = event.target.closest("[data-kanban-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-kanban-action") || "";
    if (action === "open-project") {
      const projectId = actionEl.getAttribute("data-project-id") || "";
      if (!projectId) return;
      if (typeof kanbanState.ctx?.openKanbanProjectDrilldown === "function") {
        kanbanState.ctx.openKanbanProjectDrilldown(projectId);
      }
      return;
    }
    if (action === "open-solution") {
      const solutionId = actionEl.getAttribute("data-solution-id") || "";
      if (!solutionId) return;
      if (typeof kanbanState.ctx?.openKanbanSolutionDrilldown === "function") {
        kanbanState.ctx.openKanbanSolutionDrilldown(solutionId);
      }
    }
  });
}

function renderSolutionCards(cards, ctx) {
  const { phaseDisplayName, formatStatus } = ctx;
  if (!cards.length) return "<p class='muted'>Empty</p>";
  return cards
    .map((s) => {
      const phaseLabel = phaseDisplayName(s.current_phase) || "No phase";
      const versionMeta = s.version ? `<div class="meta">${esc(s.version)}</div>` : "";
      return `<div class="kanban-card"><div class="kanban-card-title">${renderKanbanSolutionLink(s.solution_name, s.solution_id)}</div>${versionMeta}<div class="meta">Owner ${esc(s.owner || "—")} • Assignee ${esc(s.assignee || "—")}</div><div class="meta">P${esc(s.priority ?? "")} • ${esc(phaseLabel)}</div><div class="meta">Due ${esc(s.due_date || "—")} • ${esc(formatStatus(s.status))}</div></div>`;
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
    html += `<div class="kanban-column"><h4>${esc(groupName)}</h4>${renderSolutionCards(groupCards, ctx)}</div>`;
  });
  html += `</div>`;
  return html;
}

export function renderKanban(ctx) {
  const { state, els, filteredSolutionsForKanban } = ctx;
  if (!els.kanbanBoard) return;
  kanbanState.ctx = ctx;
  bindKanbanEvents();

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
    html += `<div class="kanban-project"><div class="kanban-project-title">${renderKanbanProjectLink(projName, pid)} <span class="pill">${items.length}</span></div>`;
    html += renderSolutionSwimlane(items, phaseGroups, ctx);
    html += `</div>`;
  });

  els.kanbanBoard.innerHTML = html || "<p class='muted'>No items</p>";
}

export function render(ctx) {
  renderKanban(ctx);
}
