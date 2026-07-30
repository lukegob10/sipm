import {
  bindSharedActions,
  renderSharedActionNotice,
  renderSharedActions,
} from "./my-work/shared-actions.js";

const LANE_ORDER = ["today", "later"];

const LANE_DEFINITIONS = {
  today: {
    title: "Today",
    description: "The short list you intend to work on now.",
    empty: "Drop a task here when you are ready to work on it.",
  },
  later: {
    title: "Later",
    description: "Assigned work that is staged for another time.",
    empty: "No tasks are waiting for later.",
  },
};

const PRIVATE_BUCKETS = new Set(["today", "later"]);

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
      savingPrivateTaskId: "",
      detailTab: "task",
      privateNotice: null,
    };
  }
  const work = state.myWork;
  work.detailTab = work.detailTab === "notes" ? "notes" : "task";
  return work;
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
    record.private_note,
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

function normalizedPrivateBucket(record) {
  return PRIVATE_BUCKETS.has(record?.private_bucket) ? record.private_bucket : "later";
}

function laneForRecord(record) {
  return isClosedTask(record?.task) ? "later" : normalizedPrivateBucket(record);
}

function numberOr(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function compareFallback(a, b) {
  const aTask = a.task || {};
  const bTask = b.task || {};
  const urgencyDifference = numberOr(bTask.urgency_score, 0) - numberOr(aTask.urgency_score, 0);
  if (urgencyDifference) return urgencyDifference;
  const aDue = aTask.due_date || "9999-12-31";
  const bDue = bTask.due_date || "9999-12-31";
  const dueDifference = String(aDue).localeCompare(String(bDue));
  if (dueDifference) return dueDifference;
  const priorityDifference = numberOr(aTask.priority, 999) - numberOr(bTask.priority, 999);
  if (priorityDifference) return priorityDifference;
  return String(aTask.task_name || "").localeCompare(String(bTask.task_name || ""), undefined, {
    sensitivity: "base",
  });
}

function comparePrivate(a, b) {
  const aRank = numberOr(a.private_sort_rank, 0);
  const bRank = numberOr(b.private_sort_rank, 0);
  const normalizedARank = aRank > 0 ? aRank : Number.POSITIVE_INFINITY;
  const normalizedBRank = bRank > 0 ? bRank : Number.POSITIVE_INFINITY;
  if (normalizedARank !== normalizedBRank) return normalizedARank - normalizedBRank;
  return compareFallback(a, b);
}

function compareClosed(a, b) {
  const aDate = Date.parse(a.task?.completed_at || a.task?.updated_at || 0) || 0;
  const bDate = Date.parse(b.task?.completed_at || b.task?.updated_at || 0) || 0;
  if (aDate !== bDate) return bDate - aDate;
  return compareFallback(a, b);
}

function plannedRecords(records) {
  const lanes = Object.fromEntries(LANE_ORDER.map((lane) => [lane, []]));
  records.forEach((record) => lanes[laneForRecord(record)].push(record));
  lanes.today.sort(comparePrivate);
  const activeLater = lanes.later.filter((record) => !isClosedTask(record.task)).sort(comparePrivate);
  const closedLater = lanes.later.filter((record) => isClosedTask(record.task)).sort(compareClosed);
  lanes.later = [...activeLater, ...closedLater];
  return lanes;
}

function recordsInDisplayOrder(lanes) {
  return LANE_ORDER.flatMap((lane) => lanes[lane]);
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

function reminderLabel(value) {
  if (!value) return "No reminder";
  const reminder = new Date(value);
  if (Number.isNaN(reminder.getTime())) return "No reminder";
  return reminder.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function datetimeLocalValue(value) {
  if (!value) return "";
  const reminder = new Date(value);
  if (Number.isNaN(reminder.getTime())) return "";
  const localTime = new Date(reminder.getTime() - reminder.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 16);
}

function reminderUtcValue(value) {
  if (!value) return null;
  const reminder = new Date(value);
  if (Number.isNaN(reminder.getTime())) throw new Error("Choose a valid reminder date and time.");
  return reminder.toISOString();
}

function renderRepo(ctx, task) {
  const url = task.effective_github_repo_url || "";
  if (!url) return '<span class="muted">No repository attached</span>';
  return ctx.renderExternalRepoLink(url, {
    label: url,
    className: "repo-external-link-inline",
  });
}

function taskSignal(ctx, record) {
  const task = record.task || {};
  if (task.blocked) return "Blocked";
  if (task.is_overdue) return "Overdue";
  if (record.reminder_due) return "Reminder due";
  if (String(task.status || "").toLowerCase() === "on_hold") return "Waiting";
  if (task.is_due_soon) return "Due soon";
  return statusLabel(ctx, task.status);
}

function taskCard(ctx, record, selected, lane, reorderEnabled) {
  const task = record.task;
  const closed = isClosedTask(task);
  const attention = !closed && !!(record.needs_attention || record.reminder_due || task.is_overdue || task.blocked);
  const draggable = reorderEnabled && !closed;
  const saving = myWorkState(ctx.state).savingPrivateTaskId === task.task_id;
  const targetLane = lane === "today" ? "later" : "today";
  return `
    <article class="my-work-card${selected ? " is-selected" : ""}${attention ? " needs-attention" : ""}${closed ? " is-closed" : ""}" data-my-work-card="${ctx.escapeHtml(task.task_id)}" data-my-work-lane="${lane}" role="listitem"${draggable ? ' draggable="true"' : ""}>
      <button type="button" class="my-work-card-main" data-my-work-select="${ctx.escapeHtml(task.task_id)}" aria-pressed="${selected ? "true" : "false"}">
        <span class="my-work-task-title">${ctx.escapeHtml(task.task_name)}</span>
        <span class="my-work-task-description">${ctx.escapeHtml(task.description || "No description provided.")}</span>
        <span class="my-work-card-meta">
          <span class="my-work-card-signal${attention ? " is-attention" : ""}">${ctx.escapeHtml(taskSignal(ctx, record))}</span>
          <span class="my-work-card-due">${ctx.escapeHtml(dueLabel(task))}</span>
        </span>
      </button>
      ${closed ? "" : `<button type="button" class="my-work-card-move" data-my-work-move="${targetLane}" data-my-work-task="${ctx.escapeHtml(task.task_id)}" aria-label="Move ${ctx.escapeHtml(task.task_name)} to ${LANE_DEFINITIONS[targetLane].title}"${saving ? " disabled" : ""}>${targetLane === "today" ? "← Today" : "Later →"}</button>`}
    </article>
  `;
}

function renderLane(ctx, lane, records, selectedTaskId, reorderEnabled) {
  const definition = LANE_DEFINITIONS[lane];
  return `
    <section class="my-work-lane is-${lane}" data-my-work-lane-panel="${lane}">
      <div class="my-work-lane-heading">
        <div>
          <h2>${definition.title}</h2>
          <p>${definition.description}</p>
        </div>
        <span class="my-work-count">${records.length}</span>
      </div>
      <div class="my-work-card-list is-drop-zone" data-my-work-drop-zone="${lane}" role="list" tabindex="0" aria-label="${definition.title} tasks">
        ${records.length
          ? records.map((record) => taskCard(
            ctx,
            record,
            record.task.task_id === selectedTaskId,
            lane,
            reorderEnabled,
          )).join("")
          : `<p class="my-work-empty-bucket">${definition.empty}</p>`}
      </div>
    </section>
  `;
}

function renderQueue(ctx, lanes, records, selectedTaskId) {
  const work = myWorkState(ctx.state);
  const filtered = !!work.search.trim() || !!work.repository;
  const reorderEnabled = !filtered;
  if (!records.length && filtered) {
    return `
      <section class="my-work-queue-panel">
        <div class="my-work-filter-empty">
          <h2>No work matches these filters</h2>
          <p>Adjust the search or repository filter to see assigned work.</p>
        </div>
      </section>
    `;
  }
  return `
    <section class="my-work-queue-panel">
      <div class="my-work-queue-heading">
        <div>
          <h2>Plan</h2>
          <p>${reorderEnabled ? "Drag to prioritize, or use each task's Move button." : "Clear filters to drag and reorder. Move buttons still work."}</p>
        </div>
        <span class="my-work-count">${records.length}</span>
      </div>
      <div class="my-work-lanes">
        ${LANE_ORDER.map((lane) => renderLane(
          ctx,
          lane,
          lanes[lane],
          selectedTaskId,
          reorderEnabled,
        )).join("")}
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

function notesPanel(ctx, record) {
  const work = myWorkState(ctx.state);
  const saving = myWorkState(ctx.state).savingPrivateTaskId === record.task.task_id;
  const notice = work.privateNotice?.taskId === record.task.task_id
    ? work.privateNotice.message
    : "";
  return `
    <section id="my-work-notes-panel" class="my-work-notes-panel" role="tabpanel" aria-labelledby="my-work-notes-tab">
      <div class="my-work-notes-heading">
        <div>
          <span class="eyebrow">Private workspace</span>
          <h3>Notes for ${ctx.escapeHtml(record.task.task_name)}</h3>
          <p>Only you can see this note and reminder. They stay attached to this task.</p>
        </div>
      </div>
      <form data-my-work-private-form>
        <label class="my-work-edit-field"><span>Private note for this task</span><textarea name="private_note" rows="12" placeholder="Capture your working notes, decisions to revisit, or next steps.">${ctx.escapeHtml(record.private_note || "")}</textarea></label>
        <label class="my-work-edit-field my-work-reminder-field"><span>Reminder</span><input type="datetime-local" name="reminder_at" value="${ctx.escapeHtml(datetimeLocalValue(record.private_reminder_at))}" /></label>
        <div class="my-work-notes-actions">
          <button type="submit"${saving ? " disabled" : ""}>Save note</button>
          <button type="button" class="secondary" data-my-work-clear-reminder${record.private_reminder_at ? "" : " disabled"}>Clear reminder</button>
        </div>
        <p class="form-notice" data-my-work-private-feedback role="status" aria-live="polite">${ctx.escapeHtml(notice)}</p>
      </form>
    </section>
  `;
}

function taskDetailPanel(ctx, record) {
  const task = record.task;
  return `
    <div id="my-work-task-panel" role="tabpanel" aria-labelledby="my-work-task-tab">
      <div class="my-work-detail-section">
        <div class="my-work-detail-facts">
          <span><small>Status</small><strong>${ctx.escapeHtml(statusLabel(ctx, task.status))}</strong></span>
          <span><small>Due</small><strong>${ctx.escapeHtml(dueLabel(task))}</strong></span>
          <span><small>Priority</small><strong>${ctx.escapeHtml(task.priority)}</strong></span>
          <span><small>Plan</small><strong>${ctx.escapeHtml(LANE_DEFINITIONS[laneForRecord(record)].title)}</strong></span>
          <span><small>Reminder</small><strong>${ctx.escapeHtml(reminderLabel(record.private_reminder_at))}</strong></span>
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
        ${renderSharedActions(ctx, record)}
      </div>
    </div>
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
  const notesSelected = work.detailTab === "notes";
  return `
    <aside class="my-work-detail my-work-detail-view">
      <div class="my-work-detail-head">
        <div class="my-work-detail-head-copy">
          <span class="eyebrow">Shared SIPM Task</span>
          <h2>${ctx.escapeHtml(task.task_name)}</h2>
          <p>${ctx.escapeHtml(record.program_name || "Unmapped Program")} / ${ctx.escapeHtml(record.project_name)} / ${ctx.escapeHtml(record.solution_name)}</p>
        </div>
        ${notesSelected ? "" : '<button type="button" class="secondary" data-my-work-edit>Edit Task</button>'}
      </div>
      <div class="my-work-detail-tabs" role="tablist" aria-label="Selected task workspace">
        <button id="my-work-task-tab" type="button" role="tab" aria-selected="${notesSelected ? "false" : "true"}" aria-controls="my-work-task-panel" data-my-work-detail-tab="task">Task details</button>
        <button id="my-work-notes-tab" type="button" role="tab" aria-selected="${notesSelected ? "true" : "false"}" aria-controls="my-work-notes-panel" data-my-work-detail-tab="notes">My notes${record.private_note ? '<span class="my-work-note-indicator" aria-label="Has a saved private note"></span>' : ""}</button>
      </div>
      ${notesSelected ? notesPanel(ctx, record) : taskDetailPanel(ctx, record)}
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

async function patchPrivateState(ctx, taskId, patch) {
  const work = myWorkState(ctx.state);
  work.savingPrivateTaskId = taskId;
  work.privateNotice = null;
  const feedback = ctx.els.myWorkRoot.querySelector("[data-my-work-private-feedback]");
  if (feedback) feedback.textContent = "Saving your note…";
  try {
    const saved = await ctx.api(`/my-work/tasks/${encodeURIComponent(taskId)}/state`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    const record = (work.records || []).find((item) => item.task.task_id === taskId);
    if (record) {
      record.private_bucket = saved.bucket;
      record.private_sort_rank = saved.sort_rank;
      record.private_reminder_at = saved.reminder_at;
      record.private_note = saved.private_note;
      record.reminder_due = !!saved.reminder_at && new Date(saved.reminder_at).getTime() <= Date.now();
      record.needs_attention = !isClosedTask(record.task) && !!(
        record.reminder_due || record.task.is_overdue || record.task.blocked
      );
    }
    work.savingPrivateTaskId = "";
    work.error = "";
    work.privateNotice = { taskId, message: "Private note saved." };
    renderMyWork(ctx);
  } catch (err) {
    work.savingPrivateTaskId = "";
    if (feedback) feedback.textContent = err.message || "Your private note could not be saved.";
    else work.error = err.message || "Your private note could not be saved.";
  } finally {
    work.savingPrivateTaskId = "";
  }
}

async function moveInPrivateLanes(ctx, taskId, targetBucket, targetTaskId, insertAfter) {
  if (!PRIVATE_BUCKETS.has(targetBucket)) return;
  const work = myWorkState(ctx.state);
  const allLanes = plannedRecords((work.records || []).filter((record) => !isClosedTask(record.task)));
  const moving = (work.records || []).find((record) => record.task.task_id === taskId);
  const sourceBucket = normalizedPrivateBucket(moving || {});
  if (!moving) return;

  const sourceRecords = allLanes[sourceBucket].filter((record) => record.task.task_id !== taskId);
  const targetRecords = sourceBucket === targetBucket
    ? sourceRecords
    : allLanes[targetBucket].filter((record) => record.task.task_id !== taskId);
  let insertionIndex = targetRecords.length;
  if (targetTaskId) {
    const targetIndex = targetRecords.findIndex((record) => record.task.task_id === targetTaskId);
    if (targetIndex >= 0) insertionIndex = targetIndex + (insertAfter ? 1 : 0);
  }
  targetRecords.splice(insertionIndex, 0, moving);

  const previousState = new Map(targetRecords.map((record) => [record.task.task_id, {
    bucket: record.private_bucket,
    sortRank: record.private_sort_rank,
  }]));
  const updates = [];
  targetRecords.forEach((record, index) => {
    const desiredRank = (index + 1) * 100;
    if (normalizedPrivateBucket(record) !== targetBucket || numberOr(record.private_sort_rank, 0) !== desiredRank) {
      updates.push({ record, bucket: targetBucket, sortRank: desiredRank });
    }
    record.private_bucket = targetBucket;
    record.private_sort_rank = desiredRank;
  });
  work.savingPrivateTaskId = taskId;
  work.privateNotice = null;
  renderMyWork(ctx);
  try {
    await Promise.all(updates.map((update) => ctx.api(
      `/my-work/tasks/${encodeURIComponent(update.record.task.task_id)}/state`,
      {
        method: "PATCH",
        body: JSON.stringify({ bucket: update.bucket, sort_rank: update.sortRank }),
      },
    )));
    work.savingPrivateTaskId = "";
    work.error = "";
    renderMyWork(ctx);
  } catch (err) {
    const saveError = err.message || "Private work order could not be saved.";
    previousState.forEach((previous, previousTaskId) => {
      const record = (work.records || []).find((item) => item.task.task_id === previousTaskId);
      if (!record) return;
      record.private_bucket = previous.bucket;
      record.private_sort_rank = previous.sortRank;
    });
    work.savingPrivateTaskId = "";
    try {
      work.records = await ctx.api("/my-work");
      work.error = saveError;
    } catch (refreshError) {
      work.records = [];
      work.error = `${saveError} ${refreshError.message || "My Work could not be refreshed."}`;
    }
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
      work.draggingTaskId = card.dataset.myWorkCard || "";
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
      const targetCard = event.target.closest("[data-my-work-card]");
      if (!targetCard || targetCard.dataset.myWorkCard === work.draggingTaskId) return;
      const insertAfter = event.clientY > targetCard.getBoundingClientRect().top
        + targetCard.getBoundingClientRect().height / 2;
      targetCard.classList.add(insertAfter ? "drop-after" : "drop-before");
    });
    zone.addEventListener("dragleave", (event) => {
      if (!zone.contains(event.relatedTarget)) clearQueueDropPreview(root);
    });
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      const taskId = work.draggingTaskId || event.dataTransfer.getData("text/plain");
      const targetCard = event.target.closest("[data-my-work-card]");
      const targetTaskId = targetCard?.dataset.myWorkCard || "";
      const targetBucket = zone.dataset.myWorkDropZone || "";
      const insertAfter = targetCard ? targetCard.classList.contains("drop-after") : true;
      work.draggingTaskId = "";
      clearQueueDropPreview(root);
      if (targetTaskId === taskId) return;
      void moveInPrivateLanes(ctx, taskId, targetBucket, targetTaskId, insertAfter);
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

function bindPrivatePlanning(ctx, selected) {
  if (!selected) return;
  const root = ctx.els.myWorkRoot;
  const form = root.querySelector("[data-my-work-private-form]");
  form?.querySelector("[data-my-work-clear-reminder]")?.addEventListener("click", () => {
    const reminderInput = form.querySelector('[name="reminder_at"]');
    reminderInput.value = "";
    reminderInput.focus();
  });
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const feedback = form.querySelector("[data-my-work-private-feedback]");
    try {
      const patch = {
        reminder_at: reminderUtcValue(String(data.get("reminder_at") || "")),
        private_note: String(data.get("private_note") || "").trim() || null,
      };
      void patchPrivateState(ctx, selected.task.task_id, patch);
    } catch (err) {
      if (feedback) feedback.textContent = err.message;
    }
  });
}

function bindInteractions(ctx, selected) {
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
      work.detailTab = "task";
      work.privateNotice = null;
      renderMyWork(ctx);
    });
  });
  root.querySelectorAll("[data-my-work-move]").forEach((button) => {
    button.addEventListener("click", () => {
      const targetLane = button.dataset.myWorkMove || "";
      const taskId = button.dataset.myWorkTask || "";
      if (!PRIVATE_BUCKETS.has(targetLane) || !taskId) return;
      void moveInPrivateLanes(ctx, taskId, targetLane, "", true);
    });
  });
  root.querySelectorAll("[data-my-work-detail-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      work.detailTab = button.dataset.myWorkDetailTab === "notes" ? "notes" : "task";
      work.editingTaskId = "";
      renderMyWork(ctx);
      if (work.detailTab === "notes") root.querySelector('[name="private_note"]')?.focus();
    });
  });
  bindQueueDragging(ctx);
  bindTaskEditing(ctx);
  bindPrivatePlanning(ctx, selected);

  bindSharedActions(ctx, {
    record: selected,
    refresh: () => renderMyWork(ctx),
  });
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
  const lanes = plannedRecords(records);
  const displayRecords = recordsInDisplayOrder(lanes);
  const selected = displayRecords.find((record) => record.task.task_id === work.selectedTaskId)
    || displayRecords[0]
    || null;
  if (selected && selected.task.task_id !== work.selectedTaskId) work.selectedTaskId = selected.task.task_id;
  const repositories = [...new Set((work.records || [])
    .map((record) => record.task.effective_github_repo_url)
    .filter(Boolean))].sort();
  const showCompleted = !!ctx.showCompletedOperationalWork?.();
  const hiddenClosedCount = showCompleted
    ? 0
    : (work.records || []).filter((record) => isClosedTask(record.task)).length;
  const emptyMessage = hiddenClosedCount
    ? `No open Tasks are assigned to you in this space. ${hiddenClosedCount} completed or abandoned task${hiddenClosedCount === 1 ? " is" : "s are"} hidden. Enable Show completed work in Preferences to review ${hiddenClosedCount === 1 ? "it" : "them"}.`
    : "No active Tasks are assigned to you in this space.";
  root.innerHTML = `
    <div class="my-work-toolbar">
      <label class="my-work-control my-work-search"><span>Search work</span><input type="search" data-my-work-search value="${ctx.escapeHtml(work.search)}" placeholder="Task, project, solution, repository, or private note" /></label>
      <label class="my-work-control"><span>Repository</span><select class="app-select" data-my-work-repo><option value="">All repositories</option>${repositories.map((repo) => `<option value="${ctx.escapeHtml(repo)}"${work.repository === repo ? " selected" : ""}>${ctx.escapeHtml(repo.replace("https://github.com/", ""))}</option>`).join("")}</select></label>
      <div class="my-work-toolbar-summary"><strong>${records.length}</strong><span>${showCompleted ? "assigned" : "active assigned"} task${records.length === 1 ? "" : "s"}</span></div>
    </div>
    ${renderSharedActionNotice(ctx)}
    ${work.error ? `<div class="route-error-card"><strong>My Work unavailable</strong><p>${ctx.escapeHtml(work.error)}</p></div>` : ""}
    ${!work.error && !records.length && !work.search && !work.repository ? `<div class="my-work-empty"><span aria-hidden="true">✓</span><h2>You are clear</h2><p>${ctx.escapeHtml(emptyMessage)}</p></div>` : `
      <div class="my-work-layout">
        <div class="my-work-queue">${renderQueue(ctx, lanes, records, selected?.task?.task_id || "")}</div>
        ${detailPane(ctx, selected)}
      </div>`}
  `;
  bindInteractions(ctx, selected);
}

export function render(ctx) {
  renderMyWork(ctx);
}
