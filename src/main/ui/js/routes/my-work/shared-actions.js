import { beginTaskMutations, captureEntityMutationContext, isEntityMutationContextCurrent } from "../../utils/form-state.js";

const CLOSED_STATUSES = new Set(["complete", "abandoned"]);
const STARTABLE_STATUSES = new Set(["to_do", "on_hold"]);

function escapeHtml(ctx, value) {
  if (typeof ctx?.escapeHtml === "function") return ctx.escapeHtml(value);
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function sharedActionState(ctx) {
  if (!ctx?.state) return {
    pendingTaskId: "",
    blockComposerTaskId: "",
    blockDraft: "",
    notice: null,
  };
  if (!ctx.state.myWork) ctx.state.myWork = {};
  if (!ctx.state.myWork.sharedActions) {
    ctx.state.myWork.sharedActions = {
      pendingTaskId: "",
      blockComposerTaskId: "",
      blockDraft: "",
      notice: null,
    };
  }
  return ctx.state.myWork.sharedActions;
}

function isClosed(task) {
  return CLOSED_STATUSES.has(String(task?.status || "").toLowerCase());
}

function mutationButton(action, label, { secondary = false, disabled = false } = {}) {
  return `<button type="button"${secondary ? ' class="secondary"' : ""} data-my-work-action="${action}"${disabled ? " disabled" : ""}>${label}</button>`;
}

function repositoryAction(ctx, task) {
  const url = task?.effective_github_repo_url || "";
  if (!url || typeof ctx?.renderExternalRepoLink !== "function") return "";
  return ctx.renderExternalRepoLink(url, {
    label: "Open Repository",
    className: "secondary my-work-action-link",
  }) || "";
}

function setNotice(actionState, notice, onNotice) {
  actionState.notice = notice;
  if (typeof onNotice === "function") onNotice(notice);
}

function defaultApplyUpdatedTask(record, updatedTask) {
  record.task = updatedTask;
  record.needs_attention = !isClosed(updatedTask) && Boolean(record.reminder_due || updatedTask?.blocked || updatedTask?.is_overdue);
}

function refreshView(refresh) {
  if (typeof refresh === "function") refresh();
}

/**
 * Render the shared Task controls for a My Work detail record.
 *
 * This function only reads shared Task fields. It never changes the private
 * My Work bucket, rank, reminder, or note stored on the surrounding record.
 */
export function renderSharedActions(ctx, record) {
  const task = record?.task;
  if (!task?.task_id) return "";

  const actionState = sharedActionState(ctx);
  const taskId = String(task.task_id);
  const pending = !!actionState.pendingTaskId || !!ctx?.state?.myWork?.sharedTaskSaveRequest;
  const closed = isClosed(task);
  const blocked = Boolean(task.blocked);
  const status = String(task.status || "").toLowerCase();
  const buttons = [];

  if (!closed && !blocked && STARTABLE_STATUSES.has(status)) {
    buttons.push(mutationButton("start", "Start work", { disabled: pending }));
  }
  if (!closed && !blocked && status === "in_progress") {
    buttons.push(mutationButton("complete", "Mark complete", { disabled: pending }));
  }
  if (!closed && blocked) {
    buttons.push(mutationButton("unblock", "Unblock", { disabled: pending }));
  } else if (!closed && actionState.blockComposerTaskId !== taskId) {
    buttons.push(mutationButton("show-block", "Block", { secondary: true, disabled: pending }));
  }

  const repoAction = repositoryAction(ctx, task);
  if (repoAction) buttons.push(repoAction);
  buttons.push(`<button type="button" class="secondary" data-my-work-open-tasks="${escapeHtml(ctx, taskId)}"${pending ? " disabled" : ""}>Open in Tasks</button>`);

  const composer = !closed && !blocked && actionState.blockComposerTaskId === taskId
    ? `<form class="my-work-block-composer" data-my-work-block-form="${escapeHtml(ctx, taskId)}">
        <label>
          <span>What is blocking this task?</span>
          <textarea name="blocker_note" rows="3" required placeholder="Describe what is needed to resume work"${pending ? " disabled" : ""}>${escapeHtml(ctx, actionState.blockDraft || "")}</textarea>
        </label>
        <p class="form-notice" data-my-work-block-feedback role="status" aria-live="polite"></p>
        <div class="my-work-block-composer-actions">
          <button type="submit"${pending ? " disabled" : ""}>Block task</button>
          <button type="button" class="secondary" data-my-work-block-cancel${pending ? " disabled" : ""}>Cancel</button>
        </div>
      </form>`
    : "";

  return `<div class="my-work-shared-actions"${pending ? ' aria-busy="true"' : ""}>
      <div class="my-work-detail-actions">${buttons.join("")}</div>
      ${composer}
    </div>`;
}

/** Render the persistent route-level result of the latest shared action. */
export function renderSharedActionNotice(ctx) {
  const notice = sharedActionState(ctx).notice;
  if (!notice?.message) return "";
  const tone = ["success", "error", "info"].includes(notice.tone) ? notice.tone : "info";
  return `<p class="my-work-action-notice is-${tone}" role="status" aria-live="polite">${escapeHtml(ctx, notice.message)}</p>`;
}

export function clearSharedActionNotice(ctx) {
  sharedActionState(ctx).notice = null;
}

/**
 * Bind shared Task actions rendered by {@link renderSharedActions}.
 *
 * Integration hooks:
 * - refresh(): rerender My Work after pending/composer/notice state changes.
 * - onTaskUpdated(updatedTask, metadata): replace/reload the route's record.
 * - onNotice(notice): mirror the persistent notice into a route-level store.
 * - openTaskInWorkbench(task): navigate to Tasks with this task selected.
 */
export function bindSharedActions(ctx, {
  record,
  refresh,
  onTaskUpdated,
  onNotice,
  openTaskInWorkbench,
} = {}) {
  const task = record?.task;
  const taskId = String(task?.task_id || "");
  const root = ctx?.els?.myWorkRoot;
  if (!root || !taskId) return;

  const actionState = sharedActionState(ctx);
  const work = ctx.state.myWork;
  const context = captureEntityMutationContext(ctx.state);
  const authed = ctx.state.authed;
  const isCurrent = () => ctx.state.myWork === work && work.sharedActions === actionState
    && isEntityMutationContextCurrent(ctx.state, context) && ctx.state.authed === authed;
  const isSelected = () => isCurrent() && (!work.selectedTaskId || String(work.selectedTaskId) === taskId);
  const applyUpdatedTask = typeof onTaskUpdated === "function"
    ? onTaskUpdated
    : (updatedTask) => {
      const currentRecord = Array.isArray(work.records)
        ? work.records.find((item) => String(item?.task?.task_id || "") === taskId)
        : record;
      if (currentRecord) defaultApplyUpdatedTask(currentRecord, updatedTask);
    };

  const runMutation = async (action, payload, successMessage) => {
    if (!isCurrent() || actionState.pendingTaskId || work.sharedTaskSaveRequest
        || (work.selectedTaskId && String(work.selectedTaskId) !== taskId)) return;
    const release = beginTaskMutations(ctx.state, [taskId]);
    if (!release) {
      setNotice(actionState, { tone: "error", message: "This task is already being updated. Try again when it finishes.", taskId, action }, onNotice);
      refreshView(refresh);
      return;
    }
    actionState.pendingTaskId = taskId;
    if (work.loading) {
      // Refresh after the write instead of applying a pre-write snapshot.
      work.loadRequestId = (Number(work.loadRequestId) || 0) + 1;
      work.loading = false;
      work.needsRefresh = true;
    }
    setNotice(actionState, {
      tone: "info",
      message: "Updating shared task...",
      taskId,
      action,
    }, onNotice);
    refreshView(refresh);
    if (!isCurrent()) { release(); return; }
    try {
      const updatedTask = await ctx.api(`/tasks/${encodeURIComponent(taskId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      if (!isCurrent()) return;
      if (!updatedTask || String(updatedTask.task_id || "") !== taskId) throw new Error("Task update returned an invalid response.");
      await applyUpdatedTask(updatedTask, { action, previousTask: task, record });
      if (!isCurrent()) return;
      actionState.pendingTaskId = "";
      if (action === "block") {
        actionState.blockComposerTaskId = "";
        actionState.blockDraft = "";
      }
      setNotice(actionState, {
        tone: "success",
        message: successMessage,
        taskId,
        action,
      }, onNotice);
      refreshView(refresh);
    } catch (error) {
      if (!isCurrent()) return;
      actionState.pendingTaskId = "";
      setNotice(actionState, {
        tone: "error",
        message: error?.message || "Task update failed.",
        taskId,
        action,
      }, onNotice);
      refreshView(refresh);
    } finally {
      release();
    }
  };

  root.querySelectorAll("[data-my-work-action]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!isSelected() || actionState.pendingTaskId || work.sharedTaskSaveRequest) return;
      const action = button.dataset.myWorkAction;
      if (action === "show-block") {
        actionState.blockComposerTaskId = taskId;
        actionState.blockDraft = "";
        actionState.notice = null;
        refreshView(refresh);
        return;
      }
      if (action === "start") void runMutation("start", { status: "in_progress" }, "Task started.");
      if (action === "unblock") void runMutation("unblock", { blocked: false }, "Task unblocked.");
      if (action === "complete") void runMutation("complete", { status: "complete" }, "Task marked complete.");
    });
  });

  const blockForm = Array.from(root.querySelectorAll("[data-my-work-block-form]"))
    .find((form) => form.dataset.myWorkBlockForm === taskId);
  const blockInput = blockForm?.querySelector('[name="blocker_note"]');
  blockInput?.addEventListener("input", () => {
    if (!isSelected()) return;
    actionState.blockDraft = blockInput.value;
    blockInput.setCustomValidity("");
    blockInput.removeAttribute("aria-invalid");
    const feedback = blockForm.querySelector("[data-my-work-block-feedback]");
    if (feedback) feedback.textContent = "";
  });
  blockForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!isSelected()) return;
    const blockerNote = String(blockInput?.value || "").trim();
    if (!blockerNote) {
      const message = "Add blocker context before blocking this task.";
      blockInput?.setCustomValidity(message);
      blockInput?.setAttribute("aria-invalid", "true");
      blockInput?.reportValidity?.();
      const feedback = blockForm.querySelector("[data-my-work-block-feedback]");
      if (feedback) feedback.textContent = message;
      setNotice(actionState, { tone: "error", message, taskId, action: "block" }, onNotice);
      return;
    }
    actionState.blockDraft = blockerNote;
    void runMutation("block", { blocked: true, blocker_note: blockerNote }, "Task blocked.");
  });
  root.querySelector("[data-my-work-block-cancel]")?.addEventListener("click", () => {
    if (!isSelected()) return;
    actionState.blockComposerTaskId = "";
    actionState.blockDraft = "";
    refreshView(refresh);
  });

  root.querySelectorAll("[data-my-work-open-tasks]").forEach((button) => {
    if (button.dataset.myWorkOpenTasks !== taskId) return;
    button.addEventListener("click", () => {
      if (!isSelected()) return;
      const open = openTaskInWorkbench || ctx.openTaskInWorkbench;
      if (typeof open === "function") {
        open(task);
        return;
      }
      ctx.setView?.("tasks-workbench");
    });
  });
}
