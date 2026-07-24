function myWorkState(state) {
  if (!state.myWork) {
    state.myWork = {
      records: null,
      loading: false,
      error: "",
      selectedTaskId: "",
      search: "",
      repository: "",
      editingTaskId: "",
      draggingTaskId: "",
    };
  }
  return state.myWork;
}

function searchableText(record) {
  const task = record.task || {};
  return [
    task.task_name,
    task.description,
    task.status,
    record.program_name,
    record.project_name,
    record.solution_name,
    task.effective_github_repo_url,
  ].map((value) => String(value || "").toLowerCase()).join(" ");
}

function isClosedTask(task) {
  return ["complete", "abandoned"].includes(String(task?.status || "").toLowerCase());
}

function visibleRecords(ctx) {
  const work = myWorkState(ctx.state);
  const search = work.search.trim().toLowerCase();
  return (work.records || []).filter((record) => {
    if (!ctx.showCompletedOperationalWork?.() && isClosedTask(record.task)) return false;
    if (work.repository && record.task?.effective_github_repo_url !== work.repository) return false;
    return !search || searchableText(record).includes(search);
  });
}

function statusLabel(ctx, value) {
  return ctx.formatStatus ? ctx.formatStatus(value) : String(value || "").replaceAll("_", " ");
}

const HOURS_PER_FTE_MONTH = 160;

function fteInputValue(hours, fallback = "") {
  if (hours === null || hours === undefined || hours === "") return fallback;
  const numericHours = Number(hours);
  return Number.isFinite(numericHours) ? (numericHours / HOURS_PER_FTE_MONTH).toFixed(2) : fallback;
}

function hoursFromFteInput(value, fallback = null) {
  if (value === null || value === undefined || String(value).trim() === "") return fallback;
  const fte = Number(value);
  return Number.isFinite(fte) ? Math.round(Math.max(fte, 0) * HOURS_PER_FTE_MONTH) : fallback;
}

function resolvedAssigneeSoeid(ctx, task) {
  if (task.assignee_user_soeid) return String(task.assignee_user_soeid);
  if (!task.assignee) return "";
  return String((ctx.state.users || []).find((user) => user.display_name === task.assignee)?.soeid || "");
}

function assigneeOptions(ctx, task) {
  const users = [...(ctx.state.users || [])].sort((left, right) => (
    String(left.display_name || left.soeid).localeCompare(String(right.display_name || right.soeid))
  ));
  const selectedSoeid = resolvedAssigneeSoeid(ctx, task);
  const options = ['<option value="">Unassigned</option>'];

  if (!selectedSoeid && task.assignee) {
    options.push(`<option value="__legacy__" selected>${ctx.escapeHtml(task.assignee)} (not linked)</option>`);
  }
  if (selectedSoeid && !users.some((user) => user.soeid === selectedSoeid)) {
    options.push(`<option value="${ctx.escapeHtml(selectedSoeid)}" selected>${ctx.escapeHtml(task.assignee || selectedSoeid)}</option>`);
  }
  options.push(...users.map((user) => {
    const label = user.display_name ? `${user.display_name} (${user.soeid})` : user.soeid;
    return `<option value="${ctx.escapeHtml(user.soeid)}"${user.soeid === selectedSoeid ? " selected" : ""}>${ctx.escapeHtml(label)}</option>`;
  }));
  return options.join("");
}

function dueLabel(task) {
  if (!task.due_date) return "No due date";
  const formatted = new Date(`${task.due_date}T00:00:00`).toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
  if (task.is_overdue) return `Overdue · ${formatted}`;
  if (task.is_due_soon) return `Due soon · ${formatted}`;
  return `Due ${formatted}`;
}

function renderRepo(ctx, task) {
  const url = task.effective_github_repo_url || "";
  if (!url) return '<span class="muted">No repository attached</span>';
  return ctx.renderExternalRepoLink(url, {
    label: url,
    className: "repo-external-link-inline",
  });
}

