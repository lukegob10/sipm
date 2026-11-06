import { createContextualEntityMutationGate, createContextualFormSaveGate, createEditorModalFocus, captureEntityMutationContext, isEntityMutationContextCurrent, nullableTextValue, textValue } from "../utils/form-state.js";
import { createFormDraftGuard } from "../utils/form-draft.js";

export function buildProjectPayload(data) {
  return {
    program_id: textValue(data.get("program_id")),
    project_name: textValue(data.get("project_name")),
    function: nullableTextValue(data.get("function")),
    area: nullableTextValue(data.get("area")),
    status: data.get("status"),
    description: data.get("description"),
    success_criteria: nullableTextValue(data.get("success_criteria")),
    sponsor: textValue(data.get("sponsor")),
    sponsor_user_soeid: nullableTextValue(data.get("sponsor_user_soeid")),
    owner: textValue(data.get("owner")),
    owner_user_soeid: nullableTextValue(data.get("owner_user_soeid")),
    strategic_objective: nullableTextValue(data.get("strategic_objective")),
    priority: Number(data.get("priority") || 3),
  };
}

export function createProjectEntityController({
  state,
  els,
  api,
  upsertById,
  removeById,
  populateSelects,
  renderMasterTable,
  renderDashboard,
  renderKanban,
  renderCalendar,
  renderGantt,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  timestampLabel,
  showConfirmModal,
  trackWorkflow = null,
}) {
  let projectFormRevision = 0;
  let projectPayloadBaseline = null;
  const modalFocus = createEditorModalFocus(state, els.projectModal, els.projectModalClose);
  const beginMutation = createContextualEntityMutationGate(state);
  const saveGate = createContextualFormSaveGate({ state, form: els.projectForm, submit: els.projectSubmitBtn });
  const projectDraft = createFormDraftGuard({
    form: els.projectForm,
    indicator: els.projectModal?.querySelector('[data-form-dirty-indicator="project"]'),
    entityLabel: "Project",
    showConfirmModal,
  });

  function setProjectFormVisibility(show) {
    if (!els.projectModal) return;
    els.projectModal.classList.toggle("hidden", !show);
  }

  function setProjectActionButtonLabel(isEditing) {
    if (els.projectModalTitle) {
      els.projectModalTitle.textContent = isEditing ? "Edit Project" : "Create Project";
    }
    if (els.projectSubmitBtn) {
      els.projectSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Project";
    }
  }

  function fillProjectForm(project = null, { preserveNotice = false } = {}) {
    if (!els.projectForm) return;
    els.projectForm.reset();
    if (!preserveNotice) clearDeliverableFormNotice(els.projectFormStatus);
    const setVal = (name, value = "") => {
      const field = els.projectForm.querySelector(`[name="${name}"]`);
      if (field) field.value = value ?? "";
    };
    setVal("project_id", project?.project_id || "");
    setVal(
      "program_id",
      project?.program_id
        || state.programs?.find((program) => program.program_name === "Default Program")?.program_id
        || state.programs?.[0]?.program_id
        || "",
    );
    setVal("project_name", project?.project_name || "");
    setVal("function", project?.function || "");
    setVal("area", project?.area || "");
    setVal("status", project?.status || "not_started");
    setVal("description", project?.description || "");
    setVal("success_criteria", project?.success_criteria || "");
    setVal("sponsor", project?.sponsor || "");
    setVal("sponsor_user_soeid", project?.sponsor_user_soeid || "");
    setVal("owner", project?.owner || "");
    setVal("owner_user_soeid", project?.owner_user_soeid || "");
    setVal("strategic_objective", project?.strategic_objective || "");
    setVal("priority", project?.priority ?? 3);
    if (els.deleteProjectBtn) {
      els.deleteProjectBtn.disabled = !project?.project_id;
    }
    projectDraft.capture();
    projectPayloadBaseline = project?.project_id ? buildProjectPayload(new FormData(els.projectForm)) : null;
  }

  function openProjectForm(project = null, options = {}) {
    const opening = modalFocus.open();
    projectFormRevision += 1;
    fillProjectForm(project, options);
    setProjectFormVisibility(true);
    setProjectActionButtonLabel(!!project?.project_id);
    if (opening) modalFocus.focus();
  }

  function finishClosingProjectForm(restoreFocus = true) {
    projectFormRevision += 1;
    fillProjectForm(null);
    setProjectFormVisibility(false);
    setProjectActionButtonLabel(false);
    modalFocus.close(restoreFocus);
    return true;
  }

  function closeProjectForm(options = {}) {
    if (options.discardChanges || !projectDraft.isDirty()) {
      return finishClosingProjectForm(!options.discardChanges);
    }
    const revision = projectFormRevision;
    const context = captureEntityMutationContext(state);
    const draft = JSON.stringify([...new FormData(els.projectForm).entries()]);
    return projectDraft.confirmDiscard().then((confirmed) => {
      if (!confirmed || revision !== projectFormRevision || !isEntityMutationContextCurrent(state, context)
          || draft !== JSON.stringify([...new FormData(els.projectForm).entries()])) return false;
      return finishClosingProjectForm();
    });
  }

  function bindProjectForm() {
    if (!els.projectForm) return;
    projectDraft.bind();
    els.projectModalClose?.addEventListener("click", () => void closeProjectForm());
    els.projectModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => void closeProjectForm());
    els.projectForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (saveGate.isPending()) return;
      const data = new FormData(els.projectForm);
      const id = (data.get("project_id") || "").toString().trim();
      const isEditing = !!id;
      const submittedPayload = buildProjectPayload(data);
      let payload = submittedPayload;
      if (isEditing && projectPayloadBaseline) {
        payload = Object.fromEntries(Object.entries(submittedPayload)
          .filter(([field, value]) => !Object.is(value, projectPayloadBaseline[field])));
        for (const fields of [["owner", "owner_user_soeid"], ["sponsor", "sponsor_user_soeid"]]) {
          if (fields.some((field) => Object.hasOwn(payload, field))) {
            fields.forEach((field) => { payload[field] = submittedPayload[field]; });
          }
        }
      }
      const formRevision = projectFormRevision;
      const formSnapshot = JSON.stringify([...data.entries()]);

      const requestContext = captureEntityMutationContext(state);
      const isSameEditor = () => formRevision === projectFormRevision;
      const isCurrentSubmission = () => isSameEditor()
        && JSON.stringify([...new FormData(els.projectForm).entries()]) === formSnapshot;
      const saveRequest = saveGate.begin();
      if (!saveRequest) return;
      const release = isEditing ? beginMutation(id) : () => {};
      if (!release) {
        saveGate.end(saveRequest);
        setDeliverableFormNotice(els.projectFormStatus, "This project is being updated. Try again when it finishes.", "error");
        return;
      }
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.projectFormStatus, "Saving project...");
        } else {
          setDeliverableFormNotice(els.projectFormStatus, "Creating project...");
        }
        const saved = isEditing
          ? await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api("/projects", { method: "POST", body: JSON.stringify(payload) });
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        const shouldUpdateForm = isCurrentSubmission();
        upsertById(state.projects, saved, "project_id");
        if (shouldUpdateForm) {
          fillProjectForm(saved);
          setProjectActionButtonLabel(true);
        } else if (isSameEditor()) {
          projectPayloadBaseline = submittedPayload;
          if (!isEditing && saved?.project_id) {
            els.projectForm.querySelector('[name="project_id"]').value = saved.project_id;
            setProjectActionButtonLabel(true);
          }
          projectDraft.rebase(formSnapshot, { project_id: saved?.project_id || id });
        }
        populateSelects();
        renderMasterTable();
        renderDashboard();
        renderKanban();
        renderCalendar();
        renderGantt();
        const successMessage = isEditing
          ? `Saved project at ${timestampLabel()}.`
          : `Created project at ${timestampLabel()}.`;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("projects", isEditing ? "update" : "create", "success", { source: "project_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.projectFormStatus,
            shouldUpdateForm ? successMessage : `${isEditing ? "Saved" : "Created"} project; you have unsaved edits.`,
            "success",
            shouldUpdateForm ? 3200 : 0
          );
        }
      } catch (err) {
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("projects", isEditing ? "update" : "create", "failure", { source: "project_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.projectFormStatus,
            `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
            "error"
          );
        }
      } finally {
        saveGate.end(saveRequest);
        release();
      }
    });
    if (els.deleteProjectBtn) {
      els.deleteProjectBtn.addEventListener("click", async () => {
        const id = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
        if (!id) return;
        const projectName = els.projectForm?.querySelector('[name="project_name"]')?.value || "this project";
        const formRevision = projectFormRevision;
        const isSameEditor = () => formRevision === projectFormRevision;
        const requestContext = captureEntityMutationContext(state);
        const release = beginMutation(id);
        if (!release) {
          setDeliverableFormNotice(els.projectFormStatus, "This project is being updated. Try again when it finishes.", "error");
          return;
        }
        try {
          const confirmed = await showConfirmModal({
            title: "Delete Project?",
            message: `Delete project "${projectName}"? This cannot be undone.`,
            confirmLabel: "Delete Project",
          });
          if (!confirmed || !isSameEditor() || !isEntityMutationContextCurrent(state, requestContext)) return;
          setDeliverableFormNotice(els.projectFormStatus, "Deleting project...");
          await api(`/projects/${id}`, { method: "DELETE" });
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          removeById(state.projects, id, "project_id");
          if (isSameEditor()) closeProjectForm({ discardChanges: true });
          populateSelects();
          renderMasterTable();
          renderDashboard();
          renderKanban();
          renderCalendar();
          renderGantt();
          if (typeof trackWorkflow === "function") {
            trackWorkflow("projects", "delete", "success", { source: "project_form" });
          }
        } catch (err) {
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          if (typeof trackWorkflow === "function") {
            trackWorkflow("projects", "delete", "failure", { source: "project_form" });
          }
          if (isSameEditor()) {
            setDeliverableFormNotice(
              els.projectFormStatus,
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
    bindProjectForm,
    closeProjectForm,
    openProjectForm,
  };
}
