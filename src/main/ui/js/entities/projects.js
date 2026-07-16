import { nullableTextValue, textValue } from "../utils/form-values.js";

export function buildProjectPayload(data) {
  return {
    program_id: textValue(data.get("program_id")),
    project_name: textValue(data.get("project_name")),
    status: data.get("status"),
    description: data.get("description"),
    success_criteria: nullableTextValue(data.get("success_criteria")),
    sponsor: textValue(data.get("sponsor")),
    sponsor_user_soeid: nullableTextValue(data.get("sponsor_user_soeid")),
    strategic_objective: nullableTextValue(data.get("strategic_objective")),
    priority: Number(data.get("priority") || 3),
  };
}

export function createProjectEntityController({
  state,
  els,
  api,
  markIgnoreRefresh,
  ignoreNextRefresh,
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
  let resettingProjectForm = false;

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

  function fillProjectForm(project = null) {
    if (!els.projectForm) return;
    resettingProjectForm = true;
    try {
      els.projectForm.reset();
    } finally {
      resettingProjectForm = false;
    }
    clearDeliverableFormNotice(els.projectFormStatus);
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
    setVal("status", project?.status || "not_started");
    setVal("description", project?.description || "");
    setVal("success_criteria", project?.success_criteria || "");
    setVal("sponsor", project?.sponsor || "");
    setVal("sponsor_user_soeid", project?.sponsor_user_soeid || "");
    setVal("strategic_objective", project?.strategic_objective || "");
    setVal("priority", project?.priority ?? 3);
    if (els.deleteProjectBtn) {
      els.deleteProjectBtn.disabled = !project?.project_id;
    }
  }

  function openProjectForm(project = null) {
    fillProjectForm(project);
    setProjectFormVisibility(true);
    setProjectActionButtonLabel(!!project?.project_id);
  }

  function closeProjectForm() {
    fillProjectForm(null);
    setProjectFormVisibility(false);
    setProjectActionButtonLabel(false);
  }

  function bindProjectForm() {
    if (!els.projectForm) return;
    els.projectModalClose?.addEventListener("click", () => closeProjectForm());
    els.projectModal?.querySelector(".modal-backdrop")?.addEventListener("click", () => closeProjectForm());
    els.projectForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.projectForm);
      const id = (data.get("project_id") || "").toString().trim();
      const isEditing = !!id;
      const payload = buildProjectPayload(data);
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.projectFormStatus, "Saving project...");
        } else {
          setDeliverableFormNotice(els.projectFormStatus, "Creating project...");
        }
        markIgnoreRefresh("projects");
        const saved = isEditing
          ? await api(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api("/projects", { method: "POST", body: JSON.stringify(payload) });
        upsertById(state.projects, saved, "project_id");
        fillProjectForm(saved);
        setProjectActionButtonLabel(true);
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
        setDeliverableFormNotice(
          els.projectFormStatus,
          successMessage,
          "success",
          3200
        );
      } catch (err) {
        ignoreNextRefresh.delete("projects");
        if (typeof trackWorkflow === "function") {
          trackWorkflow("projects", isEditing ? "update" : "create", "failure", { source: "project_form" });
        }
        setDeliverableFormNotice(
          els.projectFormStatus,
          `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
          "error"
        );
      }
    });
    els.projectForm.addEventListener("reset", () => {
      if (resettingProjectForm) return;
      clearDeliverableFormNotice(els.projectFormStatus);
      fillProjectForm(null);
      setProjectActionButtonLabel(false);
    });
    if (els.deleteProjectBtn) {
      els.deleteProjectBtn.addEventListener("click", async () => {
        const id = els.projectForm?.querySelector('[name="project_id"]')?.value || "";
        if (!id) return;
        const projectName = els.projectForm?.querySelector('[name="project_name"]')?.value || "this project";
        const confirmed = await showConfirmModal({
          title: "Delete Project?",
          message: `Delete project "${projectName}"? This cannot be undone.`,
          confirmLabel: "Delete Project",
        });
        if (!confirmed) return;
        try {
          setDeliverableFormNotice(els.projectFormStatus, "Deleting project...");
          markIgnoreRefresh("projects");
          await api(`/projects/${id}`, { method: "DELETE" });
          removeById(state.projects, id, "project_id");
          closeProjectForm();
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
          ignoreNextRefresh.delete("projects");
          if (typeof trackWorkflow === "function") {
            trackWorkflow("projects", "delete", "failure", { source: "project_form" });
          }
          setDeliverableFormNotice(
            els.projectFormStatus,
            `Delete failed: ${err.message}`,
            "error"
          );
        }
      });
    }
  }

  return {
    bindProjectForm,
    closeProjectForm,
    openProjectForm,
  };
}
