import { escDisplay } from "../utils/display-tokens.js";
import { formatUtcTimestamp } from "../utils/date-only.js";

const escapeAttr = escDisplay;
const escapeHtml = escDisplay;

export function renderSolutionTaskCard(task) {
  return `<button type="button" class="swimlane-card" data-id="${escapeAttr(task.task_id)}" aria-label="Edit task ${escapeAttr(task.task_name || "Unnamed task")}">
    <span class="swimlane-title">${escapeHtml(task.task_name)}</span>
    <span class="swimlane-meta">${escapeHtml(task.assignee || "—")} • P${escapeHtml(task.priority ?? "–")}</span>
    <span class="swimlane-meta">Due ${escapeHtml(task.due_date || "—")}</span>
  </button>`;
}

export function renderSolutionTaskRow(task, statusLabel) {
  return `<tr data-id="${escapeAttr(task.task_id)}">
    <td><button type="button" class="icon-btn edit-task-btn" data-id="${escapeAttr(task.task_id)}" aria-label="Edit task ${escapeAttr(task.task_name || "Unnamed task")}" title="Edit">✎</button></td>
    <td>${escapeHtml(task.task_name || "—")}</td>
    <td>${escapeHtml(statusLabel)}</td>
    <td>${escapeHtml(task.assignee || "—")}</td>
    <td>${escapeHtml(task.priority ?? "—")}</td>
    <td>${escapeHtml(task.due_date || "")}</td>
  </tr>`;
}

export function renderSolutionActivityItems(rows) {
  return rows
    .map((row) => {
      const when = formatUtcTimestamp(row.created_at);
      const field = row.field ? ` • ${escapeHtml(row.field)}` : "";
      const change = row.new_value ? ` → ${escapeHtml(row.new_value)}` : "";
      return `<div class="activity-item">
        <div class="activity-title">${escapeHtml(row.action)}${field}${change}</div>
        <div class="activity-meta">${escapeHtml(row.user_id || "system")} • ${escapeHtml(when)}</div>
      </div>`;
    })
    .join("");
}
