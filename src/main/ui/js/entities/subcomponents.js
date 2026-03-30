export function createSubcomponentEntityController({
  state,
  els,
  api,
  findUserBySoeid,
  resolveAssigneeSelectValue,
  numberOr,
  hoursFromFteInput,
  hoursFromNullableFteInput,
  fteFromHoursForInput,
  updateSubcomponentRepoPreview,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
  markIgnoreRefresh,
  ignoreNextRefresh,
  upsertById,
  deleteSubcomponentsById,
  renderSolutionSubcomponents,
  renderDashboard,
  timestampLabel,
  trackWorkflow = null,
}) {
  function buildSubcomponentPayload(data) {
    const assigneeUserId = (data.get("assignee") || "").toString().trim();
    const assigneeUser = findUserBySoeid(assigneeUserId);
    return {
      subcomponent_name: data.get("subcomponent_name"),
      github_repo_url: data.get("github_repo_url") || null,
      status: data.get("status"),
      priority: Number(data.get("priority") || 3),
      due_date: data.get("due_date") || null,
      assignee: assigneeUser?.display_name || "",
      assignee_user_soeid: assigneeUserId || null,
      estimate_hours: hoursFromNullableFteInput(data.get("estimate_hours")),
      estimate_fte_months: numberOr(data.get("estimate_hours"), 0),
      blocked: data.get("blocked") ? true : false,
      blocker_note: data.get("blocker_note") || null,
      done_criteria: data.get("done_criteria") || null,
      capacity_hours: hoursFromFteInput(data.get("capacity_hours")),
      capacity_fte_months: numberOr(data.get("capacity_hours"), 0),
    };
  }

  function setSubcomponentActionButtonLabel(isEditing) {
    if (els.subcomponentSubmitBtn) {
      els.subcomponentSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Subcomponent";
    }
  }

  function setSubcomponentFormVisibility(show) {
    if (els.subcomponentForm) {
      els.subcomponentForm.classList.toggle("hidden", !show);
    }
    if (els.subcomponentFormFooter) {
      els.subcomponentFormFooter.classList.toggle("hidden", !show);
    }
  }

  function prepareSubcomponentCreateForm(solution, options = {}) {
    if (!els.subcomponentForm) return;
    const { resetForm = true } = options;
    const sol = solution || state.solutions.find((s) => s.solution_id === els.solutionForm?.querySelector('[name="solution_id"]')?.value);
    if (!sol) return;
    setSubcomponentFormVisibility(true);
    if (resetForm) els.subcomponentForm.reset();
    clearDeliverableFormNotice(els.subcomponentFormStatus);
    els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
    els.subcomponentForm.querySelector('[name="project_id"]').value = sol.project_id;
    els.subcomponentForm.querySelector('[name="solution_id"]').value = sol.solution_id;
    els.subcomponentForm.querySelector('[name="github_repo_url"]').value = "";
    els.subcomponentForm.querySelector('[name="priority"]').value = 3;
    els.subcomponentForm.querySelector('[name="status"]').value = "to_do";
    els.subcomponentForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(0, 0);
    updateSubcomponentRepoPreview(sol.solution_id, "");
    if (els.deleteSubcomponentBtn) {
      els.deleteSubcomponentBtn.disabled = true;
    }
    setSubcomponentActionButtonLabel(false);
  }

  function showSubcomponentForm(solution) {
    prepareSubcomponentCreateForm(solution);
  }

  function fillSubcomponentForm(sub) {
    if (!els.subcomponentForm || !sub) return;
    setSubcomponentFormVisibility(true);
    els.subcomponentForm.reset();
    clearDeliverableFormNotice(els.subcomponentFormStatus);
    els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = sub.subcomponent_id;
    els.subcomponentForm.querySelector('[name="project_id"]').value = sub.project_id;
    els.subcomponentForm.querySelector('[name="solution_id"]').value = sub.solution_id;
    els.subcomponentForm.querySelector('[name="subcomponent_name"]').value = sub.subcomponent_name || "";
    els.subcomponentForm.querySelector('[name="github_repo_url"]').value = sub.github_repo_url || "";
    els.subcomponentForm.querySelector('[name="priority"]').value = sub.priority ?? "";
    els.subcomponentForm.querySelector('[name="due_date"]').value = sub.due_date || "";
    els.subcomponentForm.querySelector('[name="status"]').value = sub.status || "to_do";
    els.subcomponentForm.querySelector('[name="assignee"]').value = resolveAssigneeSelectValue(sub.assignee_user_soeid, sub.assignee);
    els.subcomponentForm.querySelector('[name="assignee_user_soeid"]').value = sub.assignee_user_soeid || "";
    els.subcomponentForm.querySelector('[name="estimate_hours"]').value =
      sub.estimate_hours != null ? fteFromHoursForInput(sub.estimate_hours, 0) : "";
    els.subcomponentForm.querySelector('[name="blocked"]').checked = !!sub.blocked;
    els.subcomponentForm.querySelector('[name="blocker_note"]').value = sub.blocker_note || "";
    els.subcomponentForm.querySelector('[name="done_criteria"]').value = sub.done_criteria || "";
    els.subcomponentForm.querySelector('[name="capacity_hours"]').value = fteFromHoursForInput(sub.capacity_hours, 0);
    updateSubcomponentRepoPreview(sub.solution_id, sub.github_repo_url || "");
    if (els.deleteSubcomponentBtn) {
      els.deleteSubcomponentBtn.disabled = !sub.subcomponent_id;
    }
    setSubcomponentActionButtonLabel(!!sub.subcomponent_id);
  }

  function bindSubcomponentForm() {
    if (!els.subcomponentForm) return;
    if (!els.subcomponentForm._repoPreviewBound) {
      els.subcomponentForm.addEventListener("input", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const repoInput = target.closest('[name="github_repo_url"]');
        if (!repoInput) return;
        const solutionId = els.subcomponentForm?.querySelector('[name="solution_id"]')?.value || "";
        updateSubcomponentRepoPreview(solutionId, repoInput.value || "");
      });
      els.subcomponentForm._repoPreviewBound = true;
    }
    if (els.showSubcomponentFormBtn) {
      els.showSubcomponentFormBtn.onclick = () => {
        if (els.subcomponentForm.classList.contains("hidden")) {
          const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
          if (!solutionId) {
            renderSolutionSubcomponents("");
            return;
          }
          const solution = state.solutions.find((s) => s.solution_id === solutionId);
          showSubcomponentForm(solution);
        } else {
          setSubcomponentFormVisibility(false);
        }
      };
    }
    els.subcomponentForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(els.subcomponentForm);
      const id = (data.get("subcomponent_id") || "").toString().trim();
      const solutionId = (data.get("solution_id") || "").toString().trim();
      const isEditing = !!id;
      if (!solutionId) {
        setDeliverableFormNotice(els.subcomponentFormStatus, "Save the solution before adding subcomponents.", "error");
        return;
      }
      const payload = buildSubcomponentPayload(data);
      try {
        if (isEditing) {
          setDeliverableFormNotice(els.subcomponentFormStatus, "Saving subcomponent...");
        } else {
          setDeliverableFormNotice(els.subcomponentFormStatus, "Creating subcomponent...");
        }
        markIgnoreRefresh("subcomponents");
        const saved = isEditing
          ? await api(`/subcomponents/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
          : await api(`/solutions/${solutionId}/subcomponents`, { method: "POST", body: JSON.stringify(payload) });
        upsertById(state.subcomponents, saved, "subcomponent_id");
        fillSubcomponentForm(saved);
        renderSolutionSubcomponents(saved.solution_id);
        renderDashboard();
        const successMessage = isEditing
          ? `Saved subcomponent at ${timestampLabel()}.`
          : `Created subcomponent at ${timestampLabel()}.`;
        if (typeof trackWorkflow === "function") {
          trackWorkflow("subcomponents", isEditing ? "update" : "create", "success", { source: "subcomponent_form" });
        }
        setDeliverableFormNotice(
          els.subcomponentFormStatus,
          successMessage,
          "success",
          3200
        );
      } catch (err) {
        ignoreNextRefresh.delete("subcomponents");
        if (typeof trackWorkflow === "function") {
          trackWorkflow("subcomponents", isEditing ? "update" : "create", "failure", { source: "subcomponent_form" });
        }
        setDeliverableFormNotice(
          els.subcomponentFormStatus,
          `${isEditing ? "Save" : "Create"} failed: ${err.message}`,
          "error"
        );
      }
    });
    els.subcomponentForm.addEventListener("reset", () => {
      clearDeliverableFormNotice(els.subcomponentFormStatus);
      const solutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
      const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
      if (solution) {
        prepareSubcomponentCreateForm(solution, { resetForm: false });
        return;
      }
      els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
      if (els.deleteSubcomponentBtn) {
        els.deleteSubcomponentBtn.disabled = true;
      }
      setSubcomponentActionButtonLabel(false);
    });
    if (els.deleteSubcomponentBtn) {
      els.deleteSubcomponentBtn.addEventListener("click", async () => {
        const id = els.subcomponentForm?.querySelector('[name="subcomponent_id"]')?.value || "";
        if (!id) return;
        const solutionId = els.subcomponentForm?.querySelector('[name="solution_id"]')?.value || "";
        markIgnoreRefresh("subcomponents");
        const result = await deleteSubcomponentsById([id], {
          title: "Delete Subcomponent?",
        });
        if (result.cancelled) return;
        if (!result.deletedIds.length) {
          ignoreNextRefresh.delete("subcomponents");
        }
        const solution = state.solutions.find((item) => item.solution_id === solutionId) || null;
        if (solution) {
          showSubcomponentForm(solution);
        } else {
          els.subcomponentForm.reset();
          els.subcomponentForm.querySelector('[name="subcomponent_id"]').value = "";
          if (els.deleteSubcomponentBtn) els.deleteSubcomponentBtn.disabled = true;
          setSubcomponentActionButtonLabel(false);
        }
        renderSolutionSubcomponents(solutionId);
        renderDashboard();
        if (result.failed.length) {
          if (typeof trackWorkflow === "function") {
            trackWorkflow("subcomponents", "delete", "failure", { source: "subcomponent_form" });
          }
          setDeliverableFormNotice(
            els.subcomponentFormStatus,
            `Delete failed: ${result.failed[0]?.error?.message || "Unable to delete subcomponent."}`,
            "error"
          );
          return;
        }
        setDeliverableFormNotice(
          els.subcomponentFormStatus,
          `Deleted subcomponent at ${timestampLabel()}.`,
          "success",
          3200
        );
        if (typeof trackWorkflow === "function") {
          trackWorkflow("subcomponents", "delete", "success", { source: "subcomponent_form" });
        }
      });
    }
  }

  return {
    bindSubcomponentForm,
    fillSubcomponentForm,
    setSubcomponentActionButtonLabel,
    setSubcomponentFormVisibility,
    showSubcomponentForm,
  };
}
