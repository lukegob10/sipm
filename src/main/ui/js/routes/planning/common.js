import {
  FLASH_DURATION_MS,
  UNASSIGNED_TEAM_ID,
  boardState,
  rerenderPlanning,
} from "./state.js";

export function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function numberOr(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export function clampPercent(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function formatFte(value) {
  return numberOr(value, 0).toFixed(2);
}

export function isClosedTaskStatus(statusValue) {
  const status = String(statusValue || "").trim().toLowerCase();
  return status === "complete" || status === "abandoned";
}

export function showCompletedOperationalWork(ctx = boardState.ctx) {
  return !!ctx?.state?.workspacePrefs?.showCompleted;
}

export function visibleBoardTasks(ctx = boardState.ctx) {
  const tasks = Array.isArray(boardState.data.tasks) ? boardState.data.tasks : [];
  if (showCompletedOperationalWork(ctx)) return tasks;
  const subcomponents = Array.isArray(ctx?.state?.subcomponents) ? ctx.state.subcomponents : [];
  const statusByTaskId = new Map(
    subcomponents
      .filter((row) => row?.subcomponent_id)
      .map((row) => [String(row.subcomponent_id), String(row.status || "")])
  );
  return tasks.filter((task) => {
    const status = statusByTaskId.get(String(task?.id || ""));
    if (!status) return true;
    return !isClosedTaskStatus(status);
  });
}

export function visibleBoardAllocations(ctx = boardState.ctx, tasks = visibleBoardTasks(ctx)) {
  const visibleTaskIds = new Set(tasks.map((task) => String(task?.id || "")).filter(Boolean));
  return (boardState.data.allocations || []).filter((allocation) => visibleTaskIds.has(String(allocation?.task_id || "")));
}

export function toneClass(value, hasCapacity = true) {
  if (!hasCapacity && value > 0) return "over";
  if (value > 1) return "over";
  if (value >= 0.8) return "warn";
  return "ok";
}

export function clearFlashItems() {
  boardState.flashItems = [];
  if (boardState.flashTimer) {
    window.clearTimeout(boardState.flashTimer);
    boardState.flashTimer = 0;
  }
}

export function flashTargets(items, tone = "success", duration = FLASH_DURATION_MS) {
  const normalized = (Array.isArray(items) ? items : [])
    .filter((item) => item && item.kind && item.id)
    .map((item) => ({
      kind: String(item.kind),
      id: String(item.id),
      tone: item.tone || tone,
    }));
  clearFlashItems();
  boardState.flashItems = normalized;
  if (!normalized.length) return;
  boardState.flashTimer = window.setTimeout(() => {
    boardState.flashItems = [];
    boardState.flashTimer = 0;
    rerenderPlanning();
  }, duration);
}

export function flashClass(kind, id) {
  const match = (boardState.flashItems || []).find((item) => item.kind === kind && item.id === String(id));
  if (!match) return "";
  return ` wab-flash wab-flash-${match.tone || "success"}`;
}

export function setNotice(message, tone = "info") {
  boardState.notice = { message: String(message || ""), tone };
}

export function toggleTopPanel(panelName) {
  const next = String(panelName || "").trim();
  boardState.topPanel = boardState.topPanel === next ? "" : next;
  rerenderPlanning();
}

export function allocationsByTask() {
  const map = new Map();
  visibleBoardAllocations().forEach((allocation) => {
    if (!allocation?.task_id) return;
    const list = map.get(allocation.task_id) || [];
    list.push(allocation);
    map.set(allocation.task_id, list);
  });
  return map;
}

export function sortedTeams() {
  return [...(boardState.data.teams || [])].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
}

export function sortedPeople() {
  return [...(boardState.data.people || [])].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
}

export function sortedTasks() {
  return [...visibleBoardTasks()].sort((a, b) => (a.title || "").localeCompare(b.title || ""));
}

export function matchesPersonSearch(person) {
  const query = String(boardState.personSearch || "").trim().toLowerCase();
  if (!query) return true;
  return String(person?.name || "").toLowerCase().includes(query) || String(person?.id || "").toLowerCase().includes(query);
}

export function applyBacklogFilters(tasks) {
  const search = String(boardState.search || "").trim().toLowerCase();
  const effortFilter = boardState.effortFilter || "all";
  return tasks.filter((task) => {
    const title = String(task?.title || "").toLowerCase();
    if (search && !title.includes(search)) return false;
    const effort = numberOr(task?.fte_months, 0);
    if (effortFilter === "small" && effort > 0.25) return false;
    if (effortFilter === "medium" && (effort <= 0.25 || effort > 0.5)) return false;
    if (effortFilter === "large" && effort <= 0.5) return false;
    return true;
  });
}

export function normalizeTeamId(value) {
  const token = String(value || "").trim();
  if (!token || token === UNASSIGNED_TEAM_ID) return null;
  return token;
}

export function parseAssignmentTarget(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  if (raw === "backlog") return { type: "backlog", id: "" };
  const [kind, ...rest] = raw.split(":");
  const id = rest.join(":").trim();
  if (!id) return null;
  if (kind === "team" || kind === "person") return { type: kind, id };
  return null;
}

export function assignmentOptionsHtml(teams, people, selectedValue = "") {
  const assignablePeople = people.filter((person) => normalizeTeamId(person.team_id));
  const teamOptions = teams
    .map((team) => {
      const value = `team:${team.id}`;
      return `<option value="team:${esc(team.id)}" ${selectedValue === value ? "selected" : ""}>${esc(team.name)}</option>`;
    })
    .join("");
  const personOptions = assignablePeople
    .map((person) => {
      const team = teams.find((teamRow) => teamRow.id === person.team_id);
      const suffix = team?.name ? ` (${team.name})` : "";
      const value = `person:${person.id}`;
      return `<option value="person:${esc(person.id)}" ${selectedValue === value ? "selected" : ""}>${esc(person.name)}${esc(suffix)}</option>`;
    })
    .join("");
  return [
    `<option value="" ${selectedValue ? "" : "selected"}>Choose assignee</option>`,
    teamOptions ? `<optgroup label="Teams">${teamOptions}</optgroup>` : "",
    personOptions ? `<optgroup label="People">${personOptions}</optgroup>` : "",
  ].join("");
}
