import { createContextualEntityMutationGate, createContextualFormSaveGate, createEditorModalFocus, captureEntityMutationContext, isEntityMutationContextCurrent, nullableTextValue, textValue } from "../utils/form-state.js";
import { createFormDraftGuard } from "../utils/form-draft.js";

export function buildProgramPayload(data) {
  return {
    program_name: textValue(data.get("program_name")),
    description: nullableTextValue(data.get("description")),
  };
}

export function createProgramEntityController({
  state,
  els,
  api,
  upsertById,
  removeById,
  populateSelects,
  renderActiveView,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  timestampLabel,
  showConfirmModal,
  trackWorkflow = null,
}) {
  let resettingProgramForm = false;
  let programFormRevision = 0;
  let programPayloadBaseline = null;
  const modalFocus = createEditorModalFocus(state, els.programModal, els.programModalClose);
  const beginMutation = createContextualEntityMutationGate(state);
  const saveGate = createContextualFormSaveGate({ state, form: els.programForm, submit: els.programSubmitBtn });
  const programDraft = createFormDraftGuard({ form: els.programForm, indicator: els.programModal?.querySelector('[data-form-dirty-indicator="program"]'), entityLabel: "Program", showConfirmModal });

  function setProgramFormVisibility(show) {
    if (!els.programModal) return;
    els.programModal.classList.toggle("hidden", !show);
  }

  function setProgramActionButtonLabel(isEditing) {
    if (els.programModalTitle) {
      els.programModalTitle.textContent = isEditing ? "Edit Program" : "Create Program";
    }
    if (els.programSubmitBtn) {
      els.programSubmitBtn.textContent = isEditing ? "Save Program" : "Create Program";
    }
  }

  function fillProgramForm(program = null) {
    if (!els.programForm) return;
    resettingProgramForm = true;
    try {
      els.programForm.reset();
    } finally {
      resettingProgramForm = false;
    }
    clearDeliverableFormNotice(els.programFormStatus);
    const setVal = (name, value = "") => {
      const field = els.programForm.querySelector(`[name="${name}"]`);
      if (field) field.value = value ?? "";
    };
    setVal("program_id", program?.program_id || "");
    setVal("program_name", program?.program_name || "");
    setVal("description", program?.description || "");
    if (els.deleteProgramBtn) {
      els.deleteProgramBtn.disabled = !program?.program_id;
    }
    programPayloadBaseline = program?.program_id ? buildProgramPayload(new FormData(els.programForm)) : null;
    programDraft.capture();
  }

  function openProgramForm(program = null) {
    const opening = modalFocus.open();
    programFormRevision += 1;
    fillProgramForm(program);
    setProgramFormVisibility(true);
    setProgramActionButtonLabel(!!program?.program_id);
    if (opening) modalFocus.focus();
  }

  function finishClosingProgramForm(restoreFocus = true) {
    programFormRevision += 1;
    fillProgramForm(null);
    setProgramFormVisibility(false);
    setProgramActionButtonLabel(false);
    modalFocus.close(restoreFocus);
    return true;
  }

  function closeProgramForm(options = {}) {
    if (options.discardChanges || !programDraft.isDirty()) return finishClosingProgramForm(!options.discardChanges);
    const revision = programFormRevision;
    const context = captureEntityMutationContext(state);
    const draft = JSON.stringify([...new FormData(els.programForm).entries()]);
    return programDraft.confirmDiscard().then((confirmed) => {
      if (!confirmed || revision !== programFormRevision || !isEntityMutationContextCurrent(state, context)
          || draft !== JSON.stringify([...new FormData(els.programForm).entries()])) return false;
      return finishClosingProgramForm();
    });
  }

  function bindProgramForm() {
    if (!els.programForm) return;
    programDraft.bind();
    els.programModalClose?.addEventListener("click", () => closeProgramForm());
    els.programModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => closeProgramForm());
    els.programForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (saveGate.isPending()) return;
      const data = new FormData(els.programForm);
      const id = (data.get("program_id") || "").toString().trim();
      const isEditing = !!id;
      const submittedPayload = buildProgramPayload(data);
      const payload = isEditing && programPayloadBaseline
        ? Object.fromEntries(Object.entries(submittedPayload).filter(([field, value]) => !Object.is(value, programPayloadBaseline[field])))
        : submittedPayload;
      const formRevision = programFormRevision;
      const formSnapshot = JSON.stringify([...data.entries()]);

      const requestContext = captureEntityMutationContext(state);
      const isSameEditor = () => formRevision === programFormRevision;
      const isCurrentSubmission = () => isSameEditor()
        && JSON.stringify([...new FormData(els.programForm).entries()]) === formSnapshot;
      const saveRequest = saveGate.begin();
      if (!saveRequest) return;
      const release = isEditing ? beginMutation(id) : () => {};
      if (!release) {
        saveGate.end(saveRequest);
        setDeliverableFormNotice(els.programFormStatus, "This program is being updated. Try again when it finishes.", "error");
        return;
      }
      try {
        setDeliverableFormNotice(els.programFormStatus, isEditing ? "Saving program..." : "Creating program...");
        const saved = isEditing
          ? await api(`/programs/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api("/programs", { method: "POST", body: JSON.stringify(payload) });
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        const shouldUpdateForm = isCurrentSubmission();
        upsertById(state.programs, saved, "program_id");
        state.projects = (state.projects || []).map((project) => (
          project.program_id === saved.program_id
            ? { ...project, program_name: saved.program_name }
            : project
        ));
        if (shouldUpdateForm) {
          fillProgramForm(saved);
          setProgramActionButtonLabel(true);
        } else if (isSameEditor()) {
          programPayloadBaseline = submittedPayload;
          if (!isEditing && saved?.program_id) {
            els.programForm.querySelector('[name="program_id"]').value = saved.program_id;
            setProgramActionButtonLabel(true);
          }
          programDraft.rebase(formSnapshot, { program_id: saved?.program_id || id });
        }
        populateSelects();
        renderActiveView();
        if (typeof trackWorkflow === "function") {
          trackWorkflow("programs", isEditing ? "update" : "create", "success", { source: "program_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.programFormStatus,
            shouldUpdateForm ? `${isEditing ? "Saved" : "Created"} program at ${timestampLabel()}.` : `${isEditing ? "Saved" : "Created"} program; you have unsaved edits.`,
            "success",
            shouldUpdateForm ? 3200 : 0,
          );
        }
      } catch (err) {
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("programs", isEditing ? "update" : "create", "failure", { source: "program_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.programFormStatus,
            `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
            "error",
          );
        }
      } finally {
        saveGate.end(saveRequest);
        release();
      }
    });
    els.programForm.addEventListener("reset", () => {
      if (resettingProgramForm) return;
      programFormRevision += 1;
      clearDeliverableFormNotice(els.programFormStatus);
      fillProgramForm(null);
      setProgramActionButtonLabel(false);
    });
    if (els.deleteProgramBtn) {
      els.deleteProgramBtn.addEventListener("click", async () => {
        const id = els.programForm?.querySelector('[name="program_id"]')?.value || "";
        if (!id) return;
        const programName = els.programForm?.querySelector('[name="program_name"]')?.value || "this program";
        const formRevision = programFormRevision;
        const isSameEditor = () => formRevision === programFormRevision;
        const requestContext = captureEntityMutationContext(state);
        const release = beginMutation(id);
        if (!release) {
          setDeliverableFormNotice(els.programFormStatus, "This program is being updated. Try again when it finishes.", "error");
          return;
        }
        try {
          const confirmed = await showConfirmModal({
            title: "Delete Program?",
            message: `Delete program "${programName}"? Programs with active projects cannot be deleted.`,
            confirmLabel: "Delete Program",
          });
          if (!confirmed || !isSameEditor() || !isEntityMutationContextCurrent(state, requestContext)) return;
          setDeliverableFormNotice(els.programFormStatus, "Deleting program...");
          await api(`/programs/${id}`, { method: "DELETE" });
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          removeById(state.programs, id, "program_id");
          if (isSameEditor()) closeProgramForm({ discardChanges: true });
          populateSelects();
          renderActiveView();
          if (typeof trackWorkflow === "function") {
            trackWorkflow("programs", "delete", "success", { source: "program_form" });
          }
        } catch (err) {
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          if (typeof trackWorkflow === "function") {
            trackWorkflow("programs", "delete", "failure", { source: "program_form" });
          }
          if (isSameEditor()) {
            setDeliverableFormNotice(els.programFormStatus, `Delete failed: ${err.message}`, "error");
          }
        } finally {
          release();
        }
      });
    }
  }

  return {
    resetSaveForContext: saveGate.reset,
    bindProgramForm,
    closeProgramForm,
    openProgramForm,
  };
}
