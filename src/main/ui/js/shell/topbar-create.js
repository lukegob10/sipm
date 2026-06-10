export function createTopbarCreateController({
  state,
  els,
  escapeHtml,
  openProgramForm,
  openProjectForm,
  openSolutionModal,
  showTaskForm,
  clearDeliverableFormNotice,
  setDeliverableFormNotice,
}) {
  function closeTopbarCreateMenu({ restoreFocus = true } = {}) {
    if (!els.topbarCreatePanel || !els.topbarCreateToggle) return;
    els.topbarCreatePanel.classList.add("hidden");
    els.topbarCreateToggle.setAttribute("aria-expanded", "false");
    if (restoreFocus) els.topbarCreateToggle.focus();
  }

  function taskCreateCandidateSolutions() {
    return [...(state.solutions || [])].sort((a, b) => {
      const projectA = state.projects.find((project) => project.project_id === a.project_id)?.project_name || "";
      const projectB = state.projects.find((project) => project.project_id === b.project_id)?.project_name || "";
      const projectDiff = projectA.localeCompare(projectB);
      if (projectDiff !== 0) return projectDiff;
      return String(a.solution_name || "").localeCompare(String(b.solution_name || ""));
    });
  }

  function taskCreateSolutionLabel(solution) {
    const projectName = state.projects.find((project) => project.project_id === solution?.project_id)?.project_name || "";
    const solutionName = String(solution?.solution_name || "").trim() || "Untitled Solution";
    return projectName ? `${projectName} / ${solutionName}` : solutionName;
  }

  function closeTaskCreatePicker() {
    if (!els.taskCreatePickerModal) return;
    els.taskCreatePickerModal.classList.add("hidden");
    clearDeliverableFormNotice(els.taskCreatePickerStatus);
  }

  function continueTaskCreateForSolution(solution) {
    if (!solution?.solution_id) return;
    closeTaskCreatePicker();
    openSolutionModal(solution, "tasks");
    showTaskForm(solution);
  }

  function populateTaskCreatePickerOptions(selectedSolutionId = "") {
    if (!els.taskCreatePickerSelect) return;
    const solutions = taskCreateCandidateSolutions();
    const options = solutions
      .map((solution) => {
        const selected = solution.solution_id === selectedSolutionId ? "selected" : "";
        return `<option value="${escapeHtml(solution.solution_id)}" ${selected}>${escapeHtml(taskCreateSolutionLabel(solution))}</option>`;
      })
      .join("");
    els.taskCreatePickerSelect.innerHTML = options;
    if (selectedSolutionId) {
      els.taskCreatePickerSelect.value = selectedSolutionId;
    }
  }

  function openTaskCreatePicker(selectedSolutionId = "") {
    if (!els.taskCreatePickerModal) return;
    populateTaskCreatePickerOptions(selectedSolutionId);
    clearDeliverableFormNotice(els.taskCreatePickerStatus);
    els.taskCreatePickerModal.classList.remove("hidden");
    window.setTimeout(() => {
      els.taskCreatePickerSelect?.focus();
    }, 0);
  }

  function handleTopbarTaskCreate() {
    closeTopbarCreateMenu({ restoreFocus: false });
    const currentOpenSolutionId = !els.solutionModal?.classList.contains("hidden")
      ? (els.solutionForm?.querySelector('[name="solution_id"]')?.value || "")
      : "";
    const currentOpenSolution = currentOpenSolutionId
      ? state.solutions.find((solution) => solution.solution_id === currentOpenSolutionId)
      : null;
    if (currentOpenSolution?.solution_id) {
      continueTaskCreateForSolution(currentOpenSolution);
      return;
    }
    const solutions = taskCreateCandidateSolutions();
    if (!solutions.length) {
      openSolutionModal(null, "details");
      setDeliverableFormNotice(els.solutionFormStatus, "Create a solution first, then add tasks.", "error");
      return;
    }
    if (solutions.length === 1) {
      continueTaskCreateForSolution(solutions[0]);
      return;
    }
    openTaskCreatePicker(currentOpenSolutionId);
  }

  function openTopbarCreateMenu() {
    if (!els.topbarCreatePanel || !els.topbarCreateToggle) return;
    if (els.csvActionsMenu && !els.csvActionsMenu.classList.contains("hidden")) {
      els.csvActionsMenu.classList.add("hidden");
      els.csvActionsToggle?.setAttribute("aria-expanded", "false");
    }
    els.topbarCreatePanel.classList.remove("hidden");
    els.topbarCreateToggle.setAttribute("aria-expanded", "true");
    const items = Array.from(els.topbarCreatePanel.querySelectorAll("[role='menuitem']"));
    items[0]?.focus();
  }

  function bindTopbarCreateMenu() {
    const topbarCreateMenuItems = () => Array.from(els.topbarCreatePanel?.querySelectorAll("[role='menuitem']") || []);
    const toggleTopbarCreateMenu = () => {
      if (!els.topbarCreatePanel || !els.topbarCreateToggle) return;
      const isHidden = els.topbarCreatePanel.classList.contains("hidden");
      if (isHidden) {
        openTopbarCreateMenu();
      } else {
        closeTopbarCreateMenu();
      }
    };

    if (els.topbarCreateToggle && !els.topbarCreateToggle._bound) {
      els.topbarCreateToggle.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " " && event.key !== "ArrowDown") return;
        event.preventDefault();
        openTopbarCreateMenu();
      });
      els.topbarCreateToggle.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleTopbarCreateMenu();
      });
      els.topbarCreateToggle._bound = true;
    }

    if (els.topbarCreatePanel && !els.topbarCreatePanel._bound) {
      els.topbarCreatePanel.addEventListener("keydown", (event) => {
        const items = topbarCreateMenuItems();
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        const activeIndex = items.indexOf(document.activeElement);

        if (event.key === "Escape") {
          event.preventDefault();
          closeTopbarCreateMenu();
          return;
        }
        if (event.key === "ArrowDown") {
          event.preventDefault();
          items[(activeIndex + 1) % items.length]?.focus();
          return;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          items[(activeIndex - 1 + items.length) % items.length]?.focus();
          return;
        }
        if (event.key === "Home") {
          event.preventDefault();
          first.focus();
          return;
        }
        if (event.key === "End") {
          event.preventDefault();
          last.focus();
          return;
        }
      });
      els.topbarCreatePanel.addEventListener("click", (event) => {
        event.stopPropagation();
      });
      els.topbarCreatePanel._bound = true;
    }

    if (!document._topbarCreateMenuCloseBound) {
      document.addEventListener("click", (event) => {
        const menu = els.topbarCreatePanel;
        const toggle = els.topbarCreateToggle;
        if (!menu || !toggle) return;
        if (menu.classList.contains("hidden")) return;
        if (menu.contains(event.target) || toggle.contains(event.target)) return;
        closeTopbarCreateMenu({ restoreFocus: false });
      });
      document._topbarCreateMenuCloseBound = true;
    }

    if (els.topbarCreateProject && !els.topbarCreateProject._bound) {
      els.topbarCreateProject.addEventListener("click", () => {
        closeTopbarCreateMenu({ restoreFocus: false });
        openProjectForm(null);
      });
      els.topbarCreateProject._bound = true;
    }

    if (els.topbarCreateProgram && !els.topbarCreateProgram._bound) {
      els.topbarCreateProgram.addEventListener("click", () => {
        closeTopbarCreateMenu({ restoreFocus: false });
        openProgramForm(null);
      });
      els.topbarCreateProgram._bound = true;
    }

    if (els.topbarCreateSolution && !els.topbarCreateSolution._bound) {
      els.topbarCreateSolution.addEventListener("click", () => {
        closeTopbarCreateMenu({ restoreFocus: false });
        openSolutionModal(null, "details");
      });
      els.topbarCreateSolution._bound = true;
    }

    if (els.topbarCreateTask && !els.topbarCreateTask._bound) {
      els.topbarCreateTask.addEventListener("click", handleTopbarTaskCreate);
      els.topbarCreateTask._bound = true;
    }
  }

  function bindTaskCreatePicker() {
    if (els.taskCreatePickerClose && !els.taskCreatePickerClose._bound) {
      els.taskCreatePickerClose.addEventListener("click", closeTaskCreatePicker);
      els.taskCreatePickerClose._bound = true;
    }
    if (els.taskCreatePickerCancel && !els.taskCreatePickerCancel._bound) {
      els.taskCreatePickerCancel.addEventListener("click", closeTaskCreatePicker);
      els.taskCreatePickerCancel._bound = true;
    }
    if (els.taskCreatePickerModal && !els.taskCreatePickerModal._bound) {
      els.taskCreatePickerModal.querySelector(".modal-backdrop")?.addEventListener("click", closeTaskCreatePicker);
      els.taskCreatePickerModal._bound = true;
    }
    if (els.taskCreatePickerForm && !els.taskCreatePickerForm._bound) {
      els.taskCreatePickerForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const solutionId = (new FormData(els.taskCreatePickerForm).get("solution_id") || "").toString().trim();
        const solution = state.solutions.find((row) => row.solution_id === solutionId);
        if (!solution?.solution_id) {
          setDeliverableFormNotice(els.taskCreatePickerStatus, "Choose a solution first.", "error");
          return;
        }
        continueTaskCreateForSolution(solution);
      });
      els.taskCreatePickerForm._bound = true;
    }
  }

  return {
    bindTaskCreatePicker,
    bindTopbarCreateMenu,
    closeTopbarCreateMenu,
    closeTaskCreatePicker,
  };
}
