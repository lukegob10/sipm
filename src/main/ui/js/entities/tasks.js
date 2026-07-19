import { nullableTextValue, textValue } from "../utils/form-values.js";

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
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  deleteTasksById,
  renderSolutionTasks,
  renderDashboard,
  renderGantt,
  timestampLabel,
  trackWorkflow = null,
}) {
  function setTaskActionButtonLabel(isEditing) {
    if (els.taskSubmitBtn) {
      els.taskSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Task";
    }
  }

  function setTaskFormVisibility(show) {
    if (els.taskForm) {
      els.taskForm.classList.toggle("hidden", !show);
    }
    if (els.taskFormFooter) {
      els.taskFormFooter.classList.toggle("hidden", !show);
    }
  }

  function prepareTaskCreateForm(solution, options = {}) {
    if (!els.taskForm) return;
    const { resetForm = true } = options;
    const sol = solution || state.solutions.find((s) => s.solution_id === els.solutionForm?.querySelector('[name="solution_id"]')?.value);
    if (!sol) return;
    setTaskFormVisibility(true);
    if (resetForm) els.taskForm.reset();
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
  }

  function showTaskForm(solution) {
    prepareTaskCreateForm(solution);
  }

  function fillTaskForm(task) {
    if (!els.taskForm || !task) return;
    setTaskFormVisibility(true);
    els.taskForm.reset();
    clearDeliverableFormNotice(els.taskFormStatus);
    els.taskForm.querySelector('[name="task_id"]').value = task.task_id;
    els.taskForm.querySelector('[name="project_id"]').value = task.project_id;
    els.taskForm.querySelector('[name="solution_id"]').value = task.solution_id;
    els.taskForm.querySelector('[name="task_name"]').value = task.task_name || "";
    els.taskForm.querySelector('[name="description"]').value = task.description || "";
    els.taskForm.querySelector('[name="github_repo_url"]').value = task.github_repo_url || "";
    els.taskForm.querySelector('[name="priority"]').value = task.priority ?? "";
    els.taskForm.querySelector('[name="due_date"]').value = task.due_date || "";
    els.taskForm.querySelector('[name="status"]').value = task.status || "to_do";
    els.taskForm.querySelector('[name="assignee"]').value = resolveAssigneeSelectValue(task.assignee_user_soeid, task.assignee);
    els.taskForm.querySelector('[name="assignee_user_soeid"]').value = task.assignee_user_soeid || "";
    els.taskForm.querySelector('[name="estimate_hours"]').value =
      task.estimate_hours != null ? fteFromHoursForInput(task.estimate_hours, 0) : "";
    els.taskForm.querySelector('[name="blocked"]').checked = !!task.blocked;
    els.taskForm.querySelector('[name="blocker_note"]').value = task.blocker_note || "";
    els.taskForm.querySelector('[name="acceptance_criteria"]').value =
      task.acceptance_criteria || task.done_criteria || "";
    els.taskForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(task.capacity_hours, 0);
    updateTaskRepoPreview(task.solution_id, task.github_repo_url || "");
    if (els.deleteTaskBtn) {
      els.deleteTaskBtn.disabled = !task.task_id;
    }
    setTaskActionButtonLabel(!!task.task_id);
  }

  function bindTaskForm() {
    if (!els.taskForm) return;
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
          setTaskFormVisibility(false);
        }
      };
    }
    els.taskForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.taskForm);
      const id = (data.get("task_id") || "").toString().trim();
      const solutionId = (data.get("solution_id") || "").toString().trim();
      const isEditing = !!id;
      if (!solutionId) {
        setDeliverableFormNotice(els.taskFormStatus, "Save the solution before adding tasks.", "error");
        return;
      }
      const payload = buildTaskPayload(data, {
        findUserBySoeid,
        hoursFromFteInput,
        hoursFromNullableFteInput,
      });
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.taskFormStatus, "Saving task...");
        } else {
          setDeliverableFormNotice(els.taskFormStatus, "Creating task...");
        }
        markIgnoreRefresh("tasks");
        const saved = isEditing
          ? await api(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api(`/solutions/${solutionId}/tasks`, { method: "POST", body: JSON.stringify(payload) });
        upsertById(state.tasks, saved, "task_id");
        fillTaskForm(saved);
        renderSolutionTasks(saved.solution_id);
        renderDashboard();
        renderGantt();
        const successMessage = isEditing
          ? `Saved task at ${timestampLabel()}.`
          : `Created task at ${timestampLabel()}.`;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("tasks", isEditing ? "update" : "create", "success", { source: "task_form" });
        }
        setDeliverableFormNotice(
          els.taskFormStatus,
          successMessage,
          "success",
          3200
        );
      } catch (err) {
        ignoreNextRefresh.delete("tasks");
        if (typeof trackWorkflow === "function") {
          trackWorkflow("tasks", isEditing ? "update" : "create", "failure", { source: "task_form" });
        }
        setDeliverableFormNotice(
          els.taskFormStatus,
          `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
          "error"
        );
      }
    });
    els.taskForm.addEventListener("reset", () => {
      clearDeliverableFormNotice(els.taskFormStatus);
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
      if (solution) {
        prepareTaskCreateForm(solution, { resetForm: false });
        return;
      }
      els.taskForm.querySelector('[name="task_id"]').value = "";
      if (els.deleteTaskBtn) {
        els.deleteTaskBtn.disabled = true;
      }
      setTaskActionButtonLabel(false);
    });
    if (els.deleteTaskBtn) {
      els.deleteTaskBtn.addEventListener("click", async () => {
        const id = els.taskForm?.querySelector('[name="task_id"]')?.value || "";
        if (!id) return;
        const solutionId = els.taskForm?.querySelector('[name="solution_id"]')?.value || "";
        markIgnoreRefresh("tasks");
        const result = await deleteTasksById([id], {
          title: "Delete Task?",
        });
        if (result.cancelled) return;
        if (!result.deletedIds.length) {
          ignoreNextRefresh.delete("tasks");
        }
        const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
        if (solution) {
          showTaskForm(solution);
        } else {
          els.taskForm.reset();
          els.taskForm.querySelector('[name="task_id"]').value = "";
          if (els.deleteTaskBtn) els.deleteTaskBtn.disabled = true;
          setTaskActionButtonLabel(false);
        }
        renderSolutionTasks(solutionId);
        renderDashboard();
        renderGantt();
        if (result.failed.length) {
          if (typeof trackWorkflow === "function") {
            trackWorkflow("tasks", "delete", "failure", { source: "task_form" });
          }
          setDeliverableFormNotice(
            els.taskFormStatus,
            `Delete failed: ${result.failed[0]?.error?.message || "Unable to delete task."}`,
            "error"
          );
          return;
        }
        setDeliverableFormNotice(
          els.taskFormStatus,
          `Deleted task at ${timestampLabel()}.`,
          "success",
          3200
        );
        if (typeof trackWorkflow === "function") {
          trackWorkflow("tasks", "delete", "success", { source: "task_form" });
        }
      });
    }
  }

  return {
    bindTaskForm,
    fillTaskForm,
    setTaskActionButtonLabel,
    setTaskFormVisibility,
    showTaskForm,
  };
}
