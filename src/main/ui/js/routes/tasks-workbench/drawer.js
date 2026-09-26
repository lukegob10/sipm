import { captureEntityMutationContext, isEntityMutationContextCurrent } from "../../entities/mutation-context.js";

const taskWorkbenchDraftFields = [
  "task_name",
  "description",
  "acceptance_criteria",
  "status",
  "priority",
  "due_date",
  "blocker_note",
  "blocked",
  "assignee",
  "assignee_user_soeid",
];
const taskWorkbenchDraftBaselines = new WeakMap();

function readTaskWorkbenchDraft(form) {
  return Object.fromEntries(taskWorkbenchDraftFields.map((name) => {
    const field = form.querySelector(`[name="${name}"]`);
    return [name, field?.type === "checkbox" ? !!field.checked : (field?.value || "")];
  }));
}

function taskWorkbenchValues(ctx, task) {
  const assigneeValue = ctx.resolveAssigneeSelectValue(task.assignee_user_soeid, task.assignee) || "";
  return {
    task_name: task.task_name || "",
    description: task.description || "",
    acceptance_criteria: task.acceptance_criteria || task.done_criteria || "",
    status: task.status || "to_do",
    priority: task.priority == null ? "" : String(task.priority),
    due_date: task.due_date || "",
    blocker_note: task.blocker_note || "",
    blocked: !!task.blocked,
    assignee: assigneeValue,
    assignee_user_soeid: assigneeValue,
  };
}

function writeTaskWorkbenchDraft(form, values) {
  taskWorkbenchDraftFields.forEach((name) => {
    const field = form.querySelector(`[name="${name}"]`);
    if (!field) return;
    if (field.type === "checkbox") field.checked = !!values[name];
    else field.value = values[name] == null ? "" : values[name];
  });
}

function sameTaskWorkbenchDraft(left, right) {
  return taskWorkbenchDraftFields.every((name) => left[name] === right[name]);
}

function taskWorkbenchSelectionRevision(form) {
  return Number(form.dataset.taskSelectionRevision || 0);
}

function advanceTaskWorkbenchSelectionRevision(form) {
  form.dataset.taskSelectionRevision = String(taskWorkbenchSelectionRevision(form) + 1);
}

function isTypingInputTarget(target) {
  if (!target) return false;
  const tag = (target.tagName || "").toLowerCase();
  if (["input", "textarea", "select", "button"].includes(tag)) return true;
  if (target.isContentEditable) return true;
  return false;
}

function renderTasksWorkbenchDrawerProjectLink(ctx, label, projectId) {
  const { escapeHtml } = ctx;
  const text = String(label || "").trim() || "Unknown project";
  const targetId = String(projectId || "").trim();
  if (!targetId) return escapeHtml(text);
  return `<button type="button" class="task-workbench-context-link" data-twb-context-action="open-project" data-project-id="${escapeHtml(targetId)}">${escapeHtml(text)}</button>`;
}

function renderTasksWorkbenchDrawerSolutionLink(ctx, label, solutionId) {
  const { escapeHtml } = ctx;
  const text = String(label || "").trim() || "Unknown solution";
  const targetId = String(solutionId || "").trim();
  if (!targetId) return escapeHtml(text);
  return `<button type="button" class="task-workbench-context-link" data-twb-context-action="open-solution" data-solution-id="${escapeHtml(targetId)}">${escapeHtml(text)}</button>`;
}

function renderTasksWorkbenchDrawerRepoContext(ctx, task) {
  const { effectiveTaskRepoInfo, renderExternalRepoLink, escapeHtml } = ctx;
  const { url, source } = effectiveTaskRepoInfo(
    task?.solution_id,
    task?.github_repo_url
  );
  if (!url) {
    return `<span class="task-workbench-context-secondary">Repo: <span class="muted">Not set</span></span>`;
  }
  const sourceLabel = source === "override" ? "override" : "inherited";
  return `<span class="task-workbench-context-secondary">Repo: ${renderExternalRepoLink(url, {
    label: url,
    className: "repo-external-link-inline",
  })} <span class="task-workbench-context-source">(${escapeHtml(sourceLabel)})</span></span>`;
}

export function syncTasksWorkbenchDrawer(ctx) {
  const { state, els } = ctx;
  const wb = state.tasksWorkbench;
  const drawerOpen = wb.drawerOpen !== false;
  if (els.tasksWorkbenchDrawer) {
    els.tasksWorkbenchDrawer.classList.toggle("hidden", !drawerOpen);
    els.tasksWorkbenchDrawer.setAttribute("aria-hidden", drawerOpen ? "false" : "true");
  }
  if (els.tasksWorkbenchLayout) {
    els.tasksWorkbenchLayout.classList.toggle("task-workbench-layout-editor-open", drawerOpen);
  }
}

