import { captureEntityMutationContext, isEntityMutationContextCurrent, nullableTextValue, textValue } from "../utils/form-state.js";

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
  markIgnoreRefresh,
  ignoreNextRefresh,
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
  let programSaveInFlight = false;

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
  }

  function openProgramForm(program = null) {
    programFormRevision += 1;
    fillProgramForm(program);
    setProgramFormVisibility(true);
    setProgramActionButtonLabel(!!program?.program_id);
  }

  function closeProgramForm() {
    programFormRevision += 1;
    fillProgramForm(null);
    setProgramFormVisibility(false);
    setProgramActionButtonLabel(false);
  }

  function bindProgramForm() {
    if (!els.programForm) return;
    els.programModalClose?.addEventListener("click", () => closeProgramForm());
    els.programModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => closeProgramForm());
    els.programForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (programSaveInFlight) return;
      const data = new FormData(els.programForm);
      const id = (data.get("program_id") || "").toString().trim();
      const isEditing = !!id;
      const payload = buildProgramPayload(data);
      const formRevision = programFormRevision;
      const formSnapshot = JSON.stringify([...data.entries()]);
      const submitWasDisabled = !!els.programSubmitBtn?.disabled;
      const requestContext = captureEntityMutationContext(state);
      const isSameEditor = () => formRevision === programFormRevision;
      const isCurrentSubmission = () => isSameEditor()
        && JSON.stringify([...new FormData(els.programForm).entries()]) === formSnapshot;
      programSaveInFlight = true;
      if (els.programSubmitBtn) els.programSubmitBtn.disabled = true;
      els.programForm.setAttribute("aria-busy", "true");
      try {
        setDeliverableFormNotice(els.programFormStatus, isEditing ? "Saving program..." : "Creating program...");
        markIgnoreRefresh("programs");
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
        } else if (isSameEditor() && !isEditing && saved?.program_id) {
          els.programForm.querySelector('[name="program_id"]').value = saved.program_id;
          setProgramActionButtonLabel(true);
        }
        populateSelects();
        renderActiveView();
        if (typeof trackWorkflow === "function") {
          trackWorkflow("programs", isEditing ? "update" : "create", "success", { source: "program_form" });
        }
        if (isSameEditor()) {
          setDeliverableFormNotice(
            els.programFormStatus,
            `${isEditing ? "Saved" : "Created"} program at ${timestampLabel()}.`,
            "success",
            3200,
          );
        }
      } catch (err) {
        if (!isEntityMutationContextCurrent(state, requestContext)) return;
        ignoreNextRefresh.delete("programs");
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
        programSaveInFlight = false;
        els.programForm.removeAttribute("aria-busy");
        if (els.programSubmitBtn) els.programSubmitBtn.disabled = submitWasDisabled;
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
        const confirmed = await showConfirmModal({
          title: "Delete Program?",
          message: `Delete program "${programName}"? Programs with active projects cannot be deleted.`,
          confirmLabel: "Delete Program",
        });
        if (!confirmed || !isSameEditor() || !isEntityMutationContextCurrent(state, requestContext)) return;
        try {
          setDeliverableFormNotice(els.programFormStatus, "Deleting program...");
          markIgnoreRefresh("programs");
          await api(`/programs/${id}`, { method: "DELETE" });
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          removeById(state.programs, id, "program_id");
          if (isSameEditor()) closeProgramForm();
          populateSelects();
          renderActiveView();
          if (typeof trackWorkflow === "function") {
            trackWorkflow("programs", "delete", "success", { source: "program_form" });
          }
        } catch (err) {
          if (!isEntityMutationContextCurrent(state, requestContext)) return;
          ignoreNextRefresh.delete("programs");
          if (typeof trackWorkflow === "function") {
            trackWorkflow("programs", "delete", "failure", { source: "program_form" });
          }
          if (isSameEditor()) {
            setDeliverableFormNotice(els.programFormStatus, `Delete failed: ${err.message}`, "error");
          }
        }
      });
    }
  }

  return {
    bindProgramForm,
    closeProgramForm,
    openProgramForm,
  };
}
