import { renderRouteState } from "../ui/route-state.js";

const kanbanState = {
  boundRoots: new WeakSet(),
  ctx: null,
  draggedSolutionId: "",
  draggedProjectId: "",
  draggedPhaseId: "",
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

function clearKanbanDragState(root) {
  kanbanState.draggedSolutionId = "";
  kanbanState.draggedProjectId = "";
  kanbanState.draggedPhaseId = "";
  root?.querySelectorAll(".is-dragging, .is-drop-eligible, .is-drop-target").forEach((element) => {
    element.classList.remove("is-dragging", "is-drop-eligible", "is-drop-target");
  });
}

function isValidPhaseDrop(column) {
  if (!column || !kanbanState.draggedSolutionId) return false;
  return column.dataset.projectId === kanbanState.draggedProjectId
    && !!column.dataset.phaseId
    && column.dataset.phaseId !== kanbanState.draggedPhaseId;
}

function showEligiblePhaseDrops(root) {
  root.querySelectorAll('[data-kanban-dropzone="phase"]').forEach((column) => {
    column.classList.toggle("is-drop-eligible", isValidPhaseDrop(column));
  });
}

function renderKanbanPhaseOptions(phases, currentPhaseId) {
  const hasCurrentPhase = phases.some((phase) => phase.phase_id === currentPhaseId);
  const placeholder = hasCurrentPhase ? "" : "<option value=\"\" selected disabled>Choose phase</option>";
  const options = phases.map((phase) => {
    const selected = phase.phase_id === currentPhaseId ? " selected" : "";
    return "<option value=\"" + esc(phase.phase_id) + "\"" + selected + ">" + esc(phase.phase_name) + "</option>";
  }).join("");
  return placeholder + options;
}

function renderKanbanPhaseControl(solution, phases, pending) {
  if (!phases.length) return "";
  const currentPhase = phases.find((phase) => phase.phase_id === solution.current_phase);
  const initialOption = currentPhase
    ? "<option value=\"" + esc(currentPhase.phase_id) + "\" selected>" + esc(currentPhase.phase_name) + "</option>"
    : "<option value=\"\" selected disabled>Choose phase</option>";
  const disabled = pending ? " disabled" : "";
  const label = "Move " + esc(solution.solution_name || "Untitled solution") + " to phase";
  return "<select class=\"kanban-phase-select\" data-kanban-phase-select data-solution-id=\""
    + esc(solution.solution_id)
    + "\" data-current-phase=\"" + esc(solution.current_phase || "")
    + "\" aria-label=\"" + label + "\"" + disabled + ">" + initialOption + "</select>";
}

function populateKanbanPhaseOptions(phaseSelect) {
  if (phaseSelect.dataset.kanbanOptionsLoaded === "true") return;
  const phases = [...(kanbanState.ctx?.state?.phases || [])].sort((a, b) => a.sequence - b.sequence);
  phaseSelect.innerHTML = renderKanbanPhaseOptions(phases, phaseSelect.dataset.currentPhase || "");
  phaseSelect.dataset.kanbanOptionsLoaded = "true";
}

function bindKanbanEvents() {
  const viewRoot = document.getElementById("view-kanban");
  if (!viewRoot || kanbanState.boundRoots.has(viewRoot)) return;
  kanbanState.boundRoots.add(viewRoot);
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
  viewRoot.addEventListener("change", (event) => {
    const phaseSelect = event.target.closest("[data-kanban-phase-select]");
    if (!phaseSelect) return;
    const restoreFocus = phaseSelect.dataset.kanbanKeyboardSelection === "true"
      && document.activeElement === phaseSelect;
    delete phaseSelect.dataset.kanbanKeyboardSelection;
    const solutionId = phaseSelect.getAttribute("data-solution-id") || "";
    const phaseId = phaseSelect.value || "";
    if (solutionId && phaseId) {
      const move = kanbanState.ctx?.moveKanbanSolutionToPhase?.(solutionId, phaseId);
      if (restoreFocus && move && typeof move.then === "function") {
        void Promise.resolve(move).finally(() => {
          if (!viewRoot.isConnected) return;
          const activeElement = document.activeElement;
          if (activeElement !== document.body && activeElement !== phaseSelect) return;
          const replacement = [...viewRoot.querySelectorAll("[data-kanban-phase-select]")]
            .find((select) => select.getAttribute("data-solution-id") === solutionId);
          if (replacement && !replacement.disabled) replacement.focus();
        });
      }
    }
  });
  viewRoot.addEventListener("keydown", (event) => {
    const phaseSelect = event.target.closest("[data-kanban-phase-select]");
    if (!phaseSelect) return;
    const selectionKeys = [" ", "Spacebar", "ArrowDown", "ArrowUp", "Home", "End", "PageDown", "PageUp", "Enter"];
    if (selectionKeys.includes(event.key) || (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey)) {
      phaseSelect.dataset.kanbanKeyboardSelection = "true";
    }
  });
  viewRoot.addEventListener("focusin", (event) => {
    const phaseSelect = event.target.closest("[data-kanban-phase-select]");
    if (phaseSelect) populateKanbanPhaseOptions(phaseSelect);
  });
  viewRoot.addEventListener("pointerdown", (event) => {
    const phaseSelect = event.target.closest("[data-kanban-phase-select]");
    if (!phaseSelect) return;
    delete phaseSelect.dataset.kanbanKeyboardSelection;
    populateKanbanPhaseOptions(phaseSelect);
  });
  viewRoot.addEventListener("dragstart", (event) => {
    if (event.target.closest("[data-kanban-phase-select]")) return;
    const card = event.target.closest('[data-kanban-draggable="solution"]');
    if (!card || card.getAttribute("draggable") !== "true") return;
    kanbanState.draggedSolutionId = card.dataset.solutionId || "";
    kanbanState.draggedProjectId = card.dataset.projectId || "";
    kanbanState.draggedPhaseId = card.dataset.currentPhase || "";
    card.classList.add("is-dragging");
    showEligiblePhaseDrops(viewRoot);
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", kanbanState.draggedSolutionId);
    }
  });
  viewRoot.addEventListener("dragover", (event) => {
    const column = event.target.closest('[data-kanban-dropzone="phase"]');
    if (!isValidPhaseDrop(column)) return;
    event.preventDefault();
    viewRoot.querySelectorAll(".is-drop-target").forEach((element) => {
      if (element !== column) element.classList.remove("is-drop-target");
    });
    column.classList.add("is-drop-target");
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
  });
  viewRoot.addEventListener("dragleave", (event) => {
    const column = event.target.closest('[data-kanban-dropzone="phase"]');
    if (column && !column.contains(event.relatedTarget)) column.classList.remove("is-drop-target");
  });
  viewRoot.addEventListener("drop", (event) => {
    const column = event.target.closest('[data-kanban-dropzone="phase"]');
    if (!isValidPhaseDrop(column)) return;
    event.preventDefault();
    const solutionId = kanbanState.draggedSolutionId || event.dataTransfer?.getData("text/plain") || "";
    const phaseId = column.dataset.phaseId || "";
    clearKanbanDragState(viewRoot);
    if (solutionId && phaseId) {
      void kanbanState.ctx?.moveKanbanSolutionToPhase?.(solutionId, phaseId);
    }
  });
  viewRoot.addEventListener("dragend", () => clearKanbanDragState(viewRoot));
}

