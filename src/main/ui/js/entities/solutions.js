import { nullableTextValue, textValue } from "../utils/form-values.js";

export function buildSolutionPayload(data, { hoursFromFteInput }) {
  return {
    solution_name: textValue(data.get("solution_name")),
    project_id: textValue(data.get("project_id")),
    github_repo_url: nullableTextValue(data.get("github_repo_url")),
    version: textValue(data.get("version")),
    status: data.get("status"),
    priority: Number(data.get("priority") || 3),
    due_date: data.get("due_date") || null,
    planned_start_date: data.get("planned_start_date") || null,
    current_phase: data.get("current_phase") || null,
    description: data.get("description"),
    problem_statement: nullableTextValue(data.get("problem_statement")),
    success_criteria: nullableTextValue(data.get("success_criteria")),
    escalation: nullableTextValue(data.get("escalation")),
    impact_confidence: data.get("impact_confidence") || null,
    owner: textValue(data.get("owner")),
    owner_user_soeid: nullableTextValue(data.get("owner_user_soeid")),
    assignee: textValue(data.get("assignee")),
    assignee_user_soeid: nullableTextValue(data.get("assignee_user_soeid")),
    approver: nullableTextValue(data.get("approver")),
    approver_user_soeid: nullableTextValue(data.get("approver_user_soeid")),
    key_stakeholder: textValue(data.get("key_stakeholder")),
    rag_confidence: data.get("rag_confidence") ? Number(data.get("rag_confidence")) : null,
    blockers: nullableTextValue(data.get("blockers")),
    risks: nullableTextValue(data.get("risks")),
    capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
    rag_status: data.get("rag_status") || "green",
    rag_reason: nullableTextValue(data.get("rag_reason")),
  };
}