function taskCard(ctx, record, selected) {
  const task = record.task;
  const attention = record.needs_attention;
  return `
    <button type="button" class="my-work-card${selected ? " is-selected" : ""}${attention ? " needs-attention" : ""}" data-my-work-select="${ctx.escapeHtml(task.task_id)}"${attention ? ' title="Pinned while blocked or overdue"' : ' draggable="true"'}>
      <span class="my-work-task-title">${ctx.escapeHtml(task.task_name)}</span>
      <span class="my-work-task-description">${ctx.escapeHtml(task.description || "No description provided.")}</span>
      <span class="my-work-card-due${attention ? " is-attention" : ""}">${ctx.escapeHtml(dueLabel(task))}</span>
    </button>
  `;
}

function renderQueue(ctx, records) {
  const work = myWorkState(ctx.state);
  return `
    <section class="my-work-queue-panel">
      <div class="my-work-queue-heading">
        <div>
          <h2>Task queue</h2>
          <p>Attention items stay pinned. Drag the rest to prioritize your work.</p>
        </div>
        <span class="my-work-count">${records.length}</span>
      </div>
      <div class="my-work-card-list is-drop-zone" data-my-work-drop-zone="queue">
        ${records.length
          ? records.map((record) => taskCard(ctx, record, record.task.task_id === work.selectedTaskId)).join("")
          : '<p class="my-work-empty-bucket">No tasks match these filters</p>'}
      </div>
    </section>
  `;
}

function editTaskForm(ctx, record) {
  const task = record.task;
  const statusOptions = [
    ["to_do", "To do"],
    ["in_progress", "In progress"],
    ["on_hold", "On hold"],
    ["complete", "Complete"],
    ["abandoned", "Abandoned"],
  ];
  return `
    <form class="my-work-detail my-work-edit-form" data-my-work-edit-form>
      <div class="my-work-edit-heading">
        <div>
          <span class="eyebrow">Edit shared Task</span>
          <h2>${ctx.escapeHtml(task.task_name)}</h2>
        </div>
        <div class="my-work-edit-heading-actions">
          <button type="submit">Save Task</button>
          <button type="button" class="secondary" data-my-work-edit-cancel>Cancel</button>
        </div>
      </div>
      <label class="my-work-edit-field"><span>Task name</span><input name="task_name" required value="${ctx.escapeHtml(task.task_name)}" /></label>
      <div class="my-work-edit-grid">
        <label class="my-work-edit-field"><span>Status</span><select class="app-select" name="status">${statusOptions.map(([value, label]) => `<option value="${value}"${task.status === value ? " selected" : ""}>${label}</option>`).join("")}</select></label>
        <label class="my-work-edit-field"><span>Due date</span><input type="date" name="due_date" value="${ctx.escapeHtml(task.due_date || "")}" /></label>
        <label class="my-work-edit-field"><span>Priority</span><select class="app-select" name="priority">${[0, 1, 2, 3, 4, 5].map((priority) => `<option value="${priority}"${Number(task.priority) === priority ? " selected" : ""}>${priority}</option>`).join("")}</select></label>
        <label class="preference-switch my-work-blocked-toggle"><input type="checkbox" name="blocked"${task.blocked ? " checked" : ""} /><span>Task is blocked</span></label>
      </div>
      <div class="my-work-edit-assignment-grid">
        <label class="my-work-edit-field"><span>Assignee</span><select class="app-select" name="assignee">${assigneeOptions(ctx, task)}</select></label>
        <label class="my-work-edit-field"><span>Assignee SOEID</span><input name="assignee_user_soeid" value="${ctx.escapeHtml(resolvedAssigneeSoeid(ctx, task))}" placeholder="SOEID" autocapitalize="none" spellcheck="false" /></label>
        <label class="my-work-edit-field"><span>Estimate (FTE-months)</span><input type="number" name="estimate_hours" min="0" step="0.01" value="${ctx.escapeHtml(fteInputValue(task.estimate_hours))}" /></label>
        <label class="my-work-edit-field"><span>Resource need (FTE-months)</span><input type="number" name="capacity_hours" min="0" step="0.01" value="${ctx.escapeHtml(fteInputValue(task.capacity_hours, "0.00"))}" /></label>
      </div>
      <label class="my-work-edit-field my-work-repo-editor"><span>GitHub repo override</span><input type="url" name="github_repo_url" value="${ctx.escapeHtml(task.github_repo_url || "")}" placeholder="https://github.com/owner/repository" /><small>${task.repo_source === "inherited" && task.effective_github_repo_url ? `Currently inherited from Solution: ${ctx.escapeHtml(task.effective_github_repo_url)}` : "Leave blank to inherit the Solution repository."}</small></label>
      <div class="my-work-edit-copy-grid">
        <label class="my-work-edit-field"><span>Description and context</span><textarea class="my-work-longform-editor" name="description" rows="6" placeholder="What needs to happen, and why?">${ctx.escapeHtml(task.description || "")}</textarea></label>
        <label class="my-work-edit-field"><span>Acceptance criteria</span><textarea class="my-work-longform-editor my-work-acceptance-editor" name="acceptance_criteria" rows="6" placeholder="What must be true for this Task to be complete?">${ctx.escapeHtml(task.acceptance_criteria || task.done_criteria || "")}</textarea></label>
      </div>
      <label class="my-work-edit-field"><span>Blocker context</span><textarea class="my-work-blocker-editor" name="blocker_note" rows="3" placeholder="What is blocked, and what would unblock it?"${task.blocked ? "" : " disabled"}>${ctx.escapeHtml(task.blocker_note || "")}</textarea></label>
      <p class="form-notice" data-my-work-edit-feedback role="status" aria-live="polite"></p>
    </form>
  `;
}

