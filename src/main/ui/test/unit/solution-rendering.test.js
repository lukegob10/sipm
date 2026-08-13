import { describe, expect, it, vi } from "vitest";

import {
  renderSolutionActivityItems,
  renderSolutionTaskCard,
  renderSolutionTaskRow,
} from "../../js/entities/solution-rendering.js";

const injectedSelector = [
  "script",
  "img",
  "svg",
  "iframe",
  "a",
  "[autofocus]",
  "[onerror]",
  "[onfocus]",
  "[onload]",
].join(",");

function maliciousTask() {
  return {
    task_id: 'task-1" autofocus onfocus="alert(1)',
    task_name: '<script data-xss="task-name">alert(1)</script>',
    assignee: '<img data-xss="assignee" src=x onerror="alert(2)">',
    status: '<svg data-xss="status" onload="alert(3)"></svg>',
    priority: '<iframe data-xss="priority"></iframe>',
    due_date: '<a data-xss="due" href="javascript:alert(4)">today</a>',
  };
}

describe("solution detail rendering", () => {
  it("renders swimlane task values as text without allowing data-id attribute breakout", () => {
    const task = maliciousTask();
    const container = document.createElement("div");

    container.innerHTML = renderSolutionTaskCard(task);

    const card = container.querySelector(".swimlane-card");
    const meta = card.querySelectorAll(".swimlane-meta");
    expect(container.querySelector(injectedSelector)).toBeNull();
    expect(card.dataset.id).toBe(task.task_id);
    expect(card.querySelector(".swimlane-title").textContent).toBe(task.task_name);
    expect(meta[0].textContent).toBe(`${task.assignee} • P${task.priority}`);
    expect(meta[1].textContent).toBe(`Due ${task.due_date}`);
  });

  it("renders table task values as text without allowing data-id attribute breakout", () => {
    const task = maliciousTask();
    const table = document.createElement("table");
    const body = document.createElement("tbody");
    table.appendChild(body);

    body.innerHTML = renderSolutionTaskRow(task, task.status);

    const row = body.querySelector("tr");
    const editButton = row.querySelector(".edit-task-btn");
    const cells = row.querySelectorAll("td");
    expect(body.querySelector(injectedSelector)).toBeNull();
    expect(row.dataset.id).toBe(task.task_id);
    expect(editButton.dataset.id).toBe(task.task_id);
    expect(cells[1].textContent).toBe(task.task_name);
    expect(cells[2].textContent).toBe(task.status);
    expect(cells[3].textContent).toBe(task.assignee);
    expect(cells[4].textContent).toBe(task.priority);
    expect(cells[5].textContent).toBe(task.due_date);
  });

  it("renders every solution activity value as text", () => {
    const action = '<script data-xss="action">alert(1)</script>';
    const field = '<img data-xss="field" src=x onerror="alert(2)">';
    const newValue = '<svg data-xss="new-value" onload="alert(3)"></svg>';
    const user = '<iframe data-xss="user"></iframe>';
    const time = '<a data-xss="time" href="javascript:alert(4)">now</a>';
    vi.spyOn(Date.prototype, "toLocaleString").mockReturnValue(time);
    const container = document.createElement("div");

    container.innerHTML = renderSolutionActivityItems([{
      action,
      field,
      new_value: newValue,
      user_id: user,
      created_at: "2026-08-12T12:34:56Z",
    }]);

    expect(container.querySelector(injectedSelector)).toBeNull();
    expect(container.querySelector(".activity-title").textContent).toBe(`${action} • ${field} → ${newValue}`);
    expect(container.querySelector(".activity-meta").textContent).toBe(`${user} • ${time}`);
  });
});