export function openTasksWorkbenchDrawer(ctx, preferredTaskId = "") {
  const { state, els, persistTasksWorkbenchUiState, renderTasksWorkbench } = ctx;
  const wb = state.tasksWorkbench;
  if (wb.drawerOpen === false) {
    const anchorId =
      preferredTaskId || wb.activeTaskId || (Array.isArray(wb.visibleIds) ? wb.visibleIds[0] : "") || "";
    wb.drawerReturnTaskId = anchorId;
    wb.drawerReturnScrollY = window.scrollY || window.pageYOffset || 0;
  }
  if (preferredTaskId) {
    wb.activeTaskId = preferredTaskId;
  } else if (!wb.activeTaskId && Array.isArray(wb.visibleIds) && wb.visibleIds.length) {
    wb.activeTaskId = wb.visibleIds[0];
  }
  wb.drawerOpen = true;
  persistTasksWorkbenchUiState();
  renderTasksWorkbench();
  window.requestAnimationFrame(() => {
    const target = document.getElementById("tasks-workbench-editor-title")
      || els.tasksWorkbenchForm?.querySelector('[name="task_name"]');
    if (target && typeof target.focus === "function") {
      try {
        target.focus({ preventScroll: true });
      } catch {
        target.focus();
      }
    }
  });
}

export function closeTasksWorkbenchDrawer(ctx) {
  const { state, els, persistTasksWorkbenchUiState, renderTasksWorkbench } = ctx;
  const wb = state.tasksWorkbench;
  const returnTaskId = wb.activeTaskId || wb.drawerReturnTaskId || "";
  wb.activeTaskId = returnTaskId;
  wb.drawerOpen = false;
  wb.drawerReturnTaskId = "";
  wb.drawerReturnScrollY = null;
  wb.suppressAutoScrollOnce = true;
  persistTasksWorkbenchUiState();
  renderTasksWorkbench();
  window.requestAnimationFrame(() => {
    if (!returnTaskId || !els.tasksWorkbenchTable) return;
    const row = Array.from(els.tasksWorkbenchTable.querySelectorAll("tr[data-id]")).find(
      (node) => node.getAttribute("data-id") === returnTaskId
    );
    if (row && typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest" });
    }
    const target = row || row?.querySelector(".scwb-select-row");
    if (!target || typeof target.focus !== "function") return;
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  });
}

export function setActiveTaskByOffset(ctx, offset) {
  const { state, renderTasksWorkbench } = ctx;
  const wb = state.tasksWorkbench;
  const ids = wb.visibleIds || [];
  if (!ids.length) return;
  const rawIndex = ids.indexOf(wb.activeTaskId);
  if (rawIndex === -1) {
    wb.activeTaskId = offset >= 0 ? ids[0] : ids[ids.length - 1];
    renderTasksWorkbench();
    return;
  }
  const nextIndex = Math.min(ids.length - 1, Math.max(0, rawIndex + offset));
  const nextId = ids[nextIndex];
  if (!nextId) return;
  wb.activeTaskId = nextId;
  renderTasksWorkbench();
}

export function scrollActiveTaskIntoView(ctx) {
  const { state, els } = ctx;
  const wb = state.tasksWorkbench;
  if (!wb.activeTaskId || !els.tasksWorkbenchTable) return;
  const row = els.tasksWorkbenchTable.querySelector(`tr[data-id="${wb.activeTaskId}"]`);
  if (row && typeof row.scrollIntoView === "function") {
    row.scrollIntoView({ block: "nearest" });
  }
}

export async function renderTasksWorkbenchActivity(ctx, taskId) {
  const { els, state, api, escapeHtml } = ctx;
  const activityEl = els.tasksWorkbenchActivity;
  const wb = state.tasksWorkbench;
  if (!activityEl) return;
  const reqId = (wb.activityRequestId || 0) + 1;
  wb.activityRequestId = reqId;
  if (!taskId) {
    activityEl.innerHTML = "<p class='muted'>Select a task to see activity.</p>";
    return;
  }
  activityEl.innerHTML = "<p class='muted'>Loading activity…</p>";
  try {
    const rows = await api(`/tasks/${encodeURIComponent(taskId)}/activity?limit=12`);
    if (wb.activityRequestId !== reqId) return;
    if (!rows?.length) {
      activityEl.innerHTML = "<p class='muted'>No activity yet.</p>";
      return;
    }
    activityEl.innerHTML = rows
      .map((row) => {
        const action = escapeHtml(row.action || "update");
        const field = row.field ? ` • ${escapeHtml(row.field)}` : "";
        const change = row.new_value ? ` → ${escapeHtml(String(row.new_value).slice(0, 90))}` : "";
        const when = row.created_at ? new Date(row.created_at).toLocaleString() : "";
        return `<div class="activity-item">
          <div class="activity-title">${action}${field}${change}</div>
          <div class="activity-meta">${escapeHtml(row.user_id || "system")} • ${escapeHtml(when)}</div>
        </div>`;
      })
      .join("");
  } catch (_err) {
    if (wb.activityRequestId !== reqId) return;
    activityEl.innerHTML = "<p class='muted'>Activity unavailable for this role.</p>";
  }
}