function detailPane(ctx, record) {
  if (!record) {
    return `
      <aside class="my-work-detail my-work-detail-empty">
        <div>
          <span class="my-work-detail-icon" aria-hidden="true">↗</span>
          <h2>Select a task</h2>
          <p>Review context, update shared status, or organize your private focus.</p>
        </div>
      </aside>
    `;
  }
  const work = myWorkState(ctx.state);
  if (work.editingTaskId === record.task.task_id) return editTaskForm(ctx, record);
  const task = record.task;
  const sharedAction = task.status === "in_progress"
    ? '<button type="button" data-my-work-shared-status="complete">Mark complete</button>'
    : '<button type="button" data-my-work-shared-status="in_progress">Start work</button>';
  return `
    <aside class="my-work-detail my-work-detail-view">
      <div class="my-work-detail-head">
        <div class="my-work-detail-head-copy">
          <span class="eyebrow">Shared SIPM Task</span>
          <h2>${ctx.escapeHtml(task.task_name)}</h2>
          <p>${ctx.escapeHtml(record.program_name || "Unmapped Program")} / ${ctx.escapeHtml(record.project_name)} / ${ctx.escapeHtml(record.solution_name)}</p>
        </div>
        <button type="button" class="secondary" data-my-work-edit>Edit Task</button>
      </div>
      <div class="my-work-detail-section">
        <div class="my-work-detail-facts">
          <span><small>Status</small><strong>${ctx.escapeHtml(statusLabel(ctx, task.status))}</strong></span>
          <span><small>Due</small><strong>${ctx.escapeHtml(dueLabel(task))}</strong></span>
          <span><small>Priority</small><strong>${ctx.escapeHtml(task.priority)}</strong></span>
        </div>
        ${task.blocked ? `<div class="my-work-blocker"><strong>Blocked</strong><span>${ctx.escapeHtml(task.blocker_note || "No blocker detail provided")}</span></div>` : ""}
      </div>
      <div class="my-work-detail-copy">
        <section class="my-work-detail-copy-section">
          <h3>Context</h3>
          <p>${ctx.escapeHtml(task.description || "No description yet.")}</p>
        </section>
        <section class="my-work-detail-copy-section">
          <h3>Acceptance criteria</h3>
          <p>${ctx.escapeHtml(task.acceptance_criteria || task.done_criteria || "No acceptance criteria yet.")}</p>
        </section>
      </div>
      <div class="my-work-detail-section">
        <h3>Repository</h3>
        <p>${renderRepo(ctx, task)}</p>
        ${task.effective_github_repo_url ? `<span class="muted">${ctx.escapeHtml(task.repo_source === "override" ? "Task override" : "Inherited from Solution")}</span>` : ""}
      </div>
      <div class="my-work-detail-footer">
        <p class="form-notice" data-my-work-feedback role="status" aria-live="polite"></p>
        <div class="my-work-detail-actions">
          ${sharedAction}
          <button type="button" class="secondary" data-my-work-open-tasks>Open in Tasks</button>
        </div>
      </div>
    </aside>
  `;
}