export function createSolutionEntityController({
  state,
  els,
  api,
  hoursFromFteInput,
  fteFromHoursForInput,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  removeById,
  populateSelects,
  renderActiveView,
  renderMasterTable,
  renderDashboard,
  renderKanban,
  renderCalendar,
  renderGantt,
  renderSolutionPhases,
  renderSolutionTasks,
  renderSolutionDocuments,
  renderSolutionActivity,
  setTaskFormVisibility,
  setTaskActionButtonLabel,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  updateCurrentPhaseOptions,
  updateTaskRepoPreview,
  setSolutionTab,
  timestampLabel,
  showConfirmModal,
  trackWorkflow = null,
}) {
  function fillSolutionForm(solution = null) {
    if (!els.solutionForm) return;
    els.solutionForm.reset();
    clearDeliverableFormNotice(els.solutionFormStatus);
    els.solutionForm.querySelector('[name="solution_id"]').value = solution?.solution_id || "";
    els.solutionForm.querySelector('[name="project_id"]').value = solution?.project_id || "";
    els.solutionForm.querySelector('[name="solution_name"]').value = solution?.solution_name || "";
    els.solutionForm.querySelector('[name="github_repo_url"]').value = solution?.github_repo_url || "";
    els.solutionForm.querySelector('[name="version"]').value = solution?.version || "0.1.0";
    els.solutionForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(solution?.capacity_hours, 0);
    els.solutionForm.querySelector('[name="status"]').value = solution?.status || "not_started";
    els.solutionForm.querySelector('[name="rag_status"]').value = solution?.rag_status || "green";
    els.solutionForm.querySelector('[name="rag_reason"]').value = solution?.rag_reason || "";
    els.solutionForm.querySelector('[name="priority"]').value = solution?.priority ?? 3;
    els.solutionForm.querySelector('[name="due_date"]').value = solution?.due_date || "";
    els.solutionForm.querySelector('[name="planned_start_date"]').value = solution?.planned_start_date || "";
    els.solutionForm.querySelector('[name="description"]').value = solution?.description || "";
    els.solutionForm.querySelector('[name="problem_statement"]').value = solution?.problem_statement || "";
    els.solutionForm.querySelector('[name="success_criteria"]').value = solution?.success_criteria || "";
    els.solutionForm.querySelector('[name="escalation"]').value = solution?.escalation || "";
    els.solutionForm.querySelector('[name="impact_confidence"]').value = solution?.impact_confidence || "";
    els.solutionForm.querySelector('[name="owner"]').value = solution?.owner || "";
    els.solutionForm.querySelector('[name="owner_user_soeid"]').value = solution?.owner_user_soeid || "";
    els.solutionForm.querySelector('[name="assignee"]').value = solution?.assignee || "";
    els.solutionForm.querySelector('[name="assignee_user_soeid"]').value = solution?.assignee_user_soeid || "";
    els.solutionForm.querySelector('[name="approver"]').value = solution?.approver || "";
    els.solutionForm.querySelector('[name="approver_user_soeid"]').value = solution?.approver_user_soeid || "";
    els.solutionForm.querySelector('[name="key_stakeholder"]').value = solution?.key_stakeholder || "";
    els.solutionForm.querySelector('[name="rag_confidence"]').value = solution?.rag_confidence ?? "";
    els.solutionForm.querySelector('[name="blockers"]').value = solution?.blockers || "";
    els.solutionForm.querySelector('[name="risks"]').value = solution?.risks || "";
    updateCurrentPhaseOptions(solution?.solution_id || "", solution?.current_phase || "");
    els.solutionForm.querySelector('[name="current_phase"]').value = solution?.current_phase || "";
    if (els.deleteSolutionBtn) {
      els.deleteSolutionBtn.disabled = !solution?.solution_id;
    }
  }

  function setSolutionActionButtonLabel(isEditing) {
    if (els.solutionModalTitle) {
      els.solutionModalTitle.textContent = isEditing ? "Edit Solution" : "Create Solution";
    }
    if (els.solutionSubmitBtn) {
      els.solutionSubmitBtn.textContent = isEditing ? "Save Solution" : "Create Solution";
    }
  }

  function setTaskCreateAvailability(solutionId) {
    if (!els.showTaskFormBtn) return;
    const hasSolution = !!String(solutionId || "").trim();
    els.showTaskFormBtn.disabled = !hasSolution;
    els.showTaskFormBtn.title = hasSolution
      ? "Add a task to this solution"
      : "Save the solution before adding tasks.";
  }

  function openSolutionModal(solution = null, tab = "details") {
    if (!els.solutionModal) return;
    fillSolutionForm(solution);
    setSolutionActionButtonLabel(!!solution?.solution_id);
    setTaskCreateAvailability(solution?.solution_id || "");
    if (els.taskForm) {
      setTaskFormVisibility(false);
      setTaskActionButtonLabel(false);
    }
    els.solutionModal.classList.remove("hidden");
    if (els.taskViewToggle) {
      els.taskViewToggle.textContent = state.taskView === "table" ? "Swimlane View" : "Table View";
    }
    setSolutionTab(tab);
    if (solution?.solution_id) {
      renderSolutionPhases(solution.solution_id);
      renderSolutionTasks(solution.solution_id);
      renderSolutionDocuments(solution.solution_id);
      renderSolutionActivity(solution.solution_id);
    } else {
      if (els.phasesTable) els.phasesTable.innerHTML = "<p class='muted'>Save the solution to manage phases.</p>";
      if (els.solutionTaskTable) els.solutionTaskTable.innerHTML = "<p class='muted'>Save the solution to add tasks.</p>";
      if (els.solutionDocumentsList) els.solutionDocumentsList.innerHTML = "<p class='muted'>Save the solution to upload documents.</p>";
      if (els.solutionActivity) els.solutionActivity.innerHTML = "<p class='muted'>Save the solution to see activity.</p>";
    }
  }

  function closeSolutionModal() {
    if (!els.solutionModal) return;
    fillSolutionForm(null);
    setSolutionActionButtonLabel(false);
    setTaskCreateAvailability("");
    els.solutionModal.classList.add("hidden");
    setSolutionTab("details");
    if (els.taskForm) {
      setTaskFormVisibility(false);
      setTaskActionButtonLabel(false);
    }
  }

  function bindSolutionForm() {
    if (!els.solutionForm) return;
    els.solutionModalClose?.addEventListener("click", () => closeSolutionModal());
    els.solutionModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => closeSolutionModal());

    const saveHandler = async () => {
      const data = new FormData(els.solutionForm);
      const id = (data.get("solution_id") || "").toString().trim();
      const isEditing = !!id;
      const projectId = (data.get("project_id") || "").toString().trim();
      if (!isEditing && !projectId) {
        setDeliverableFormNotice(
          els.solutionFormStatus,
          "Select a project before creating a solution.",
          "error"
        );
        return;
      }
      const payload = buildSolutionPayload(data, { hoursFromFteInput });
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...");
        } else {
          setDeliverableFormNotice(els.solutionFormStatus, "Creating solution...");
        }
        markIgnoreRefresh("solutions");
        const saved = isEditing
          ? await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api(`/projects/${projectId}/solutions`, { method: "POST", body: JSON.stringify(payload) });
        upsertById(state.solutions, saved, "solution_id");
        populateSelects();
        fillSolutionForm(saved);
        if (els.taskForm && !els.taskForm.classList.contains("hidden")) {
          const activeOverride = els.taskForm.querySelector('[name="github_repo_url"]')?.value || "";
          updateTaskRepoPreview(saved.solution_id, activeOverride);
        }
        setSolutionActionButtonLabel(true);
        renderActiveView();
        renderSolutionPhases(saved.solution_id);
        renderSolutionTasks(saved.solution_id);
        renderSolutionDocuments(saved.solution_id, { force: true });
        renderSolutionActivity(saved.solution_id);
        const successMessage = isEditing
          ? `Saved solution at ${timestampLabel()}.`
          : `Created solution at ${timestampLabel()}.`;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("solutions", isEditing ? "update" : "create", "success", { source: "solution_form" });
        }
        setDeliverableFormNotice(
          els.solutionFormStatus,
          successMessage,
          "success",
          3200
        );
      } catch (err) {
        ignoreNextRefresh.delete("solutions");
        if (typeof trackWorkflow === "function") {
          trackWorkflow("solutions", isEditing ? "update" : "create", "failure", { source: "solution_form" });
        }
        setDeliverableFormNotice(
          els.solutionFormStatus,
          `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
          "error"
        );
      }
    };

    els.solutionForm.addEventListener("submit", (e) => {
      e.preventDefault();
      saveHandler();
    });
    els.solutionForm.addEventListener("reset", () => {
      clearDeliverableFormNotice(els.solutionFormStatus);
      fillSolutionForm(null);
      setSolutionActionButtonLabel(false);
      updateCurrentPhaseOptions("");
      renderSolutionPhases();
    });
    if (els.deleteSolutionBtn) {
      els.deleteSolutionBtn.addEventListener("click", async () => {
        const id = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (!id) return;
        const solutionName = els.solutionForm?.querySelector('[name="solution_name"]')?.value || "this solution";
        const confirmed = await showConfirmModal({
          title: "Delete Solution?",
          message: `Delete solution "${solutionName}"? This cannot be undone.`,
          confirmLabel: "Delete Solution",
        });
        if (!confirmed) return;
        try {
          setDeliverableFormNotice(els.solutionFormStatus, "Deleting solution...");
          markIgnoreRefresh("solutions");
          await api(`/solutions/${id}`, { method: "DELETE" });
          removeById(state.solutions, id, "solution_id");
          delete state.solutionPhases[id];
          delete state.solutionDocuments[id];
          closeSolutionModal();
          populateSelects();
          renderMasterTable();
          renderDashboard();
          renderKanban();
          renderCalendar();
          renderGantt();
          if (typeof trackWorkflow === "function") {
            trackWorkflow("solutions", "delete", "success", { source: "solution_form" });
          }
        } catch (err) {
          ignoreNextRefresh.delete("solutions");
          if (typeof trackWorkflow === "function") {
            trackWorkflow("solutions", "delete", "failure", { source: "solution_form" });
          }
          setDeliverableFormNotice(
            els.solutionFormStatus,
            `Delete failed: ${err.message}`,
            "error"
          );
        }
      });
    }
  }

  return {
    bindSolutionForm,
    closeSolutionModal,
    openSolutionModal,
    setTaskCreateAvailability,
  };
}
