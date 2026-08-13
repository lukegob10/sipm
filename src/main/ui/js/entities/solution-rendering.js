import { escDisplay } from "../utils/display-tokens.js";

const escapeAttr = escDisplay;
const escapeHtml = escDisplay;

export function renderSolutionTaskCard(task) {
  return `<div class="swimlane-card" data-id="${escapeAttr(task.task_id)}">
    <div class="swimlane-title">${escapeHtml(task.task_name)}</div>
    <div class="swimlane-meta">${escapeHtml(task.assignee || "—")} • P${escapeHtml(task.priority ?? "–")}</div>
    <div class="swimlane-meta">Due ${escapeHtml(task.due_date || "—")}</div>
  </div>`;
}

export function renderSolutionTaskRow(task, statusLabel) {
  return `<tr data-id="${escapeAttr(task.task_id)}">
    <td><button class="icon-btn edit-task-btn" data-id="${escapeAttr(task.task_id)}" title="Edit">✎</button></td>
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
      const when = row.created_at ? new Date(row.created_at).toLocaleString() : "";
      const field = row.field ? ` • ${escapeHtml(row.field)}` : "";
      const change = row.new_value ? ` → ${escapeHtml(row.new_value)}` : "";
      return `<div class="activity-item">
        <div class="activity-title">${escapeHtml(row.action)}${field}${change}</div>
        <div class="activity-meta">${escapeHtml(row.user_id || "system")} • ${escapeHtml(when)}</div>
      </div>`;
    })
    .join("");
}