async function refreshMyWork(ctx) {
  const work = myWorkState(ctx.state);
  if (work.loading) return;
  work.loading = true;
  work.error = "";
  try {
    work.records = await ctx.api("/my-work");
    if (!work.selectedTaskId || !work.records.some((record) => record.task.task_id === work.selectedTaskId)) {
      work.selectedTaskId = work.records[0]?.task?.task_id || "";
    }
  } catch (err) {
    work.error = err.message || "My Work could not be loaded.";
    work.records = [];
  } finally {
    work.loading = false;
    renderMyWork(ctx);
  }
}

async function moveInQueue(ctx, taskId, targetTaskId, insertAfter) {
  const work = myWorkState(ctx.state);
  const moving = (work.records || []).find((record) => record.task.task_id === taskId);
  if (!moving || moving.needs_attention) return;

  const targetRecords = visibleRecords(ctx)
    .filter((record) => !record.needs_attention && record.task.task_id !== taskId);
  let insertionIndex = targetRecords.length;
  if (targetTaskId) {
    const target = (work.records || []).find((record) => record.task.task_id === targetTaskId);
    if (target?.needs_attention) {
      insertionIndex = 0;
    } else {
      const targetIndex = targetRecords.findIndex((record) => record.task.task_id === targetTaskId);
      if (targetIndex >= 0) insertionIndex = targetIndex + (insertAfter ? 1 : 0);
    }
  }
  targetRecords.splice(insertionIndex, 0, moving);

  try {
    await Promise.all(targetRecords.map((record, index) => ctx.api(
      `/my-work/tasks/${encodeURIComponent(record.task.task_id)}/state`,
      {
        method: "PATCH",
        body: JSON.stringify({ sort_rank: (index + 1) * 100 }),
      },
    )));
    work.records = null;
    renderMyWork(ctx);
  } catch (err) {
    work.error = err.message || "Queue order could not be saved.";
    renderMyWork(ctx);
  }
}

function clearQueueDropPreview(root) {
  root.querySelectorAll(".is-drag-over").forEach((zone) => zone.classList.remove("is-drag-over"));
  root.querySelectorAll(".drop-before, .drop-after").forEach((card) => {
    card.classList.remove("drop-before", "drop-after");
  });
}

function bindQueueDragging(ctx) {
  const root = ctx.els.myWorkRoot;
  const work = myWorkState(ctx.state);
  root.querySelectorAll('.my-work-card[draggable="true"]').forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      work.draggingTaskId = card.dataset.myWorkSelect || "";
      card.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", work.draggingTaskId);
    });
    card.addEventListener("dragend", () => {
      work.draggingTaskId = "";
      card.classList.remove("is-dragging");
      clearQueueDropPreview(root);
    });
  });

  root.querySelectorAll("[data-my-work-drop-zone]").forEach((zone) => {
    zone.addEventListener("dragover", (event) => {
      if (!work.draggingTaskId) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      zone.classList.add("is-drag-over");
      root.querySelectorAll(".drop-before, .drop-after").forEach((card) => {
        card.classList.remove("drop-before", "drop-after");
      });
      const targetCard = event.target.closest("[data-my-work-select]");
      if (!targetCard || targetCard.dataset.myWorkSelect === work.draggingTaskId) return;
      const targetIsPinned = targetCard.classList.contains("needs-attention");
      const insertAfter = targetIsPinned
        || event.clientY > targetCard.getBoundingClientRect().top + targetCard.getBoundingClientRect().height / 2;
      targetCard.classList.add(insertAfter ? "drop-after" : "drop-before");
    });
    zone.addEventListener("dragleave", (event) => {
      if (!zone.contains(event.relatedTarget)) clearQueueDropPreview(root);
    });
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      const taskId = work.draggingTaskId || event.dataTransfer.getData("text/plain");
      const targetCard = event.target.closest("[data-my-work-select]");
      const targetTaskId = targetCard?.dataset.myWorkSelect || "";
      const insertAfter = targetCard
        ? targetCard.classList.contains("drop-after")
        : true;
      work.draggingTaskId = "";
      clearQueueDropPreview(root);
      if (targetTaskId === taskId) return;
      void moveInQueue(ctx, taskId, targetTaskId, insertAfter);
    });
  });
}