export function fillTasksWorkbenchForm(ctx, task) {
  const {
    state,
    els,
    clearDeliverableFormNotice,
  } = ctx;
  if (!els.tasksWorkbenchForm) return;
  const form = els.tasksWorkbenchForm;
  const idInput = form.querySelector('[name="task_id"]');
  const saveButton = Array.from(form.elements).find((element) => element.type === "submit")
    || form.querySelector('button[type="submit"]');
  const deleteButton = els.tasksWorkbenchDelete;
  const previousId = form.dataset.activeTaskId || "";
  if (!task) {
    if (previousId) advanceTaskWorkbenchSelectionRevision(form);
    taskWorkbenchDraftBaselines.delete(form);
    form.dataset.activeTaskId = "";
    form.reset();
    if (idInput) idInput.value = "";
    if (els.tasksWorkbenchContext) {
      els.tasksWorkbenchContext.textContent = "Select a task to edit.";
    }
    if (saveButton) saveButton.disabled = true;
    if (deleteButton) deleteButton.disabled = true;
    clearDeliverableFormNotice(els.tasksWorkbenchFormStatus);
    void renderTasksWorkbenchActivity(ctx, "");
    return;
  }
  const currentId = task.task_id || "";
  const taskChanged = previousId !== currentId;
  if (taskChanged) {
    advanceTaskWorkbenchSelectionRevision(form);
    clearDeliverableFormNotice(els.tasksWorkbenchFormStatus);
  }
  form.dataset.activeTaskId = currentId;
  if (saveButton) saveButton.disabled = false;
  if (deleteButton) deleteButton.disabled = !currentId;
  if (idInput) idInput.value = task.task_id || "";
  const values = taskWorkbenchValues(ctx, task);
  const baseline = taskWorkbenchDraftBaselines.get(form);
  const currentValues = readTaskWorkbenchDraft(form);
  if (taskChanged || baseline?.taskId !== currentId) {
    writeTaskWorkbenchDraft(form, values);
  } else {
    const nextValues = {};
    taskWorkbenchDraftFields.forEach((name) => {
      nextValues[name] = currentValues[name] === baseline.values[name] ? values[name] : currentValues[name];
    });
    writeTaskWorkbenchDraft(form, nextValues);
  }
  taskWorkbenchDraftBaselines.set(form, { taskId: currentId, values });

  if (els.tasksWorkbenchContext) {
    const project = state.projects.find((row) => row.project_id === task.project_id)?.project_name || "Unknown project";
    const solution = state.solutions.find((row) => row.solution_id === task.solution_id)?.solution_name || "Unknown solution";
    els.tasksWorkbenchContext.innerHTML = `
      <span class="task-workbench-context-primary">${renderTasksWorkbenchDrawerProjectLink(ctx, project, task.project_id)} / ${renderTasksWorkbenchDrawerSolutionLink(ctx, solution, task.solution_id)}</span>
      ${renderTasksWorkbenchDrawerRepoContext(ctx, task)}
    `;
  }
  void renderTasksWorkbenchActivity(ctx, task.task_id);
}

export function openTasksWorkbenchProjectDrilldown(ctx, projectId) {
  const { state, openProjectForm } = ctx;
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  openProjectForm(project);
}

