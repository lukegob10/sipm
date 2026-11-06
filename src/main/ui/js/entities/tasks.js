import { createFormDraftGuard } from "../utils/form-draft.js";
import { beginTaskMutations, createContextualFormSaveGate, captureEntityMutationContext, isEntityMutationContextCurrent, nullableTextValue, textValue } from "../utils/form-state.js";
import { invalidateMyWorkRecords } from "../utils/my-work-state.js";

export function buildTaskPayload(
  data,
  {
    findUserBySoeid,
    hoursFromFteInput,
    hoursFromNullableFteInput,
  }
) {
  const assigneeUserId = textValue(data.get("assignee"));
  const assigneeUser = findUserBySoeid(assigneeUserId);
  const blocked = !!data.get("blocked");
  return {
    task_name: textValue(data.get("task_name")),
    description: nullableTextValue(data.get("description")),
    github_repo_url: nullableTextValue(data.get("github_repo_url")),
    status: data.get("status"),
    priority: Number(data.get("priority") || 3),
    due_date: data.get("due_date") || null,
    assignee: assigneeUser?.display_name || "",
    assignee_user_soeid: assigneeUserId || null,
    estimate_hours: hoursFromNullableFteInput(data.get("estimate_hours")),
    blocked,
    blocker_note: blocked ? nullableTextValue(data.get("blocker_note")) : null,
    acceptance_criteria: nullableTextValue(data.get("acceptance_criteria")),
    capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
  };
}