function bindTaskEditing(ctx) {
  const root = ctx.els.myWorkRoot;
  const work = myWorkState(ctx.state);
  const selectedRecord = (work.records || []).find((record) => record.task.task_id === work.selectedTaskId) || null;
  root.querySelector("[data-my-work-edit]")?.addEventListener("click", () => {
    work.editingTaskId = work.selectedTaskId;
    renderMyWork(ctx);
  });
  root.querySelectorAll("[data-my-work-edit-cancel]").forEach((button) => {
    button.addEventListener("click", () => {
      work.editingTaskId = "";
      renderMyWork(ctx);
    });
  });

  const form = root.querySelector("[data-my-work-edit-form]");
  const blockedInput = form?.querySelector('[name="blocked"]');
  const blockerNote = form?.querySelector('[name="blocker_note"]');
  const assigneeSelect = form?.querySelector('[name="assignee"]');
  const assigneeSoeid = form?.querySelector('[name="assignee_user_soeid"]');
  blockedInput?.addEventListener("change", () => {
    blockerNote.disabled = !blockedInput.checked;
    if (blockedInput.checked) blockerNote.focus();
  });
  assigneeSelect?.addEventListener("change", () => {
    if (assigneeSelect.value !== "__legacy__") assigneeSoeid.value = assigneeSelect.value;
  });
  assigneeSoeid?.addEventListener("input", () => {
    const normalized = assigneeSoeid.value.trim().toLowerCase();
    const matchingUser = (ctx.state.users || []).find((user) => String(user.soeid).toLowerCase() === normalized);
    if (matchingUser) assigneeSelect.value = matchingUser.soeid;
    else if (!normalized) assigneeSelect.value = "";
  });
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const feedback = form.querySelector("[data-my-work-edit-feedback]");
    const submit = form.querySelector('button[type="submit"]');
    const data = new FormData(form);
    const blocked = !!data.get("blocked");
    const assigneeSelection = String(data.get("assignee") || "");
    const assigneeUserSoeid = String(data.get("assignee_user_soeid") || "").trim();
    const linkedAssignee = (ctx.state.users || []).find((user) => (
      String(user.soeid).toLowerCase() === assigneeUserSoeid.toLowerCase()
    ));
    const preserveLegacyAssignee = assigneeSelection === "__legacy__" && !assigneeUserSoeid;
    submit.disabled = true;
    if (feedback) feedback.textContent = "Saving shared Task…";
    try {
      await ctx.api(`/tasks/${encodeURIComponent(work.selectedTaskId)}`, {
        method: "PATCH",
        body: JSON.stringify({
          task_name: String(data.get("task_name") || "").trim(),
          description: String(data.get("description") || "").trim() || null,
          github_repo_url: String(data.get("github_repo_url") || "").trim() || null,
          status: String(data.get("status") || "to_do"),
          acceptance_criteria: String(data.get("acceptance_criteria") || "").trim() || null,
          due_date: String(data.get("due_date") || "") || null,
          priority: Number(data.get("priority")),
          assignee: preserveLegacyAssignee
            ? selectedRecord?.task?.assignee || null
            : assigneeUserSoeid ? linkedAssignee?.display_name || assigneeUserSoeid : null,
          assignee_user_soeid: assigneeUserSoeid || null,
          estimate_hours: hoursFromFteInput(data.get("estimate_hours")),
          capacity_hours: hoursFromFteInput(data.get("capacity_hours"), 0),
          blocked,
          blocker_note: blocked ? String(data.get("blocker_note") || "").trim() || null : null,
        }),
      });
      work.editingTaskId = "";
      work.records = null;
      renderMyWork(ctx);
    } catch (err) {
      if (feedback) feedback.textContent = err.message || "Task changes could not be saved.";
      submit.disabled = false;
    }
  });
}