export function openTasksWorkbenchSolutionDrilldown(ctx, solutionId) {
  const { state, openSolutionModal } = ctx;
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

export function handleTasksWorkbenchTableClick(ctx, event) {
  const actionEl = event.target.closest("[data-twb-action]");
  if (actionEl) {
    const action = actionEl.getAttribute("data-twb-action") || "";
    if (action === "open-project") {
      openTasksWorkbenchProjectDrilldown(ctx, actionEl.getAttribute("data-project-id"));
    }
    if (action === "open-solution") {
      openTasksWorkbenchSolutionDrilldown(ctx, actionEl.getAttribute("data-solution-id"));
    }
    return;
  }
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  if (event.target.closest("button,input,select,textarea,label")) return;
  const taskId = row.getAttribute("data-id") || "";
  if (!taskId) return;
  openTasksWorkbenchDrawer(ctx, taskId);
}

export function handleTasksWorkbenchContextClick(ctx, event) {
  const actionEl = event.target.closest("[data-twb-context-action]");
  if (!actionEl) return;
  const action = actionEl.getAttribute("data-twb-context-action") || "";
  if (action === "open-project") {
    openTasksWorkbenchProjectDrilldown(ctx, actionEl.getAttribute("data-project-id"));
  }
  if (action === "open-solution") {
    openTasksWorkbenchSolutionDrilldown(ctx, actionEl.getAttribute("data-solution-id"));
  }
}

export async function saveTasksWorkbenchForm(ctx) {
  const {
    state,
    els,
    api,
    upsertById,
    findUserBySoeid,
    renderTasksWorkbench,
    renderSolutionTasks,
    setDeliverableFormNotice,
    timestampLabel,
  } = ctx;
  const formEl = els.tasksWorkbenchForm;
  if (!formEl) return;
  const data = new FormData(formEl);
  const taskId = data.get("task_id");
  if (!taskId) {
    setDeliverableFormNotice(els.tasksWorkbenchFormStatus, "Select a task first.", "error");
    return;
  }
  const submittedDraft = readTaskWorkbenchDraft(formEl);
  const selectionRevision = taskWorkbenchSelectionRevision(formEl);
  const requestContext = captureEntityMutationContext(state);
  const isSelectedEditor = () => {
    const currentTaskId = formEl.querySelector('[name="task_id"]')?.value || "";
    const formTaskId = formEl.dataset.activeTaskId || currentTaskId;
    const workbench = state.tasksWorkbench;
    const hasActiveTaskId = workbench && Object.prototype.hasOwnProperty.call(workbench, "activeTaskId");
    return currentTaskId === taskId
      && formTaskId === taskId
      && taskWorkbenchSelectionRevision(formEl) === selectionRevision
      && (!hasActiveTaskId || workbench.activeTaskId === taskId);
  };
  const assigneeUserId = String(data.get("assignee_user_soeid") || "").trim();
  const assigneeUser = findUserBySoeid(assigneeUserId);
  const payload = {
    task_name: data.get("task_name") || "",
    description: data.get("description") || null,
    acceptance_criteria: data.get("acceptance_criteria") || null,
    status: data.get("status") || "to_do",
    priority: Number(data.get("priority") || 3),
    due_date: data.get("due_date") || null,
    assignee: assigneeUser?.display_name || assigneeUserId,
    assignee_user_soeid: assigneeUserId || null,
    blocked: !!data.get("blocked"),
    blocker_note: data.get("blocker_note") || null,
  };
  try {
    setDeliverableFormNotice(els.tasksWorkbenchFormStatus, "Saving task...");
    const updated = await api(`/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    if (!isEntityMutationContextCurrent(state, requestContext)) return;
    const sameEditor = isSelectedEditor();
    const unchangedDraft = sameEditor && sameTaskWorkbenchDraft(readTaskWorkbenchDraft(formEl), submittedDraft);
    upsertById(state.tasks, updated, "task_id");
    if (unchangedDraft) {
      const savedValues = taskWorkbenchValues(ctx, { ...payload, ...updated, task_id: updated.task_id || taskId });
      writeTaskWorkbenchDraft(formEl, savedValues);
      taskWorkbenchDraftBaselines.set(formEl, { taskId, values: savedValues });
    }
    ctx.persistTasksWorkbenchUiState();
    renderTasksWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionTasks(openSolutionId);
    }
    if (unchangedDraft && isSelectedEditor()) {
      setDeliverableFormNotice(
        els.tasksWorkbenchFormStatus,
        `Saved task at ${timestampLabel()}.`,
        "success",
        3200
      );
    }
  } catch (err) {
    if (isEntityMutationContextCurrent(state, requestContext) && isSelectedEditor()) {
      setDeliverableFormNotice(els.tasksWorkbenchFormStatus, `Save failed: ${err.message || err}`, "error");
    }
  }
}

export async function deleteActiveTasksWorkbenchItem(ctx) {
  const {
    state,
    els,
    deleteTasksById,
    ignoreNextRefresh,
    renderTasksWorkbench,
    renderSolutionTasks,
    renderDashboard,
    setDeliverableFormNotice,
    timestampLabel,
  } = ctx;
  const form = els.tasksWorkbenchForm;
  const taskId = form?.querySelector('[name="task_id"]')?.value || "";
  if (!taskId) {
    setDeliverableFormNotice(els.tasksWorkbenchFormStatus, "Select a task first.", "error");
    return;
  }
  const selectionRevision = taskWorkbenchSelectionRevision(form);
  const isCurrentEditor = (result) => {
    const currentTaskId = form.querySelector('[name="task_id"]')?.value || "";
    const formTaskId = form.dataset.activeTaskId || currentTaskId;
    const workbench = state?.tasksWorkbench;
    const hasActiveTaskId = workbench && Object.prototype.hasOwnProperty.call(workbench, "activeTaskId");
    const activeTaskMatches = !hasActiveTaskId
      || workbench.activeTaskId === taskId
      || (result.deletedIds.includes(taskId) && !workbench.activeTaskId);
    return currentTaskId === taskId
      && formTaskId === taskId
      && taskWorkbenchSelectionRevision(form) === selectionRevision
      && activeTaskMatches;
  };
  const result = await deleteTasksById([taskId], {
    title: "Delete Task?",
  });
  if (result.cancelled) return;
  const shouldNotifyEditor = isCurrentEditor(result);
  if (!result.deletedIds.length) {
    ignoreNextRefresh.delete("tasks");
  }
  renderTasksWorkbench();
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
    renderSolutionTasks(openSolutionId);
  }
  renderDashboard();
  if (result.failed.length) {
    if (shouldNotifyEditor && isCurrentEditor(result)) {
      setDeliverableFormNotice(
        els.tasksWorkbenchFormStatus,
        `Delete failed for ${result.failed.length} task(s).`,
        "error"
      );
    }
    return;
  }
  if (shouldNotifyEditor && isCurrentEditor(result)) {
    setDeliverableFormNotice(
      els.tasksWorkbenchFormStatus,
      `Deleted task at ${timestampLabel()}.`,
      "success",
      3200
    );
  }
}

export function resetTasksWorkbenchEditor(ctx) {
  const { state, persistTasksWorkbenchUiState, renderTasksWorkbench } = ctx;
  state.tasksWorkbench.activeTaskId = "";
  persistTasksWorkbenchUiState();
  renderTasksWorkbench();
}

export async function handleTasksWorkbenchShortcut(ctx, event) {
  const {
    state,
    els,
    deleteTasksById,
    ignoreNextRefresh,
    renderTasksWorkbench,
    renderSolutionTasks,
    renderDashboard,
    setTasksWorkbenchBulkFeedback,
  } = ctx;
  if (state.currentView !== "tasks-workbench") return;
  if (event.altKey || event.ctrlKey || event.metaKey) return;

  const wb = state.tasksWorkbench;
  const key = (event.key || "").toLowerCase();
  const inWorkbenchTable = !!event.target?.closest?.("#tasks-workbench-table");
  const typingContext = isTypingInputTarget(event.target) && !inWorkbenchTable;

  if (key === "/" && !typingContext) {
    event.preventDefault();
    els.tasksWorkbenchSearch?.focus();
    return;
  }
  if (key === "escape") {
    if (wb.drawerOpen !== false) {
      event.preventDefault();
      closeTasksWorkbenchDrawer(ctx);
    }
    return;
  }
  if (typingContext) return;

  if (key === "arrowdown" || key === "arrowup") {
    event.preventDefault();
    setActiveTaskByOffset(ctx, key === "arrowdown" ? 1 : -1);
    return;
  }
  if (key === "e") {
    event.preventDefault();
    openTasksWorkbenchDrawer(ctx);
    window.setTimeout(() => {
      const target = els.tasksWorkbenchForm?.querySelector('[name="task_name"]');
      if (target) target.focus();
    }, 0);
    return;
  }
  if (key !== "delete") return;

  const selectedIds = Array.from(wb.selected);
  const targetIds = selectedIds.length
    ? selectedIds
    : (wb.activeTaskId ? [wb.activeTaskId] : []);
  if (!targetIds.length) return;
  event.preventDefault();
  const result = await deleteTasksById(targetIds, {
    title: targetIds.length === 1 ? "Delete Task?" : "Delete Selected Tasks?",
  });
  if (result.cancelled) return;
  if (!result.deletedIds.length) {
    ignoreNextRefresh.delete("tasks");
  }
  renderTasksWorkbench();
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
    renderSolutionTasks(openSolutionId);
  }
  renderDashboard();
  if (result.failed.length) {
    setTasksWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,
      "error"
    );
  } else {
    setTasksWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length} task${result.deletedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
  }
}
