import { beginSolutionMutation, createContextualFormSaveGate, createEditorModalFocus, captureEntityMutationContext, isEntityMutationContextCurrent, nullableTextValue, textValue } from "../utils/form-state.js";
import { createFormDraftGuard } from "../utils/form-draft.js";

export function buildSolutionPayload(data, { hoursFromFteInput }) {
  const ragStatus = data.get("rag_status") || "green";
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
    rag_status: ragStatus,
    rag_reason: ragStatus === "green" ? null : nullableTextValue(data.get("rag_reason")),
  };
}

export function createSolutionEntityController({
  state,
  els,
  api,
  hoursFromFteInput,
  fteFromHoursForInput,
  upsertById,
  removeById,
  populateSelects,
  renderActiveView,
  renderMasterTable,
  renderDashboard,
  renderKanban,
  renderCalendar,
  renderGantt,
  renderSolutionTasks,
  renderSolutionDocuments,
  renderSolutionActivity,
  setTaskFormVisibility,
  setTaskActionButtonLabel,
  confirmTaskDraftDiscard = () => true,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  updateCurrentPhaseOptions,
  updateTaskRepoPreview,
  setSolutionTab,
  timestampLabel,
  showConfirmModal,
  trackWorkflow = null,
}) {
  let solutionFormRevision = 0;
  const modalFocus = createEditorModalFocus(state, els.solutionModal, els.solutionModalClose);
  let solutionPayloadBaseline = null;
  let solutionDocumentEditorRevision = 0;
  const saveGate = createContextualFormSaveGate({ state, form: els.solutionForm, submit: els.solutionSubmitBtn });
  const solutionDraft = createFormDraftGuard({
    form: els.solutionForm,
    indicator: els.solutionModal?.querySelector('[data-form-dirty-indicator="solution"]'),
    entityLabel: "Solution",
    showConfirmModal,
  });

  function updateRagReasonVisibility() {
    const status = els.solutionForm?.querySelector('[name="rag_status"]')?.value || "green";
    const reasonField = els.solutionForm?.querySelector("[data-solution-rag-reason]");
    if (!reasonField) return;
    const showReason = status === "amber" || status === "red";
    reasonField.hidden = !showReason;
    reasonField.setAttribute("aria-hidden", showReason ? "false" : "true");
  }

  function fillSolutionForm(solution = null, { preserveNotice = false } = {}) {
    if (!els.solutionForm) return;
    els.solutionForm.reset();
    if (!preserveNotice) clearDeliverableFormNotice(els.solutionFormStatus);
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
    updateRagReasonVisibility();
    solutionDraft.capture();
    solutionPayloadBaseline = solution?.solution_id
      ? buildSolutionPayload(new FormData(els.solutionForm), { hoursFromFteInput }) : null;
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

  function openSolutionModal(solution = null, tab = "details", options = {}) {
    if (!els.solutionForm || !els.solutionModal) return false;
    if (options.preserveNotice) {
      openSolutionModalNow(solution, tab, options);
      return true;
    }
    const revision = solutionFormRevision;
    const context = captureEntityMutationContext(state);
    const snapshot = JSON.stringify([...new FormData(els.solutionForm).entries()]);
    const current = () => revision === solutionFormRevision && isEntityMutationContextCurrent(state, context)
      && snapshot === JSON.stringify([...new FormData(els.solutionForm).entries()]);
    const open = () => { if (!current()) return false; openSolutionModalNow(solution, tab, options); return true; };
    const afterTask = (ok) => {
      if (!ok || !current()) return false;
      if (els.solutionModal?.classList.contains("hidden") || !solutionDraft.isDirty()) return open();
      const taskSnapshot = els.taskForm ? JSON.stringify([...new FormData(els.taskForm).entries()]) : "";
      return solutionDraft.confirmDiscard().then((confirmed) => {
        if (!confirmed || (els.taskForm && taskSnapshot !== JSON.stringify([...new FormData(els.taskForm).entries()]))) return false;
        return open();
      });
    };
    const allowed = confirmTaskDraftDiscard();
    return allowed instanceof Promise ? allowed.then(afterTask) : afterTask(allowed);
  }

  function openSolutionModalNow(solution = null, tab = "details", options = {}) {
    if (!els.solutionModal) return;
    const opening = modalFocus.open();
    solutionFormRevision += 1;
    if (!options.preserveNotice) {
      solutionDocumentEditorRevision += 1;
      if (els.solutionDocumentsStatus) clearDeliverableFormNotice(els.solutionDocumentsStatus);
    }
    fillSolutionForm(solution, options);
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
    if (opening) modalFocus.focus();
    if (solution?.solution_id) {
      renderSolutionTasks(solution.solution_id);
      renderSolutionDocuments(solution.solution_id);
      renderSolutionActivity(solution.solution_id);
    } else {
      if (els.solutionTaskTable) els.solutionTaskTable.innerHTML = "<p class='muted'>Save the solution to add tasks.</p>";
      if (els.solutionDocumentsList) els.solutionDocumentsList.innerHTML = "<p class='muted'>Save the solution to upload documents.</p>";
      if (els.solutionActivity) els.solutionActivity.innerHTML = "<p class='muted'>Save the solution to see activity.</p>";
    }
  }

  function finishClosingSolutionModal(restoreFocus = true) {
    if (!els.solutionModal) return;
    solutionFormRevision += 1;
    solutionDocumentEditorRevision += 1;
    if (els.solutionDocumentsStatus) clearDeliverableFormNotice(els.solutionDocumentsStatus);
    fillSolutionForm(null);
    setSolutionActionButtonLabel(false);
    setTaskCreateAvailability("");
    els.solutionModal.classList.add("hidden");
    setSolutionTab("details");
    if (els.taskForm) {
      setTaskFormVisibility(false);
      setTaskActionButtonLabel(false);
    }
    modalFocus.close(restoreFocus);
    return true;
  }

  function closeSolutionModal(options = {}) {
    if (!els.solutionModal) return false;
    const revision = solutionFormRevision;
    const context = captureEntityMutationContext(state);
    const snapshot = els.solutionForm ? JSON.stringify([...new FormData(els.solutionForm).entries()]) : "";
    const afterTask = (ok) => {
      if (!ok || revision !== solutionFormRevision || !isEntityMutationContextCurrent(state, context)
          || (els.solutionForm && snapshot !== JSON.stringify([...new FormData(els.solutionForm).entries()]))) return false;
      return closeSolutionAfterTask(options);
    };
    const allowed = options.discardChanges ? true : confirmTaskDraftDiscard();
    return allowed instanceof Promise ? allowed.then(afterTask) : afterTask(allowed);
  }

  function closeSolutionAfterTask(options) {
    if (options.discardChanges || !solutionDraft.isDirty()) {
      return finishClosingSolutionModal(!options.discardChanges);
    }
    const revision = solutionFormRevision;
    const context = captureEntityMutationContext(state);
    const draft = JSON.stringify([...new FormData(els.solutionForm).entries()]);
    return solutionDraft.confirmDiscard().then((confirmed) => {
      if (!confirmed || revision !== solutionFormRevision || !isEntityMutationContextCurrent(state, context)
          || draft !== JSON.stringify([...new FormData(els.solutionForm).entries()])) return false;
      return finishClosingSolutionModal();
    });
  }

  function bindSolutionForm() {
    if (!els.solutionForm) return;
    solutionDraft.bind();
    els.solutionModalClose?.addEventListener("click", () => void closeSolutionModal());
    els.solutionModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => void closeSolutionModal());
    els.solutionForm.querySelector('[name="rag_status"]')?.addEventListener("change", updateRagReasonVisibility);

    const saveHandler = async () => {
      if (saveGate.isPending()) return;
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
      const submittedPayload = buildSolutionPayload(data, { hoursFromFteInput });
      let payload = submittedPayload;
      if (isEditing && solutionPayloadBaseline) {
        payload = Object.fromEntries(Object.entries(submittedPayload)
          .filter(([field, value]) => !Object.is(value, solutionPayloadBaseline[field])));
        for (const fields of [
          ["rag_status", "rag_reason"],
          ["owner", "owner_user_soeid"],
          ["assignee", "assignee_user_soeid"],
          ["approver", "approver_user_soeid"],
        ]) {
          if (fields.some((field) => Object.hasOwn(payload, field))) {
            fields.forEach((field) => { payload[field] = submittedPayload[field]; });
          }
        }
      }
      const formRevision = solutionFormRevision;
      const formSnapshot = JSON.stringify([...data.entries()]);

      const requestContext = captureEntityMutationContext(state);
      const isSameEditor = () => formRevision === solutionFormRevision;
      const isCurrentSubmission = () => isSameEditor()
        && JSON.stringify([...new FormData(els.solutionForm).entries()]) === formSnapshot;
      const saveRequest = saveGate.begin();
      if (!saveRequest) return;
      const release = isEditing ? beginSolutionMutation(state, id) : () => {};
      if (!release) {
        saveGate.end(saveRequest);
        setDeliverableFormNotice(els.solutionFormStatus, "This solution is being updated. Try again when it finishes.", "error");
        return;
      }
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...");
        } else {
          setDeliverableFormNotice(els.solutionFormStatus, "Creating solution...");
        }
        const saved = isEditing
          ? await api(`/solutions/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api(`/projects/${projectId}/solutions`, { method: "POST", body: JSON.stringify(payload) });
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        const shouldUpdateForm = isCurrentSubmission();
        upsertById(state.solutions, saved, "solution_id");
        populateSelects();
        if (shouldUpdateForm) {
          fillSolutionForm(saved);
        } else if (isSameEditor()) {
          // Later edits are relative to the values just submitted.
          solutionPayloadBaseline = submittedPayload;
          if (!isEditing && saved?.solution_id) {
            els.solutionForm.querySelector('[name="solution_id"]').value = saved.solution_id;
          }
          solutionDraft.rebase(formSnapshot, { solution_id: saved?.solution_id || id });
        }
        if (isSameEditor()) {
          if (els.taskForm && !els.taskForm.classList.contains("hidden")) {
            const activeOverride = els.taskForm.querySelector('[name="github_repo_url"]')?.value || "";
            updateTaskRepoPreview(saved.solution_id, activeOverride);
          }
          setSolutionActionButtonLabel(true);
        }
        renderActiveView();
        if (isSameEditor()) {
          renderSolutionTasks(saved.solution_id);
          renderSolutionDocuments(saved.solution_id, { force: true });
          renderSolutionActivity(saved.solution_id);
        }
        const successMessage = isEditing
          ? `Saved solution at ${timestampLabel()}.`
          : `Created solution at ${timestampLabel()}.`;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("solutions", isEditing ? "update" : "create", "success", { source: "solution_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.solutionFormStatus,
            shouldUpdateForm ? successMessage : `${isEditing ? "Saved" : "Created"} solution; you have unsaved edits.`,
            "success",
            shouldUpdateForm ? 3200 : 0
          );
        }
      } catch (err) {
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("solutions", isEditing ? "update" : "create", "failure", { source: "solution_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.solutionFormStatus,
            `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
            "error"
          );
        }
      } finally {
        saveGate.end(saveRequest);
        release();
      }
    };

    els.solutionForm.addEventListener("submit", (e) => {
      e.preventDefault();
      saveHandler();
    });
    if (els.deleteSolutionBtn) {
      els.deleteSolutionBtn.addEventListener("click", async () => {
        const id = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
        if (!id) return;
        const solutionName = els.solutionForm?.querySelector('[name="solution_name"]')?.value || "this solution";
        const formRevision = solutionFormRevision;
        const isSameEditor = () => formRevision === solutionFormRevision;
        const requestContext = captureEntityMutationContext(state);
        const confirmed = await showConfirmModal({
          title: "Delete Solution?",
          message: `Delete solution "${solutionName}"? This cannot be undone.`,
          confirmLabel: "Delete Solution",
        });
        if (!confirmed || !isSameEditor() || !isEntityMutationContextCurrent(state, requestContext)) return;
        const release = beginSolutionMutation(state, id);
        if (!release) {
          setDeliverableFormNotice(els.solutionFormStatus, "This solution is being updated. Try again when it finishes.", "error");
          return;
        }
        try {
          setDeliverableFormNotice(els.solutionFormStatus, "Deleting solution...");
          await api(`/solutions/${id}`, { method: "DELETE" });
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          removeById(state.solutions, id, "solution_id");
          delete state.solutionDocuments[id];
          if (isSameEditor()) closeSolutionModal({ discardChanges: true });
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
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          if (typeof trackWorkflow === "function") {
            trackWorkflow("solutions", "delete", "failure", { source: "solution_form" });
          }
          if (isSameEditor()) {
            setDeliverableFormNotice(
              els.solutionFormStatus,
              `Delete failed: ${err.message}`,
              "error"
            );
          }
        } finally {
          release();
        }
      });
    }
  }

  return {
    resetSaveForContext: saveGate.reset,
    getSolutionDocumentEditorRevision: () => solutionDocumentEditorRevision,
    bindSolutionForm,
    closeSolutionModal,
    openSolutionModal,
    setTaskCreateAvailability,
  };
}