function renderSolutionCards(cards, phases, ctx) {
  const { phaseDisplayName, formatStatus, isKanbanSolutionMovePending } = ctx;
  if (!cards.length) return "<p class='muted'>Empty</p>";
  return cards
    .map((s) => {
      const phaseLabel = phaseDisplayName(s.current_phase) || "No phase";
      const versionMeta = s.version ? `<div class="meta">${esc(s.version)}</div>` : "";
      const pending = !!isKanbanSolutionMovePending?.(s.solution_id);
      const cardClass = `kanban-card${pending ? " is-updating" : ""}`;
      const dragLabel = `Move ${s.solution_name || "Untitled solution"}. Current phase: ${phaseLabel}.`;
      return `<div class="${cardClass}" draggable="${pending ? "false" : "true"}" data-kanban-draggable="solution" data-solution-id="${esc(s.solution_id)}" data-project-id="${esc(s.project_id)}" data-current-phase="${esc(s.current_phase || "")}" aria-label="${esc(dragLabel)}"><div class="kanban-card-title">${renderKanbanSolutionLink(s.solution_name, s.solution_id)}</div>${versionMeta}<div class="meta">Owner ${esc(s.owner || "—")} • Assignee ${esc(s.assignee || "—")}</div><div class="meta">P${esc(s.priority ?? "")} • ${esc(phaseLabel)}</div><div class="meta">Due ${esc(s.due_date || "—")} • ${esc(formatStatus(s.status))}</div>${renderKanbanPhaseControl(s, phases, pending)}</div>`;
    })
    .join("");
}

function renderSolutionSwimlane(items, phases, projectId, ctx) {
  const { state } = ctx;
  let html = `<div class="kanban-swimlane">`;
  const unassigned = items.filter((s) => !s.current_phase || !state.phases.find((p) => p.phase_id === s.current_phase));
  if (unassigned.length) {
    html += `<div class="kanban-column"><h4>Unassigned</h4>${renderSolutionCards(unassigned, phases, ctx)}</div>`;
  }
  phases.forEach((phase) => {
    const phaseCards = items.filter((solution) => solution.current_phase === phase.phase_id);
    html += `<div class="kanban-column" data-kanban-dropzone="phase" data-project-id="${esc(projectId)}" data-phase-id="${esc(phase.phase_id)}"><h4>${esc(phase.phase_name)}</h4>${renderSolutionCards(phaseCards, phases, ctx)}</div>`;
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
  const phases = [...(state.phases || [])].sort((a, b) => a.sequence - b.sequence);

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
    html += renderSolutionSwimlane(items, phases, pid, ctx);
    html += `</div>`;
  });

  clearKanbanDragState(els.kanbanBoard);
  els.kanbanBoard.innerHTML = html || renderRouteState({
    kicker: "No matching work",
    title: "The board is clear",
    message: "No solutions match the selected project and owner filters.",
  });
}

export function render(ctx) {
  renderKanban(ctx);
}