export function createTaskEntityController({
  state,
  els,
  api,
  findUserBySoeid,
  resolveAssigneeSelectValue,
  hoursFromFteInput,
  hoursFromNullableFteInput,
  fteFromHoursForInput,
  updateTaskRepoPreview,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  upsertById,
  deleteTasksById,
  renderSolutionTasks,
  renderDashboard,
  renderGantt,
  timestampLabel,
  showConfirmModal,
  trackWorkflow = null,
}) {
  let taskFormRevision = 0;
  let taskInputRevision = 0;
  let taskFormBaseline = null;
  const saveGate = createContextualFormSaveGate({ state, form: els.taskForm, submit: els.taskSubmitBtn });
  const taskDraft = createFormDraftGuard({ form: els.taskForm, entityLabel: "Task", showConfirmModal });

  function confirmTaskDraftDiscard() {
    if (!els.taskForm || els.taskForm.classList.contains("hidden") || !taskDraft.isDirty()) return true;
    const revision = taskFormRevision;
    const context = captureEntityMutationContext(state);
    const snapshot = JSON.stringify([...new FormData(els.taskForm).entries()]);
    return taskDraft.confirmDiscard().then((confirmed) => confirmed && revision === taskFormRevision
      && isEntityMutationContextCurrent(state, context)
      && snapshot === JSON.stringify([...new FormData(els.taskForm).entries()]));
  }

  function taskTransition(action) {
    const allowed = confirmTaskDraftDiscard();
    return allowed instanceof Promise ? allowed.then((ok) => ok ? action() : false) : allowed ? action() : false;
  }

  function setTaskActionButtonLabel(isEditing) {
    if (els.taskSubmitBtn) {
      els.taskSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Task";
    }
  }

  function setTaskFormVisibility(show) {
    if (els.taskForm) {
      const isHidden = els.taskForm.classList.contains("hidden");
      if (isHidden === show) taskFormRevision += 1;
      els.taskForm.classList.toggle("hidden", !show);
    }
    if (els.taskFormFooter) {
      els.taskFormFooter.classList.toggle("hidden", !show);
    }
  }

  function hideTaskForm() {
    return taskTransition(finishHidingTaskForm);
  }

  function finishHidingTaskForm() {
    if (!els.taskForm) return false;
    taskFormRevision += 1;
    const taskId = els.taskForm.querySelector('[name="task_id"]')?.value || "";
    setTaskFormVisibility(false);
    clearDeliverableFormNotice(els.taskFormStatus);

    const restoreListContext = () => {
      const taskRow = Array.from(els.solutionTaskTable?.querySelectorAll("[data-id]") || [])
        .find((row) => row.getAttribute("data-id") === taskId);
      if (taskRow && typeof taskRow.scrollIntoView === "function") {
        taskRow.scrollIntoView({ block: "nearest" });
      }
      const focusTarget = taskRow?.matches(".swimlane-card") ? taskRow
        : taskRow?.querySelector(".edit-task-btn") || els.showTaskFormBtn;
      if (focusTarget && typeof focusTarget.focus === "function") {
        try {
          focusTarget.focus({ preventScroll: true });
        } catch {
          focusTarget.focus();
        }
      }
    };
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(restoreListContext);
    } else {
      restoreListContext();
    }
    return true;
  }

  function prepareTaskCreateForm(solution, options = {}) {
    if (!els.taskForm) return;
    taskFormRevision += 1;
    taskFormBaseline = null;
    const { resetForm = true } = options;
    const sol = solution || state.solutions.find((s) => s.solution_id === els.solutionForm?.querySelector('[name="solution_id"]')?.value);
    if (!sol) return;
    setTaskFormVisibility(true);
    if (resetForm) els.taskForm.reset();
    els.taskForm.querySelector('[name="assignee"] option[data-unresolved-assignee]')?.remove();
    clearDeliverableFormNotice(els.taskFormStatus);
    els.taskForm.querySelector('[name="task_id"]').value = "";
    els.taskForm.querySelector('[name="project_id"]').value = sol.project_id;
    els.taskForm.querySelector('[name="solution_id"]').value = sol.solution_id;
    els.taskForm.querySelector('[name="github_repo_url"]').value = "";
    els.taskForm.querySelector('[name="priority"]').value = 3;
    els.taskForm.querySelector('[name="status"]').value = "to_do";
    els.taskForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(0, 0);
    updateTaskRepoPreview(sol.solution_id, "");
    if (els.deleteTaskBtn) {
      els.deleteTaskBtn.disabled = true;
    }
    setTaskActionButtonLabel(false);
    taskDraft.capture();
    return true;
  }

  function showTaskForm(solution) {
    return taskTransition(() => prepareTaskCreateForm(solution));
  }

  function fillTaskForm(task, { preserveNotice = false } = {}) {
    if (!els.taskForm || !task) return;
    taskFormRevision += 1;
    setTaskFormVisibility(true);
    els.taskForm.reset();
    if (!preserveNotice) clearDeliverableFormNotice(els.taskFormStatus);
    els.taskForm.querySelector('[name="task_id"]').value = task.task_id;
    els.taskForm.querySelector('[name="project_id"]').value = task.project_id;
    els.taskForm.querySelector('[name="solution_id"]').value = task.solution_id;
    els.taskForm.querySelector('[name="task_name"]').value = task.task_name || "";
    els.taskForm.querySelector('[name="description"]').value = task.description || "";
    els.taskForm.querySelector('[name="github_repo_url"]').value = task.github_repo_url || "";
    els.taskForm.querySelector('[name="priority"]').value = task.priority ?? "";
    els.taskForm.querySelector('[name="due_date"]').value = task.due_date || "";
    els.taskForm.querySelector('[name="status"]').value = task.status || "to_do";
    const assigneeSelect = els.taskForm.querySelector('[name="assignee"]');
    assigneeSelect.querySelector('option[data-unresolved-assignee]')?.remove();
    let assigneeValue = resolveAssigneeSelectValue(task.assignee_user_soeid, task.assignee) || "";
    if ((task.assignee_user_soeid || task.assignee) && !Array.from(assigneeSelect.options).some((option) => option.value === assigneeValue && assigneeValue)) {
      assigneeValue = "__sipm_unresolved_assignee__";
      while (Array.from(assigneeSelect.options).some((option) => option.value === assigneeValue)) assigneeValue += "_";
      const option = document.createElement("option");
      option.value = assigneeValue;
      option.textContent = `${task.assignee || task.assignee_user_soeid} (unavailable)`;
      option.dataset.unresolvedAssignee = "true";
      option.dataset.assigneeSoeid = task.assignee_user_soeid || "";
      assigneeSelect.appendChild(option);
    }
    assigneeSelect.value = assigneeValue;
    els.taskForm.querySelector('[name="assignee_user_soeid"]').value = task.assignee_user_soeid || "";
    els.taskForm.querySelector('[name="estimate_hours"]').value =
      task.estimate_hours != null ? fteFromHoursForInput(task.estimate_hours, 0) : "";
    els.taskForm.querySelector('[name="blocked"]').checked = !!task.blocked;
    els.taskForm.querySelector('[name="blocker_note"]').value = task.blocker_note || "";
    els.taskForm.querySelector('[name="acceptance_criteria"]').value =
      task.acceptance_criteria || task.done_criteria || "";
    els.taskForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(task.capacity_hours, 0);
    const baselineData = new FormData(els.taskForm);
    taskFormBaseline = {
      taskId: task.task_id,
      assignee: baselineData.get("assignee") || "",
      payload: buildTaskPayload(baselineData, { findUserBySoeid, hoursFromFteInput, hoursFromNullableFteInput }),
    };
    updateTaskRepoPreview(task.solution_id, task.github_repo_url || "");
    if (els.deleteTaskBtn) {
      els.deleteTaskBtn.disabled = !task.task_id;
    }
    setTaskActionButtonLabel(!!task.task_id);
    taskDraft.capture();
    return true;
  }

  function requestFillTaskForm(task) {
    return taskTransition(() => fillTaskForm(task));
  }

  function bindTaskForm() {
    if (!els.taskForm) return;
    taskDraft.bind();
    els.taskForm.addEventListener("input", () => { taskInputRevision += 1; });
    els.taskForm.addEventListener("change", () => { taskInputRevision += 1; });
    if (!els.taskForm._repoPreviewBound) {
      els.taskForm.addEventListener("input", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const repoInput = target.closest('[name="github_repo_url"]');
        if (!repoInput) return;
        const solutionId = els.taskForm?.querySelector('[name="solution_id"]')?.value || "";
        updateTaskRepoPreview(solutionId, repoInput.value || "");
      });
      els.taskForm._repoPreviewBound = true;
    }
    if (els.showTaskFormBtn) {
      els.showTaskFormBtn.onclick = () => {
        if (els.taskForm.classList.contains("hidden")) {
          const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
          if (!solutionId) {
            renderSolutionTasks("");
            return;
          }
          const solution = state.solutions.find((s) => s.solution_id === solutionId);
          showTaskForm(solution);
        } else {
          hideTaskForm();
        }
      };
    }
    els.taskForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (saveGate.isPending()) return;
      const data = new FormData(els.taskForm);
      const id = (data.get("task_id") || "").toString().trim();
      const solutionId = (data.get("solution_id") || "").toString().trim();
      const isEditing = !!id;
      if (!solutionId) {
        setDeliverableFormNotice(els.taskFormStatus, "Save the solution before adding tasks.", "error");
        return;
      }
      const fullPayload = buildTaskPayload(data, {
        findUserBySoeid,
        hoursFromFteInput,
        hoursFromNullableFteInput,
      });
      const payload = { ...fullPayload };
      if (isEditing && taskFormBaseline?.taskId === id) {
        for (const key of Object.keys(payload)) {
          if (key === "assignee" || key === "assignee_user_soeid" || key === "blocked" || key === "blocker_note") continue;
          if (payload[key] === taskFormBaseline.payload[key]) delete payload[key];
        }
        if ((data.get("assignee") || "") === taskFormBaseline.assignee) {
          delete payload.assignee;
          delete payload.assignee_user_soeid;
        }
        if (fullPayload.blocked === taskFormBaseline.payload.blocked && fullPayload.blocker_note === taskFormBaseline.payload.blocker_note) {
          delete payload.blocked;
          delete payload.blocker_note;
        }
      }
      if (isEditing && els.taskForm.querySelector('[name="assignee"]')?.selectedOptions[0]?.dataset.unresolvedAssignee) {
        delete payload.assignee;
        delete payload.assignee_user_soeid;
      }
      const formRevision = taskFormRevision;
      const formSnapshot = JSON.stringify([...data.entries()]);

      const requestContext = captureEntityMutationContext(state);
      const isSameEditor = () => formRevision === taskFormRevision;
      const isCurrentSubmission = () => isSameEditor()
        && JSON.stringify([...new FormData(els.taskForm).entries()]) === formSnapshot;
      const saveRequest = saveGate.begin();
      if (!saveRequest) return;
      const release = isEditing ? beginTaskMutations(state, [id]) : () => {};
      if (!release) {
        saveGate.end(saveRequest);
        setDeliverableFormNotice(els.taskFormStatus, "This task is already being updated. Try again when it finishes.", "error");
        return;
      }
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.taskFormStatus, "Saving task...");
        } else {
          setDeliverableFormNotice(els.taskFormStatus, "Creating task...");
        }
        const saved = isEditing
          ? await api(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api(`/solutions/${solutionId}/tasks`, { method: "POST", body: JSON.stringify(payload) });
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        const shouldUpdateForm = isCurrentSubmission();
        const sameEditor = isSameEditor();
        upsertById(state.tasks, saved, "task_id");
        invalidateMyWorkRecords(state);
        if (shouldUpdateForm) {
          fillTaskForm(saved);
        } else if (sameEditor && !isEditing && saved?.task_id) {
          els.taskForm.querySelector('[name="task_id"]').value = saved.task_id;
          if (els.deleteTaskBtn) els.deleteTaskBtn.disabled = false;
          setTaskActionButtonLabel(true);
        }
        if (sameEditor && !shouldUpdateForm && saved?.task_id) {
          taskFormBaseline = { taskId: saved.task_id, assignee: data.get("assignee") || "", payload: fullPayload };
          taskDraft.rebase(formSnapshot, { task_id: saved.task_id });
        }
        const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (openSolutionId === saved.solution_id) {
          renderSolutionTasks(saved.solution_id);
        }
        renderDashboard();
        renderGantt();
        const successMessage = isEditing
          ? `Saved task at ${timestampLabel()}.`
          : `Created task at ${timestampLabel()}.`;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("tasks", isEditing ? "update" : "create", "success", { source: "task_form" });
        }
        if (sameEditor) {
          setDeliverableFormNotice(
            els.taskFormStatus,
            shouldUpdateForm ? successMessage : `${isEditing ? "Saved" : "Created"} task; you have unsaved edits.`,
            "success",
            shouldUpdateForm ? 3200 : 0
          );
        }
      } catch (err) {
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("tasks", isEditing ? "update" : "create", "failure", { source: "task_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.taskFormStatus,
            `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
            "error"
          );
        }
      } finally {
        saveGate.end(saveRequest);
        release();
      }
    });
    els.taskForm.addEventListener("reset", () => {
      taskFormRevision += 1;
      clearDeliverableFormNotice(els.taskFormStatus);
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
      if (solution) {
        prepareTaskCreateForm(solution, { resetForm: false });
        const revision = taskFormRevision;
        const inputRevision = taskInputRevision;
        setTimeout(() => { if (revision === taskFormRevision && inputRevision === taskInputRevision) taskDraft.capture(); }, 0);
        return;
      }
      els.taskForm.querySelector('[name="task_id"]').value = "";
      if (els.deleteTaskBtn) {
        els.deleteTaskBtn.disabled = true;
      }
      setTaskActionButtonLabel(false);
      const revision = taskFormRevision;
      const inputRevision = taskInputRevision;
      setTimeout(() => { if (revision === taskFormRevision && inputRevision === taskInputRevision) taskDraft.capture(); }, 0);
    });
    if (els.deleteTaskBtn) {
      els.deleteTaskBtn.addEventListener("click", async () => {
        const id = els.taskForm?.querySelector('[name="task_id"]')?.value || "";
        if (!id) return;
        const release = beginTaskMutations(state, [id]);
        if (!release) {
          setDeliverableFormNotice(els.taskFormStatus, "This task is already being updated. Try again when it finishes.", "error");
          return;
        }
        const solutionId = els.taskForm?.querySelector('[name="solution_id"]')?.value || "";
        const selectedSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        const editorRevision = taskFormRevision;
        const requestContext = captureEntityMutationContext(state);
        const isEditorCurrent = () => taskFormRevision === editorRevision
          && (els.taskForm?.querySelector('[name="task_id"]')?.value || "") === id
          && (els.taskForm?.querySelector('[name="solution_id"]')?.value || "") === solutionId;
        const isSolutionSelectionCurrent = () => (
          (els.solutionForm?.querySelector('[name="solution_id"]')?.value || "") === selectedSolutionId
        );
        let result;
        try {
          result = await deleteTasksById([id], {
            title: "Delete Task?",
          });
        } catch (err) {
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          if (typeof trackWorkflow === "function") {
            trackWorkflow("tasks", "delete", "failure", { source: "task_form" });
          }
          if (isEditorCurrent() && isSolutionSelectionCurrent()) {
            setDeliverableFormNotice(
              els.taskFormStatus,
              `Delete failed: ${err.message || "Unable to delete task."}`,
              "error"
            );
          }
          return;
        } finally {
          release();
        }
        if (result.cancelled) return;
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        const taskDeleted = result.deletedIds.includes(id);
        const editorIsCurrent = isEditorCurrent() && isSolutionSelectionCurrent();
        const shouldResetEditor = taskDeleted && editorIsCurrent;
        const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
        if (shouldResetEditor) {
          if (solution) {
            prepareTaskCreateForm(solution);
          } else {
            els.taskForm.reset();
            els.taskForm.querySelector('[name="task_id"]').value = "";
            if (els.deleteTaskBtn) els.deleteTaskBtn.disabled = true;
            setTaskActionButtonLabel(false);
          }
        }
        if (taskDeleted && selectedSolutionId && selectedSolutionId === solutionId && isSolutionSelectionCurrent()) {
          renderSolutionTasks(solutionId);
        }
        if (taskDeleted) {
          renderDashboard();
          renderGantt();
        }
        if (result.failed.length) {
          if (typeof trackWorkflow === "function") {
            trackWorkflow("tasks", "delete", "failure", { source: "task_form" });
          }
          if (editorIsCurrent) {
            setDeliverableFormNotice(
              els.taskFormStatus,
              `Delete failed: ${result.failed[0]?.error?.message || "Unable to delete task."}`,
              "error"
            );
          }
          return;
        }
        if (shouldResetEditor) {
          setDeliverableFormNotice(
            els.taskFormStatus,
            `Deleted task at ${timestampLabel()}.`,
            "success",
            3200
          );
        }
        if (typeof trackWorkflow === "function") {
          trackWorkflow("tasks", "delete", "success", { source: "task_form" });
        }
      });
    }
  }

  return {
    resetSaveForContext: saveGate.reset,
    bindTaskForm,
    fillTaskForm,
    requestFillTaskForm,
    confirmTaskDraftDiscard,
    hideTaskForm,
    setTaskActionButtonLabel,
    setTaskFormVisibility,
    showTaskForm,
  };
}