function bindInteractions(ctx) {
  const root = ctx.els.myWorkRoot;
  const work = myWorkState(ctx.state);
  root.querySelector("[data-my-work-search]")?.addEventListener("input", (event) => {
    work.search = event.target.value;
    renderMyWork(ctx);
    root.querySelector("[data-my-work-search]")?.focus();
  });
  root.querySelector("[data-my-work-repo]")?.addEventListener("change", (event) => {
    work.repository = event.target.value;
    renderMyWork(ctx);
  });
  root.querySelectorAll("[data-my-work-select]").forEach((button) => {
    button.addEventListener("click", () => {
      work.selectedTaskId = button.dataset.myWorkSelect || "";
      work.editingTaskId = "";
      renderMyWork(ctx);
    });
  });
  bindQueueDragging(ctx);
  bindTaskEditing(ctx);
  root.querySelector("[data-my-work-shared-status]")?.addEventListener("click", async (event) => {
    const feedback = root.querySelector("[data-my-work-feedback]");
    try {
      await ctx.api(`/tasks/${encodeURIComponent(work.selectedTaskId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: event.currentTarget.dataset.myWorkSharedStatus }),
      });
      work.records = null;
      renderMyWork(ctx);
    } catch (err) {
      if (feedback) feedback.textContent = err.message || "Task update failed.";
    }
  });
  root.querySelector("[data-my-work-open-tasks]")?.addEventListener("click", () => ctx.setView("tasks-workbench"));
}

export function renderMyWork(ctx) {
  const root = ctx.els.myWorkRoot;
  if (!root) return;
  const work = myWorkState(ctx.state);
  if (work.records === null && !work.loading) {
    root.innerHTML = '<div class="my-work-loading"><span class="spinner" aria-hidden="true"></span><p>Loading your assigned work…</p></div>';
    void refreshMyWork(ctx);
    return;
  }
  if (work.loading) return;
  const records = visibleRecords(ctx);
  const selected = records.find((record) => record.task.task_id === work.selectedTaskId) || records[0] || null;
  const repositories = [...new Set((work.records || []).map((record) => record.task.effective_github_repo_url).filter(Boolean))].sort();
  const showCompleted = !!ctx.showCompletedOperationalWork?.();
  const hiddenClosedCount = showCompleted
    ? 0
    : (work.records || []).filter((record) => isClosedTask(record.task)).length;
  const emptyMessage = hiddenClosedCount
    ? `No open Tasks are assigned to you in this space. ${hiddenClosedCount} completed or abandoned task${hiddenClosedCount === 1 ? " is" : "s are"} hidden. Enable Show completed work in Preferences to review ${hiddenClosedCount === 1 ? "it" : "them"}.`
    : "No active Tasks are assigned to you in this space.";
  root.innerHTML = `
    <div class="my-work-toolbar">
      <label class="my-work-control my-work-search"><span>Search work</span><input type="search" data-my-work-search value="${ctx.escapeHtml(work.search)}" placeholder="Task, project, solution, or repository" /></label>
      <label class="my-work-control"><span>Repository</span><select class="app-select" data-my-work-repo><option value="">All repositories</option>${repositories.map((repo) => `<option value="${ctx.escapeHtml(repo)}"${work.repository === repo ? " selected" : ""}>${ctx.escapeHtml(repo.replace("https://github.com/", ""))}</option>`).join("")}</select></label>
      <div class="my-work-toolbar-summary"><strong>${records.length}</strong><span>${showCompleted ? "assigned" : "active assigned"} task${records.length === 1 ? "" : "s"}</span></div>
    </div>
    ${work.error ? `<div class="route-error-card"><strong>My Work unavailable</strong><p>${ctx.escapeHtml(work.error)}</p></div>` : ""}
    ${!work.error && !records.length && !work.search && !work.repository ? `<div class="my-work-empty"><span aria-hidden="true">✓</span><h2>You are clear</h2><p>${ctx.escapeHtml(emptyMessage)}</p></div>` : `
      <div class="my-work-layout">
        <div class="my-work-queue">${renderQueue(ctx, records)}</div>
        ${detailPane(ctx, selected)}
      </div>`}
  `;
  bindInteractions(ctx);
}

export function render(ctx) {
  renderMyWork(ctx);
}
